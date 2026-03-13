"""Prompt loading and dynamic perspective discovery for convergence review."""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from models import GATE_CONFIGS, GateConfig

logger = logging.getLogger("convergence.prompts")

# Section letter to heading prefix mapping per gate
_SECTION_MAP: dict[str, dict[str, str]] = {
    "design-prompts.md": {"A": "DD", "B": "MP", "C": "GDD", "D": "CMP", "E": "GMP"},
    "pr-prompts.md": {"A": "PP", "B": "PC", "C": "XPP", "D": "XPC"},
    "hypothesis-experiment/review-prompts.md": {"A": "DR", "B": "CR", "C": "FR"},
}


@dataclass
class Perspective:
    """A single review perspective with its ID and prompt text."""

    id: str
    name: str
    prompt: str


def _find_skill_dir() -> Path:
    """Return this file's parent directory (the convergence-review skill dir)."""
    return Path(__file__).parent


def _extract_section_perspectives(
    content: str, section_letter: str, prompt_file: str
) -> list[Perspective]:
    """Extract perspectives from a specific section of a prompt markdown file.

    Parses ### XX-N: headings and extracts the fenced code block following each.
    """
    prefix = _SECTION_MAP.get(prompt_file, {}).get(section_letter)
    if prefix is None:
        raise ValueError(
            f"No heading prefix for section {section_letter} in {prompt_file}"
        )

    # Find section boundaries (## Section X: ...)
    section_pattern = rf"^## Section {re.escape(section_letter)}:.*$"
    section_match = re.search(section_pattern, content, re.MULTILINE)
    if not section_match:
        raise ValueError(f"Section {section_letter} not found in {prompt_file}")

    section_start = section_match.end()

    # Find next section (## Section ...) or end of file
    next_section = re.search(r"^## Section [A-Z]:", content[section_start:], re.MULTILINE)
    section_end = section_start + next_section.start() if next_section else len(content)
    section_text = content[section_start:section_end]

    # Parse ### XX-N: headings and their code blocks
    heading_pattern = rf"^### ({re.escape(prefix)}-\d+):\s*(.+)$"
    headings = list(re.finditer(heading_pattern, section_text, re.MULTILINE))

    perspectives = []
    for i, match in enumerate(headings):
        perspective_id = match.group(1)
        perspective_name = match.group(2).strip()

        # Extract text between this heading and the next (or section end)
        start = match.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(section_text)
        block_text = section_text[start:end]

        # Extract fenced code block content
        code_match = re.search(r"```\n(.*?)```", block_text, re.DOTALL)
        if code_match:
            prompt_text = code_match.group(1).strip()
        else:
            logger.warning(
                "No code block found for %s in %s", perspective_id, prompt_file
            )
            prompt_text = block_text.strip()

        perspectives.append(Perspective(perspective_id, perspective_name, prompt_text))

    logger.info(
        "Loaded %d perspectives from %s section %s",
        len(perspectives),
        prompt_file,
        section_letter,
    )
    return perspectives


def load_perspectives(gate: str) -> list[Perspective]:
    """Load all review perspectives for a gate type.

    Dynamically discovers perspectives by parsing ### XX-N: headings
    from the gate's prompt file section.
    """
    if gate not in GATE_CONFIGS:
        raise ValueError(
            f"Unknown gate '{gate}'. Valid gates: {', '.join(sorted(GATE_CONFIGS))}"
        )

    config = GATE_CONFIGS[gate]
    skill_dir = _find_skill_dir()
    prompt_path = skill_dir / config.prompt_file

    # If not found relative to convergence-review/, try relative to .claude/skills/
    if not prompt_path.exists():
        skills_root = skill_dir.parent
        prompt_path = skills_root / config.prompt_file

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    content = prompt_path.read_text()
    return _extract_section_perspectives(content, config.prompt_section, config.prompt_file)


def load_artifact_content(gate: str, artifact_path: str | None) -> str:
    """Load artifact content based on gate type.

    Returns the text content to be reviewed.
    """
    config = GATE_CONFIGS[gate]

    if config.artifact_type == "git_diff":
        # Use git diff HEAD to capture both staged and unstaged changes
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
        except FileNotFoundError:
            raise RuntimeError("git is not installed or not in PATH") from None
        if result.returncode != 0:
            raise RuntimeError(f"git diff failed: {result.stderr}")
        content = result.stdout.strip()
        if not content:
            raise ValueError("git diff is empty — nothing to review")
        return content

    if artifact_path is None:
        raise ValueError(f"Gate '{gate}' requires an artifact path")

    path = Path(artifact_path)

    if config.artifact_type == "file":
        if not path.exists():
            raise FileNotFoundError(f"Artifact not found: {path}")
        return path.read_text()

    if config.artifact_type == "directory":
        # h-code: concatenate run.sh + analyze.py from artifact directory
        parts = []
        for filename in ("run.sh", "analyze.py"):
            file_path = path / filename
            if file_path.exists():
                parts.append(f"=== {filename} ===\n{file_path.read_text()}")
            else:
                logger.warning("Expected file not found: %s", file_path)
        if not parts:
            raise FileNotFoundError(
                f"No run.sh or analyze.py found in {path}"
            )
        return "\n\n".join(parts)

    raise ValueError(f"Unknown artifact type: {config.artifact_type}")


def get_gate_config(gate: str) -> GateConfig:
    """Get gate configuration, raising ValueError for unknown gates."""
    if gate not in GATE_CONFIGS:
        raise ValueError(
            f"Unknown gate '{gate}'. Valid gates: {', '.join(sorted(GATE_CONFIGS))}"
        )
    return GATE_CONFIGS[gate]
