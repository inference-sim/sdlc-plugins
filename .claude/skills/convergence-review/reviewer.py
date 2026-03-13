"""Async reviewer dispatch via OpenAI-compatible API."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import asdict
from pathlib import Path

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from models import Finding, ReviewerOutput
from progress import emit_reviewer_done, emit_reviewer_error, write_json_file
from prompts import Perspective

logger = logging.getLogger("convergence.reviewer")

# Retry config for API errors
_MAX_RETRIES = 3
_RETRY_DELAYS = [2, 4, 8]  # seconds

# Patterns in prompt templates that should be replaced with artifact content
_PLACEHOLDER_RE = re.compile(r"<paste [^>]+>|<path to [^>]+>")


_OUTPUT_FORMAT_SUFFIX = """

## Required Output Format

You MUST respond with ONLY a JSON object. No markdown, no commentary, no explanation outside the JSON.

```json
{
    "perspective": "<your perspective ID>",
    "findings": [
        {
            "severity": "CRITICAL",
            "description": "Clear description of the issue",
            "location": "file:line or section reference if applicable, else null",
            "evidence": "Quote or reference from the artifact supporting this finding"
        }
    ]
}
```

Severity definitions:
- CRITICAL: Must fix. Missing control, contradicted status, silent data loss, cross-document contradiction.
- IMPORTANT: Should fix. Would reader be misled? Would a conclusion change?
- SUGGESTION: Cosmetic. Style, terminology, minor clarity improvements.

