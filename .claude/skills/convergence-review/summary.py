"""Human-readable summary file writer for convergence reviews."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

from models import Assessment, FixResult, ReviewerOutput

logger = logging.getLogger("convergence.summary")


def _compute_summary_path(artifact: str | None, state_dir: Path) -> Path:
    """Compute primary summary path: next to the artifact if possible, else state dir.

    For file artifacts: <artifact-stem>-review.md in the same directory.
    For git_diff / directory / None: state_dir/summary.md.
    """
    if artifact:
        artifact_path = Path(artifact)
        if artifact_path.is_file():
            return artifact_path.parent / f"{artifact_path.stem}-review.md"
    return state_dir / "summary.md"


class SummaryWriter:
    """Accumulates round results into a readable summary.md file."""

    def __init__(
        self,
        state_dir: Path,
        gate: str,
        artifact: str | None,
        max_rounds: int,
        reviewer_model: str = "",
        fixer_model: str = "",
    ):
        self.path = _compute_summary_path(artifact, state_dir)
        self.state_dir_copy = state_dir / "summary.md"
        self.gate = gate
        self.artifact = artifact or "git-diff"
        self.max_rounds = max_rounds
        self._round_history: list[dict] = []

        # Append header (preserves previous reviews)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        separator = "\n---\n\n" if self.path.exists() and self.path.stat().st_size > 0 else ""
        with open(self.path, "a") as f:
            f.write(
                f"{separator}# Convergence Review: {gate} — {self.artifact}\n"
                f"**Started**: {timestamp} | "
                f"**Max rounds**: {max_rounds} | "
                f"**Reviewer**: {reviewer_model} | "
                f"**Fixer**: {fixer_model}\n\n"
            )
        logger.info("Summary file: %s", self.path)

    def _sync_to_state_dir(self) -> None:
        """Copy summary to state dir if primary path differs. Fails silently."""
        if self.path != self.state_dir_copy:
            try:
                shutil.copy2(self.path, self.state_dir_copy)
            except OSError as e:
                logger.warning("Failed to sync summary to state dir: %s", e)

    @staticmethod
    def _ts() -> str:
        """Return a compact timestamp for action steps."""
        return datetime.now().strftime("%H:%M:%S")

    def _append(self, text: str) -> None:
        """Append text and sync to state dir. Degrades gracefully on I/O errors."""
        try:
            with open(self.path, "a") as f:
                f.write(text)
            self._sync_to_state_dir()
        except OSError as e:
            logger.error("Failed to write summary file %s: %s", self.path, e)

    def write_round_start(self, round_num: int, num_perspectives: int) -> None:
        """Append round header — written before reviewers start."""
        self._append(
            f"## Round {round_num}/{self.max_rounds}\n\n"
            f"- `{self._ts()}` **Dispatching** {num_perspectives} reviewers...\n\n"
        )

    def write_review_complete(
        self,
        reviewer_outputs: list[ReviewerOutput],
        elapsed_sec: float,
    ) -> None:
        """Append review phase results."""
        ok = sum(1 for o in reviewer_outputs if o.error is None)
        failed = len(reviewer_outputs) - ok
        total_raw = sum(len(o.findings) for o in reviewer_outputs)
        line = f"- `{self._ts()}` **Review complete**: {ok} reviewers, {total_raw} raw findings"
        if failed:
            line += f" ({failed} failed)"
        line += f" ({elapsed_sec:.0f}s)\n\n"
        self._append(line)

    def write_assess_start(self, total_raw: int) -> None:
        """Append assessment start line."""
        self._append(f"- `{self._ts()}` **Assessing** {total_raw} raw findings...\n\n")

    def write_fix_start(self, critical: int, important: int) -> None:
        """Append fix start line."""
        self._append(f"- `{self._ts()}` **Fixing** {critical}C {important}I...\n\n")

    def write_assessment_complete(self, assessment: Assessment) -> None:
        """Append assessment phase results with finding list."""
        s = assessment.summary
        fallback_note = " **[FALLBACK: raw findings, no dedup/validation]**" if assessment.fallback else ""
        lines = [
            f"- `{self._ts()}` **Assessment**: {s.get('critical', 0)} CRITICAL, "
            f"{s.get('important', 0)} IMPORTANT, "
            f"{s.get('suggestion', 0)} SUGGESTION "
            f"({s.get('dismissed', 0)} dismissed, "
            f"{s.get('deduplicated', 0)} deduped){fallback_note}\n"
        ]
        for f in assessment.assessed_findings:
            if f.severity in ("CRITICAL", "IMPORTANT"):
                status_tag = ""
                if f.cross_round_status and f.cross_round_status != "novel":
                    ref = f" see {f.prior_finding_ref}" if f.prior_finding_ref else ""
                    status_tag = f" *({f.cross_round_status}{ref})*"
                lines.append(
                    f"  - **{f.id}** [{f.severity}] {f.description}{status_tag}\n"
                )
        lines.append("\n")
        self._append("".join(lines))

    def write_fix_complete(self, fix_result: FixResult | None, converged: bool = False) -> None:
        """Append fix phase results."""
        if fix_result:
            if fix_result.error:
                self._append(f"- `{self._ts()}` **Fix**: FAILED — {fix_result.error}\n\n")
            else:
                c_fixed = sum(
                    1 for f in fix_result.fixes_applied
                    if f.get("severity") == "CRITICAL"
                )
                i_fixed = sum(
                    1 for f in fix_result.fixes_applied
                    if f.get("severity") == "IMPORTANT"
                )
                skipped = len(fix_result.fixes_skipped)
                self._append(f"- `{self._ts()}` **Fix complete**: {c_fixed}C {i_fixed}I fixed, {skipped} skipped\n\n")
        elif converged:
            self._append(f"- `{self._ts()}` **Fix**: not needed (0 CRITICAL, 0 IMPORTANT)\n\n")

    def write_round_summary(
        self,
        assessment: Assessment | None,
        fix_result: FixResult | None,
    ) -> None:
        """Append a compact round summary with cross-round status breakdown."""
        if not assessment:
            return

        ci = [
            f for f in assessment.assessed_findings
            if f.severity in ("CRITICAL", "IMPORTANT")
        ]
        if not ci:
            self._append("  > **Summary**: 0 C+I — converged\n\n")
            return

        c_count = sum(1 for f in ci if f.severity == "CRITICAL")
        i_count = sum(1 for f in ci if f.severity == "IMPORTANT")

        # Cross-round status breakdown
        from collections import Counter
        statuses = Counter(f.cross_round_status for f in ci)
        status_parts = []
        for s in ("novel", "regression", "recurring-skipped", "recurring-fixed", "recurring-escalate"):
            if statuses.get(s, 0) > 0:
                status_parts.append(f"{statuses[s]} {s}")

        # Actionable count
        non_actionable = {"recurring-fixed", "recurring-escalate"}
        actionable = [f for f in ci if f.cross_round_status not in non_actionable]
        filtered = len(ci) - len(actionable)

        lines = [f"  > **Summary**: {len(ci)} C+I ({c_count}C, {i_count}I)"]
        if status_parts:
            lines[0] += f" — {', '.join(status_parts)}"
        lines.append(f"\n  > **Actionable**: {len(actionable)}")
        if filtered > 0:
            lines[-1] += f" ({filtered} filtered as recurring-fixed/escalated)"

        if fix_result and not fix_result.error:
            applied = len(fix_result.fixes_applied)
            skipped = len(fix_result.fixes_skipped)
            lines.append(f"\n  > **Fixes**: {applied} applied, {skipped} skipped")
        elif fix_result and fix_result.error:
            lines.append(f"\n  > **Fixes**: FAILED — {fix_result.error}")

        lines.append("\n\n")
        self._append("".join(lines))

    def write_recurring(self, recurring: int, total: int, escalated: int = 0) -> None:
        """Append recurring findings note after assessment."""
        if recurring > 0:
            esc_note = f" ({escalated} escalated as persistent)" if escalated else ""
            self._append(
                f"  - *Recurring*: {recurring}/{total} findings from prior rounds{esc_note}\n"
            )

    def record_round(
        self,
        round_num: int,
        assessment: Assessment | None = None,
        fix_result: FixResult | None = None,
    ) -> None:
        """Record round stats for the history table."""
        row: dict = {"round": round_num}
        if assessment:
            s = assessment.summary
            row["critical"] = s.get("critical", 0)
            row["important"] = s.get("important", 0)
            row["suggestion"] = s.get("suggestion", 0)
            row["dismissed"] = s.get("dismissed", 0)
        if fix_result and not fix_result.error:
            row["applied"] = len(fix_result.fixes_applied)
            row["skipped"] = len(fix_result.fixes_skipped)
        self._round_history.append(row)

    def _write_history_table(self) -> None:
        """Append a markdown summary table of all rounds."""
        if not self._round_history:
            return
        lines = [
            "\n## Round History\n\n",
            "| Round | CRITICAL | IMPORTANT | SUGGESTION | Dismissed | Applied | Skipped | C+I Remaining |\n",
            "|------:|---------:|----------:|-----------:|----------:|--------:|--------:|--------------:|\n",
        ]
        for row in self._round_history:
            c = row.get("critical", "-")
            i = row.get("important", "-")
            s = row.get("suggestion", "-")
            d = row.get("dismissed", "-")
            a = row.get("applied", "-")
            sk = row.get("skipped", "-")
            ci = (c + i) if isinstance(c, int) and isinstance(i, int) else "-"
            lines.append(
                f"| {row['round']} | {c} | {i} | {s} | {d} | {a} | {sk} | {ci} |\n"
            )
        lines.append("\n")
        self._append("".join(lines))

    def write_persistent_themes(self, themes: list[dict]) -> None:
        """Append persistent themes section — design trade-offs the loop couldn't resolve."""
        if not themes:
            return
        lines = [
            "\n## Persistent Themes (not blocking convergence)\n\n",
            "These themes were flagged in 3+ rounds and represent design trade-offs or "
            "scope limitations rather than fixable defects. Human review recommended.\n\n",
            "| # | Severity | Theme | Escalated in Round |\n",
            "|--:|----------|-------|-------------------:|\n",
        ]
        for i, t in enumerate(themes, 1):
            desc = t.get("description", "")[:200]
            sev = t.get("severity", "?")
            rd = t.get("round_escalated", "?")
            lines.append(f"| {i} | {sev} | {desc} | {rd} |\n")
        lines.append("\n")
        self._append("".join(lines))

    def write_converged(self, round_num: int, total_elapsed: float) -> None:
        """Append convergence result."""
        self._append(
            f"## Result: CONVERGED — `{self._ts()}`\n\n"
            f"Converged in {round_num} round(s) ({total_elapsed:.0f}s total). "
            f"0 CRITICAL, 0 IMPORTANT remaining.\n"
        )
        self._write_history_table()

    def write_stalled(
        self,
        round_num: int,
        remaining_critical: int,
        remaining_important: int,
        reason: str = "max rounds reached",
    ) -> None:
        """Append stall result."""
        self._append(
            f"## Result: STALLED — `{self._ts()}`\n\n"
            f"**Reason**: {reason}\n\n"
            f"{remaining_critical} CRITICAL, {remaining_important} IMPORTANT remaining "
            f"after {round_num} round(s).\n"
        )
        self._write_history_table()

    def write_error(self, message: str) -> None:
        """Append error result."""
        self._append(f"## Result: ERROR\n\n{message}\n")
        self._write_history_table()
