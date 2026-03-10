"""Assessment phase: dedup, validate, re-prioritize findings via OpenAI-compatible API."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from models import (
    AssessedFinding,
    Assessment,
    DismissedFinding,
    ReviewerOutput,
)

logger = logging.getLogger("convergence.assessor")

ASSESSMENT_SYSTEM_PROMPT = """\
You are a senior technical reviewer performing quality control on review findings.

You will receive:
1. The review gate type and what it expects
2. Raw findings from multiple reviewer perspectives
3. The artifact being reviewed

Your job is to produce a consolidated, high-quality assessment by:

1. **GATE FIT**: First, check whether the artifact is appropriate for this gate type. \
If the artifact is fundamentally the wrong type (e.g., a Python design doc reviewed \
with Go code review prompts, or a macro plan reviewed as a design doc), flag this as a \
single CRITICAL finding with id "F-0" and description starting with "GATE MISMATCH:". \
Dismiss all other findings as downstream of the mismatch.

2. **DEDUP**: Merge findings from different perspectives that describe the same issue. \
Cite all originating perspectives.

3. **CROSS-ROUND DEDUP**: If a prior-round finding ledger is provided, check each \
current finding for thematic overlap with prior findings. Assign a cross_round_status:
   - "novel": Not seen in any prior round.
   - "regression": A prior fix introduced this new problem.
   - "recurring-fixed": Same theme as a prior finding that was fixed. \
DISMISS unless you can state a specific deficiency in the prior fix.
   - "recurring-skipped": Same theme the fixer already skipped. \
Keep only if you can explain what the skip rationale missed.
   - "recurring-escalate": Same theme flagged in 3+ prior rounds. \
This is a persistent design trade-off. DISMISS from the fix loop.
   If no ledger is provided, set cross_round_status to "novel" for all findings.

4. **VALIDATE**: Check whether evidence supports each claim. Dismiss findings that are:
   - Factually wrong or unsupported by the artifact content
   - Asking for content that is out of scope for this artifact type \
(e.g., demanding Go code in a design doc, or DES event definitions in a tooling spec)
   - Applying standards from a different domain than the artifact addresses

5. **RE-PRIORITIZE**: Independently assign severity using these definitions:
   - CRITICAL: Must fix. Missing control, contradicted status, silent data loss, \
cross-document contradiction.
   - IMPORTANT: Should fix. Would reader be misled? Would conclusion change?
   - SUGGESTION: Cosmetic. Off-by-one citations, style, terminology.

6. **NOTE GAPS**: Flag perspectives that timed out or errored as uncovered.

