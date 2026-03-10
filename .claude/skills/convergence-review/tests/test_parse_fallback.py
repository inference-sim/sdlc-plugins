"""Tests for reviewer parse fallback extraction."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from reviewer import (
    _extract_findings_fallback,
    _fix_json_escapes,
    _parse_reviewer_response,
    run_reviewer,
)
from helpers import FakePerspective


def _make_async_chat_response(content: str) -> MagicMock:
    """Build a mock that looks like an AsyncOpenAI chat completion response."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]

    async def _create(**kwargs):
        return resp

    client = MagicMock()
    client.chat.completions.create = _create
    return client


class TestFixJsonEscapes:
    """Test the sentinel-based JSON escape fixer."""

    def test_valid_json_unchanged(self):
        raw = '{"findings": [{"severity": "CRITICAL", "description": "test"}]}'
        assert json.loads(_fix_json_escapes(raw)) == json.loads(raw)

    def test_fixes_bare_backslash_w(self):
        # \w is invalid JSON escape
        raw = r'{"evidence": "matches \w+ pattern"}'
        fixed = _fix_json_escapes(raw)
        data = json.loads(fixed)
        assert "\\w+" in data["evidence"]

    def test_preserves_already_escaped(self):
        # \\w should stay as \\w (literal backslash + w)
        raw = '{"evidence": "matches \\\\w+ pattern"}'
        fixed = _fix_json_escapes(raw)
        data = json.loads(fixed)
        assert "\\w+" in data["evidence"]

    def test_mixed_escapes(self):
        # Mix of valid \\w and invalid \d in the same string
        raw = r'{"evidence": "\\w and \d patterns"}'
        fixed = _fix_json_escapes(raw)
        data = json.loads(fixed)
        assert "\\w" in data["evidence"]
        assert "\\d" in data["evidence"]


class TestFallbackExtraction:
    """Test the LLM fallback extraction for unparseable responses."""

    def test_fallback_recovers_findings(self):
        unparseable = "Here are my findings:\n1. [CRITICAL] Something is wrong\nBut this text has weird formatting..."
        extraction_json = json.dumps({
            "findings": [
                {"severity": "CRITICAL", "description": "Something is wrong"}
            ]
        })
        client = _make_async_chat_response(extraction_json)

        findings = asyncio.run(
            _extract_findings_fallback(client, "test-model", "XPP-1", unparseable, 60.0)
        )
        assert findings is not None
        assert len(findings) == 1
        assert findings[0].severity == "CRITICAL"

    def test_fallback_returns_none_on_failure(self):
        """Fallback returns None if extraction also fails to parse."""
        client = _make_async_chat_response("I couldn't parse that either")

        findings = asyncio.run(
            _extract_findings_fallback(client, "test-model", "XPP-1", "junk", 60.0)
        )
        assert findings is None


class TestRunReviewerFallback:
    """Integration: run_reviewer invokes fallback when primary parsing fails."""

    def test_fallback_invoked_on_parse_failure(self):
        """Non-empty unparseable response triggers fallback extraction."""
        # First call: reviewer returns unparseable text
        # Second call: fallback extraction returns valid JSON
        unparseable_response = "A" * 100  # 100 chars, no findings pattern
        extraction_json = json.dumps({
            "findings": [
                {"severity": "IMPORTANT", "description": "Recovered finding"}
            ]
        })

        call_count = {"n": 0}

        async def mock_create(*, model, messages, temperature=0.0, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                content = unparseable_response
            else:
                content = extraction_json
            msg = MagicMock()
            msg.content = content
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            return resp

        client = MagicMock()
        client.chat.completions.create = mock_create

        perspective = FakePerspective("XPP-1", "Test")
        result = asyncio.run(
            run_reviewer(client, "test-model", perspective, "artifact text", 60.0, 1)
        )

        assert call_count["n"] == 2  # reviewer + fallback
        assert len(result.findings) == 1
        assert result.findings[0].severity == "IMPORTANT"
        assert result.parse_warning is None  # fallback succeeded, no warning
