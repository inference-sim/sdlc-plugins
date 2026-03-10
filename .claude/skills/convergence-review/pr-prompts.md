# PR Review Perspective Prompts

Reference file for the convergence-review skill. Contains exact prompts for PR review perspectives across plan review, code review, and cross-system plan review gates.

**Canonical source:** `docs/contributing/pr-workflow.md`. If prompts here diverge from pr-workflow.md, the process doc is authoritative. Sections A and B use inference-sim perspectives (v3.0). Section C uses sim2real perspectives (v1.0).

**Dispatch pattern:** Launch each perspective as a parallel Task agent. **Do NOT paste the artifact content into the prompt** — this causes output generation to hang when dispatching 8+ agents in parallel. Instead, tell agents to read the file themselves:
```
Task(subagent_type="general-purpose", model=REVIEW_MODEL, run_in_background=True,
     prompt="<prompt from below with ARTIFACT_PATH substituted>")
```
Each prompt below uses `ARTIFACT_PATH` as a placeholder. The dispatcher must replace it with the actual file path before launching agents. For `pr-code` gate, agents should run `git diff` themselves instead of reading a file.

Model selection is controlled by the `--model` flag in the convergence-review skill (default: `haiku`).

---

## Section A: PR Plan Review (10 perspectives) — Step 2.5

### PP-1: Substance & Design

```
Review this implementation plan for substance: Are the behavioral contracts logically sound? Are there mathematical errors, scale mismatches, or unit confusions? Could the design actually achieve what the contracts promise? Check formulas, thresholds, and edge cases from first principles — not just structural completeness.

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### PP-2: Cross-Document Consistency

```
Does this micro plan's scope match the source document? Are file paths consistent with the actual codebase? Does the deviation log account for all differences between what the source says and what the micro plan does? Check for stale references to completed PRs or removed files.

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### PP-3: Architecture Boundary Verification

```
Does this plan maintain architectural boundaries? Check:
(1) Individual instances don't access cluster-level state
(2) Types are in the right packages (sim/ vs sim/cluster/ vs cmd/)
(3) No import cycles introduced
(4) Does the plan introduce multiple construction sites for the same type?
(5) Does adding one field to a new type require >3 files?
(6) Does library code (sim/) call logrus.Fatalf anywhere in new code?
(7) Dependency direction: cmd/ → sim/cluster/ → sim/ (never reversed)

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### PP-4: Codebase Readiness

```
We're about to implement this PR. Review the codebase for readiness. Check each file the plan will modify for:
- Stale comments ("planned for PR N" where N is completed)
- Pre-existing bugs that would complicate implementation
- Missing dependencies
- Unclear insertion points
- TODO/FIXME items in the modification zone

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### PP-5: Structural Validation (perform directly, no agent)

> **For Claude:** Perform these 4 checks directly. Do NOT dispatch an agent.

**Check 1 — Task Dependencies:**
For each task, verify it can actually start given what comes before it. Trace the dependency chain: what files does each task create/modify? Does any task require a file or type that hasn't been created yet?

**Check 2 — Template Completeness:**
Verify all sections from `docs/contributing/templates/micro-plan.md` are present and non-empty: Header, Part 1 (A-E), Part 2 (F-I), Part 3 (J), Appendix.

**Check 3 — Executive Summary Clarity:**
Read the executive summary as if you're a new team member. Is the scope clear without reading the rest?

**Check 4 — Under-specified Tasks:**
For each task, verify it has complete code. Flag any step an executing agent would need to figure out on its own.

### PP-6: DES Expert

```
Review this plan as a discrete-event simulation expert. Check for:
- Event ordering bugs in the proposed design
- Clock monotonicity violations (INV-3)
- Stale signal propagation between event types (INV-7)
- Heap priority errors (cluster uses (timestamp, priority, seqID))
- Event-driven race conditions
- Work-conserving property violations (INV-8)
- Incorrect assumptions about DES event processing semantics

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### PP-7: vLLM/SGLang Expert

```
Review this plan as a vLLM/SGLang inference serving expert. Check for:
- Batching semantics that don't match real continuous-batching servers
- KV cache eviction policies that differ from vLLM's implementation
- Chunked prefill behavior mismatches
- Preemption policy differences from vLLM
- Missing scheduling features that real servers have
- Flag any assumption about LLM serving that this plan gets wrong

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### PP-8: Distributed Inference Platform Expert

