---
name: _formulate-hypothesis
description: Formulate a single testable hypothesis by scanning the project for untested behaviors, gaps, and claims
user-invocable: false
allowed-tools:
  - Read
  - Glob
  - Grep
---

# Formulate Hypothesis

Generate a single testable, falsifiable hypothesis about the project.

## Invocation

```
Skill(_formulate-hypothesis "<project_root>" "<focus_area>" "<existing_claims>" "<language>" "<background_context>")
```

Arguments:
- `project_root` — absolute path to the target project root directory
- `focus_area` — `entire project`, `performance`, `correctness`, or a specific component name
- `existing_claims` — comma-separated list of already-generated claims (empty string if none)
- `language` — detected project language: `go`, `python`, `node`, or `other`
- `background_context` (optional) — background context gathered from repos, papers, and other sources. Empty string if none provided.

## Process

1. **Scan the project** (scoped to `[FOCUS_AREA]`, rooted at `[PROJECT_ROOT]`):
   - `Glob("[PROJECT_ROOT]/README*")` — read README for claimed behaviors
   - `Glob("[PROJECT_ROOT]/**/test*/**", "[PROJECT_ROOT]/**/*_test*", "[PROJECT_ROOT]/**/*test*.*")` — what IS tested (find gaps)
   - `Grep` source files under `[PROJECT_ROOT]` — complex logic, error paths, config options
   - Identify recently changed behavior from source
1b. **Review background context** (if `[BACKGROUND_CONTEXT]` is non-empty):
    - Read the provided background for domain knowledge, architectural patterns, and known issues
    - Use background insights to identify more targeted testable gaps
    - Cross-reference background claims with what the project actually implements
2. **Identify a testable gap**:
   - Performance claims with no benchmark
   - Edge cases in core logic (boundary values, empty inputs, error paths)
   - Config options whose effects are never validated
   - Recently changed behavior with no corresponding test
3. **Produce a testable claim** — one sentence naming:
   - The system/component under test
   - The specific behavior or metric
   - The expected outcome (with a number if possible)
4. **Add falsifiability** — "This is refuted if [opposite/null result]"
5. **Check against `[EXISTING_CLAIMS]`** — must be distinct

**Principle:** Generate the hypothesis WITHOUT reading implementation details. Test behavior, not implementation.

## Output

Return this structured text to the calling skill:

```
HYPOTHESIS: [testable claim]
REFUTED_IF: [falsifiability condition]
```
