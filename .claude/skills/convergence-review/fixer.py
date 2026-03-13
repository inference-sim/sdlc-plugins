"""Fix phase: claude -p subprocess for applying assessed findings."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

from openai import OpenAI

from models import AssessedFinding, FixResult
from progress import write_json_file

logger = logging.getLogger("convergence.fixer")

_FIX_PROMPT_TEMPLATE = """\
You are fixing issues found during a convergence review. Apply each fix carefully.

## Instructions

1. Read the current state of each file mentioned in the findings below.
2. Fix all CRITICAL findings first, then IMPORTANT.
3. After each fix, verify the surrounding context still makes sense.
4. Do NOT re-review, dispatch evaluators, or add new findings.
5. When done, write a fix summary JSON to: {summary_path}

## Fix Summary Schema

Write this exact JSON structure to the summary path:
```json
{{
    "fixes_applied": [
        {{"finding_id": "F-1", "severity": "CRITICAL", "file": "path/to/file", "action": "Description of fix"}}
    ],
    "fixes_skipped": [
        {{"finding_id": "F-3", "severity": "IMPORTANT", "reason": "Why this was skipped"}}
    ]
}}
```

## Findings to Fix

{findings_text}

## Artifact Path

{artifact_path}
"""


def _format_findings(findings: list[AssessedFinding]) -> str:
    """Format assessed findings for the fix prompt."""
    parts = []
    # Sort: CRITICAL first, then IMPORTANT
    severity_order = {"CRITICAL": 0, "IMPORTANT": 1, "SUGGESTION": 2}
    sorted_findings = sorted(findings, key=lambda f: severity_order.get(f.severity, 9))

    for f in sorted_findings:
        location = f" at {f.location}" if f.location else ""
        evidence = f"\n   Evidence: {f.evidence}" if f.evidence else ""
        parts.append(
            f"### {f.id} [{f.severity}]{location}\n"
            f"   {f.description}{evidence}\n"
            f"   Sources: {', '.join(f.source_perspectives)}\n"
            f"   Rationale: {f.assessment_rationale}"
        )
    return "\n\n".join(parts)


def _parse_claude_output(stdout: str) -> FixResult | None:
    """Try to extract fix results from claude -p --output-format json stdout.

    The claude JSON output contains a 'result' field with the assistant's
    final text response. We look for fix/edit actions in that text.
    """
    if not stdout or not stdout.strip():
        return None

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return None

    # claude --output-format json wraps output in {"type":"result","result":"..."}
    result_text = data.get("result", "")
    if not result_text:
        return None

    # Try to find a JSON fix summary embedded in the result text.
    # Use json.JSONDecoder.raw_decode from the opening brace before "fixes_applied".
    marker = result_text.find('"fixes_applied"')
    if marker >= 0:
        brace_start = result_text.rfind("{", 0, marker)
        if brace_start >= 0:
            decoder = json.JSONDecoder()
            try:
                summary, _ = decoder.raw_decode(result_text, brace_start)
                return FixResult(
                    fixes_applied=summary.get("fixes_applied", []),
                    fixes_skipped=summary.get("fixes_skipped", []),
                )
            except json.JSONDecodeError:
                logger.warning(
                    "Found 'fixes_applied' marker at position %d but could not "
                    "parse valid JSON from claude -p output (%d chars)",
                    marker, len(result_text),
                )

    # If no embedded JSON, count Edit/Write tool uses as proxy for fixes applied
    # This is a rough heuristic but better than returning empty
    edits = result_text.lower().count("edit") + result_text.lower().count("wrote")
    if edits > 0:
        logger.info(
            "claude -p result mentions ~%d edit/write actions but no structured summary",
            edits,
        )

    return None


_FIX_EXTRACTION_PROMPT = """\
The following is the raw JSON output from a `claude -p` subprocess that was asked to fix \
review findings in a file. The subprocess applied edits but its "result" field does not \
contain a structured fix summary. Extract what was actually done.