Respond with ONLY a JSON object matching this schema:
{
    "assessed_findings": [
        {
            "id": "F-1",
            "severity": "CRITICAL",
            "original_severity": "CRITICAL",
            "description": "...",
            "location": "file:line or null",
            "evidence": "...",
            "source_perspectives": ["XX-1", "XX-2"],
            "assessment_rationale": "...",
            "cross_round_status": "novel",
            "prior_finding_ref": null
        }
    ],
    "dismissed": [
        {
            "description": "...",
            "source_perspectives": ["XX-3"],
            "dismissal_reason": "..."
        }
    ],
    "uncovered_perspectives": [],
    "summary": {
        "critical": 0,
        "important": 0,
        "suggestion": 0,
        "dismissed": 0,
        "deduplicated": 0
    }
}
"""


_GATE_DESCRIPTIONS = {
    "design": "Design document review. Artifact should be a behavioral specification describing what modules do and why. Reviewers check DES foundations, module architecture, invariants, etc.",
    "macro-plan": "Macro plan review. Artifact should be a multi-PR implementation plan with PR decomposition, dependency DAG, and module contracts.",
    "x-macro-plan": "Cross-system macro plan review. Artifact should be a multi-PR implementation plan spanning multiple systems/repos, with cross-system dependency DAG, component contracts, and integration points.",
    "g-macro-plan": "Generalized macro plan review. Artifact should be a multi-PR implementation plan for a generalized/reusable pipeline, with PR decomposition, component contracts, and extension points.",
    "pr-plan": "PR micro plan review. Artifact should be a single-PR implementation plan with TDD tasks and behavioral contracts.",
    "x-pr-plan": "Cross-system PR micro plan review. Artifact should be a single-PR implementation plan for transferring logic between two codebases, with signal mappings, schema contracts, and cross-system integration steps.",
    "pr-code": "PR code review. Artifact is a git diff of code changes.",
    "x-pr-code": "Cross-system PR code review. Artifact is a git diff of code changes for a cross-system transfer pipeline (sim2real). Review focuses on cross-system contract integrity, artifact consistency, prompt template quality, and Python CLI + Go harness code correctness.",
    "h-design": "Hypothesis experiment design review. Artifact should be a hypothesis sentence, classification, and experiment design.",
    "h-code": "Hypothesis experiment code review. Artifact should be run.sh and analyze.py scripts.",
    "h-findings": "Hypothesis FINDINGS.md review. Artifact should be experimental results with analysis.",
}


def build_prior_ledger(state_dir: Path, current_round: int, max_detail_rounds: int = 3) -> str:
    """Build a text ledger of prior-round findings and their fix dispositions.

    Reads assessment-round-{1..N-1}.json and fix-summary-round-{1..N-1}.json
    from the state directory. Recent rounds get full detail; older rounds get
    a one-line summary to bound prompt length.

    Returns empty string for round 1 (no prior rounds).
    """
    if current_round <= 1:
        return ""

    parts = ["## Prior Round Findings\n"]
    detail_cutoff = max(1, current_round - max_detail_rounds)

    for r in range(1, current_round):
        assessment_path = state_dir / f"assessment-round-{r}.json"
        fix_path = state_dir / f"fix-summary-round-{r}.json"

        if not assessment_path.exists():
            continue

        try:
            assessment_data = json.loads(assessment_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not read assessment-round-%d.json: %s", r, e)
            continue

        findings = assessment_data.get("assessed_findings", [])
        summary = assessment_data.get("summary", {})
        c_count = summary.get("critical", 0)
        i_count = summary.get("important", 0)

        # Load fix dispositions
        fix_map: dict[str, dict] = {}  # finding_id -> fix/skip info
        if fix_path.exists():
            try:
                fix_data = json.loads(fix_path.read_text())
                for fa in fix_data.get("fixes_applied", []):
                    fid = fa.get("finding_id", "")
                    fix_map[fid] = {"status": "FIXED", "detail": fa.get("action", "")}
                for fs in fix_data.get("fixes_skipped", []):
                    fid = fs.get("finding_id", "")
                    fix_map[fid] = {"status": "SKIPPED", "detail": fs.get("reason", "")}
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Could not read fix-summary-round-%d.json: %s", r, e)

        applied = sum(1 for v in fix_map.values() if v["status"] == "FIXED")
        skipped = sum(1 for v in fix_map.values() if v["status"] == "SKIPPED")

        if r < detail_cutoff:
            # Older rounds: one-line summary only
            parts.append(
                f"### Round {r} (summary): {c_count}C {i_count}I — "
                f"{applied} fixed, {skipped} skipped\n"
            )
            continue

        # Recent rounds: full detail
        parts.append(f"### Round {r} ({c_count}C {i_count}I — {applied} fixed, {skipped} skipped)\n")
        for f in findings:
            if f.get("severity") not in ("CRITICAL", "IMPORTANT"):
                continue
            fid = f.get("id", "?")
            sev = f.get("severity", "?")
            desc = f.get("description", "")[:200]
            disposition = fix_map.get(fid)
            if disposition:
                disp_detail = disposition["detail"][:150]
                parts.append(f"- {fid} [{sev}] {desc} → {disposition['status']}: {disp_detail}\n")
            else:
                parts.append(f"- {fid} [{sev}] {desc} → (no fix data)\n")

    parts.append("")
    return "\n".join(parts)


def _format_assessment_input(
    reviewer_outputs: list[ReviewerOutput], artifact_content: str,
    gate: str = "", prior_ledger: str = "",
) -> str:
    """Format reviewer outputs and artifact for the assessment call."""
    parts = []

    if gate:
        gate_desc = _GATE_DESCRIPTIONS.get(gate, gate)
        parts.append(f"## Gate Type: {gate}\n{gate_desc}\n")

    if prior_ledger:
        parts.append(prior_ledger)

    parts.append("## Reviewer Findings\n")

    for output in reviewer_outputs:
        if output.error:
            parts.append(
                f"### {output.perspective} — ERROR: {output.error}\n"
            )
            continue

        parts.append(f"### {output.perspective}\n")
        for f in output.findings:
            location = f" (at {f.location})" if f.location else ""
            evidence = f"\n  Evidence: {f.evidence}" if f.evidence else ""
            parts.append(
                f"- [{f.severity}] {f.description}{location}{evidence}\n"
            )
        if not output.findings:
            parts.append("No findings.\n")

    parts.append("\n## Artifact Being Reviewed\n")
    parts.append(artifact_content)

    return "\n".join(parts)


def _parse_assessment(text: str) -> Assessment:
    """Parse assessment JSON response."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Lenient: find JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(text[start : end + 1])
        else:
            raise

    assessed = []
    for i, f in enumerate(data.get("assessed_findings", []), 1):
        assessed.append(
            AssessedFinding(
                id=f.get("id", f"F-{i}"),
                severity=f.get("severity", "SUGGESTION"),
                original_severity=f.get("original_severity", f.get("severity", "SUGGESTION")),
                description=f.get("description", ""),
                source_perspectives=f.get("source_perspectives", []),
                assessment_rationale=f.get("assessment_rationale", ""),
                location=f.get("location"),
                evidence=f.get("evidence"),
                cross_round_status=f.get("cross_round_status", "novel"),
                prior_finding_ref=f.get("prior_finding_ref"),
            )
        )

    dismissed = []
    for d in data.get("dismissed", []):
        dismissed.append(
            DismissedFinding(
                description=d.get("description", ""),
                source_perspectives=d.get("source_perspectives", []),
                dismissal_reason=d.get("dismissal_reason", ""),
            )
        )

    summary = data.get("summary", {})
    # Recompute summary from parsed data to ensure accuracy
    computed_summary = {
        "critical": sum(1 for f in assessed if f.severity == "CRITICAL"),
        "important": sum(1 for f in assessed if f.severity == "IMPORTANT"),
        "suggestion": sum(1 for f in assessed if f.severity == "SUGGESTION"),
        "dismissed": len(dismissed),
        "deduplicated": summary.get("deduplicated", 0),
    }

    return Assessment(
        assessed_findings=assessed,
        dismissed=dismissed,
        uncovered_perspectives=data.get("uncovered_perspectives", []),
        summary=computed_summary,
    )


