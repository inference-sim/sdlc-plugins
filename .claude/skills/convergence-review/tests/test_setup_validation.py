"""BC-4: Setup validation errors exit with code 2, no round_start event."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from conftest import harvest_events
from helpers import FakePerspective, run_main


class TestSetupValidation:
    """BC-4: All setup/arg errors → exit 2, no round_start event emitted."""

    def test_invalid_gate(self, capsys):
        """Unrecognized gate name → argparse error → SystemExit(2)."""
        with pytest.raises(SystemExit) as exc_info:
            run_main(["bogus", "file.md"])
        assert exc_info.value.code == 2

    def test_missing_artifact_for_file_gate(self, env_vars, capsys):
        """File gate without artifact path → argparse error → SystemExit(2)."""
        with pytest.raises(SystemExit) as exc_info:
            run_main(["design"])
        assert exc_info.value.code == 2

    def test_missing_api_key(self, monkeypatch, work_dir, capsys):
        """No API key env vars → exit 2, error event mentions key."""
        artifact = work_dir / "artifact.md"
        artifact.write_text("# Test")

        monkeypatch.setenv("LITELLM_BASE_URL", "http://test.local/v1")
        monkeypatch.delenv("LITELLM_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with patch("orchestrator.load_perspectives", return_value=[FakePerspective("DD-1", "Arch")]):
            code = run_main(["design", str(artifact)])

        assert code == 2
        events = harvest_events(capsys)
        assert not any(e.get("event") == "round_start" for e in events)
        error_events = [e for e in events if e.get("event") == "error"]
        assert len(error_events) >= 1
        assert "key" in error_events[0]["message"].lower()

    def test_missing_base_url(self, monkeypatch, work_dir, capsys):
        """No base URL env vars → exit 2, error event mentions URL."""
        artifact = work_dir / "artifact.md"
        artifact.write_text("# Test")

        monkeypatch.delenv("LITELLM_BASE_URL", raising=False)
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        monkeypatch.setenv("LITELLM_API_KEY", "test-key")

        with patch("orchestrator.load_perspectives", return_value=[FakePerspective("DD-1", "Arch")]):
            code = run_main(["design", str(artifact)])

        assert code == 2
        events = harvest_events(capsys)
        assert not any(e.get("event") == "round_start" for e in events)
        error_events = [e for e in events if e.get("event") == "error"]
        assert len(error_events) >= 1
        assert "url" in error_events[0]["message"].lower()
