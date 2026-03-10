"""Shared pytest fixtures for convergence tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure skill dir is on sys.path (also done in helpers.py but needed early)
SKILL_DIR = Path(__file__).resolve().parent.parent
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

# Ensure tests dir is on sys.path so `import helpers` works
TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from helpers import FakePerspective


@pytest.fixture
def env_vars(monkeypatch):
    """Set required env vars for the orchestrator."""
    monkeypatch.setenv("LITELLM_BASE_URL", "http://test.local/v1")
    monkeypatch.setenv("LITELLM_API_KEY", "test-key-123")


@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    """Change cwd to tmp_path so state_dir is always under cwd."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def artifact_file(work_dir):
    """Write a dummy artifact .md file under work_dir and return its path."""
    p = work_dir / "artifact.md"
    p.write_text("# Test Artifact\n\nThis is a test document for review.\n")
    return p


@pytest.fixture
def state_dir(work_dir):
    """Return a state dir path under work_dir (not pre-created)."""
    return work_dir / ".claude" / "convergence-state" / "test"


def harvest_events(capsys) -> list[dict]:
    """Parse all JSON event lines from captured stdout.

    Fails if any non-empty line is not valid JSON — prevents silent event loss.
    """
    out = capsys.readouterr().out
    events = []
    bad_lines = []
    for line in out.strip().splitlines():
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                bad_lines.append(line)
    assert not bad_lines, f"Unparseable JSON lines in stdout: {bad_lines}"
    return events


@pytest.fixture
def default_perspectives():
    """Return a list of 3 fake perspectives for testing."""
    return [
        FakePerspective("DD-1", "Architecture"),
        FakePerspective("DD-2", "Invariants"),
        FakePerspective("DD-3", "Extension"),
    ]