If you find no issues, return: {"perspective": "<ID>", "findings": []}
"""


def _inject_artifact(
    prompt: str,
    artifact_content: str,
    prior_round_context: str | None = None,
) -> str:
    """Replace placeholder patterns in prompt with actual artifact content,
    and append structured output format instructions.

    Handles three placeholder styles:
    - <paste ...> / <path to ...> tags (legacy)
    - ARTIFACT_PATH literal (pr-prompts.md convention)
    - "First, read the plan file at ARTIFACT_PATH..." instruction lines
    """
    # re.sub treats \w in replacement as backreference — escape it
    filled = _PLACEHOLDER_RE.sub(lambda _: artifact_content, prompt)

    # Replace ARTIFACT_PATH and rewrite "read the file" instructions since
    # API-based reviewers can't read files — inject the content directly.
    if "ARTIFACT_PATH" in filled:
        # Remove "First, read ... using the Read tool." instruction lines
        filled = re.sub(
            r"^First,.*(?:Read tool|Bash tool|git diff).*$\n?",
            "",
            filled,
            flags=re.MULTILINE,
        )
        filled = filled.replace("ARTIFACT_PATH", "")

    # Append prior round context if available (round 2+)
    context_section = ""
    if prior_round_context:
        context_section = "\n\n" + prior_round_context

    # Append artifact content and output format
    return (
        filled.rstrip()
        + context_section
        + "\n\n## Artifact Content\n\n"
        + artifact_content
        + _OUTPUT_FORMAT_SUFFIX
    )


def _parse_reviewer_response(perspective_id: str, text: str) -> list[Finding]:
    """Parse reviewer output, trying JSON first then falling back to markdown.

    JSON format:
    {"findings": [{"severity": "CRITICAL", "description": "..."}]}

    Markdown format (model's natural output):
    1. [CRITICAL] Description of finding
    - **[CRITICAL]** Description of finding
    **CRITICAL**: Description of finding
    """
    # Try JSON first
    findings = _try_parse_json(perspective_id, text)
    if findings is not None:
        return findings

    # Fall back to markdown/text parsing
    findings = _parse_markdown_findings(perspective_id, text)
    if findings:
        logger.info(
            "%s: parsed %d findings from markdown output",
            perspective_id,
            len(findings),
        )
    else:
        logger.warning(
            "%s: no findings parsed from %d char response",
            perspective_id,
            len(text),
        )
    return findings


def _fix_json_escapes(raw: str) -> str:
    r"""Fix invalid JSON escape sequences produced by LLMs quoting code/regex.

    Models often embed regex patterns (e.g. \w, \d, \.) in JSON string values.
    These are valid regex but invalid JSON escapes.  We must handle mixed
    content where some backslashes are already properly escaped (\\w) while
    others are not (\w).

    Strategy: temporarily protect valid \\ pairs, fix remaining bad escapes,
    then restore.
    """
    _SENTINEL = "\x00BKSL\x00"
    # Protect already-escaped backslashes
    protected = raw.replace("\\\\", _SENTINEL)
    # Fix remaining lone backslashes not followed by valid JSON escape chars
    fixed = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', protected)
    # Restore protected backslashes
    return fixed.replace(_SENTINEL, "\\\\")


def _try_parse_json(perspective_id: str, text: str) -> list[Finding] | None:
    """Try to parse response as JSON. Returns None if not JSON."""
    # Try direct parse
    try:
        data = json.loads(text)
        return _extract_json_findings(perspective_id, data)
    except json.JSONDecodeError as e:
        logger.debug("%s: direct JSON parse failed: %s", perspective_id, e)

    # Try finding a JSON code block
    json_block = re.search(r"```(?:json)?\s*\n(\{.*\})\s*\n```", text, re.DOTALL)
    if json_block:
        raw = json_block.group(1)
        for attempt_text in (raw, _fix_json_escapes(raw)):
            try:
                data = json.loads(attempt_text)
                return _extract_json_findings(perspective_id, data)
            except json.JSONDecodeError as e:
                logger.debug("%s: code block JSON parse failed: %s", perspective_id, e)

    # Try direct parse with escape fix (no code block)
    try:
        data = json.loads(_fix_json_escapes(text))
        return _extract_json_findings(perspective_id, data)
    except json.JSONDecodeError:
        pass

    return None


def _extract_json_findings(perspective_id: str, data: dict) -> list[Finding]:
    """Extract findings from a parsed JSON dict."""
    findings_data = data.get("findings", [])
    findings = []
    for f in findings_data:
        raw_severity = f.get("severity", "SUGGESTION")
        severity = raw_severity.upper()
        if severity not in ("CRITICAL", "IMPORTANT", "SUGGESTION"):
            logger.warning(
                "%s: unknown severity %r demoted to SUGGESTION",
                perspective_id, raw_severity,
            )
            severity = "SUGGESTION"
        findings.append(
            Finding(
                perspective=perspective_id,
                severity=severity,
                description=f.get("description", ""),
                location=f.get("location"),
                evidence=f.get("evidence"),
            )
        )
    return findings


# Patterns to match severity tags in various markdown formats
_SEVERITY_PATTERNS = [
    # 1. [CRITICAL] description  or  - [CRITICAL] description
    re.compile(
        r"^[\s\-\*\d.]*\[(?P<sev>CRITICAL|IMPORTANT|SUGGESTION)\]\s*(?P<desc>.+)",
        re.MULTILINE,
    ),
    # **[CRITICAL]** description  or  **CRITICAL**: description
    re.compile(
        r"\*\*\[?(?P<sev>CRITICAL|IMPORTANT|SUGGESTION)\]?\*\*[:\s]+(?P<desc>.+)",
        re.MULTILINE,
    ),
    # CRITICAL: description (standalone line)
    re.compile(
        r"^(?P<sev>CRITICAL|IMPORTANT|SUGGESTION):\s+(?P<desc>.+)",
        re.MULTILINE,
    ),
    # Severity: CRITICAL — or — Rating: CRITICAL (followed by description on next context)
    re.compile(
        r"(?:Severity|Rating)[:\s]+\*?\*?(?P<sev>CRITICAL|IMPORTANT|SUGGESTION)\*?\*?",
        re.MULTILINE,
    ),
]


def _parse_markdown_findings(perspective_id: str, text: str) -> list[Finding]:
    """Extract findings from markdown-formatted reviewer output."""
    findings = []
    seen_descriptions = set()

    for pattern in _SEVERITY_PATTERNS:
        for match in pattern.finditer(text):
            severity = match.group("sev").upper()
            desc = match.group("desc").strip() if "desc" in match.groupdict() else ""

            # Skip if no description (severity-only pattern)
            if not desc:
                continue

            # Clean up markdown formatting
            desc = re.sub(r"\*\*", "", desc).strip()
            desc = re.sub(r"^\W+", "", desc).strip()

            # Deduplicate by first 80 chars of description
            dedup_key = desc[:80].lower()
            if dedup_key in seen_descriptions:
                continue
            seen_descriptions.add(dedup_key)

            if severity not in ("CRITICAL", "IMPORTANT", "SUGGESTION"):
                severity = "SUGGESTION"

            findings.append(
                Finding(
                    perspective=perspective_id,
                    severity=severity,
                    description=desc,
                )
            )

    return findings


_EXTRACTION_PROMPT = """\
The following is a review response that could not be parsed as JSON. \
Extract ALL findings from it and return them as a JSON object.

You MUST respond with ONLY a JSON object — no markdown, no commentary.

```json
{
    "findings": [
        {
            "severity": "CRITICAL or IMPORTANT or SUGGESTION",
            "description": "Clear description of the issue",
            "location": "file:line or section reference if applicable, else null",
            "evidence": "Quote or reference from the review supporting this finding"
        }
    ]
}
```

If the review found no issues, return: {"findings": []}

--- BEGIN REVIEW RESPONSE ---
"""


async def _extract_findings_fallback(
    client: AsyncOpenAI,
    model: str,
    perspective_id: str,
    raw_text: str,
    timeout: float,
) -> list[Finding] | None:
    """Fallback: ask an LLM to extract findings from an unparseable response."""
    prompt = _EXTRACTION_PROMPT + raw_text + "\n--- END REVIEW RESPONSE ---"
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            ),
            timeout=timeout,
        )
        if not response.choices:
            return None
        extraction = response.choices[0].message.content or ""
        findings = _try_parse_json(perspective_id, extraction)
        if findings is not None:
            logger.info(
                "%s: fallback extraction recovered %d findings",
                perspective_id,
                len(findings),
            )
        else:
            logger.warning(
                "%s: fallback extraction also failed to parse",
                perspective_id,
            )
        return findings
    except (asyncio.TimeoutError, APIConnectionError, APIStatusError, APITimeoutError) as e:
        logger.warning("%s: fallback extraction failed: %s", perspective_id, e)
        return None


async def run_reviewer(
    client: AsyncOpenAI,
    model: str,
    perspective: Perspective,
    artifact_content: str,
    timeout: float,
    round_num: int,
    prior_round_context: str | None = None,
) -> ReviewerOutput:
    """Run a single reviewer perspective via OpenAI chat completion."""
    start = time.monotonic()

    # Inject artifact content into prompt placeholders
    prompt_with_artifact = _inject_artifact(
        perspective.prompt, artifact_content, prior_round_context
    )

    for attempt in range(_MAX_RETRIES):
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "user", "content": prompt_with_artifact},
                    ],
                    temperature=0.0,
                ),
                timeout=timeout,
            )
            elapsed = time.monotonic() - start
            if not response.choices:
                raise ValueError(f"{perspective.id}: API returned empty choices list")
            text = response.choices[0].message.content or ""
            logger.debug(
                "%s raw response (%d chars): %s",
                perspective.id,
                len(text),
                text[:500],
            )
            findings = _parse_reviewer_response(perspective.id, text)

            # Detect non-empty response that yielded no findings (possible parse failure)
            parse_warning = None
            if not findings and len(text.strip()) > 50:
                logger.warning(
                    "%s: non-empty response (%d chars) yielded 0 findings — trying fallback extraction",
                    perspective.id,
                    len(text),
                )
                fallback = await _extract_findings_fallback(
                    client, model, perspective.id, text, timeout,
                )
                if fallback:
                    findings = fallback
                else:
                    parse_warning = (
                        f"non-empty response ({len(text)} chars) yielded 0 findings"
                    )

            logger.info(
                "%s completed: %d findings in %.1fs",
                perspective.id,
                len(findings),
                elapsed,
            )
            emit_reviewer_done(round_num, perspective.id, len(findings), elapsed)
            return ReviewerOutput(
                perspective=perspective.id,
                findings=findings,
                parse_warning=parse_warning,
                elapsed_sec=elapsed,
            )

        except asyncio.TimeoutError:
            elapsed = time.monotonic() - start
            logger.warning("%s timed out after %.1fs", perspective.id, elapsed)
            emit_reviewer_error(round_num, perspective.id, "timeout", elapsed)
            return ReviewerOutput(
                perspective=perspective.id,
                error="timeout",
                elapsed_sec=elapsed,
            )

        except (APIConnectionError, APIStatusError, APITimeoutError) as e:
            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_DELAYS[attempt]
                logger.warning(
                    "%s attempt %d failed: %s, retrying in %ds",
                    perspective.id,
                    attempt + 1,
                    e,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                elapsed = time.monotonic() - start
                error_msg = f"failed after {_MAX_RETRIES} attempts: {e}"
                logger.error("%s %s", perspective.id, error_msg)
                emit_reviewer_error(round_num, perspective.id, error_msg, elapsed)
                return ReviewerOutput(
                    perspective=perspective.id,
                    error=error_msg,
                    elapsed_sec=elapsed,
                )

    # Unreachable, but satisfy type checker
    elapsed = time.monotonic() - start
    return ReviewerOutput(perspective=perspective.id, error="unknown", elapsed_sec=elapsed)


async def run_all_reviewers(
    client: AsyncOpenAI,
    model: str,
    perspectives: list[Perspective],
    artifact_content: str,
    timeout: float,
    round_num: int,
    state_dir: Path,
    prior_round_context: str | None = None,
) -> list[ReviewerOutput]:
    """Dispatch all reviewers in parallel and collect results."""
    tasks = [
        run_reviewer(
            client, model, p, artifact_content, timeout, round_num,
            prior_round_context,
        )
        for p in perspectives
    ]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert exceptions to error outputs
    results: list[ReviewerOutput] = []
    for i, r in enumerate(raw_results):
        if isinstance(r, BaseException):
            pid = perspectives[i].id if i < len(perspectives) else f"unknown-{i}"
            logger.error("%s raised unexpected exception: %s", pid, r)
            results.append(ReviewerOutput(perspective=pid, error=f"internal error: {r}"))
        else:
            results.append(r)

    # Save raw reviewer outputs to state directory
    reviewers_dir = state_dir / f"reviewers-round-{round_num}"
    reviewers_dir.mkdir(parents=True, exist_ok=True)
    for output in results:
        data = {
            "perspective": output.perspective,
            "findings": [asdict(f) for f in output.findings],
            "error": output.error,
            "elapsed_sec": output.elapsed_sec,
        }
        write_json_file(reviewers_dir / f"{output.perspective}.json", data)

    return list(results)
