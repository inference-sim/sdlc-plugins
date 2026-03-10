"""Convergence review orchestrator: review → assess → fix round loop."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import shutil
import sys
import time
from dataclasses import asdict
from pathlib import Path

from openai import AsyncOpenAI

from assessor import assess_findings, build_prior_ledger
from fixer import apply_fixes
from models import GATE_CONFIGS, Assessment, FixResult, RoundResult
from progress import (
    emit_assessment_complete,
    emit_converged,
    emit_error,
    emit_event,
    emit_fix_start,
    emit_fixes_applied,
    emit_interrupted,
    emit_reviews_complete,
    emit_round_complete,
    emit_round_start,
    emit_stalled,
    write_json_file,
    write_progress_file,
)
from prompts import load_artifact_content, load_perspectives
from reviewer import run_all_reviewers
from summary import SummaryWriter

logger = logging.getLogger("convergence")

DEFAULT_REVIEWER_MODEL = "haiku"
DEFAULT_FIXER_MODEL = "opus"
DEFAULT_MAX_ROUNDS = 10
DEFAULT_REVIEWER_TIMEOUT = 300
DEFAULT_ASSESSOR_TIMEOUT = 600
DEFAULT_FIXER_TIMEOUT = 900


def _load_model_aliases() -> dict[str, str]:
    """Load model alias mapping from model-aliases.json next to this file."""
    aliases_path = Path(__file__).parent / "model-aliases.json"
    if not aliases_path.exists():
        logger.debug("No model-aliases.json found at %s", aliases_path)
        return {}
    try:
        return json.loads(aliases_path.read_text())
    except json.JSONDecodeError as e:
        raise RuntimeError(f"model-aliases.json is not valid JSON: {e}") from e


def _resolve_model(name: str) -> str:
    """Resolve a short model name to its full LiteLLM name via aliases."""
    aliases = _load_model_aliases()
    return aliases.get(name, name)


def _sanitize_path(path: str) -> str:
    """Sanitize artifact path for use as directory name."""
    return re.sub(r"[^a-zA-Z0-9_-]", "-", path).strip("-")[:80]


def _default_state_dir(gate: str, artifact: str | None) -> Path:
    """Compute default state directory path."""
    suffix = _sanitize_path(artifact) if artifact else "diff"
    return Path(".claude") / "convergence-state" / f"{gate}-{suffix}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Convergence review orchestrator",
        prog="orchestrator.py",
    )
    parser.add_argument("gate", choices=sorted(GATE_CONFIGS.keys()), help="Review gate type")
    parser.add_argument("artifact", nargs="?", default=None, help="Artifact path (not needed for pr-code)")
    parser.add_argument(
        "--reviewer-model",
        default=os.environ.get("CONVERGENCE_REVIEWER_MODEL", DEFAULT_REVIEWER_MODEL),
        help=f"Model for reviewers (default: {DEFAULT_REVIEWER_MODEL})",
    )
    parser.add_argument(
        "--fixer-model",
        default=os.environ.get("CONVERGENCE_FIXER_MODEL", DEFAULT_FIXER_MODEL),
        help=f"Model for assessment and fixes (default: {DEFAULT_FIXER_MODEL})",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=DEFAULT_MAX_ROUNDS,
        help=f"Maximum convergence rounds (default: {DEFAULT_MAX_ROUNDS})",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("LITELLM_BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL"),
        help="API base URL (checks LITELLM_BASE_URL then ANTHROPIC_BASE_URL)",
    )
    # API key sourced from environment only (not CLI) to avoid process-list exposure.
    parser.set_defaults(
        api_key=(
            os.environ.get("LITELLM_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or os.environ.get("ANTHROPIC_API_KEY")
            or ""
        ).strip(),
    )
    parser.add_argument(
        "--state-dir",
        default=None,
        help="State directory (default: .claude/convergence-state/<gate>-<path>)",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: WARNING)",
    )
    parser.add_argument(
        "--reviewer-timeout",
        type=int,
        default=DEFAULT_REVIEWER_TIMEOUT,
        help=f"Per-reviewer timeout in seconds (default: {DEFAULT_REVIEWER_TIMEOUT})",
    )
    parser.add_argument(
        "--assessor-timeout",
        type=int,
        default=DEFAULT_ASSESSOR_TIMEOUT,
        help=f"Assessment phase timeout in seconds (default: {DEFAULT_ASSESSOR_TIMEOUT})",
    )
    parser.add_argument(
        "--fixer-timeout",
        type=int,
        default=DEFAULT_FIXER_TIMEOUT,
        help=f"Fix phase (claude -p) timeout in seconds (default: {DEFAULT_FIXER_TIMEOUT})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Disable early stall detection (run all rounds even if not converging)",
    )
    parser.add_argument(
        "--stall-window",
        type=int,
        default=5,
        help="Number of rounds without improvement before early exit (default: 5)",
    )
    parser.add_argument(
        "--human",
        action="store_true",
        default=False,
        help="Human-readable one-line progress to stderr (suppresses JSON and httpx noise)",
    )

    args = parser.parse_args(argv)

    # Validate stall window
    if args.stall_window < 2:
        parser.error("--stall-window must be >= 2")

    # Resolve model aliases
    try:
        args.reviewer_model = _resolve_model(args.reviewer_model)
        args.fixer_model = _resolve_model(args.fixer_model)
    except RuntimeError as e:
        parser.error(str(e))

    # Validate artifact requirement
    config = GATE_CONFIGS[args.gate]
    if config.artifact_type != "git_diff" and args.artifact is None:
        parser.error(f"Gate '{args.gate}' requires an artifact path")

    # Compute state dir
    if args.state_dir is None:
        args.state_dir = str(_default_state_dir(args.gate, args.artifact))

    return args


def _human_print(msg: str) -> None:
    """Print a human-readable progress line to stderr."""
    print(msg, file=sys.stderr, flush=True)


async def run_round(
    client: AsyncOpenAI,
    args: argparse.Namespace,
    round_num: int,
    artifact_content: str,
    perspectives: list,
    state_dir: Path,
    summary: SummaryWriter,
) -> RoundResult:
    """Execute one convergence round: review → assess → fix."""
    round_start = time.monotonic()

    emit_round_start(
        round_num,
        args.max_rounds,
        args.gate,
        args.artifact or "git-diff",
        args.reviewer_model,
        args.fixer_model,
        len(perspectives),
    )
    summary.write_round_start(round_num, len(perspectives))

    if args.human:
        _human_print(
            f"Round {round_num}/{args.max_rounds}: Dispatching {len(perspectives)} reviewers..."
        )

    # Phase 1: Review
    reviewer_outputs = await run_all_reviewers(
        client,
        args.reviewer_model,
        perspectives,
        artifact_content,
        args.reviewer_timeout,
        round_num,
        state_dir,
    )

    total_raw = sum(len(o.findings) for o in reviewer_outputs)
    ok_count = sum(1 for o in reviewer_outputs if o.error is None)
    fail_count = len(reviewer_outputs) - ok_count
    review_elapsed = time.monotonic() - round_start

    emit_reviews_complete(round_num, total_raw, ok_count, fail_count, review_elapsed)
    summary.write_review_complete(reviewer_outputs, review_elapsed)

    if args.human:
        _human_print(
            f"  Reviewed: {ok_count} reviewers → {total_raw} raw findings ({review_elapsed:.0f}s)"
        )

    # Guard: if all reviewers failed or returned 0 raw findings, that's
    # suspicious — not convergence.
    if ok_count == 0:
        logger.error("All %d reviewers failed in round %d", len(reviewer_outputs), round_num)
    elif total_raw == 0 and ok_count > 0:
        # 0 raw findings from successful reviewers. If any have parse
        # warnings, this is a parsing failure — abort the round. Otherwise
        # treat as genuine convergence (all reviewers found nothing).
        parse_warnings = [
            f"  {o.perspective}: {o.parse_warning}"
            for o in reviewer_outputs
            if o.parse_warning
        ]

        if parse_warnings:
            diag = (
                f"Round {round_num}: {ok_count} reviewers succeeded but returned "
                f"0 total findings. This is likely a parsing failure, not convergence."
                f"\n\nParse warnings:\n" + "\n".join(parse_warnings)
            )
            logger.error(diag)
            emit_error(diag)
            summary.write_error(diag)

            round_elapsed = time.monotonic() - round_start
            emit_round_complete(round_num, "error", 0, 0, 0, 0, round_elapsed)
            if args.human:
                _human_print(f"\n  ERROR: 0 raw findings from {ok_count} reviewers — aborting round")
                for pw in parse_warnings:
                    _human_print(pw)
            return RoundResult(
                round_num=round_num,
                reviewer_outputs=reviewer_outputs,
                status="error",
                elapsed_sec=round_elapsed,
            )

    # Phase 2: Assess (with cross-round ledger)
    prior_ledger = build_prior_ledger(state_dir, round_num)
    summary.write_assess_start(total_raw)
    if args.human:
        ledger_note = f" (with {round_num - 1}-round ledger)" if prior_ledger else ""
        _human_print(f"  Assessing {total_raw} findings{ledger_note}...")
    assess_start = time.monotonic()
    assessment = await assess_findings(
        client, args.fixer_model, reviewer_outputs, artifact_content,
        timeout=args.assessor_timeout, gate=args.gate, prior_ledger=prior_ledger,
    )
    assess_elapsed = time.monotonic() - assess_start

    if assessment.fallback:
        emit_event({
            "event": "assessment_fallback",
            "round": round_num,
            "message": "Assessment API failed. Using raw findings without dedup/validation.",
        })
        if args.human:
            _human_print(
                "  WARNING: Assessment failed — using raw findings (may contain duplicates)"
            )

    emit_assessment_complete(
        round_num,
        assessment.summary.get("critical", 0),
        assessment.summary.get("important", 0),
        assessment.summary.get("suggestion", 0),
        assessment.summary.get("dismissed", 0),
        assessment.summary.get("deduplicated", 0),
        assess_elapsed,
    )

    summary.write_assessment_complete(assessment)

    if args.human:
        s = assessment.summary
        _human_print(
            f"  Assessment: {s.get('critical', 0)}C {s.get('important', 0)}I "
            f"{s.get('suggestion', 0)}S "
            f"({s.get('dismissed', 0)} dismissed, {s.get('deduplicated', 0)} deduped, "
            f"{assess_elapsed:.0f}s)"
        )

    # Save assessment
    write_json_file(
        state_dir / f"assessment-round-{round_num}.json",
        {
            "assessed_findings": [asdict(f) for f in assessment.assessed_findings],
            "dismissed": [asdict(d) for d in assessment.dismissed],
            "uncovered_perspectives": assessment.uncovered_perspectives,
            "summary": assessment.summary,
        },
    )

    # Compute actionable C+I: exclude recurring-fixed and recurring-escalate
    # (those are persistent themes surfaced to the user, not fixable in the loop)
    _NON_ACTIONABLE = {"recurring-fixed", "recurring-escalate"}
    actionable = [
        f for f in assessment.assessed_findings
        if f.severity in ("CRITICAL", "IMPORTANT")
        and f.cross_round_status not in _NON_ACTIONABLE
    ]
    critical = sum(1 for f in actionable if f.severity == "CRITICAL")
    important = sum(1 for f in actionable if f.severity == "IMPORTANT")

    # Check for failed round: all reviewers errored or none returned findings
    if ok_count == 0:
        round_elapsed = time.monotonic() - round_start
        emit_round_complete(round_num, "error", 0, 0, 0, 0, round_elapsed)
        return RoundResult(
            round_num=round_num,
            reviewer_outputs=reviewer_outputs,
            assessment=assessment,
            status="error",
            elapsed_sec=round_elapsed,
        )

    # Phase 3: Fix (only if needed — only actionable findings)
    fix_result = None
    if critical + important > 0:
        emit_fix_start(round_num, critical + important)
        summary.write_fix_start(critical, important)
        if args.human:
            _human_print(f"  Fixing {critical + important} findings ({critical}C {important}I)...")

        fix_start = time.monotonic()
        fix_result = apply_fixes(
            actionable,
            args.artifact or ".",
            state_dir,
            round_num,
            fixer_model=args.fixer_model,
            timeout=args.fixer_timeout,
            base_url=args.base_url,
            api_key=args.api_key,
            reviewer_model=args.reviewer_model,
        )
        fix_elapsed = time.monotonic() - fix_start

        critical_fixed = sum(
            1 for f in fix_result.fixes_applied if f.get("severity") == "CRITICAL"
        )
        important_fixed = sum(
            1 for f in fix_result.fixes_applied if f.get("severity") == "IMPORTANT"
        )
        emit_fixes_applied(
            round_num, critical_fixed, important_fixed, len(fix_result.fixes_skipped), fix_elapsed
        )
        if args.human:
            _human_print(
                f"  Fix: {critical_fixed}C {important_fixed}I fixed, "
                f"{len(fix_result.fixes_skipped)} skipped ({fix_elapsed:.0f}s)"
            )
        summary.write_fix_complete(fix_result)
        summary.write_round_summary(assessment, fix_result)
        status = "fixed"
    else:
        summary.write_fix_complete(None, converged=True)
        summary.write_round_summary(assessment, None)
        status = "converged"
        critical_fixed = 0
        important_fixed = 0

    round_elapsed = time.monotonic() - round_start
    emit_round_complete(
        round_num, status, critical, important, critical_fixed, important_fixed, round_elapsed
    )

    # Write progress
    round_data = {
        "round": round_num,
        "status": status,
        "critical": critical,
        "important": important,
        "suggestion": assessment.summary.get("suggestion", 0),
        "dismissed": assessment.summary.get("dismissed", 0),
        "fixes_applied": len(fix_result.fixes_applied) if fix_result else 0,
        "elapsed_sec": round(round_elapsed, 1),
    }
    write_progress_file(state_dir, round_num, round_data)
    summary.record_round(round_num, assessment=assessment, fix_result=fix_result)

    return RoundResult(
        round_num=round_num,
        reviewer_outputs=reviewer_outputs,
        assessment=assessment,
        fix_result=fix_result,
        status=status,
        elapsed_sec=round_elapsed,
    )


async def main(argv: list[str] | None = None) -> int:
    """Main orchestrator entry point. Returns exit code."""
    args = parse_args(argv)

    # Configure logging
    log_level = getattr(logging, args.log_level)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    if args.human:
        # Suppress noisy third-party loggers
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("openai").setLevel(logging.WARNING)

    logger.info("Starting convergence review: gate=%s artifact=%s", args.gate, args.artifact)

    # Validate setup
    if not args.base_url:
        emit_error("No LiteLLM base URL configured. Set LITELLM_BASE_URL or use --base-url.")
        return 2

    if not args.api_key:
        emit_error(
            "No API key configured. Set LITELLM_API_KEY, ANTHROPIC_AUTH_TOKEN, "
            "or ANTHROPIC_API_KEY."
        )
        return 2

    # Load perspectives
    try:
        perspectives = load_perspectives(args.gate)
    except (ValueError, FileNotFoundError) as e:
        emit_error(str(e))
        return 2

    # Load artifact content
    try:
        artifact_content = load_artifact_content(args.gate, args.artifact)
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        emit_error(str(e))
        return 2

    # Prepare state directory (clean start)
    state_dir = Path(args.state_dir).resolve()
    cwd = Path.cwd().resolve()
    if not state_dir.is_relative_to(cwd):
        emit_error(f"State directory must be under current working directory: {state_dir}")
        return 2
    if state_dir.exists():
        try:
            shutil.rmtree(state_dir)
        except OSError as e:
            emit_error(f"Failed to clean state directory {state_dir}: {e}")
            return 2
    state_dir.mkdir(parents=True, exist_ok=True)

    # Create summary writer
    summary = SummaryWriter(
        state_dir, args.gate, args.artifact, args.max_rounds,
        reviewer_model=args.reviewer_model, fixer_model=args.fixer_model,
    )
    logger.info("Summary file: %s", summary.path)
    emit_event({"event": "summary_path", "path": str(summary.path)})

    # Strip SOCKS proxy env vars that break httpx without socksio (process-global).
    # Only ALL_PROXY/all_proxy are stripped; HTTPS_PROXY/HTTP_PROXY are kept.
    for var in ("ALL_PROXY", "all_proxy"):
        os.environ.pop(var, None)

    # Create OpenAI client
    client = AsyncOpenAI(base_url=args.base_url, api_key=args.api_key)

    total_start = time.monotonic()
    round_num = 0
    finding_history: list[int] = []  # actionable critical+important per round
    fixes_history: list[int] = []  # fixes applied per round
    recurring_history: list[int] = []  # recurring finding count per round
    persistent_themes: list[dict] = []  # accumulated escalated themes for summary

    try:
        for round_num in range(1, args.max_rounds + 1):
            result = await run_round(
                client, args, round_num, artifact_content, perspectives, state_dir, summary
            )

            if result.status == "converged":
                total_elapsed = time.monotonic() - total_start
                summary.write_persistent_themes(persistent_themes)
                summary.write_converged(round_num, total_elapsed)
                emit_converged(round_num, round_num, total_elapsed)
                if args.human:
                    _human_print(f"\nCONVERGED in {round_num} rounds ({total_elapsed:.0f}s)")
                logger.info("Converged in %d rounds (%.1fs)", round_num, total_elapsed)
                return 0

            if result.status == "error":
                summary.write_error(f"Round {round_num} failed: all reviewers errored")
                emit_error(f"Round {round_num} failed: all reviewers errored")
                if args.human:
                    _human_print(f"\nERROR: Round {round_num} failed — all reviewers errored")
                return 2

            # Track actionable finding counts and fixes for stall detection
            actionable_count = 0
            recurring = 0
            escalated_this_round = []
            if result.assessment:
                _NA = {"recurring-fixed", "recurring-escalate"}
                for f in result.assessment.assessed_findings:
                    if f.severity in ("CRITICAL", "IMPORTANT"):
                        if f.cross_round_status not in _NA:
                            actionable_count += 1
                        if f.cross_round_status != "novel":
                            recurring += 1
                        if f.cross_round_status == "recurring-escalate":
                            escalated_this_round.append({
                                "description": f.description,
                                "severity": f.severity,
                                "first_seen_ref": f.prior_finding_ref,
                                "round_escalated": round_num,
                            })

            finding_history.append(actionable_count)
            fixes_history.append(
                len(result.fix_result.fixes_applied) if result.fix_result else 0
            )
            recurring_history.append(recurring)

            # Accumulate persistent themes (deduplicate by description prefix)
            for theme in escalated_this_round:
                prefix = theme["description"][:100]
                if not any(t["description"][:100] == prefix for t in persistent_themes):
                    persistent_themes.append(theme)

            total_ci = (
                result.assessment.summary.get("critical", 0)
                + result.assessment.summary.get("important", 0)
            ) if result.assessment else 0
            summary.write_recurring(recurring, total_ci, len(escalated_this_round))
            if recurring > 0:
                logger.info(
                    "Round %d: %d/%d recurring, %d escalated as persistent themes",
                    round_num, recurring, total_ci, len(escalated_this_round),
                )
                emit_event({
                    "event": "recurring_findings",
                    "round": round_num,
                    "recurring": recurring,
                    "total": total_ci,
                    "actionable": actionable_count,
                    "escalated": len(escalated_this_round),
                })
                if args.human:
                    _human_print(
                        f"  Cross-round: {recurring}/{total_ci} recurring, "
                        f"{actionable_count} actionable, "
                        f"{len(escalated_this_round)} escalated as persistent"
                    )

            # Early stall detection: exit early if findings aren't decreasing
            # AND no fixes are being applied across the stall window.
            # If fixes are being applied, the fixer is making progress even
            # if new findings keep appearing — so we keep going.
            if not args.force and len(finding_history) >= args.stall_window:
                window = finding_history[-args.stall_window :]
                fixes_window = fixes_history[-args.stall_window :]
                no_fixes = sum(fixes_window) == 0
                if min(window) >= window[0] and window[0] > 0 and no_fixes:
                    logger.warning(
                        "Early stall: findings not decreasing and no fixes applied "
                        "over %d rounds: %s (fixes: %s)",
                        args.stall_window,
                        window,
                        fixes_window,
                    )
                    emit_event({
                        "event": "early_stall",
                        "round": round_num,
                        "finding_history": finding_history,
                        "recurring_history": recurring_history,
                        "message": (
                            f"Finding counts not decreasing over {args.stall_window} rounds "
                            f"({window}). Use --force to override."
                        ),
                    })
                    remaining_critical = result.assessment.summary.get("critical", 0) if result.assessment else 0
                    remaining_important = result.assessment.summary.get("important", 0) if result.assessment else 0
                    summary.write_persistent_themes(persistent_themes)
                    summary.write_stalled(
                        round_num, remaining_critical, remaining_important,
                        reason=f"findings not decreasing over {args.stall_window} rounds ({window})",
                    )
                    emit_stalled(round_num, remaining_critical, remaining_important)
                    if args.human:
                        _human_print(
                            f"\nSTALLED (early): not converging after {args.stall_window} rounds "
                            f"({remaining_critical}C {remaining_important}I remaining). "
                            f"Use --force to override."
                        )
                    return 1

            # Reload artifact content for next round (fixes may have changed it)
            if result.status == "fixed":
                reload_ok = False
                for reload_attempt in range(3):
                    try:
                        artifact_content = load_artifact_content(args.gate, args.artifact)
                        reload_ok = True
                        break
                    except (ValueError, FileNotFoundError, RuntimeError) as e:
                        logger.warning(
                            "Artifact reload attempt %d failed: %s",
                            reload_attempt + 1, e,
                        )
                        await asyncio.sleep(1)
                if not reload_ok:
                    summary.write_error(
                        f"Failed to reload artifact after fixes (3 attempts). "
                        f"The fixer may have corrupted or deleted the file."
                    )
                    emit_error("Failed to reload artifact after fixes")
                    return 2

        # Max rounds reached
        last_assessment = result.assessment
        remaining_critical = last_assessment.summary.get("critical", 0) if last_assessment else 0
        remaining_important = last_assessment.summary.get("important", 0) if last_assessment else 0
        summary.write_persistent_themes(persistent_themes)
        summary.write_stalled(
            round_num, remaining_critical, remaining_important,
            reason=f"max rounds ({args.max_rounds}) exhausted",
        )
        emit_stalled(round_num, remaining_critical, remaining_important)
        if args.human:
            _human_print(
                f"\nSTALLED: max rounds ({round_num}) reached. "
                f"{remaining_critical}C {remaining_important}I remaining."
            )
        logger.warning(
            "Stalled after %d rounds: %d CRITICAL, %d IMPORTANT remaining",
            round_num,
            remaining_critical,
            remaining_important,
        )
        return 1

    except KeyboardInterrupt:
        summary.write_error("Interrupted by user")
        emit_interrupted()
        logger.info("Interrupted by user")
        return 130

    except Exception as e:
        logger.exception("Unhandled error in convergence loop")
        summary.write_error(f"Unhandled error: {e}")
        emit_error(f"Unhandled error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
