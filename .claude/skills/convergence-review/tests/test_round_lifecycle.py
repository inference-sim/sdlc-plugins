"""BC-12, BC-13, BC-14: Artifact reload, summary incremental write, state isolation."""

from __future__ import annotations

import json
from pathlib import Path
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


class TestArtifactReloadAfterFix:
    """BC-12: Artifact is reloaded after a fix round (not cached)."""

    def test_artifact_reload_after_fix(
        self, env_vars, artifact_file, state_dir, capsys, default_perspectives
    ):
        load_calls = []

        def mock_load(gate, path):
            load_calls.append(len(load_calls) + 1)
            return f"content v{len(load_calls)}"

        round_counter = {"n": 0}

        async def side_effect(*, model, messages, temperature=0.0, **kwargs):
            if model == FIXER_MODEL:
                if round_counter["n"] == 1:
                    resp = make_assessment_response(
                        assessed_findings=[{
                            "id": "F-1", "severity": "CRITICAL",
                            "original_severity": "CRITICAL",
                            "description": "Bug", "source_perspectives": ["DD-1"],
                            "assessment_rationale": "Real",
                        }],
                    )
                else:
                    resp = make_assessment_response()
                return _make_chat_response(json.dumps(resp))

            if round_counter["n"] == 1:
                resp = make_reviewer_response("DD-1", [{
                    "severity": "CRITICAL", "description": "Bug",
                }])
            else:
                resp = make_reviewer_response("DD-1", [])
            return _make_chat_response(json.dumps(resp))

        import orchestrator as orch_mod
        original_run_round = orch_mod.run_round

        async def tracking_run_round(client, args, round_num, *a, **kw):
            round_counter["n"] = round_num
            return await original_run_round(client, args, round_num, *a, **kw)

        mock_client = MagicMock()
        mock_client.chat.completions.create = side_effect

        def mock_apply_fixes(findings, artifact_path, sd, round_num, **kwargs):
            return FixResult(
                fixes_applied=[{"finding_id": "F-1", "severity": "CRITICAL", "action": "fixed"}],
            )

        with (
            patch("orchestrator.load_perspectives", return_value=default_perspectives),
            patch("orchestrator.load_artifact_content", side_effect=mock_load),
            patch("orchestrator.AsyncOpenAI", return_value=mock_client),
            patch("orchestrator.apply_fixes", side_effect=mock_apply_fixes),
            patch("orchestrator.run_round", side_effect=tracking_run_round),
        ):
            code = run_main([
                "design", str(artifact_file),
                "--reviewer-model", REVIEWER_MODEL,
                "--fixer-model", FIXER_MODEL,
                "--max-rounds", "5",
                "--state-dir", str(state_dir),
            ])

        assert code == 0
        assert len(load_calls) >= 2


class TestSummaryIncremental:
    """BC-13: Summary file updated incrementally (review+assessment before fix)."""

    def test_summary_written_before_fix(
        self, env_vars, artifact_file, state_dir, capsys, default_perspectives
    ):
        summary_content_during_fix = {}

        reviewer_resp = {
            p.id: make_reviewer_response(p.id, [{
                "severity": "CRITICAL", "description": "Must fix issue",
            }]) for p in default_perspectives
        }
        assessor = make_assessment_response(
            assessed_findings=[{
                "id": "F-1", "severity": "CRITICAL",
                "original_severity": "CRITICAL",
                "description": "Must fix issue",
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
            # Read summary file during fix phase
            # Check both state dir copy and artifact-adjacent
            for candidate in [
                sd / "summary.md",
                artifact_file.parent / f"{artifact_file.stem}-review.md",
            ]:
                if candidate.exists():
                    summary_content_during_fix["text"] = candidate.read_text()
                    break
            return FixResult(
                fixes_applied=[{"finding_id": "F-1", "severity": "CRITICAL", "action": "fixed"}],
            )

        with (
            patch("orchestrator.load_perspectives", return_value=default_perspectives),
            patch("orchestrator.load_artifact_content", return_value="test content"),
            patch("orchestrator.AsyncOpenAI", return_value=mock_client),
            patch("orchestrator.apply_fixes", side_effect=mock_apply_fixes),
        ):
            run_main([
                "design", str(artifact_file),
                "--reviewer-model", REVIEWER_MODEL,
                "--fixer-model", FIXER_MODEL,
                "--max-rounds", "1",
                "--state-dir", str(state_dir),
                "--force",
            ])

        assert "text" in summary_content_during_fix
        text = summary_content_during_fix["text"]
        assert "Round" in text
        assert "Assessment" in text or "CRITICAL" in text


class TestStateIsolation:
    """BC-14: Old state dir is cleaned before a new run."""

    def test_state_isolation(
        self, env_vars, artifact_file, state_dir, capsys, default_perspectives
    ):
        state_dir.mkdir(parents=True)

        leftover1 = state_dir / "assessment-round-1.json"
        leftover1.write_text('{"old": true}')
        leftover2 = state_dir / "old-progress.json"
        leftover2.write_text('{"stale": true}')

        reviewer_resp = {
            p.id: make_reviewer_response(p.id, []) for p in default_perspectives
        }
        assessor = make_assessment_response()

        mock_client = MagicMock()
        mock_client.chat.completions.create = make_round_mock(
            reviewer_resp, assessor,
            reviewer_model=REVIEWER_MODEL, fixer_model=FIXER_MODEL,
        )

        with (
            patch("orchestrator.load_perspectives", return_value=default_perspectives),
            patch("orchestrator.load_artifact_content", return_value="test content"),
            patch("orchestrator.AsyncOpenAI", return_value=mock_client),
        ):
            code = run_main([
                "design", str(artifact_file),
                "--reviewer-model", REVIEWER_MODEL,
                "--fixer-model", FIXER_MODEL,
                "--max-rounds", "1",
                "--state-dir", str(state_dir),
            ])

        assert code == 0
        assert not leftover2.exists(), "Leftover files should be cleaned by rmtree"

        new_files = list(state_dir.iterdir())
        assert len(new_files) > 0

        # assessment-round-1.json may be recreated by the new run, but must not have old content
        if leftover1.exists():
            data = json.loads(leftover1.read_text())
            assert "old" not in data, "State dir should be fully cleaned before new run"
        # The key invariant: old-progress.json (not recreated by the new run) must be gone
        assert not (state_dir / "old-progress.json").exists()
