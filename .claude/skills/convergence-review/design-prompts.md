# Design & Macro Plan Review Perspective Prompts

Reference file for the convergence-review skill. Contains exact prompts for design document review (8 perspectives) and macro plan review (8 perspectives).

**Canonical sources:** `docs/contributing/design-process.md` (Design Review Perspectives section) and `docs/contributing/macro-planning.md` (Macro Plan Review Perspectives section). The perspective names and checklist items below are expanded versions of the process doc checklists, with full prompt context for agent dispatch. If perspective names diverge, the process docs are authoritative.

**Related documents:**
- Design doc process: `docs/contributing/design-process.md`
- Design guidelines: `docs/contributing/templates/design-guidelines.md`
- Macro plan process: `docs/contributing/macro-planning.md`
- Macro plan template: `docs/contributing/templates/macro-plan.md`

**Dispatch pattern:** Launch each perspective as a parallel Task agent:
```
Task(subagent_type="general-purpose", model="haiku", run_in_background=True,
     prompt="<prompt from below>\n\n<artifact content>")

---

## Section A: Design Document Review (8 perspectives) — `design` gate

### DD-1: Motivation & Scoping

```
You are reviewing a BLIS design document.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Motivation & Scoping
- Are the analysis questions clear, specific, and testable?
- Does every pipeline stage trace back to at least one analysis question? Are there stages that don't contribute to answering any question?
- Is the scope boundary crisp? For each "out of scope" item, is it clear why it's excluded and what breaks if it's accidentally included?
- Are the abstraction gaps between source and target systems enumerated? For each gap, is the handling strategy stated (bridge faithfully / approximate / punt)?
- For each "approximate" gap: what fidelity is lost and what's the risk?
- Could a simpler pipeline (fewer stages, less validation) answer the same analysis questions? What's the minimum viable pipeline?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### DD-2: Pipeline Correctness

```
You are reviewing a BLIS design document.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Pipeline Correctness
- Are stage triggers and ordering well-defined? Which stages are sequential vs parallelizable?
- Is mutable state (retry counts, error context, generated files) clearly owned by a specific stage or orchestrator?
- Are failure modes specified for each stage? Is it clear what happens on failure (halt, retry, degrade, flag for human)?
- Is the pipeline deterministic where it claims to be? Where non-determinism is introduced (e.g., LLM generation), is it acknowledged and acceptable?
- Are timeouts specified? What prevents the pipeline from hanging indefinitely on an external dependency?
- How do you verify the pipeline itself works correctly, independent of any specific algorithm being transferred?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### DD-3: Stage Contract Completeness

```
You are reviewing a BLIS design document.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Stage Contract Completeness
- For each pipeline stage: are the inputs, outputs, and side effects (files created, PRs opened, comments posted) fully specified?
- Is state ownership clear? For each piece of mutable state (retry count, error context, generated code, signal coverage report), which stage or orchestrator owns it?
- Are stage boundaries testable? Could someone implement one stage without reading the design of other stages, working only from the input/output contract?
- Are failure modes specified per stage? What happens with bad input, external service down, LLM generates garbage, or ambiguous results?
- For artifacts passed between stages (e.g., signal coverage report, mapped algorithm spec): is the format/schema specified well enough to implement against?
- How hard is it to extend the pipeline? (add a new validation suite, support a new signal type, target a new production system)

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### DD-4: Integration Fit

```
You are reviewing a BLIS design document.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Integration Fit
- Does the generated artifact (e.g., scorer plugin) follow the target system's conventions? Is it additive (new files only) or does it require modifying existing code?
- Is the no-op default specified? Does the target system work normally when the pipeline hasn't been run or the generated artifact is disabled?
- Can the generated artifact be rolled back or disabled without side effects?
- What's the coupling between the pipeline and the target system's internal APIs? How does the pipeline handle API evolution in the target system?
- Does the generated code access data through proper interfaces, or does it reach into internal state?
- Can the pipeline run against one version of the target system while that system's development continues on HEAD?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### DD-5: Prohibited Content

```
You are reviewing a BLIS design document.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Prohibited Content
Design docs describe WHAT the pipeline does and WHY, never HOW it's implemented. This doc spans two external systems (source simulator, target production system) whose internals will evolve. Check for:
- Concrete type names from either system (e.g., specific language types, struct field names) — belong in the mapping artifact, not the design
- Specific API method names, metric paths, or config field names from the target system — will stale as the target evolves
- Architecture pattern names tied to current implementation (e.g., naming a specific design pattern) — misleading if the target system changes its plugin mechanism
- Internal signal/field names from the source system — will stale if the source renames internals

