---
name: _scaffold-experiment
description: Design experiment and generate run.sh, analyze script, and FINDINGS.md template
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - Bash(ls *)
  - Bash(chmod *)
  - Bash(mkdir *)
---

# Scaffold Experiment

Generate a complete experiment directory for a hypothesis. Each scaffolding runs in its own background agent dispatched by the orchestrator.

## Invocation

```
Skill(_scaffold-experiment "<project_root>" "<hypothesis_dir>" "<claim>" "<refuted_if>" "<language>" "<build_cmd>" "<entry_point>")
```

Arguments:
- `project_root` — absolute path to the target project root directory
- `hypothesis_dir` — absolute path to hypothesis directory (e.g., `<project_root>/hypotheses/h3-caching-latency`)
- `claim` — the testable hypothesis claim
- `refuted_if` — the falsifiability condition
- `language` — project language: `go`, `python`, `node`, or `other`
- `build_cmd` — project build command (e.g., `go build ./...`)
- `entry_point` — main binary or script path

## Step 1: Design the Experiment

Determine:

1. **Independent variable** — what changes between Config A and Config B
2. **Controlled variables** — what stays the same
3. **Dependent variable** — what you measure

**No approval gate here.** The orchestrator handles batch approval in Screen 7 after all experiments are scaffolded.

Use `[PROJECT_ROOT]` to locate the project source for context when designing the experiment. Write all generated files to `[HYPOTHESIS_DIR]`.

## Step 2: Generate `run.sh`

**All `run.sh` scripts must:**
- Start with `#!/usr/bin/env bash` and `set -euo pipefail`
- Comment block explaining the hypothesis
- Create `output/` subdirectory
- Run Config A → `output/config_a.txt`
- Run Config B → `output/config_b.txt`
- Print completion summary

Tailor commands to detected language:
- Go: `go build && ./binary [flags]`
- Python: `python3 [script] [args]`
- Node: `node [script] [args]`
- Other: generic shell with TODOs

After writing, `chmod +x run.sh`.

## Step 3: Generate `analyze.py`

Python script that:
1. Reads `output/config_a.txt` and `output/config_b.txt`
2. Parses metrics (auto-detect: JSON, CSV, key-value, raw text)
3. Computes comparison
4. Prints formatted summary table

Customize parsing logic based on expected output format.

## Step 4: Generate `FINDINGS.md` Template

Pre-fill hypothesis and experiment design sections. Leave Results and Analysis as `<!-- Auto-populated after experiment runs -->`. Include Reproducing section.

## Output

Return this structured text to the calling skill:

```
HYPOTHESIS_DIR: hypotheses/h<N>-<slug>
FILES_CREATED: run.sh, analyze.py, FINDINGS.md
DESIGN_SUMMARY: "Vary: <independent var>. Measure: <dependent var>. Control: <controlled vars>."
```

The orchestrator parses `DESIGN_SUMMARY` for Screen 7 (batch approval).
