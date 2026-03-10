"""BC-1, BC-2, BC-3: Convergence loop outcomes (converged, stalled, early stall)."""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from conftest import harvest_events
from helpers import (
    _make_chat_response,
    make_assessment_response,
    make_reviewer_response,
    make_round_mock,
    run_main,
)
from models import FixResult

REVIEWER_MODEL = "openai/test-reviewer"
FIXER_MODEL = "openai/test-fixer"


def _make_argv(artifact_path, state_dir, max_rounds=10, force=False, stall_window=3):
    argv = [
        "design", str(artifact_path),
        "--reviewer-model", REVIEWER_MODEL,
        "--fixer-model", FIXER_MODEL,
        "--max-rounds", str(max_rounds),
        "--state-dir", str(state_dir),
        "--stall-window", str(stall_window),
    ]
    if force:
        argv.append("--force")
    return argv


class TestConvergence:
    """BC-1: R1 finds 1 CRITICAL (fixed), R2 finds 0 → exit=0, converged event."""

    def test_convergence_exit(
        self, env_vars, artifact_file, state_dir, capsys, default_perspectives
    ):
        round_counter = {"n": 0}

        async def side_effect(*, model, messages, temperature=0.0, **kwargs):
            if model == FIXER_MODEL:
                if round_counter["n"] == 1:
                    resp = make_assessment_response(
                        assessed_findings=[{
                            "id": "F-1", "severity": "CRITICAL",
                            "original_severity": "CRITICAL",
                            "description": "Missing invariant check",
                            "source_perspectives": ["DD-1"],
                            "assessment_rationale": "Valid finding",
                        }],
                    )
                else:
                    resp = make_assessment_response()
                return _make_chat_response(json.dumps(resp))

            if round_counter["n"] == 1:
                resp = make_reviewer_response("DD-1", [{
                    "severity": "CRITICAL", "description": "Missing invariant check",
                }])
            else:
                resp = make_reviewer_response("DD-1", [])
            return _make_chat_response(json.dumps(resp))

        load_call_count = {"n": 0}

        def mock_load(gate, path):
            load_call_count["n"] += 1
            return "content v" + str(load_call_count["n"])

        mock_client = MagicMock()
        mock_client.chat.completions.create = side_effect

        def mock_apply_fixes(findings, artifact_path, sd, round_num, **kwargs):
            return FixResult(
                fixes_applied=[{"finding_id": "F-1", "severity": "CRITICAL", "action": "fixed"}],
            )

        import orchestrator as orch_mod
        original_run_round = orch_mod.run_round

        async def tracking_run_round(client, args, round_num, *a, **kw):
            round_counter["n"] = round_num
            return await original_run_round(client, args, round_num, *a, **kw)

        with (
            patch("orchestrator.load_perspectives", return_value=default_perspectives),
            patch("orchestrator.load_artifact_content", side_effect=mock_load),
            patch("orchestrator.AsyncOpenAI", return_value=mock_client),
            patch("orchestrator.apply_fixes", side_effect=mock_apply_fixes),
            patch("orchestrator.run_round", side_effect=tracking_run_round),
        ):
            code = run_main(_make_argv(artifact_file, state_dir, max_rounds=5))

        assert code == 0
        events = harvest_events(capsys)
        event_names = [e["event"] for e in events if "event" in e]
        assert "converged" in event_names

        # Summary file should contain "CONVERGED"
        summary_files = list(state_dir.glob("summary.md"))
        assert len(summary_files) == 1, f"Expected summary.md in {state_dir}"
        assert "CONVERGED" in summary_files[0].read_text()


class TestStallMaxRounds:
    """BC-2: CRITICAL persists every round, max-rounds reached → exit=1, stalled event."""

    def test_stall_max_rounds(
        self, env_vars, artifact_file, state_dir, capsys, default_perspectives
    ):
        reviewer_resp = {
            p.id: make_reviewer_response(p.id, [{
                "severity": "CRITICAL", "description": "Persistent issue",
            }]) for p in default_perspectives
        }
        assessor = make_assessment_response(
            assessed_findings=[{
                "id": "F-1", "severity": "CRITICAL",
                "original_severity": "CRITICAL",
                "description": "Persistent issue",
                "source_perspectives": ["DD-1"],
                "assessment_rationale": "Real issue",
            }],
        )

        mock_client = MagicMock()
        mock_client.chat.completions.create = make_round_mock(
            reviewer_resp, assessor,
            reviewer_model=REVIEWER_MODEL, fixer_model=FIXER_MODEL,
        )

        def mock_apply_fixes(findings, artifact_path, sd, round_num, **kwargs):
            return FixResult(
                fixes_applied=[{"finding_id": "F-1", "severity": "CRITICAL", "action": "attempted"}],
            )

        with (
            patch("orchestrator.load_perspectives", return_value=default_perspectives),
            patch("orchestrator.load_artifact_content", return_value="test content"),
            patch("orchestrator.AsyncOpenAI", return_value=mock_client),
            patch("orchestrator.apply_fixes", side_effect=mock_apply_fixes),
        ):
            code = run_main(_make_argv(artifact_file, state_dir, max_rounds=2, force=True))

        assert code == 1
        events = harvest_events(capsys)
        event_names = [e["event"] for e in events if "event" in e]
        assert "stalled" in event_names

        stalled = [e for e in events if e.get("event") == "stalled"]
        assert stalled[0]["remaining_critical"] > 0

        summary_files = list(state_dir.glob("summary.md"))
        assert len(summary_files) == 1, f"Expected summary.md in {state_dir}"
        assert "STALLED" in summary_files[0].read_text()


class TestEarlyStall:
    """BC-3: Finding counts don't decrease over stall window → early exit."""

    def test_stall_early_no_improvement(
        self, env_vars, artifact_file, state_dir, capsys, default_perspectives
    ):
        reviewer_resp = {
            p.id: make_reviewer_response(p.id, [{
                "severity": "IMPORTANT", "description": "Persists",
            }]) for p in default_perspectives
        }
        assessor = make_assessment_response(
            assessed_findings=[{
                "id": "F-1", "severity": "IMPORTANT",
                "original_severity": "IMPORTANT",
                "description": "Persists",
                "source_perspectives": ["DD-1"],
                "assessment_rationale": "Valid",
            }],
        )

        mock_client = MagicMock()
        mock_client.chat.completions.create = make_round_mock(
            reviewer_resp, assessor,
            reviewer_model=REVIEWER_MODEL, fixer_model=FIXER_MODEL,
        )

        def mock_apply_fixes(findings, artifact_path, sd, round_num, **kwargs):
            return FixResult(
                fixes_applied=[],
                fixes_skipped=[{"finding_id": "F-1", "severity": "IMPORTANT", "reason": "cannot fix"}],
            )

        with (
            patch("orchestrator.load_perspectives", return_value=default_perspectives),
            patch("orchestrator.load_artifact_content", return_value="test content"),
            patch("orchestrator.AsyncOpenAI", return_value=mock_client),
            patch("orchestrator.apply_fixes", side_effect=mock_apply_fixes),
        ):
            code = run_main(_make_argv(
                artifact_file, state_dir, max_rounds=10, stall_window=3,
            ))

        assert code == 1
        events = harvest_events(capsys)
        event_names = [e["event"] for e in events if "event" in e]
        assert "early_stall" in event_names

        # No round 4 events
        round_starts = [e for e in events if e.get("event") == "round_start"]
        max_round = max(e["round"] for e in round_starts)
        assert max_round <= 3
