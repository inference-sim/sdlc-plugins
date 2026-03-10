"""BC-8, BC-9, BC-10: Round event ordering and failure tolerance."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from conftest import harvest_events
from helpers import (
    make_assessment_response,
    make_error_side_effect,
    make_reviewer_response,
    make_round_mock,
    run_main,
)

REVIEWER_MODEL = "openai/test-reviewer"
FIXER_MODEL = "openai/test-fixer"


def _base_argv(artifact_path, state_dir):
    return [
        "design", str(artifact_path),
        "--reviewer-model", REVIEWER_MODEL,
        "--fixer-model", FIXER_MODEL,
        "--max-rounds", "1",
        "--state-dir", str(state_dir),
    ]


class TestEventOrdering:
    """BC-8: Events within a round occur in deterministic order."""

    def test_single_round_event_order(
        self, env_vars, artifact_file, state_dir, capsys, default_perspectives
    ):
        reviewer_responses = {
            p.id: make_reviewer_response(p.id, []) for p in default_perspectives
        }
        assessor = make_assessment_response()

        mock_client = MagicMock()
        mock_client.chat.completions.create = make_round_mock(
            reviewer_responses, assessor,
            reviewer_model=REVIEWER_MODEL, fixer_model=FIXER_MODEL,
        )

        with (
            patch("orchestrator.load_perspectives", return_value=default_perspectives),
            patch("orchestrator.load_artifact_content", return_value="test content"),
            patch("orchestrator.AsyncOpenAI", return_value=mock_client),
        ):
            code = run_main(_base_argv(artifact_file, state_dir))

        assert code == 0
        events = harvest_events(capsys)
        event_names = [e["event"] for e in events if "event" in e]

        for required in ["round_start", "reviews_complete", "assessment_complete", "round_complete"]:
            assert event_names.count(required) == 1, f"Expected 1 '{required}', got {event_names.count(required)}"

        ordered = ["round_start", "reviews_complete", "assessment_complete", "round_complete"]
        indices = [event_names.index(e) for e in ordered]
        assert indices == sorted(indices), f"Events out of order: {list(zip(ordered, indices))}"

        assert "converged" in event_names


class TestPartialReviewerFailure:
    """BC-9: Partial reviewer failure doesn't kill the round."""

    def test_one_of_three_fails(
        self, env_vars, artifact_file, state_dir, capsys, default_perspectives
    ):
        good_responses = {
            "DD-2": make_reviewer_response("DD-2", []),
            "DD-3": make_reviewer_response("DD-3", []),
        }
        assessor = make_assessment_response()

        mock_client = MagicMock()
        mock_client.chat.completions.create = make_error_side_effect(
            error_perspectives={"DD-1"},
            reviewer_responses=good_responses,
            assessor_response=assessor,
            reviewer_model=REVIEWER_MODEL,
            fixer_model=FIXER_MODEL,
        )

        with (
            patch("orchestrator.load_perspectives", return_value=default_perspectives),
            patch("orchestrator.load_artifact_content", return_value="test content"),
            patch("orchestrator.AsyncOpenAI", return_value=mock_client),
        ):
            code = run_main(_base_argv(artifact_file, state_dir))

        assert code == 0
        events = harvest_events(capsys)

        reviews_complete = [e for e in events if e.get("event") == "reviews_complete"]
        assert len(reviews_complete) == 1
        rc = reviews_complete[0]
        assert rc["perspectives_failed"] >= 1
        assert rc["perspectives_ok"] >= 1

        assert any(e.get("event") == "assessment_complete" for e in events)


class TestTotalReviewerFailure:
    """BC-10: All reviewers fail → round status=error, no fix_start."""

    def test_all_fail_gives_error(
        self, env_vars, artifact_file, state_dir, capsys, default_perspectives
    ):
        all_ids = {p.id for p in default_perspectives}
        assessor = make_assessment_response()

        mock_client = MagicMock()
        mock_client.chat.completions.create = make_error_side_effect(
            error_perspectives=all_ids,
            reviewer_responses={},
            assessor_response=assessor,
            reviewer_model=REVIEWER_MODEL,
            fixer_model=FIXER_MODEL,
        )

        with (
            patch("orchestrator.load_perspectives", return_value=default_perspectives),
            patch("orchestrator.load_artifact_content", return_value="test content"),
            patch("orchestrator.AsyncOpenAI", return_value=mock_client),
        ):
            code = run_main(_base_argv(artifact_file, state_dir))

        assert code == 2
        events = harvest_events(capsys)

        round_completes = [e for e in events if e.get("event") == "round_complete"]
        assert len(round_completes) == 1
        assert round_completes[0]["status"] == "error"

        assert not any(e.get("event") == "fix_start" for e in events)
