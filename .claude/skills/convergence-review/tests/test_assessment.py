"""BC-5, BC-6, BC-7: Assessment deduplication, severity independence, dismissal."""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from conftest import harvest_events
from helpers import (
    make_assessment_response,
    make_reviewer_response,
    make_round_mock,
    run_main,
)
from models import FixResult

REVIEWER_MODEL = "openai/test-reviewer"
FIXER_MODEL = "openai/test-fixer"


def _run_with_assessor(
    artifact_file, state_dir,
    default_perspectives, assessor_response,
    reviewer_findings=None,
):
    """Helper: run 1 round with specific assessor response, return exit code."""
    if reviewer_findings is None:
        reviewer_findings = [{"severity": "CRITICAL", "description": "Some finding"}]

    reviewer_resp = {
        p.id: make_reviewer_response(p.id, reviewer_findings)
        for p in default_perspectives
    }

    mock_client = MagicMock()
    mock_client.chat.completions.create = make_round_mock(
        reviewer_resp, assessor_response,
        reviewer_model=REVIEWER_MODEL, fixer_model=FIXER_MODEL,
    )

    argv = [
        "design", str(artifact_file),
        "--reviewer-model", REVIEWER_MODEL,
        "--fixer-model", FIXER_MODEL,
        "--max-rounds", "1",
        "--state-dir", str(state_dir),
        "--force",
    ]

    with (
        patch("orchestrator.load_perspectives", return_value=default_perspectives),
        patch("orchestrator.load_artifact_content", return_value="test content"),
        patch("orchestrator.AsyncOpenAI", return_value=mock_client),
        patch("orchestrator.apply_fixes", return_value=FixResult(
            fixes_applied=[{"finding_id": "F-1", "severity": "CRITICAL", "action": "fixed"}],
        )),
    ):
        return run_main(argv)


class TestDeduplication:
    """BC-5: Assessor merges findings from multiple perspectives into one."""

    def test_deduplication(
        self, env_vars, artifact_file, state_dir, capsys, default_perspectives
    ):
        assessor = make_assessment_response(
            assessed_findings=[{
                "id": "F-1", "severity": "CRITICAL",
                "original_severity": "CRITICAL",
                "description": "Missing invariant check",
                "source_perspectives": ["DD-1", "DD-2"],
                "assessment_rationale": "Both perspectives found the same issue",
            }],
        )

        _run_with_assessor(artifact_file, state_dir, default_perspectives, assessor)

        assessment_files = list(state_dir.glob("assessment-round-*.json"))
        assert len(assessment_files) >= 1
        data = json.loads(assessment_files[0].read_text())
        assessed = data["assessed_findings"]
        assert len(assessed) == 1
        assert "DD-1" in assessed[0]["source_perspectives"]
        assert "DD-2" in assessed[0]["source_perspectives"]


class TestSeverityIndependence:
    """BC-6: Assessor can re-prioritize severity independently of reviewers."""

    def test_severity_downgrade(
        self, env_vars, artifact_file, state_dir, capsys, default_perspectives
    ):
        assessor = make_assessment_response(
            assessed_findings=[{
                "id": "F-1", "severity": "SUGGESTION",
                "original_severity": "CRITICAL",
                "description": "Overstated issue",
                "source_perspectives": ["DD-1"],
                "assessment_rationale": "This is actually cosmetic",
            }],
        )

        _run_with_assessor(artifact_file, state_dir, default_perspectives, assessor)

        assessment_files = list(state_dir.glob("assessment-round-*.json"))
        assert len(assessment_files) >= 1
        data = json.loads(assessment_files[0].read_text())
        f = data["assessed_findings"][0]
        assert f["severity"] == "SUGGESTION"
        assert f["original_severity"] == "CRITICAL"


class TestDismissal:
    """BC-7: Assessor dismisses findings with reason."""

    def test_finding_dismissed(
        self, env_vars, artifact_file, state_dir, capsys, default_perspectives
    ):
        assessor = make_assessment_response(
            assessed_findings=[],
            dismissed=[{
                "description": "Factually incorrect claim",
                "source_perspectives": ["DD-3"],
                "dismissal_reason": "The code actually handles this case correctly",
            }],
        )

        _run_with_assessor(
            artifact_file, state_dir, default_perspectives, assessor,
            reviewer_findings=[{"severity": "CRITICAL", "description": "Factually incorrect claim"}],
        )

        assessment_files = list(state_dir.glob("assessment-round-*.json"))
        assert len(assessment_files) >= 1
        data = json.loads(assessment_files[0].read_text())

        assert len(data["assessed_findings"]) == 0
        assert len(data["dismissed"]) == 1
        d = data["dismissed"][0]
        assert "DD-3" in d["source_perspectives"]
        assert len(d["dismissal_reason"]) > 0

        events = harvest_events(capsys)
        assess_events = [e for e in events if e.get("event") == "assessment_complete"]
        assert len(assess_events) == 1
        assert assess_events[0]["dismissed"] == 1