Apply the staleness test: Would any content in this doc mislead if either the source or target system changes their implementation? Content that would stale should live in the mapping artifact (pinned to a commit), not the design doc.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### DD-6: Trade-off Quality

```
You are reviewing a BLIS design document.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Trade-off Quality
- Does every non-obvious decision have alternatives listed with rationale?
- For each decision: what breaks if it's wrong? What's the cost of reversal?
- For numeric thresholds and magic numbers: why this value and not another? What's the sensitivity — does ±10% change the outcome?
- Are assumptions about the target system's architecture accurate and current? What happens when those assumptions change?
- Are there assumptions about the abstraction gap between source and target systems that this design gets wrong?
- For validation choices (metrics, test sizes, acceptance criteria): are alternatives discussed? Could a different metric or test design answer the same question more cheaply or reliably?

THRESHOLD GUIDANCE: Design docs operate at a higher abstraction level than implementation specs. A threshold is JUSTIFIED at design level if the doc specifies: (a) the metric being used, (b) a provisional default, and (c) an actionable calibration protocol (when, how, and what data to collect). Do NOT flag a threshold as CRITICAL merely because it lacks empirical calibration data — that data doesn't exist yet at design time. Only flag as CRITICAL if: the metric choice itself is wrong, the calibration plan is missing or unactionable, or the provisional default has no stated rationale at all.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### DD-7: Validation Strategy

```
You are reviewing a BLIS design document.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Validation Strategy
- Are the right metrics chosen for each validation concern? Are there better alternatives?
- What properties must hold after each pipeline stage? Are these stated explicitly or only implied?
- Are success criteria quantitative and testable (not "looks correct")?
- What would prove the pipeline itself is unreliable? If a deliberately broken algorithm is transferred, does the pipeline catch it? If a good algorithm fails validation, can you diagnose why?
- What would falsify the design's core assumption (that algorithms can transfer across the abstraction gap at all)? How would you detect that the gap is too wide?
- Is there a plan for calibrating the pipeline's detection capability (false positive rate, false negative rate) before trusting its verdicts?

THRESHOLD GUIDANCE: Design docs operate at a higher abstraction level than implementation specs. A threshold is JUSTIFIED at design level if the doc specifies: (a) the metric being used, (b) a provisional default, and (c) an actionable calibration protocol (when, how, and what data to collect). Do NOT flag a threshold as CRITICAL merely because it lacks empirical calibration data — that data doesn't exist yet at design time. Only flag as CRITICAL if: the metric choice itself is wrong, the calibration plan is missing or unactionable, or the provisional default has no stated rationale at all.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### DD-8: Staleness Resistance

```
You are reviewing a BLIS design document.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Staleness Resistance
- Apply the staleness test to every section: Would this content mislead if either the source system or target system changes their implementation?
- Is content described behaviorally (what each stage does and why) rather than structurally (specific types, API names, config formats from either system)?
- Implementation details that will stale should live in a mapping artifact pinned to a commit, not in the design doc. Are there details here that belong there instead?
- Does the design account for the target system evolving while the pipeline runs? What if breaking changes land between code generation and benchmarking?
- Does the design work across different target environments (different cluster sizes, hardware, metric collection intervals) or is it implicitly tied to one specific setup?
- Where the doc references external artifacts (mapping files, templates, repos): are those references stable, or do they break if the artifact moves or is restructured?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

---

## Section B: Macro Plan Review (8 perspectives) — `macro-plan` gate

## Section C: Generalized Transfer Pipeline Design Review (8 perspectives) — `g-design` gate

These perspectives are system-agnostic. They apply to any cross-system transfer pipeline that moves algorithms or logic from a SOURCE system to a TARGET system. The SOURCE and TARGET are placeholders — the reviewer should identify the actual systems from the design document.

### GDD-1: Motivation & Scoping

```
You are a design reviewer

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Motivation & Scoping
- Are the analysis questions clear, specific, and testable? Could you write a pass/fail test for each one?
- Does every pipeline stage trace back to at least one analysis question? Are there stages that don't contribute to answering any question?
- Is the scope boundary crisp? For each "out of scope" item, is it clear why it's excluded and what breaks if it's accidentally included?
- Are the abstraction gaps between SOURCE and TARGET enumerated? For each gap, is the handling strategy stated (bridge faithfully / approximate / punt)?
- For each "approximate" gap: what fidelity is lost and what's the risk?
- Could a simpler pipeline (fewer stages, less validation) answer the same analysis questions? What's the minimum viable pipeline?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### GDD-2: Pipeline Correctness

