---
name: _run-and-analyze
description: Execute experiment run.sh, run analysis script, parse output, and interpret results
user-invocable: false
allowed-tools:
  - Bash(./hypotheses/*)
  - Bash(cd * && ./run.sh)
  - Bash(python3 *)
  - Bash(node *)
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# Run and Analyze Experiment

Execute the experiment and produce interpreted results.

## Invocation

```
Skill(_run-and-analyze "<hypothesis_dir>" "<claim>")
```

Arguments:
- `hypothesis_dir` — path to hypothesis directory (e.g., `hypotheses/h3-caching-latency`)
- `claim` — the original hypothesis claim (used for interpretation context)

## Step 1: Run the Experiment

```
Bash: cd <hypothesis_dir> && ./run.sh
```

Use a 5-minute timeout.

### Handling Failures

If `run.sh` fails:
1. Read the error output — identify the problem
2. Auto-fix if possible (build errors, bad flags, import errors) by editing `run.sh`
3. Re-run. Max 3 retry attempts.
4. If still failing, report error and stop with `VERDICT: Failed`.

## Step 2: Verify Output Files

Check `<hypothesis_dir>/output/` for `config_a.txt` and `config_b.txt`. If missing or empty, report and stop.

## Step 3: Run Analysis Script

```
Bash: cd <hypothesis_dir> && python3 analyze.py
```

Auto-fix parsing issues if needed (max 3 attempts). Capture analysis output.

## Step 4: Parse and Compare

Read output files, extract metrics, build comparison table:
- Metric name, Config A value, Config B value, delta, percent change

## Step 5: Interpret

- **Confirmed**: Dependent variable moved in predicted direction by meaningful amount
- **Refuted**: Did NOT move as predicted, or opposite direction
- **Inconclusive**: Mixed results, tiny effect, questionable data

Explain in 2-3 sentences.

## Output

Return this structured text to the calling skill:

```
VERDICT: [Confirmed|Refuted|Inconclusive|Failed]
SUMMARY: [2-3 sentence interpretation]
METRICS_TABLE: [formatted comparison table]
ANALYSIS_OUTPUT: [raw output from analyze script]
```