```
Review this plan as a distributed inference platform expert (llm-d, KServe, vLLM multi-node). Check for:
- Multi-instance coordination bugs
- Routing load imbalance under high request rates
- Stale snapshot propagation between instances
- Admission control edge cases at scale
- Horizontal scaling assumption violations
- Prefix-affinity routing correctness across instances

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### PP-9: Performance & Scalability

```
Review this plan as a performance and scalability analyst. Check for:
- Algorithmic complexity issues (O(n^2) where O(n) suffices)
- Unnecessary allocations in hot paths (event loop, batch formation)
- Map iteration in O(n) loops that could grow
- Benchmark-sensitive changes
- Memory growth patterns
- Changes that would degrade performance at 1000+ requests or 10+ instances

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### PP-10: Security & Robustness

```
Review this plan as a security and robustness reviewer. Check for:
- Input validation completeness (all CLI flags, YAML fields, config values)
- Panic paths reachable from user input (R3, R6)
- Resource exhaustion vectors (unbounded loops, unlimited memory growth) (R19)
- Degenerate input handling (empty, zero, negative, NaN, Inf) (R3, R20)
- Configuration injection risks
- Silent data loss paths (R1)

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

---

## Section B: PR Code Review (10 perspectives) — Step 4.5

### PC-1: Substance & Design

```
Review this diff for substance: Are there logic bugs, design mismatches between contracts and implementation, mathematical errors, or silent regressions? Check from first principles — not just structural patterns. Does the implementation actually achieve what the behavioral contracts promise?

First, run `git diff` using the Bash tool to see the current code changes. Then review them.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### PC-2: Code Quality + Antipattern Check

```
Review this diff for code quality. Check all of these:
(1) Any new error paths that use `continue` or early `return` — do they clean up partial state? (R1, R5)
(2) Any map iteration that accumulates floats — are keys sorted? (R2)
(3) Any struct field added — are all construction sites updated? (R4)
(4) Does library code (sim/) call logrus.Fatalf anywhere in new code? (R6)
(5) Any exported mutable maps — should they be unexported with IsValid*() accessors? (R8)
(6) Any YAML config fields using float64 instead of *float64 where zero is valid? (R9)
(7) Any division where the denominator derives from runtime state without a zero guard? (R11)
(8) Any new interface with methods only meaningful for one implementation? (R13)
(9) Any method >50 lines spanning multiple concerns (scheduling + latency + metrics)? (R14)
(10) Any changes to docs/contributing/standards/ files — are CLAUDE.md working copies updated? (DRY)

First, run `git diff` using the Bash tool to see the current code changes. Then review them.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### PC-3: Test Behavioral Quality

```
Review the tests in this diff. For each test, rate as Behavioral, Mixed, or Structural:
- Behavioral: tests observable behavior (GIVEN/WHEN/THEN), survives refactoring
- Mixed: some behavioral assertions, some structural coupling
- Structural: asserts internal structure (field access, type assertions), breaks on refactor

Also check:
- Are there golden dataset tests that lack companion invariant tests? (R7)
- Do tests verify laws (conservation, monotonicity, causality) not just values?
- Would each test still pass if the implementation were completely rewritten?

First, run `git diff` using the Bash tool to see the current code changes. Then review them.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### PC-4: Getting-Started Experience

```
Review this diff for user and contributor experience. Simulate both journeys:
(1) A user doing capacity planning with the CLI — would they find everything they need?
(2) A contributor adding a new algorithm — would they know how to extend this?

Check:
- Missing example files or CLI documentation
- Undocumented output metrics
- Incomplete contributor guide updates
- Unclear extension points
- README not updated for new features

First, run `git diff` using the Bash tool to see the current code changes. Then review them.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### PC-5: Automated Reviewer Simulation

```
The upstream community uses GitHub Copilot, Claude, and Codex to review PRs. Do a rigorous check so this will pass their review. Look for:
- Exported mutable globals
- User-controlled panic paths
- YAML typo acceptance (should use KnownFields(true))
- NaN/Inf validation gaps
- Redundant or dead code
- Style inconsistencies
- Missing error returns

First, run `git diff` using the Bash tool to see the current code changes. Then review them.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### PC-6: DES Expert