```
You are a design reviewer

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Pipeline Correctness
- Are stage triggers and ordering well-defined? Which stages are sequential vs parallelizable?
- Is mutable state (retry counts, error context, generated files, intermediate artifacts) clearly owned by a specific stage or orchestrator?
- Are failure modes specified for each stage? Is it clear what happens on failure (halt, retry, degrade, flag for human)?
- Is the pipeline deterministic where it claims to be? Where non-determinism is introduced (e.g., LLM generation, external API calls), is it acknowledged and acceptable?
- Are timeouts specified? What prevents the pipeline from hanging indefinitely on an external dependency?
- How do you verify the pipeline itself works correctly, independent of any specific algorithm being transferred?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### GDD-3: Stage Contract Completeness

```
You are a design reviewer

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Stage Contract Completeness
- For each pipeline stage: are the inputs, outputs, and side effects (files created, PRs opened, comments posted, deployments triggered) fully specified?
- Is state ownership clear? For each piece of mutable state, which stage or orchestrator owns it?
- Are stage boundaries testable? Could someone implement one stage without reading the design of other stages, working only from the input/output contract?
- Are failure modes specified per stage? What happens with bad input, external service down, generation produces garbage, or ambiguous results?
- For artifacts passed between stages: is the format/schema specified well enough to implement against?
- How hard is it to extend the pipeline? (add a new validation suite, support a new signal/feature type, target a new production system)

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### GDD-4: Integration Fit

```
You are a design reviewer

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Integration Fit
- Does the generated artifact follow the TARGET system's conventions? Is it additive (new files only) or does it require modifying existing TARGET code?
- Is the no-op default specified? Does the TARGET system work normally when the pipeline hasn't been run or the generated artifact is disabled?
- Can the generated artifact be rolled back or disabled without side effects?
- What's the coupling between the pipeline and the TARGET system's internal APIs? How does the pipeline handle API evolution in the TARGET?
- Does the generated code access data through proper TARGET interfaces, or does it reach into internal state?
- Can the pipeline run against one version of the TARGET while that system's development continues on HEAD?
- Does the pipeline similarly respect the SOURCE system's boundaries, or does it depend on SOURCE internals that may change?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### GDD-5: Prohibited Content

```
You are a design reviewer

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Prohibited Content
Design docs describe WHAT the pipeline does and WHY, never HOW it's implemented. This doc spans two external systems whose internals will evolve independently. Check for:
- Concrete type names, struct definitions, or field names from either SOURCE or TARGET — these belong in a mapping artifact, not the design
- Specific API method names, metric paths, or config field names from the TARGET — will stale as the TARGET evolves
- Architecture pattern names tied to current implementation — misleading if either system changes its architecture
- Internal signal/field names from the SOURCE — will stale if the SOURCE renames internals

Apply the staleness test: Would any content in this doc mislead if either the SOURCE or TARGET system changes their implementation? Content that would stale should live in a versioned mapping artifact pinned to a commit, not the design doc.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### GDD-6: Trade-off Quality

```
You are a design reviewer

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Trade-off Quality
- Does every non-obvious decision have alternatives listed with rationale?
- For each decision: what breaks if it's wrong? What's the cost of reversal?
- For numeric thresholds and magic numbers: why this value and not another? What's the sensitivity — does ±10% change the outcome?
- Are assumptions about the SOURCE-to-TARGET abstraction gap accurate? What happens when those assumptions change?
- Are there assumptions about either system that this design gets wrong?
- For validation choices (metrics, test sizes, acceptance criteria): are alternatives discussed? Could a different metric or test design answer the same question more cheaply or reliably?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### GDD-7: Validation Strategy

```
You are a design reviewer

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Validation Strategy
- Are equivalence metrics and acceptance thresholds justified? What evidence supports the chosen values? Has anyone calibrated them against known-good and known-bad transfers?
- What properties must hold after each pipeline stage? Are these stated explicitly or only implied?
- Are success criteria quantitative and testable (not "looks correct")? For each threshold: what's the sensitivity — does ±10% change the outcome?
- What would prove the pipeline itself is unreliable? If a deliberately broken algorithm is transferred, does the pipeline catch it? If a good algorithm fails validation, can you diagnose why?
- What would falsify the design's core assumption — that algorithms can transfer across the abstraction gap at all? How would you detect that the gap is too wide?
- Is there a plan for calibrating the pipeline's detection capability (false positive rate, false negative rate) before trusting its verdicts?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### GDD-8: Staleness Resistance