async def assess_findings(
    client: AsyncOpenAI,
    model: str,
    reviewer_outputs: list[ReviewerOutput],
    artifact_content: str,
    timeout: float = 600,
    gate: str = "",
    prior_ledger: str = "",
) -> Assessment:
    """Run assessment phase: dedup, validate, re-prioritize findings.

    Retries once on failure. If both attempts fail, returns an Assessment
    with raw findings passed through (no dedup/validation).
    """
    input_text = _format_assessment_input(
        reviewer_outputs, artifact_content, gate=gate, prior_ledger=prior_ledger,
    )

    for attempt in range(2):
        try:
            messages = [
                {"role": "system", "content": ASSESSMENT_SYSTEM_PROMPT},
                {"role": "user", "content": input_text},
            ]
            if attempt == 1:
                messages.append(
                    {
                        "role": "user",
                        "content": "Important: respond with ONLY a valid JSON object, "
                        "no markdown or commentary.",
                    }
                )

            start = time.monotonic()
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.0,
                ),
                timeout=timeout,
            )
            elapsed = time.monotonic() - start

            if not response.choices:
                raise ValueError("Assessment API returned empty choices list")
            text = response.choices[0].message.content or ""
            logger.debug(
                "Assessment raw response (%d chars): %s",
                len(text),
                text[:500],
            )
            assessment = _parse_assessment(text)

            logger.info(
                "Assessment complete in %.1fs: %d assessed, %d dismissed",
                elapsed,
                len(assessment.assessed_findings),
                len(assessment.dismissed),
            )
            return assessment

        except (
            APIConnectionError, APIStatusError, APITimeoutError,
            asyncio.TimeoutError, json.JSONDecodeError, ValueError,
        ) as e:
            if attempt == 0:
                logger.warning("Assessment attempt 1 of 2 failed: %s, retrying", e)
            else:
                logger.error("Assessment failed after 2 attempts: %s", e)

    # Fallback: pass raw findings through without assessment
    logger.error(
        "ASSESSMENT FALLBACK: passing %d raw findings through without "
        "deduplication or validation. Results may contain duplicates and false positives.",
        sum(len(o.findings) for o in reviewer_outputs),
    )
    raw_findings = []
    for i, output in enumerate(reviewer_outputs):
        for finding in output.findings:
            raw_findings.append(
                AssessedFinding(
                    id=f"F-{len(raw_findings) + 1}",
                    severity=finding.severity,
                    original_severity=finding.severity,
                    description=finding.description,
                    source_perspectives=[finding.perspective],
                    assessment_rationale="Assessment failed — raw finding passed through",
                    location=finding.location,
                    evidence=finding.evidence,
                )
            )

    return Assessment(
        assessed_findings=raw_findings,
        fallback=True,
        summary={
            "critical": sum(1 for f in raw_findings if f.severity == "CRITICAL"),
            "important": sum(1 for f in raw_findings if f.severity == "IMPORTANT"),
            "suggestion": sum(1 for f in raw_findings if f.severity == "SUGGESTION"),
            "dismissed": 0,
            "deduplicated": 0,
        },
    )