```
Review this diff as a discrete-event simulation expert. Check for:
- Event ordering bugs in the implementation
- Clock monotonicity violations (INV-3)
- Stale signal propagation between event types (INV-7)
- Heap priority errors
- Work-conserving property violations (INV-8)
- Event-driven race conditions

First, run `git diff` using the Bash tool to see the current code changes. Then review them.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### PC-7: vLLM/SGLang Expert

```
Review this diff as a vLLM/SGLang inference serving expert. Check for:
- Batching semantics that don't match real continuous-batching servers
- KV cache eviction mismatches with vLLM
- Chunked prefill behavior errors
- Preemption policy differences
- Missing scheduling features
- Flag any assumption about LLM serving that this code gets wrong

First, run `git diff` using the Bash tool to see the current code changes. Then review them.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### PC-8: Distributed Inference Platform Expert

```
Review this diff as a distributed inference platform expert (llm-d, KServe, vLLM multi-node). Check for:
- Multi-instance coordination bugs
- Routing load imbalance
- Stale snapshot propagation
- Admission control edge cases
- Horizontal scaling assumption violations
- Prefix-affinity routing correctness

First, run `git diff` using the Bash tool to see the current code changes. Then review them.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### PC-9: Performance & Scalability

```
Review this diff as a performance and scalability analyst. Check for:
- Algorithmic complexity regressions (O(n^2) where O(n) suffices)
- Unnecessary allocations in hot paths
- Map iteration in O(n) loops
- Benchmark-sensitive changes
- Memory growth patterns
- Changes degrading performance at 1000+ requests or 10+ instances

First, run `git diff` using the Bash tool to see the current code changes. Then review them.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### PC-10: Security & Robustness

```
Review this diff as a security and robustness reviewer. Check for:
- Input validation completeness (CLI flags, YAML fields, config values)
- Panic paths reachable from user input
- Resource exhaustion vectors (unbounded loops, unlimited memory growth)
- Degenerate input handling (empty, zero, NaN, Inf)
- Configuration injection risks
- Silent data loss in error paths

First, run `git diff` using the Bash tool to see the current code changes. Then review them.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

---

## Section C: Cross-System PR Plan Review (5 perspectives) — x-pr-plan

For sim2real cross-system transfer PRs. 5 perspectives aligned with `docs/contributing/pr-workflow.md` (v1.0). Not all perspectives are used for every PR category — see the pr-workflow's Perspective Assignment table.

**Canonical source:** `docs/contributing/pr-workflow.md` (v1.0). If prompts here diverge from pr-workflow.md, the process doc is authoritative.

### XPP-1: Cross-System Contract Integrity

```
Review this plan for cross-system contract integrity. Check:
(1) Do artifacts correctly describe the APIs in submodules? Read the actual submodule source files referenced in the plan and compare API signatures, types, and method names against what the plan documents.
(2) Are commit pins current? Run `git submodule status` and compare against any commit hashes referenced in the plan or mapping artifact.
(3) Do workspace artifact schemas chain correctly between stages? For each workspace artifact (algorithm_summary.json, signal_coverage.json, validation_results.json), verify that the fields written by the producing stage match the fields expected by consuming stages.
(4) Signal mapping accuracy: does each signal name in the mapping artifact match the actual field name in both the source system (inference-sim) and target system (llm-d-inference-scheduler)? Check for semantic drift, type mismatches (int vs float, absolute vs relative), unit mismatches (ms vs s), and temporal mismatches (point-in-time vs rolling average).
(5) Plugin interface compliance: do references to the target system's scorer interface, registration pattern, and config format match the actual code in the submodule?

First, read the plan file at ARTIFACT_PATH using the Read tool. Then read the relevant submodule source files to verify claims.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### XPP-2: Artifact Completeness & Consistency

