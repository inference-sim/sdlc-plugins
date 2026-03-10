# PR Review Perspective Prompts

Reference file for the convergence-review skill. Contains exact prompts for PR review perspectives across plan review, code review, and cross-system plan review gates.

**Canonical source:** `docs/contributing/pr-workflow.md` (v3.0). If prompts here diverge from pr-workflow.md, the process doc is authoritative.

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

## Section C: Cross-System PR Plan Review (10 perspectives) — x-pr-plan

For plans that transfer logic between two codebases (e.g., sim → production scheduler). Replaces domain-specific DES/vLLM perspectives with cross-system transfer concerns.

### XPP-1: Substance & Design

```
Review this cross-system implementation plan for substance: Are the behavioral contracts logically sound? Do the signal mappings preserve semantics across the source and target systems? Are there unit mismatches, type incompatibilities, or abstraction-level confusions between the two codebases? Could the design actually achieve what the contracts promise? Check formulas, thresholds, and mapping fidelity from first principles.

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### XPP-2: Cross-Document & Macro Plan Consistency

```
Does this micro plan's scope match the macro plan it references? Are file paths consistent with the actual codebase (check both source and target repos/submodules)? Does the deviation log account for all differences between the macro plan and this micro plan? Check for stale references to completed PRs, removed files, or renamed APIs in either codebase.

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### XPP-3: Cross-System Boundary Verification

```
Does this plan maintain correct boundaries between the source and target systems? Check:
(1) No direct imports or runtime dependencies between source and target code
(2) Transfer artifacts (mappings, schemas, extracted code) are self-contained
(3) The plan doesn't accidentally couple the two systems at build time
(4) Types are in the right packages for each system's conventions
(5) The transfer direction is always source → artifact → target, never bidirectional
(6) CLI tools operate on artifacts only, never directly on source/target internals

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### XPP-4: Codebase Readiness

```
We're about to implement this cross-system PR. Review both codebases for readiness. Check:
- Do the submodules point to the expected branches/commits?
- Are the source APIs referenced in the plan still present and unchanged?
- Are the target extension points (plugin interfaces, registries) still compatible?
- Are there pre-existing bugs, TODO/FIXME items, or stale comments in the modification zones?
- Are there version conflicts between dependencies?
- Missing dependencies that need to be installed?

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### XPP-5: Structural Validation (perform directly, no agent)

> **For Claude:** Perform these 4 checks directly. Do NOT dispatch an agent.

**Check 1 — Task Dependencies:**
For each task, verify it can actually start given what comes before it. Trace the dependency chain: what files does each task create/modify? Does any task require a file, type, or artifact that hasn't been created yet?

**Check 2 — Template Completeness:**
Verify all sections from `docs/contributing/templates/micro-plan.md` are present and non-empty: Header, Part 1 (A-E), Part 2 (F-I), Part 3 (J), Appendix.

**Check 3 — Executive Summary Clarity:**
Read the executive summary as if you're a new team member unfamiliar with either codebase. Is the scope clear without reading the rest? Is the transfer direction obvious?

**Check 4 — Under-specified Tasks:**
For each task, verify it has complete code. Flag any step an executing agent would need to figure out on its own, especially cross-system integration steps.

### XPP-6: Signal Mapping & Abstraction Gap Expert

```
Review this plan as a signal mapping and abstraction gap expert. Check for:
- Signal semantic drift: does the same-named signal mean the same thing in source vs target?
- Fidelity gaps: are any "medium" or "low" fidelity mappings used in critical paths?
- Missing signals: does the target need information the source doesn't provide?
- Type mismatches: int vs float, absolute vs relative, per-request vs per-instance
- Unit mismatches: milliseconds vs seconds, bytes vs blocks, counts vs rates
- Temporal mismatches: point-in-time snapshots vs rolling averages vs cumulative counters
- Default value assumptions when a signal is unavailable in the target

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### XPP-7: Target System Integration Expert

```
Review this plan as an expert in the target system's architecture and plugin model. Check for:
- Plugin interface compliance (method signatures, return types, lifecycle)
- Registration and factory pattern correctness
- Configuration and parameter passing conventions
- Error handling conventions in the target system
- Performance expectations and hot-path constraints in the target
- Breaking changes to existing target system behavior

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### XPP-8: Source System Expert

```
Review this plan as an expert in the source system's architecture. Check for:
- Correct identification of the extractable logic (right boundaries, no missing pieces)
- Dependencies on source-system runtime state that won't exist in the target
- Implicit assumptions baked into the source code (event ordering, data freshness, invariants)
- Source API stability: could the extracted logic break if the source evolves?
- Whether the extraction captures the complete algorithm or just a fragment

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### XPP-9: Schema & Artifact Contract Verification

```
Review this plan's transfer artifacts (JSON schemas, mapping files, extracted code blocks). Check for:
- Schema completeness: do schemas cover all fields referenced in the plan?
- Schema correctness: do types, constraints, and required fields match the actual data?
- Artifact self-containment: can each artifact be validated independently?
- Versioning: is there a way to detect artifact staleness?
- Round-trip consistency: if you extract from source and validate against schema, does it pass?
- Edge cases in schema validation: empty arrays, null values, missing optional fields

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### XPP-10: Security, Robustness & CLI Quality

```
Review this plan's CLI tools, scripts, and configuration handling. Check for:
- Input validation completeness (CLI flags, file paths, JSON/YAML fields)
- Path traversal or injection risks in file operations
- Subprocess invocation safety (if any)
- Degenerate input handling (empty files, malformed JSON, missing fields)
- Exit code correctness and error message clarity
- Resource exhaustion vectors (unbounded file reads, unlimited memory growth)
- Silent data loss paths (overwriting without confirmation, swallowing errors)

First, read the plan file at ARTIFACT_PATH using the Read tool.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```
