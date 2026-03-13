"""JSON progress event emitter and state file writer."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("convergence.progress")


def emit_event(event: dict[str, Any]) -> None:
    """Emit a JSON progress event to stdout (one line)."""
    try:
        line = json.dumps(event, separators=(",", ":"), default=str)
    except (TypeError, ValueError) as e:
        logger.error("Failed to serialize event: %s — %s", event.get("event"), e)
        # Emit a minimal fallback so the parent process knows something went wrong
        fallback = json.dumps(
            {"event": "internal_error", "message": f"event serialization failed: {e}"},
            separators=(",", ":"),
        )
        try:
            print(fallback, flush=True)
        except BrokenPipeError:
            pass
        return
    try:
        print(line, flush=True)
    except BrokenPipeError:
        return
    logger.debug("Event emitted: %s", event.get("event"))


def emit_round_start(
    round_num: int,
    max_rounds: int,
    gate: str,
    artifact: str,
    reviewer_model: str,
    fixer_model: str,
    perspectives: int,
) -> None:
    emit_event(
        {
            "event": "round_start",
            "round": round_num,
            "max_rounds": max_rounds,
            "gate": gate,
            "artifact": artifact,
            "reviewer_model": reviewer_model,
            "fixer_model": fixer_model,
            "perspectives": perspectives,
        }
    )


def emit_reviewer_done(
    round_num: int, perspective: str, findings_count: int, elapsed_sec: float
) -> None:
    emit_event(
        {
            "event": "reviewer_done",
            "round": round_num,
            "perspective": perspective,
            "findings_count": findings_count,
            "elapsed_sec": round(elapsed_sec, 1),
        }
    )


def emit_reviewer_error(
    round_num: int, perspective: str, error: str, elapsed_sec: float
) -> None:
    emit_event(
        {
            "event": "reviewer_error",
            "round": round_num,
            "perspective": perspective,
            "error": error,
            "elapsed_sec": round(elapsed_sec, 1),
        }
    )


def emit_reviews_complete(
    round_num: int,
    total_raw_findings: int,
    perspectives_ok: int,
    perspectives_failed: int,
    elapsed_sec: float,
) -> None:
    emit_event(
        {
            "event": "reviews_complete",
            "round": round_num,
            "total_raw_findings": total_raw_findings,
            "perspectives_ok": perspectives_ok,
            "perspectives_failed": perspectives_failed,
            "elapsed_sec": round(elapsed_sec, 1),
        }
    )


def emit_assessment_complete(
    round_num: int,
    critical: int,
    important: int,
    suggestion: int,
    dismissed: int,
    deduplicated: int,
    elapsed_sec: float,
) -> None:
    emit_event(
        {
            "event": "assessment_complete",
            "round": round_num,
            "critical": critical,
            "important": important,
            "suggestion": suggestion,
            "dismissed": dismissed,
            "deduplicated": deduplicated,
            "elapsed_sec": round(elapsed_sec, 1),
        }
    )


def emit_fix_start(round_num: int, findings_to_fix: int) -> None:
    emit_event(
        {
            "event": "fix_start",
            "round": round_num,
            "findings_to_fix": findings_to_fix,
        }
    )


def emit_fixes_applied(
    round_num: int,
    critical_fixed: int,
    important_fixed: int,
    skipped: int,
    elapsed_sec: float,
) -> None:
    emit_event(
        {
            "event": "fixes_applied",
            "round": round_num,
            "critical_fixed": critical_fixed,
            "important_fixed": important_fixed,
            "skipped": skipped,
            "elapsed_sec": round(elapsed_sec, 1),
        }
    )


def emit_round_complete(
    round_num: int,
    status: str,
    critical: int,
    important: int,
    critical_fixed: int,
    important_fixed: int,
    elapsed_sec: float,
) -> None:
    emit_event(
        {
            "event": "round_complete",
            "round": round_num,
            "status": status,
            "critical": critical,
            "important": important,
            "critical_fixed": critical_fixed,
            "important_fixed": important_fixed,
            "elapsed_sec": round(elapsed_sec, 1),
        }
    )


def emit_converged(round_num: int, total_rounds: int, total_elapsed_sec: float) -> None:
    emit_event(
        {
            "event": "converged",
            "round": round_num,
            "total_rounds": total_rounds,
            "total_elapsed_sec": round(total_elapsed_sec, 1),
        }
    )


def emit_stalled(
    round_num: int, remaining_critical: int, remaining_important: int
) -> None:
    emit_event(
        {
            "event": "stalled",
            "round": round_num,
            "remaining_critical": remaining_critical,
            "remaining_important": remaining_important,
        }
    )


def emit_error(message: str) -> None:
    emit_event({"event": "error", "message": message})


def emit_interrupted() -> None:
    emit_event({"event": "interrupted"})


def write_progress_file(state_dir: Path, round_num: int, data: dict) -> None:
    """Write progress.json (current) and progress-round-N.json (archive)."""
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        current = state_dir / "progress.json"
        current.write_text(json.dumps(data, indent=2))
        archive = state_dir / f"progress-round-{round_num}.json"
        archive.write_text(json.dumps(data, indent=2))
        logger.debug("Progress written to %s", state_dir)
    except OSError as e:
        logger.error("Failed to write progress file in %s: %s", state_dir, e)
        emit_event({"event": "internal_error", "message": f"Failed to write progress: {e}"})


def write_json_file(path: Path, data: Any) -> None:
    """Write arbitrary JSON data to a file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))
    except OSError as e:
        logger.error("Failed to write JSON file %s: %s", path, e)
        emit_event({"event": "internal_error", "message": f"Failed to write {path.name}: {e}"})