```
Review this plan for artifact completeness and cross-artifact consistency. Check:
(1) Are all required sections present in each artifact the plan creates or modifies? (Mapping artifact: signal table, types, metric paths, staleness windows, fidelity ratings, commit pin. Scorer template: all 8 sections per design doc. Prompt templates: prerequisites, validation steps, halt conditions, expected outputs.)
(2) Do signal names match exactly across all artifacts? Grep for each signal name in the mapping artifact, JSON schemas, prompt templates, CLI code, and README. Any spelling or casing mismatch is a bug.
(3) Do field names match across workspace artifact schemas and the code that reads/writes them?
(4) Do file paths referenced in the plan exist or will be created by a preceding task? Flag any reference to a file that doesn't exist and isn't created by an earlier task.
(5) Is the deviation log current? If the plan deviates from the macro plan, is each deviation documented with rationale?
(6) Dead artifact check: is every file created by this plan consumed by a test, a later PR, or the pipeline runtime? If a file has no consumer, flag it.

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### XPP-3: Prompt Template Quality

```
Review this plan's prompt templates (or plans for prompt templates) for quality and completeness. Check:
(1) Does each prompt template specify prerequisites — which workspace artifacts must exist before this stage runs, and how to validate them (schema check + file existence)?
(2) Does each prompt template specify validation steps — how the operator or LLM verifies the stage's output before writing to workspace artifacts?
(3) Are halt conditions clear and unambiguous? For each condition that should stop the pipeline, is the trigger specific (not "if something looks wrong") and is the action explicit (exit code, error message, user decision options)?
(4) Are expected outputs fully specified — file names, JSON field names, format constraints?
(5) Does the prompt reference predecessor artifact checks? Each consuming stage should validate the predecessor artifact's schema before reading.
(6) Could the prompt cause LLM missteps? Look for ambiguous instructions, missing context, or steps where the LLM would need to guess. Each step should be self-contained enough that a capable LLM can execute it without external knowledge of the codebase.

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### XPP-4: Code Correctness (Python CLI + Go Harness)

```
Review this plan's code (Python CLI tools and Go test harness) for correctness. Check:
(1) Edge cases: empty input files, missing fields in JSON, zero-length signal lists, malformed YAML.
(2) Error handling: does every CLI command handle all three exit code paths (0 = success, 1 = validation failure, 2 = infrastructure error)? Are errors surfaced with actionable messages, not swallowed?
(3) JSON output contract: does each CLI command's actual JSON output match the schema documented in the macro plan's Component Model section? Check field names, types, and required vs optional.
(4) Go harness correctness: compilation against pinned submodule HEAD, test tuple handling, score comparison logic, timeout handling.
(5) Input validation: CLI argument parsing safety, path traversal prevention in file operations, subprocess invocation safety.
(6) Resource bounds: no unbounded file reads, no unlimited memory growth, no infinite retry loops without limits.

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### XPP-5: Plan Structural Validation (perform directly, no agent)

> **For Claude:** Perform these 5 checks directly. Do NOT dispatch an agent.

**Check 1 — Task Dependencies:**
For each task, verify it can actually start given what comes before it. Trace the dependency chain: what files does each task create/modify? Does any task require a file, type, or artifact that hasn't been created yet?

**Check 2 — Template Completeness:**
Verify all sections from `docs/contributing/templates/micro-plan-cross-system.md` are present and non-empty: Header, Part 1 (A-E), Part 2 (F-I), Part 3 (J), Appendix.

**Check 3 — Executive Summary Clarity:**
Read the executive summary as if you're a new team member unfamiliar with either codebase. Is the scope clear without reading the rest? Is the transfer direction obvious?

**Check 4 — Under-specified Tasks:**
For each task, verify it has complete code or complete artifact content. Flag any step an executing agent would need to figure out on its own, especially cross-system integration steps. Verify each task uses the correct variant (Code Task / Artifact Task / Prompt Template Task).

**Check 5 — Verification Gate Alignment:**
Does the plan's verification gate match the PR category from `docs/contributing/pr-workflow.md`? (Artifact → mapping validation + schema check. Pipeline Stage → pytest + go build + prompt check. Validation → pytest + go test + go build. Integration → end-to-end smoke test.)

---

## Section D: Cross-System PR Code Review (4 perspectives) — x-pr-code

For sim2real cross-system transfer PRs — post-implementation code/artifact review. 4 perspectives aligned with `docs/contributing/pr-workflow.md` (v1.0), minus plan structural validation (which only applies to plans, not diffs). Not all perspectives are used for every PR category — see the pr-workflow's Perspective Assignment table.

**Canonical source:** `docs/contributing/pr-workflow.md` (v1.0). If prompts here diverge from pr-workflow.md, the process doc is authoritative.

**Perspective assignment for code review by PR category:**

| Category | XPC-1 Contracts | XPC-2 Artifacts | XPC-3 Prompts | XPC-4 Code |
|----------|:---:|:---:|:---:|:---:|
| **Artifact** | X | X | | |
| **Pipeline Stage** | X | X | X | |
| **Validation** | X | X | X | X |
| **Integration** | X | X | X | X |

### XPC-1: Cross-System Contract Integrity

```
Review this diff for cross-system contract integrity. Check:
(1) Do any changes to artifacts (mapping docs, schemas, README) still correctly describe the APIs in submodules? Read the actual submodule source files and compare API signatures, types, and method names against what the changed artifacts document.
(2) Are commit pins still current? If the diff modifies files that reference submodule commit hashes, run `git submodule status` and verify they match.
(3) Do workspace artifact schema changes maintain the chain? If a schema field was added, renamed, or removed, verify that both the producing stage and all consuming stages are updated consistently.
(4) Signal mapping accuracy: if the diff touches signal names in any file (mapping artifact, schemas, CLI code, prompts), verify the name matches the actual field in both inference-sim and llm-d-inference-scheduler submodules.
(5) Plugin interface compliance: if the diff touches scorer template or generated code patterns, verify they still match the target system's actual interface.

