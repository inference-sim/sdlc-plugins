---
name: convergence-review
description: Dispatch parallel review perspectives and enforce convergence (zero CRITICAL + zero IMPORTANT). Supports gate types — design doc (8), macro plan (8), PR plan (10), cross-system PR plan (5), PR code (10), cross-system PR code (4), hypothesis design (5), hypothesis code (5), hypothesis FINDINGS (10).
argument-hint: <gate-type> [artifact-path] [--reviewer-model X] [--fixer-model Y]
---

# Convergence Review Dispatcher

Dispatch parallel review perspectives for gate **$0** and enforce convergence.

## Gate Types

| Gate | Perspectives | Artifact | Prompts Source |
|------|-------------|----------|----------------|
| `design` | 8 | Design doc at `$1` | [design-prompts.md](design-prompts.md) Section A |
| `macro-plan` | 8 | Macro plan at `$1` | [design-prompts.md](design-prompts.md) Section B |
| `x-macro-plan` | 8 | Cross-system macro plan at `$1` | [design-prompts.md](design-prompts.md) Section D |
| `g-macro-plan` | 8 | Generalized macro plan at `$1` | [design-prompts.md](design-prompts.md) Section E |
| `pr-plan` | 10 | Micro plan at `$1` | [pr-prompts.md](pr-prompts.md) Section A |
| `x-pr-plan` | 5 | Cross-system micro plan at `$1` | [pr-prompts.md](pr-prompts.md) Section C |
| `pr-code` | 10 | Current git diff | [pr-prompts.md](pr-prompts.md) Section B |
| `x-pr-code` | 4 | Current git diff (cross-system) | [pr-prompts.md](pr-prompts.md) Section D |
| `h-design` | 5 | Design doc at `$1` | `hypothesis-experiment/review-prompts.md` Section A |
| `h-code` | 5 | `run.sh` + `analyze.py` at `$1` | `hypothesis-experiment/review-prompts.md` Section B |
| `h-findings` | 10 | FINDINGS.md at `$1` | `hypothesis-experiment/review-prompts.md` Section C |

---

## Instructions

### Step 1: Validate

1. Validate gate type `$0`. If not one of the gates above, report error and stop.
2. For all gates except `pr-code`: validate that `$1` exists (file or directory as appropriate).

### Step 2: Run Orchestrator

Run the Python orchestrator from this skill's directory:

```
python .claude/skills/convergence-review/orchestrator.py $0 $1 [flags]
```

**Available flags:**
- `--reviewer-model MODEL` — Model for parallel reviewers (default: haiku, resolved via model-aliases.json). Also: `CONVERGENCE_REVIEWER_MODEL` env var.
- `--fixer-model MODEL` — Model for assessment and fix phases (default: opus). Also: `CONVERGENCE_FIXER_MODEL` env var.
- `--max-rounds N` — Maximum convergence rounds (default: 10)
- `--base-url URL` — LiteLLM proxy endpoint (default: from `LITELLM_BASE_URL` or `ANTHROPIC_BASE_URL` env)
- `--state-dir PATH` — State directory (default: `.claude/convergence-state/<gate>-<path>`)
- `--log-level LEVEL` — DEBUG, INFO, WARNING, ERROR (default: WARNING)
- `--reviewer-timeout SECS` — Per-reviewer timeout (default: 300)
- `--assessor-timeout SECS` — Assessment phase timeout (default: 600)
- `--fixer-timeout SECS` — Fix phase (claude -p) timeout (default: 900)
- `--force` — Disable early stall detection (still limited by --max-rounds)
- `--stall-window N` — Rounds without improvement *and* no fixes applied before early exit (default: 5)
- `--human` — Human-readable one-line progress to stderr

**API key:** Sourced from environment only (not CLI) — checks `LITELLM_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY` in order.

### Step 3: Report Progress

Read stdout line by line. Each line is a JSON event. Report progress to the user:

| Event | What to report |
|-------|---------------|
| `summary_path` | **Report immediately**: "Review summary: `<path>`" — the user can check this file at any time for current progress. |
| `round_start` | "Round N/M: dispatching K reviewers..." |
| `reviewer_done` | (accumulate silently) |
| `reviewer_error` | "Warning: perspective XX-N timed out/failed" |
| `reviews_complete` | "N raw findings from K/M perspectives" |
| `assessment_complete` | "Assessment: X CRITICAL, Y IMPORTANT (Z dismissed, W deduped)" |
| `fix_start` | "Fixing N findings..." |
| `fixes_applied` | "Fixed: X CRITICAL, Y IMPORTANT (Z skipped)" |
| `round_complete` | "Round N complete: [status]" |
| `converged` | "CONVERGED in N rounds (Xs total)" |
| `early_stall` | "Warning: findings not decreasing over N rounds. Use --force to override." |
| `stalled` | "STALLED after N rounds: X CRITICAL, Y IMPORTANT remaining" |
| `assessment_fallback` | "Warning: assessment API failed, using raw findings (may contain duplicates)" |
| `interrupted` | "Review interrupted by user." |
| `error` | Report the error message |