```
You are a design reviewer

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Staleness Resistance
- Apply the staleness test to every section: Would this content mislead if either the SOURCE or TARGET system changes their implementation?
- Is content described behaviorally (what each stage does and why) rather than structurally (specific types, API names, config formats from either system)?
- Implementation details that will stale should live in a versioned mapping artifact pinned to a commit, not the design doc. Are there details here that belong there instead?
- Does the design account for the TARGET system evolving while the pipeline runs? What if breaking changes land between code generation and validation?
- Does the design work across different TARGET environments (different cluster sizes, hardware, configurations) or is it implicitly tied to one specific setup?
- Where the doc references external artifacts (mapping files, templates, repos): are those references stable, or do they break if the artifact moves or is restructured?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

---

### MP-1: Objective Clarity

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Objective Clarity (macro-plan template Phase 1)
- Are 3-7 crisp objectives defined?
- Are non-goals explicitly listed?
- Is the model scoping table present (modeled / simplified / omitted / justification)?
- Are analysis questions specific enough to drive component selection?
- For each "Simplified" entry, is the lost real-system behavior documented?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### MP-2: Concept Model Quality

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Concept Model Quality (macro-plan template Phase 2)
- Is the concept model under 80 lines?
- Does every building block have all 6 module contract aspects? (observes, controls, owns, invariants, events, extension friction)
- Is real-system correspondence documented (llm-d / vLLM / SGLang mapping table)?
- Is the state ownership map complete (exactly one owner per mutable state)?
- Are behavioral contracts testable with mocks? (Enables parallel development)

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### MP-3: PR Decomposition

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: PR Decomposition Quality (macro-plan template Phase 6)
- Is each PR independently mergeable? (No PR requires another PR's uncommitted code)
- Does the dependency DAG have no cycles?
- Can module contracts be tested with mocks (parallel development enabled)?
- Does each PR identify its extension type? (policy template, subsystem module, backend swap, tier composition)
- Is each PR exercisable immediately after merge? (Via CLI or tests demonstrating new behavior)
- Are parallelizable workstreams identified? Is safe parallelism maximized?
- Are interface freeze points marked? (Which PRs unlock parallel development?)

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### MP-4: Abstraction Level

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Abstraction Level Compliance (macro-plan template Abstraction Level Rule)
The macro plan describes WHAT to build and in WHAT ORDER, not HOW. Check:
- Zero Go code in Sections A-F and H-K (only Section G may have frozen interface signatures)?
- Are all pre-freeze interfaces described behaviorally, not as Go code?
- Is every code snippet a FACT about merged code, not an ASPIRATION about unwritten code?
- Are module contracts using the template from Phase 2, not Go structs?
- Check the concept model (<80 lines?). Does it use behavioral descriptions or implementation details?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### MP-5: Risk Register

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Risk Register Completeness (macro-plan template Phase 3)
For each entry, verify:
- DECISION: Is the choice clearly stated?
- ASSUMPTION: What must be true for this to work?
- VALIDATION: How to test cheaply? (Mock study, prototype, analysis, spike)
- COST IF WRONG: How many PRs of rework? (Count affected PRs)
- GATE: When must validation complete? (Before which PR)

MANDATORY VALIDATION RULE: If cost-of-being-wrong >= 3 PRs, validation is MANDATORY.
- Are success criteria measurable (not "looks good")?
- Are abort plans specified (what changes if validation fails)?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### MP-6: Cross-Cutting Infrastructure

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Cross-Cutting Infrastructure (macro-plan template Phase 5)
Verify Phase 5 is complete:
1. Shared Test Infrastructure — which PR creates it? Which consume it? Are invariant tests planned?
2. Documentation Maintenance — CLAUDE.md update triggers? README updates? Design guidelines updates?
3. CI Pipeline — new test packages added? New linter rules? Performance benchmarks?
4. Dependency Management — new external deps justified? Version pinning?
5. Interface Freeze Schedule — which PR freezes which interface? What must be validated before freezing?

Check that NO item is left as "address when needed." Every cross-cutting concern must be assigned to a specific PR.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### MP-7: Extension Friction

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Extension Friction (design guidelines Section 4.5)
- For each new module boundary, is the touch-point count for adding one more variant specified?
- Are touch-point counts within reference targets from design guidelines Section 4.5?
- If friction exceeds targets, is this acknowledged and justified?
- Does each building block map correctly to real inference system components? (llm-d, vLLM, SGLang)
- Are batching, KV cache, scheduling, and routing semantics accurate?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### MP-8: Design Bug Prevention

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Design Bug Prevention (macro-plan template Phase 8)
Check that the plan prevents these failure modes:

General:
- Scaffolding creep prevented (every struct/method/flag exercised by end of introducing PR)?
- Documentation drift prevented (CLAUDE.md updated in the same PR that causes the change)?
- Test infrastructure duplication prevented (shared packages created early)?
- Golden dataset staleness prevented (regeneration steps included)?
- Interface over-specification prevented (frozen only after 2+ implementations designed)?

DES-specific:
- Type catalog trap prevented (behavioral descriptions, not Go structs)?
- Fidelity for its own sake prevented (every component traces to an analysis question)?
- Golden without invariant prevented (companion invariant tests for golden tests)?
- Exogenous/endogenous mixing prevented (separable workload inputs)?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

---

## Section D: Cross-System Macro Plan Review (8 perspectives) — `x-macro-plan` gate

These perspectives apply to macro plans written using the `macro-plan-cross-system.md` template — plans for pipelines that span multiple external systems and repositories.

### CMP-1: Objective Clarity

```
You are a macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Objective Clarity (cross-system macro-plan template Phase 1)
- Are 3-7 crisp objectives defined?
- Are non-goals explicitly listed?
- Is the pipeline scoping table present (v1 / deferred / out of scope / justification)?
- Are external system version constraints specified?
- Are rollback/disable guarantees specified for each target system?
- Are analysis questions (from the design doc) referenced and traceable to pipeline components?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### CMP-2: Component Model Quality

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Component Model Quality (cross-system macro-plan template Phase 2)
- Is the component model under 100 lines?
- Does every component have a full contract? (type, inputs, outputs, side effects, invariants, failure modes, external dependencies)
- Is the external system map present? (which components touch which external systems)
- Is data flow between stages clearly specified? (artifacts passed between components)
- Are user interaction points identified? (where the pipeline halts for human input)
- Is state ownership clear? (which component owns each artifact and mutable state)
- Are failure modes specified per component? (halt, retry, degrade)

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### CMP-3: PR Decomposition

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: PR Decomposition Quality (cross-system macro-plan template Phase 6)
- Does each PR specify its target repository?
- Does each PR specify its PR type? (infrastructure, artifact, pipeline-stage, integration, validation, orchestration)
- Is each PR independently mergeable within its target repo?
- Does the dependency DAG have no cycles (including cross-repo edges)?
- Is each PR exercisable immediately after merge?
- Are cross-repo ordering constraints explicit? (which PRs in repo A must merge before PRs in repo B)
- Are parallelizable workstreams identified? Is safe parallelism maximized?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### CMP-4: Abstraction Level

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Abstraction Level Compliance (cross-system macro-plan template Abstraction Level Rule)
The macro plan describes WHAT to build and in WHAT ORDER, not HOW. Check:
- Zero implementation code in Sections A-F and H-K? (No Go, Python, or other language code except in Section G for stable APIs)
- Are all component contracts described behaviorally, not as code?
- Is every code snippet a FACT about existing/stable systems, not an ASPIRATION about unwritten code?
- Are external system internals (types, struct fields, method bodies) absent? (Describe behaviorally instead)
- Check the component model (<100 lines?). Does it use behavioral descriptions or implementation details?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### CMP-5: Risk Register

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Risk Register Completeness (cross-system macro-plan template Phase 3)
For each entry, verify:
- DECISION: Is the choice clearly stated?
- ASSUMPTION: What must be true for this to work?
- VALIDATION: How to test cheaply?
- COST IF WRONG: How many PRs of rework?
- GATE: When must validation complete?

