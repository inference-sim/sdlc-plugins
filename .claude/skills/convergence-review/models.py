"""Data classes for the convergence review orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass
class GateConfig:
    """Configuration for a review gate type."""

    gate: str
    prompt_file: str
    prompt_section: str
    artifact_type: str  # "file", "git_diff", "directory"


GATE_CONFIGS: MappingProxyType[str, GateConfig] = MappingProxyType({
    "design": GateConfig("design", "design-prompts.md", "A", "file"),
    "g-design": GateConfig("g-design", "design-prompts.md", "C", "file"),
    "macro-plan": GateConfig("macro-plan", "design-prompts.md", "B", "file"),
    "x-macro-plan": GateConfig("x-macro-plan", "design-prompts.md", "D", "file"),
    "g-macro-plan": GateConfig("g-macro-plan", "design-prompts.md", "E", "file"),
    "pr-plan": GateConfig("pr-plan", "pr-prompts.md", "A", "file"),
    "x-pr-plan": GateConfig("x-pr-plan", "pr-prompts.md", "C", "file"),
    "pr-code": GateConfig("pr-code", "pr-prompts.md", "B", "git_diff"),
    "h-design": GateConfig(
        "h-design", "hypothesis-experiment/review-prompts.md", "A", "file"
    ),
    "h-code": GateConfig(
        "h-code", "hypothesis-experiment/review-prompts.md", "B", "directory"
    ),
    "h-findings": GateConfig(
        "h-findings", "hypothesis-experiment/review-prompts.md", "C", "file"
    ),
})


@dataclass
class Finding:
    """A single finding from a reviewer."""

    perspective: str
    severity: str  # "CRITICAL", "IMPORTANT", "SUGGESTION"
    description: str
    location: str | None = None
    evidence: str | None = None


@dataclass
class ReviewerOutput:
    """Output from a single reviewer perspective."""

    perspective: str
    findings: list[Finding] = field(default_factory=list)
    error: str | None = None
    parse_warning: str | None = None  # set when response was non-empty but unparseable
    elapsed_sec: float = 0.0


@dataclass
class AssessedFinding:
    """A finding after assessment (dedup, validation, re-prioritization)."""

    id: str  # "F-1", "F-2", etc.
    severity: str
    original_severity: str
    description: str
    source_perspectives: list[str] = field(default_factory=list)
    assessment_rationale: str = ""
    location: str | None = None
    evidence: str | None = None
    cross_round_status: str = "novel"  # novel, regression, recurring-fixed, recurring-skipped, recurring-escalate
    prior_finding_ref: str | None = None  # e.g. "F-R1-3" for traceability


@dataclass
class DismissedFinding:
    """A finding dismissed during assessment."""

    description: str
    source_perspectives: list[str] = field(default_factory=list)
    dismissal_reason: str = ""


@dataclass
class Assessment:
    """Result of the assessment phase."""

    assessed_findings: list[AssessedFinding] = field(default_factory=list)
    dismissed: list[DismissedFinding] = field(default_factory=list)
    uncovered_perspectives: list[str] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    fallback: bool = False  # True when assessment failed and raw findings passed through


@dataclass
class FixResult:
    """Result of the fix phase."""

    fixes_applied: list[dict] = field(default_factory=list)
    fixes_skipped: list[dict] = field(default_factory=list)
    error: str | None = None  # e.g. "timed out", "claude -p failed"


@dataclass
class RoundResult:
    """Result of a single convergence round."""

    round_num: int
    reviewer_outputs: list[ReviewerOutput] = field(default_factory=list)
    assessment: Assessment | None = None
    fix_result: FixResult | None = None
    status: str = "error"  # "converged", "fixed", "error"
    elapsed_sec: float = 0.0
