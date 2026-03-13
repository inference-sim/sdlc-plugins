"""Shared mock factories and helpers for convergence tests."""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

# Add skill directory to sys.path so tests can import orchestrator, models, etc.
SKILL_DIR = Path(__file__).resolve().parent.parent
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))


@dataclass
class FakePerspective:
    id: str
    name: str
    prompt: str = ""

    def __post_init__(self):
        if not self.prompt:
            self.prompt = f"[{self.id}] Review <paste artifact here> for issues."


def make_reviewer_response(perspective_id: str, findings: list[dict]) -> dict:
    return {"perspective": perspective_id, "findings": findings}


def make_assessment_response(
    assessed_findings: list[dict] | None = None,
    dismissed: list[dict] | None = None,
    uncovered: list[str] | None = None,
    summary: dict | None = None,
) -> dict:
    af = assessed_findings or []
    d = dismissed or []
    s = summary or {
        "critical": sum(1 for f in af if f.get("severity") == "CRITICAL"),
        "important": sum(1 for f in af if f.get("severity") == "IMPORTANT"),
        "suggestion": sum(1 for f in af if f.get("severity") == "SUGGESTION"),
        "dismissed": len(d),
        "deduplicated": 0,
    }
    return {
        "assessed_findings": af,
        "dismissed": d,
        "uncovered_perspectives": uncovered or [],
        "summary": s,
    }


def _make_chat_response(content: str) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def make_round_mock(
    reviewer_responses: dict[str, dict],
    assessor_response: dict,
    reviewer_model: str = "openai/test-reviewer",
    fixer_model: str = "openai/test-fixer",
):
    async def _side_effect(*, model, messages, temperature=0.0, **kwargs):
        if model == fixer_model:
            return _make_chat_response(json.dumps(assessor_response))
        if model == reviewer_model:
            user_msg = messages[-1]["content"] if messages else ""
            for pid, resp in reviewer_responses.items():
                if pid in user_msg:
                    return _make_chat_response(json.dumps(resp))
            raise ValueError(
                f"No reviewer response matched message content. "
                f"Expected one of {list(reviewer_responses.keys())} in message: {user_msg[:200]!r}"
            )
        raise ValueError(
            f"Unexpected model in mock: {model!r} "
            f"(expected {reviewer_model!r} or {fixer_model!r})"
        )

    return _side_effect


def make_error_side_effect(
    error_perspectives: set[str] | None = None,
    reviewer_responses: dict[str, dict] | None = None,
    assessor_response: dict | None = None,
    reviewer_model: str = "openai/test-reviewer",
    fixer_model: str = "openai/test-fixer",
):
    reviewer_responses = reviewer_responses or {}
    assessor_response = assessor_response or make_assessment_response()

    async def _side_effect(*, model, messages, temperature=0.0, **kwargs):
        if model == fixer_model:
            return _make_chat_response(json.dumps(assessor_response))
        if model == reviewer_model:
            user_msg = messages[-1]["content"] if messages else ""
            for pid in (error_perspectives or set()):
                if pid in user_msg:
                    raise Exception(f"Simulated failure for {pid}")
            for pid, resp in reviewer_responses.items():
                if pid in user_msg:
                    return _make_chat_response(json.dumps(resp))
            raise ValueError(
                f"No reviewer response matched message content. "
                f"Expected one of {list(reviewer_responses.keys())} or "
                f"error for {error_perspectives} in message: {user_msg[:200]!r}"
            )
        raise ValueError(
            f"Unexpected model in mock: {model!r} "
            f"(expected {reviewer_model!r} or {fixer_model!r})"
        )

    return _side_effect


def run_main(argv: list[str]) -> int:
    import orchestrator
    return asyncio.run(orchestrator.main(argv))