CROSS-SYSTEM RISK CATEGORIES — verify each is addressed:
- API drift (target system changes API)
- Version mismatch (pipeline vs. cluster versions)
- Schema evolution (artifact format changes)
- External availability (test infra down)
- Distributed partial failure (multi-repo inconsistency)
- Mock fidelity (test mocks diverge from reality)

MANDATORY VALIDATION RULE: If cost-of-being-wrong >= 3 PRs, validation is MANDATORY.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### CMP-6: Cross-Cutting Infrastructure

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Cross-Cutting Infrastructure (cross-system macro-plan template Phase 5)
Verify Phase 5 is complete:
1. Shared Test Infrastructure — which PR creates it? External system mocking strategy?
2. Documentation Maintenance — CLAUDE.md, README, artifact schema docs?
3. CI Pipeline — integration tests need external access? How handled?
4. Dependency Management — external system version pinning? Artifact compatibility?
5. Cross-Repo Coordination — PR ordering across repos? Branch naming? Review ownership?
6. Artifact Lifecycle — which artifacts are prerequisites? Who creates/maintains them? Version scheme?

Check that NO item is left as "address when needed." Every cross-cutting concern must be assigned to a specific PR.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### CMP-7: Extension & Integration Friction

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Extension & Integration Friction (cross-system macro-plan template Phase 2 Extension Points)
- For each extension point, is the cost of extension specified? (files to change, tests to add)
- How hard is it to add a new target system? (new production system to transfer algorithms to)
- How hard is it to add a new validation suite? (new equivalence test type)
- How hard is it to add a new signal type? (new category of signals to map)
- Are integration points with external systems loosely coupled? (Can the pipeline survive API changes with artifact updates only, or does pipeline code need changing?)
- Is there a clear boundary between what lives in the host repo vs. what lives in mapping artifacts?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### CMP-8: Design Bug Prevention

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Design Bug Prevention (cross-system macro-plan template Phase 8)
Check that the plan prevents these failure modes:

