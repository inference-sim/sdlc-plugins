---
name: _document-findings
description: Populate FINDINGS.md with results and analysis, update HYPOTHESIS.md status
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# Document Findings

Populate FINDINGS.md with experiment results and analysis. Called by background agents.

## Invocation

```
Skill(_document-findings "<hypothesis_dir>" "<verdict>" "<summary>" "<metrics_table>" "<analysis_output>")
```

Arguments:
- `hypothesis_dir` — path to hypothesis directory (e.g., `hypotheses/h3-caching-latency`)
- `verdict` — `Confirmed`, `Refuted`, `Inconclusive`, or `Failed`
- `summary` — 2-3 sentence interpretation
- `metrics_table` — formatted comparison table
- `analysis_output` — raw output from analyze script

## Step 1: Populate FINDINGS.md

Read the existing `FINDINGS.md` template in the hypothesis directory. Update:

- **Status**: Replace `Pending` with verdict
- **Date**: Set to today
- **Results section**: Replace `<!-- Auto-populated -->` with metrics comparison table (formatted as markdown table), per-configuration output summaries, key numbers highlighted
- **Analysis section**: Replace `<!-- Auto-populated -->` with verdict, reasoning, effect size, surprises. Use `Grep` and `Read` to trace mechanisms in source code — include `file:line` citations explaining WHY the result occurred.

## Step 2: Update HYPOTHESIS.md Status

Edit `HYPOTHESIS.md` in the same directory:
- Replace `**Status**: Pending` with `**Status**: <verdict>`

**Do NOT update `hypotheses/README.md`.** The orchestrator handles catalog updates after all agents complete to prevent race conditions in parallel mode.

## Output

Return this structured text to the calling skill:

```
FINDINGS_PATH: hypotheses/h<N>-<slug>/FINDINGS.md
VERDICT: <Confirmed|Refuted|Inconclusive|Failed>
```