Examine the full JSON output (including tool use history, permission denials, and the \
result text) to determine which findings were fixed, which were skipped, and why.

You MUST respond with ONLY a JSON object — no markdown, no commentary:

```json
{
    "fixes_applied": [
        {"finding_id": "F-1", "severity": "CRITICAL", "file": "path/to/file", "action": "Description of what was fixed"}
    ],
    "fixes_skipped": [
        {"finding_id": "F-3", "severity": "IMPORTANT", "reason": "Why this was skipped"}
    ]
}
```

If you cannot determine what happened, return: {"fixes_applied": [], "fixes_skipped": []}

--- BEGIN CLAUDE OUTPUT ---
"""


def _extract_fixes_fallback(
    stdout: str,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    timeout: float = 120,
) -> FixResult | None:
    """Fallback: ask an LLM to extract fix results from unparseable claude -p output."""
    base_url = base_url or os.environ.get("LITELLM_BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL")
    api_key = (
        api_key
        or os.environ.get("LITELLM_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or os.environ.get("ANTHROPIC_API_KEY")
        or ""
    ).strip()

    if not base_url or not api_key:
        logger.warning("Cannot run fix extraction fallback: no API credentials")
        return None

    # Truncate stdout to avoid blowing context — keep first and last portions
    max_chars = 60_000
    if len(stdout) > max_chars:
        half = max_chars // 2
        truncated = stdout[:half] + "\n\n[... truncated ...]\n\n" + stdout[-half:]
    else:
        truncated = stdout

    prompt = _FIX_EXTRACTION_PROMPT + truncated + "\n--- END CLAUDE OUTPUT ---"

    try:
        client = OpenAI(base_url=base_url, api_key=api_key)
        response = client.chat.completions.create(
            model=model or "aws/claude-haiku-4-5",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            timeout=timeout,
        )
        if not response.choices:
            return None
        text = response.choices[0].message.content or ""

        # Parse JSON from response
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                data = json.loads(text[start : end + 1])
            else:
                logger.warning("Fix extraction fallback returned unparseable response")
                return None

        result = FixResult(
            fixes_applied=data.get("fixes_applied", []),
            fixes_skipped=data.get("fixes_skipped", []),
        )
        logger.info(
            "Fix extraction fallback recovered %d applied, %d skipped",
            len(result.fixes_applied),
            len(result.fixes_skipped),
        )
        return result

    except Exception as e:
        logger.warning("Fix extraction fallback failed: %s", e)
        return None


def apply_fixes(
    findings: list[AssessedFinding],
    artifact_path: str,
    state_dir: Path,
    round_num: int,
    fixer_model: str | None = None,
    timeout: int = 900,
    base_url: str | None = None,
    api_key: str | None = None,
    reviewer_model: str | None = None,
) -> FixResult:
    """Apply fixes via claude -p subprocess.

    Only called when critical + important > 0.
    """
    # Check claude CLI exists
    if not shutil.which("claude"):
        raise RuntimeError("claude CLI not found in PATH")

    summary_path = state_dir / f"fix-summary-round-{round_num}.json"

    # Only include CRITICAL and IMPORTANT for fixing
    fixable = [f for f in findings if f.severity in ("CRITICAL", "IMPORTANT")]
    findings_text = _format_findings(fixable)

    fix_prompt = _FIX_PROMPT_TEMPLATE.format(
        summary_path=summary_path,
        findings_text=findings_text,
        artifact_path=artifact_path,
    )

    # Save prompt for debugging
    prompt_file = state_dir / f"fix-prompt-round-{round_num}.md"
    prompt_file.write_text(fix_prompt)

    cmd = [
        "claude",
        "-p",
        "-",
        "--allowedTools",
        "Read,Edit,Write,Glob,Grep",
        "--output-format",
        "json",
    ]
    if fixer_model:
        cmd.extend(["--model", fixer_model])

    # Clear entrypoint to avoid analytics interference in nested subprocess
    env = {**os.environ, "CLAUDE_CODE_ENTRYPOINT": ""}
    # Remove CLAUDECODE env var to allow nested claude -p subprocess
    env.pop("CLAUDECODE", None)

    logger.info(
        "Running claude -p for round %d (%d findings to fix)",
        round_num,
        len(fixable),
    )
    start = time.monotonic()

    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        try:
            stdout, stderr = proc.communicate(input=fix_prompt, timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            elapsed = time.monotonic() - start
            logger.error("claude -p timed out after %.1fs, terminated", elapsed)
            return FixResult(error=f"fixer timed out after {elapsed:.0f}s")

        elapsed = time.monotonic() - start
        logger.info("claude -p completed in %.1fs (exit %d)", elapsed, proc.returncode)

        if proc.returncode != 0:
            logger.error("claude -p exited with code %d", proc.returncode)

        if stderr:
            logger.debug("claude -p stderr:\n%s", stderr[:2000])
        if stdout:
            logger.debug("claude -p stdout:\n%s", stdout[:2000])

        # Save full stdout/stderr to state dir for post-mortem
        stdout_path = state_dir / f"fix-stdout-round-{round_num}.txt"
        stdout_path.write_text(stdout or "")
        stderr_path = state_dir / f"fix-stderr-round-{round_num}.txt"
        stderr_path.write_text(stderr or "")

    except KeyboardInterrupt:
        if proc and proc.poll() is None:
            logger.info("Interrupted — terminating claude -p subprocess")
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        raise  # Re-raise so orchestrator's KeyboardInterrupt handler catches it

    except OSError as e:
        logger.error("claude -p subprocess OS error: %s", e)
        if proc and proc.poll() is None:
            proc.terminate()
        return FixResult(error=f"claude -p subprocess OS error: {e}")

    # Parse results: try claude -p --output-format json stdout first,
    # then fall back to the fix-summary file we asked it to write
    fix_result = _parse_claude_output(stdout)
    if fix_result:
        if proc.returncode != 0:
            fix_result.error = f"claude -p exited with code {proc.returncode} (partial success)"
        # Save parsed summary for state dir consistency
        write_json_file(summary_path, {
            "fixes_applied": fix_result.fixes_applied,
            "fixes_skipped": fix_result.fixes_skipped,
        })
        return fix_result

    if summary_path.exists():
        try:
            data = json.loads(summary_path.read_text())
            result = FixResult(
                fixes_applied=data.get("fixes_applied", []),
                fixes_skipped=data.get("fixes_skipped", []),
            )
            if proc.returncode != 0:
                result.error = f"claude -p exited with code {proc.returncode} (partial success)"
            return result
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to parse fix summary file: %s", e)

    # Fallback: ask an LLM to extract fix results from raw claude output
    if stdout and len(stdout.strip()) > 50:
        logger.info(
            "Attempting LLM fallback extraction from %d char claude -p output",
            len(stdout),
        )
        fallback_result = _extract_fixes_fallback(
            stdout,
            base_url=base_url,
            api_key=api_key,
            model=reviewer_model,
        )
        if fallback_result and (fallback_result.fixes_applied or fallback_result.fixes_skipped):
            if proc.returncode != 0:
                fallback_result.error = (
                    f"claude -p exited with code {proc.returncode} "
                    f"(fix summary recovered via LLM fallback)"
                )
            write_json_file(summary_path, {
                "fixes_applied": fallback_result.fixes_applied,
                "fixes_skipped": fallback_result.fixes_skipped,
            })
            return fallback_result

    if proc.returncode != 0:
        return FixResult(error=f"claude -p exited with code {proc.returncode}")

    logger.warning(
        "Could not parse fix results from claude -p output or summary file. "
        "Check %s for raw output.",
        stdout_path,
    )
    return FixResult(error="could not parse fix results from output or summary file")
