"""BC-11, BC-15: Conditional fix and prompt delivery."""

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


class TestFixSkippedWhenClean:
    """BC-11: 0 CRITICAL + 0 IMPORTANT → no fix_start, round converges."""

    def test_fix_skipped_when_clean(
        self, env_vars, artifact_file, state_dir, capsys, default_perspectives
    ):
        reviewer_resp = {
            p.id: make_reviewer_response(p.id, [{
                "severity": "SUGGESTION", "description": "Minor style issue",
            }]) for p in default_perspectives
        }
        assessor = make_assessment_response(
            assessed_findings=[
                {
                    "id": "F-1", "severity": "SUGGESTION",
                    "original_severity": "SUGGESTION",
                    "description": "Style issue 1",
                    "source_perspectives": ["DD-1"],
                    "assessment_rationale": "Minor",
                },
                {
                    "id": "F-2", "severity": "SUGGESTION",
                    "original_severity": "SUGGESTION",
                    "description": "Style issue 2",
                    "source_perspectives": ["DD-2"],
                    "assessment_rationale": "Minor",
                },
            ],
        )

        mock_client = MagicMock()
        mock_client.chat.completions.create = make_round_mock(
            reviewer_resp, assessor,
            reviewer_model=REVIEWER_MODEL, fixer_model=FIXER_MODEL,
        )

        argv = [
            "design", str(artifact_file),
            "--reviewer-model", REVIEWER_MODEL,
            "--fixer-model", FIXER_MODEL,
            "--max-rounds", "1",
            "--state-dir", str(state_dir),
        ]

        with (
            patch("orchestrator.load_perspectives", return_value=default_perspectives),
            patch("orchestrator.load_artifact_content", return_value="test content"),
            patch("orchestrator.AsyncOpenAI", return_value=mock_client),
        ):
            code = run_main(argv)

        assert code == 0
        events = harvest_events(capsys)
        event_names = [e["event"] for e in events if "event" in e]

        assert "fix_start" not in event_names

        round_completes = [e for e in events if e.get("event") == "round_complete"]
        assert len(round_completes) == 1
        assert round_completes[0]["status"] == "converged"


class TestFixPromptViaStdin:
    """BC-15: apply_fixes passes prompt via stdin (not CLI arg)."""

    def test_fix_uses_stdin(self, work_dir):
        from models import AssessedFinding

        findings = [
            AssessedFinding(
                id="F-1", severity="CRITICAL", original_severity="CRITICAL",
                description="A" * 5000,
                source_perspectives=["DD-1"],
                assessment_rationale="Must fix",
            ),
        ]

        sd = work_dir / "state"
        sd.mkdir()

        captured_stdin = {}

        captured_communicate = {}

        def mock_popen(cmd, **kwargs):
            captured_stdin["cmd"] = cmd
            captured_stdin["stdin_pipe"] = kwargs.get("stdin")
            proc = MagicMock()

            def mock_communicate(input=None, timeout=None):
                captured_communicate["input"] = input
                return ('{"result": "done"}', "")

            proc.communicate = mock_communicate
            proc.returncode = 0
            proc.poll.return_value = 0
            return proc

        import subprocess
        with (
            patch("fixer.shutil.which", return_value="/usr/bin/claude"),
            patch("fixer.subprocess.Popen", side_effect=mock_popen),
        ):
            from fixer import apply_fixes
            apply_fixes(findings, "artifact.md", sd, 1, fixer_model=FIXER_MODEL)

        assert "-" in captured_stdin["cmd"]
        assert captured_stdin["stdin_pipe"] == subprocess.PIPE
        # Verify prompt content was actually passed via stdin
        assert captured_communicate.get("input") is not None
        assert len(captured_communicate["input"]) > 0