First, run `git diff` using the Bash tool to see the current code changes. Then read relevant submodule source files to verify claims.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### XPC-2: Artifact Completeness & Consistency

```
Review this diff for artifact completeness and cross-artifact consistency. Check:
(1) If the diff adds or modifies an artifact, are all required sections present? (Mapping artifact: signal table, types, metric paths, staleness windows, fidelity ratings, commit pin. Scorer template: all 8 sections per design doc. Prompt templates: prerequisites, validation steps, halt conditions, expected outputs.)
(2) Do signal names match exactly across all files touched by this diff? Grep for each signal name in the mapping artifact, JSON schemas, prompt templates, CLI code, and README. Any spelling or casing mismatch is a bug.
(3) Do field names in changed JSON schemas match the code that reads/writes those fields?
(4) Do file paths referenced in changed documents actually exist in the repository?
(5) Dead artifact check: does this diff create any file that has no consumer (no test reads it, no later stage uses it, no pipeline runtime depends on it)?

First, run `git diff` using the Bash tool to see the current code changes.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### XPC-3: Prompt Template Quality

```
Review this diff's prompt templates for quality and completeness. Check:
(1) Does each new or modified prompt template specify prerequisites — which workspace artifacts must exist before this stage runs, and how to validate them (schema check + file existence)?
(2) Does each prompt specify validation steps — how the operator or LLM verifies the stage's output before writing to workspace artifacts?
(3) Are halt conditions clear and unambiguous? For each condition that should stop the pipeline, is the trigger specific (not "if something looks wrong") and is the action explicit (exit code, error message, user decision options)?
(4) Are expected outputs fully specified — file names, JSON field names, format constraints?
(5) Does the prompt reference predecessor artifact checks? Each consuming stage should validate the predecessor artifact's schema before reading.
(6) Could the prompt cause LLM missteps? Look for ambiguous instructions, missing context, or steps where the LLM would need to guess.

If this diff does not touch any prompt templates, report "No prompt templates in diff — 0 CRITICAL, 0 IMPORTANT" and stop.

First, run `git diff` using the Bash tool to see the current code changes.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### XPC-4: Code Correctness (Python CLI + Go Harness)

```
Review this diff's code (Python CLI tools and Go test harness) for correctness. Check:
(1) Edge cases: empty input files, missing fields in JSON, zero-length signal lists, malformed YAML.
(2) Error handling: does every CLI command handle all three exit code paths (0 = success, 1 = validation failure, 2 = infrastructure error)? Are errors surfaced with actionable messages, not swallowed?
(3) JSON output contract: does each CLI command's JSON output match the schema documented in the macro plan? Check field names, types, and required vs optional.
(4) Go harness correctness: compilation against pinned submodule HEAD, test tuple handling, score comparison logic, timeout handling.
(5) Input validation: CLI argument parsing safety, path traversal prevention in file operations, subprocess invocation safety.
(6) Resource bounds: no unbounded file reads, no unlimited memory growth, no infinite retry loops without limits.
(7) Test quality: do tests verify observable behavior (not internal structure)? Do tests cover the contracts claimed in the plan?

If this diff does not touch any Python or Go code, report "No code in diff — 0 CRITICAL, 0 IMPORTANT" and stop.

First, run `git diff` using the Bash tool to see the current code changes.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```
