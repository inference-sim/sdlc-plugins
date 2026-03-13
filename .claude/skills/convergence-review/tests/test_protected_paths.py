"""Tests for protected paths feature across all phases."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from helpers import FakePerspective


# ---------------------------------------------------------------------------
# orchestrator: _check_protected_violations
# ---------------------------------------------------------------------------

class TestCheckProtectedViolations:
    """Unit tests for _check_protected_violations glob matching."""

    def test_no_matches_returns_empty(self):
        from orchestrator import _check_protected_violations

        fake_result = MagicMock(returncode=0, stdout="src/main.py\nREADME.md\n")
        with patch("orchestrator.subprocess.run", return_value=fake_result):
            violations = _check_protected_violations(["docs/contributing/**"])
        assert violations == []

    def test_exact_glob_match(self):
        from orchestrator import _check_protected_violations

        fake_result = MagicMock(
            returncode=0,
            stdout="src/main.py\ndocs/contributing/rules.md\nREADME.md\n",
        )
        with patch("orchestrator.subprocess.run", return_value=fake_result):
            violations = _check_protected_violations(["docs/contributing/**"])
        assert violations == ["docs/contributing/rules.md"]

    def test_multiple_patterns(self):
        from orchestrator import _check_protected_violations

        fake_result = MagicMock(
            returncode=0,
            stdout="src/main.py\ndocs/contributing/rules.md\nCONTRIBUTING.md\n",
        )
        with patch("orchestrator.subprocess.run", return_value=fake_result):
            violations = _check_protected_violations(
                ["docs/contributing/**", "CONTRIBUTING.md"]
            )
        assert set(violations) == {"docs/contributing/rules.md", "CONTRIBUTING.md"}

    def test_nested_path_match(self):
        from orchestrator import _check_protected_violations

        fake_result = MagicMock(
            returncode=0,
            stdout="docs/contributing/standards/rules.md\n",
        )
        with patch("orchestrator.subprocess.run", return_value=fake_result):
            violations = _check_protected_violations(["docs/contributing/**"])
        assert violations == ["docs/contributing/standards/rules.md"]

    def test_git_failure_returns_empty(self):
        from orchestrator import _check_protected_violations

        fake_result = MagicMock(returncode=1, stdout="")
        with patch("orchestrator.subprocess.run", return_value=fake_result):
            violations = _check_protected_violations(["docs/contributing/**"])
        assert violations == []

    def test_git_timeout_returns_empty(self):
        from orchestrator import _check_protected_violations

        with patch(
            "orchestrator.subprocess.run",
            side_effect=subprocess.TimeoutExpired("git", 30),
        ):
            violations = _check_protected_violations(["docs/contributing/**"])
        assert violations == []

    def test_os_error_returns_empty(self):
        from orchestrator import _check_protected_violations

        with patch(
            "orchestrator.subprocess.run",
            side_effect=OSError("git not found"),
        ):
            violations = _check_protected_violations(["docs/contributing/**"])
        assert violations == []

    def test_empty_diff_returns_empty(self):
        from orchestrator import _check_protected_violations

        fake_result = MagicMock(returncode=0, stdout="")
        with patch("orchestrator.subprocess.run", return_value=fake_result):
            violations = _check_protected_violations(["docs/contributing/**"])
        assert violations == []


# ---------------------------------------------------------------------------
# reviewer: protected-paths preamble in prompts
# ---------------------------------------------------------------------------

class TestReviewerProtectedPreamble:
    """Reviewer prompts include protected-file preamble when configured."""

    def test_preamble_with_paths(self):
        from reviewer import _build_protected_paths_preamble

        result = _build_protected_paths_preamble(["docs/contributing/**"])
        assert "Protected Reference Files" in result
        assert "`docs/contributing/**`" in result
        assert "ground truth" in result

    def test_preamble_empty_when_none(self):
        from reviewer import _build_protected_paths_preamble

        assert _build_protected_paths_preamble(None) == ""
        assert _build_protected_paths_preamble([]) == ""

    def test_preamble_multiple_patterns(self):
        from reviewer import _build_protected_paths_preamble

        result = _build_protected_paths_preamble(
            ["docs/contributing/**", "GOVERNANCE.md"]
        )
        assert "`docs/contributing/**`" in result
        assert "`GOVERNANCE.md`" in result

    def test_inject_artifact_includes_preamble(self):
        from reviewer import _inject_artifact

        prompt = "Review <paste artifact here> for issues."
        result = _inject_artifact(
            prompt,
            "artifact content",
            protected_paths=["docs/contributing/**"],
        )
        assert "Protected Reference Files" in result
        assert "`docs/contributing/**`" in result

    def test_inject_artifact_no_preamble_when_none(self):
        from reviewer import _inject_artifact

        prompt = "Review <paste artifact here> for issues."
        result = _inject_artifact(prompt, "artifact content", protected_paths=None)
        assert "Protected Reference Files" not in result


# ---------------------------------------------------------------------------
# assessor: protected paths in assessment input
# ---------------------------------------------------------------------------

class TestAssessorProtectedPaths:
    """Assessor dismisses findings targeting protected files."""

    def test_format_includes_protected_section(self):
        from assessor import _format_assessment_input
        from models import ReviewerOutput

        outputs = [
            ReviewerOutput(
                perspective="DD-1",
                findings=[],
            )
        ]
        result = _format_assessment_input(
            outputs,
            "artifact content",
            gate="design",
            protected_paths=["docs/contributing/**"],
        )
        assert "Protected Paths" in result
        assert "`docs/contributing/**`" in result
        assert "DISMISS" in result

    def test_format_no_protected_section_when_none(self):
        from assessor import _format_assessment_input
        from models import ReviewerOutput

        outputs = [
            ReviewerOutput(
                perspective="DD-1",
                findings=[],
            )
        ]
        result = _format_assessment_input(
            outputs, "artifact content", gate="design", protected_paths=None,
        )
        assert "Protected Paths" not in result

    def test_system_prompt_has_protected_files_rule(self):
        from assessor import ASSESSMENT_SYSTEM_PROMPT

        assert "PROTECTED FILES" in ASSESSMENT_SYSTEM_PROMPT
        assert "DISMISS" in ASSESSMENT_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# fixer: protected paths in fix prompt
# ---------------------------------------------------------------------------

class TestFixerProtectedPaths:
    """Fixer prompt includes protected paths section when configured."""

    def test_build_protected_section_with_paths(self):
        from fixer import _build_protected_section

        result = _build_protected_section(["docs/contributing/**"])
        assert "Protected Files (DO NOT MODIFY)" in result
        assert "`docs/contributing/**`" in result
        assert "read-only governance files" in result

    def test_build_protected_section_empty_when_none(self):
        from fixer import _build_protected_section

        assert _build_protected_section(None) == ""
        assert _build_protected_section([]) == ""

    def test_apply_fixes_includes_protected_section(self, tmp_path):
        from models import AssessedFinding

        findings = [
            AssessedFinding(
                id="F-1",
                severity="CRITICAL",
                original_severity="CRITICAL",
                description="Test finding",
                source_perspectives=["DD-1"],
                assessment_rationale="Must fix",
            ),
        ]

        sd = tmp_path / "state"
        sd.mkdir()

        captured_stdin = {}

        def mock_popen(cmd, **kwargs):
            proc = MagicMock()

            def mock_communicate(input=None, timeout=None):
                captured_stdin["input"] = input
                return ('{"result": "done"}', "")

            proc.communicate = mock_communicate
            proc.returncode = 0
            proc.poll.return_value = 0
            return proc

        with (
            patch("fixer.shutil.which", return_value="/usr/bin/claude"),
            patch("fixer.subprocess.Popen", side_effect=mock_popen),
        ):
            from fixer import apply_fixes

            apply_fixes(
                findings,
                "artifact.md",
                sd,
                1,
                protected_paths=["docs/contributing/**"],
            )

        prompt = captured_stdin["input"]
        assert "Protected Files (DO NOT MODIFY)" in prompt
        assert "`docs/contributing/**`" in prompt

    def test_apply_fixes_no_protected_section_without_paths(self, tmp_path):
        from models import AssessedFinding

        findings = [
            AssessedFinding(
                id="F-1",
                severity="CRITICAL",
                original_severity="CRITICAL",
                description="Test finding",
                source_perspectives=["DD-1"],
                assessment_rationale="Must fix",
            ),
        ]

        sd = tmp_path / "state"
        sd.mkdir()

        captured_stdin = {}

        def mock_popen(cmd, **kwargs):
            proc = MagicMock()

            def mock_communicate(input=None, timeout=None):
                captured_stdin["input"] = input
                return ('{"result": "done"}', "")

            proc.communicate = mock_communicate
            proc.returncode = 0
            proc.poll.return_value = 0
            return proc

        with (
            patch("fixer.shutil.which", return_value="/usr/bin/claude"),
            patch("fixer.subprocess.Popen", side_effect=mock_popen),
        ):
            from fixer import apply_fixes

            apply_fixes(findings, "artifact.md", sd, 1)

        prompt = captured_stdin["input"]
        assert "Protected Files (DO NOT MODIFY)" not in prompt