**Example user-facing output:**
```
Round 1/10: 10 reviewers dispatched... 27 raw findings → assessment: 2 CRITICAL, 1 IMPORTANT (8 dismissed, 11 deduped) → fixing... 3 fixed
Round 2/10: 10 reviewers dispatched... 3 raw findings → assessment: 0 CRITICAL, 0 IMPORTANT → CONVERGED
```

### Step 4: Interpret Exit Code

| Code | Meaning | Action |
|------|---------|--------|
| **0** | Converged | Report success. Proceed to next workflow step. |
| **1** | Stalled (max rounds or early stall) | AskUserQuestion: "Convergence stalled. Options: increase round limit / use --force / accept current state / abort" |
| **2** | Setup error | Report the error message from the `error` event. |
| **130** | Interrupted | Report "Review interrupted by user." |

---

## Three-Phase Round Architecture

Each round executes three phases:

1. **REVIEW** — All perspectives dispatched as parallel async API calls (OpenAI-compatible via LiteLLM). Fast, cheap, any model.
2. **ASSESS** — Single API call to a strong model that deduplicates, validates, re-prioritizes, and dismisses findings. Convergence decided on assessed counts, not raw.
3. **FIX** — `claude -p` subprocess for sequential, context-aware file edits using only assessed CRITICAL + IMPORTANT findings.

The round loop is a deterministic Python `for` loop — structurally immune to LLM completion bias.

---

## Convergence Logic

Convergence is decided after the ASSESS phase of each round. The loop exits successfully when the count of **actionable** CRITICAL + IMPORTANT findings reaches zero.

### What counts as "actionable"

Not all assessed C+I findings block convergence. The assessor assigns each finding a `cross_round_status` based on a prior-round ledger, and two statuses are excluded from the actionable count:

| `cross_round_status` | Blocks convergence? | Meaning |
|---|---|---|
| `novel` | **Yes** | New finding not seen in prior rounds |
| `regression` | **Yes** | A prior fix introduced this new problem |
| `recurring-skipped` | **Yes** | Fixer skipped this before, but the assessor says the skip rationale was inadequate |
| `recurring-fixed` | **No** | Same theme as a prior finding that was already fixed — assessor cannot identify a specific deficiency in the fix |
| `recurring-escalate` | **No** | Same theme flagged in 3+ rounds — a persistent design trade-off, not a fixable defect |

### Cross-round ledger

From round 2 onward, the assessor receives a ledger of prior-round findings and their fix dispositions (fixed/skipped + rationale). This lets it distinguish genuinely new issues from recurring themes that have already been addressed or that represent inherent trade-offs.

- **Recent rounds** (last 3): full finding detail with fix actions
- **Older rounds**: one-line summary with counts only (to bound prompt length)

### Persistent themes

Findings classified as `recurring-escalate` are accumulated into a "Persistent Themes" section in the summary file. These represent design trade-offs the automated loop cannot resolve — they are surfaced for human review but do not block convergence.

### Stall detection

If `--force` is not set, the orchestrator monitors finding counts over a sliding window (`--stall-window`, default 5). If actionable C+I counts are not decreasing **and** no fixes are being applied across the window, the loop exits early with code 1. The `--force` flag disables this, running all rounds up to `--max-rounds`.

---

## Severity Classification

| Severity | Definition | Blocks? |
|----------|-----------|---------|
| **CRITICAL** | Must fix. Missing control, contradicted status, silent data loss, cross-document contradiction. | Yes |
| **IMPORTANT** | Should fix. Would reader be misled? Would conclusion change? | Yes |
| **SUGGESTION** | Cosmetic. Off-by-one citations, style, terminology. | No |

---

## Integration with Other Skills

### From design process
```
/convergence-review design docs/plans/archive/<design-doc>.md
```

### From macro planning process
```
/convergence-review macro-plan docs/plans/<macro-plan>.md
```

### From PR workflow (Steps 2.5 and 4.5)
```
/convergence-review pr-plan docs/plans/pr<N>-<name>-plan.md
/convergence-review x-pr-plan docs/plans/pr<N>-<name>-plan.md   # cross-system transfer plans
/convergence-review pr-code                                     # inference-sim code review
/convergence-review x-pr-code                                   # cross-system (sim2real) code review
```

### From hypothesis-experiment skill (Steps 2, 5, and 8)
```
/convergence-review h-design hypotheses/h-<name>/design.md
/convergence-review h-code hypotheses/h-<name>/
/convergence-review h-findings hypotheses/h-<name>/FINDINGS.md
```

---

## Summary File

The orchestrator writes a human-readable `<artifact-stem>-review.md` next to the artifact being reviewed (e.g., `docs/plans/roofline-design-review.md`). For `pr-code` (git diff) or directory artifacts, it falls back to the state directory. A copy is always kept in the state directory. The file is updated after each round — the user can check it at any time for current progress.

## State Directory

Runtime state is stored at `.claude/convergence-state/<gate>-<sanitized-path>/` (gitignored). Contains per-round reviewer outputs, assessments, fix prompts, progress files, and a copy of the summary file.

## Dependencies

- Python 3.11+
- `openai` pip package (async client)
- `claude` CLI (fix phase only)
- LiteLLM proxy endpoint (configurable)