General:
- Scaffolding creep prevented (every file/function exercised by end of introducing PR)?
- Documentation drift prevented (docs updated in same PR that causes change)?
- Test infrastructure duplication prevented (shared packages created early)?

Cross-system-specific:
- API contract drift prevented (version-pinned artifacts + staleness checks)?
- Mock divergence prevented (mocks derived from real artifacts, not hand-written)?
- Distributed partial failure handled (cleanup procedures for multi-repo inconsistency)?
- Artifact staleness prevented (compile + smoke test + version distance checks)?
- Cross-repo merge ordering enforced (dependency DAG includes cross-repo edges)?
- External system evolution handled (what happens when target system releases a new version)?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

---

## Section E: Generalized Macro Plan Review (8 perspectives) — `g-macro-plan` gate

These perspectives are system-agnostic. They apply to any macro plan for any project — single-repo or multi-repo, any language, any domain. They generalize the `macro-plan` gate (Section B) the same way `g-design` (Section C) generalizes `design` (Section A).

### GMP-1: Objective Clarity

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Objective Clarity
- Are 3-7 crisp objectives defined? Is each objective testable (you could write a pass/fail check)?
- Are non-goals explicitly listed? For each, is it clear why it's excluded?
- Is a scoping table present that classifies capabilities as in-scope, deferred, or out of scope — with justification for each?
- Are the plan's objectives traceable to a design document or requirements source? Can every component trace back to an objective?
- Are version/compatibility constraints specified for external dependencies?
- Are rollback/disable guarantees specified? If the delivered code breaks something, how is it reverted?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### GMP-2: Component/Concept Model Quality

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Component/Concept Model Quality
- Is the component or concept model concise (under 80-100 lines)?
- Does every component have a clear contract? At minimum: responsibility, inputs, outputs, side effects, invariants, and failure modes.
- Is data flow between components clearly specified? (What artifacts or state crosses each boundary?)
- Is state ownership unambiguous? (Exactly one component owns each piece of mutable state.)
- Are failure modes specified per component? (halt, retry, degrade, flag for human)
- Are extension points identified? (Where do new capabilities plug in, and what's the cost?)
- Are behavioral contracts testable with mocks? (Enables parallel development of components.)

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### GMP-3: PR Decomposition

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: PR Decomposition Quality
- Is each PR independently mergeable? (No PR requires another PR's uncommitted code.)
- Does the dependency DAG have no cycles?
- Is each PR exercisable immediately after merge? (Via CLI, tests, or demonstrable new behavior.)
- Does each PR deliver one cohesive change? (Not a grab-bag of unrelated modifications.)
- Are parallelizable workstreams identified? Is safe parallelism maximized?
- Are interface boundaries between PRs clear? (Which PRs define interfaces that later PRs consume?)
- Does each PR specify its type? (infrastructure, feature, refactor, test, documentation, etc.)

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### GMP-4: Abstraction Level

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Abstraction Level Compliance
The macro plan describes WHAT to build and in WHAT ORDER, not HOW to implement each piece. Check:
- Zero implementation code (any language) in the plan body? (Only Section G / Stable API Reference may contain code, and only for already-frozen interfaces.)
- Are all component contracts described behaviorally, not as type definitions or code signatures?
- Is every code snippet a FACT about existing/stable systems, not an ASPIRATION about unwritten code?
- Does the component model use behavioral descriptions rather than implementation details?
- Are internal details of external systems absent? (Referenced behaviorally, not structurally.)

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### GMP-5: Risk Register

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Risk Register Completeness
For each entry, verify all five columns:
- DECISION: Is the choice clearly stated?
- ASSUMPTION: What must be true for this to work?
- VALIDATION: How to test cheaply? (Mock, prototype, spike, analysis)
- COST IF WRONG: How many PRs of rework?
- GATE: When must validation complete? (Before which PR)

MANDATORY VALIDATION RULE: If cost-of-being-wrong >= 3 PRs, validation is MANDATORY.
- Are success criteria measurable (not "looks good")?
- Are abort plans specified (what changes if validation fails)?
- Are there obvious risks missing from the register? (External dependency changes, performance cliffs, security concerns, data migration issues)

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### GMP-6: Cross-Cutting Infrastructure

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Cross-Cutting Infrastructure
Verify these cross-cutting concerns are fully addressed:
1. Shared Test Infrastructure — which PR creates it? Which PRs consume it? Are test helpers, fixtures, and mocks planned?
2. Documentation Maintenance — when are CLAUDE.md, README, and user-facing docs updated? Is it the same PR that causes the change?
3. CI Pipeline — new test packages? New linter rules? Performance benchmarks? Integration test requirements?
4. Dependency Management — new external dependencies justified? Version pinning strategy?
5. Configuration — new config surfaces? Migration from old config?

Check that NO item is left as "address when needed." Every cross-cutting concern must be assigned to a specific PR.

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### GMP-7: Extension Friction

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Extension Friction
- For each component boundary, is the cost of adding one more variant specified? (files to change, tests to add)
- Are touch-point counts reasonable? Adding a variant of an existing component should require changing a small, bounded set of files.
- If extension friction is high, is this acknowledged and justified?
- Are integration points between components loosely coupled? (Can one component change without cascading updates?)
- Is there a clear separation between stable interfaces and implementation details?
- Could a new contributor extend the system by reading only the component contracts, without understanding the full codebase?

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```

### GMP-8: Design Bug Prevention

```
You are a BLIS macro-plan reviewer.

DESIGN DOCUMENT:
<paste design doc>

YOUR FOCUS: Design Bug Prevention
Check that the plan prevents these common failure modes:

General:
- Scaffolding creep prevented? (Every file, function, and config exercised by end of introducing PR — no dead code "for later".)
- Documentation drift prevented? (Docs updated in the same PR that causes the change.)
- Test infrastructure duplication prevented? (Shared test packages created early and reused.)
- Premature abstraction prevented? (Abstractions introduced only after 2+ concrete uses exist.)

Structural:
- Regression surfaces identified? (Which existing tests must keep passing?)
- State migration risks addressed? (If data formats change across PRs, is migration planned?)
- Invariants enumerated? (What must ALWAYS hold? What must NEVER happen?)
- Interface over-specification prevented? (Interfaces frozen only after sufficient design confidence.)

Rate each finding as CRITICAL, IMPORTANT, or SUGGESTION.
Report: (1) numbered list of findings with severity, (2) total CRITICAL count, (3) total IMPORTANT count.
```
