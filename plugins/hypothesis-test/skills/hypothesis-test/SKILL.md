---
name: hypothesis-test
description: Guided hypothesis-driven experimentation. Choose a project, generate hypotheses, select which to test, run experiments in parallel or sequentially, document findings.
allowed-tools:
  - Skill(_formulate-hypothesis *)
  - Skill(_scaffold-experiment *)
  - Skill(_summarize-problem-context *)
  - Task
  - TaskOutput
  - AskUserQuestion
  - TaskCreate
  - TaskUpdate
  - TaskList
  - TaskGet
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(git *)
  - Bash(ls *)
---

# Hypothesis Test

End-to-end guided hypothesis experimentation with a deterministic 6-screen flow and background agent dispatch.

**CRITICAL:** This skill MUST present the same UI flow every time. Determinism is required because users build muscle memory around the screen sequence, documentation references specific screen numbers, and background agents expect a fixed configuration structure from each screen.

## Terminology

- **Background context** — domain knowledge and architectural information used to generate hypotheses
- **Problem context file** — the file at `[PROJECT_ROOT]/hypotheses/problem-context.md` that stores background context
- **Background sources** — user-selected source types (repos, papers, web search) used to generate the problem context file

**CRITICAL: NEVER STOP BETWEEN SCREENS.** After the user answers a config screen, immediately proceed to the next screen. Do NOT:
- Summarize what the user just selected
- Ask "Ready to proceed?" or "Shall I continue?"
- Say "Great, now let's move on to..."
- Recap configuration before starting generation
- Ask for confirmation or approval to continue
- Add any commentary between screens

The ONLY time the flow pauses is when an AskUserQuestion is presented. Between screens, the transition is instant and silent. Screen 1 answer → immediately run project detection + background processing + Screen 2 (Generation). And so on.

## Fixed Screen Sequence

<!-- If screen count changes, update the count in the heading above Screen sequence table AND in the intro line. -->

Every invocation presents exactly these screens in this order:

| Screen | Headers | Type | Purpose |
|--------|---------|------|---------|
| 1 | "Project" + "Focus" + "Count" + "Background" | Config (4 questions) | Setup: project, focus area, hypothesis count, background sources |
| 2 | — | Dashboard | Hypothesis generation progress |
| 3 | "Select" + "Execution" | Config (2 questions) | Pick hypotheses to test + execution mode |
| 4 | "Approve" | Dashboard + Config | Scaffold experiments (dashboard), then batch approve |
| 5 | — | Dashboard | Experiment progress (background agents) |
| 6 | "Commit" | Config | Commit results |

No screens are ever skipped. All screens are shown regardless of detected state.

**Navigation:** Config screens (1, 3) use multi-question AskUserQuestion calls so the user can navigate left/right between questions before submitting.

## Rules

1. **No conditional skipping** — All 6 screens shown regardless of detected state
2. **Same option order** — Options always in the same order within each screen
3. **Defaults clearly marked** — Recommended options have "(Recommended)" suffix
4. **Auto-detection informs, doesn't skip** — Detected state sets defaults, never skips screens
5. **Dashboards are task-driven** — Screens 2, 4 (scaffolding phase), and 5 use TaskCreate/TaskUpdate for progress
6. **One agent per hypothesis** — Every hypothesis scaffolding (Screen 4) and test (Screen 5) runs in its own background agent
7. **Orchestrator owns the catalog** — Only the orchestrator writes to `[PROJECT_ROOT]/hypotheses/README.md`. Background agents never touch it.
8. **Approval before testing** — Experiment designs are scaffolded by background agents, then approved in bulk (Screen 4), before any testing agents launch (Screen 5). Testing agents never ask for approval.
9. **All paths relative to project** — All file operations (Glob, Grep, Read, Write) use `[PROJECT_ROOT]` as base. Never assume the current working directory is the target project.
10. **Always invoke internal skills** — Never ask the user for permission before invoking internal skills. `_formulate-hypothesis`, `_scaffold-experiment`, `_run-and-analyze`, and `_document-findings` are always used automatically at their respective stages. No opt-in, no confirmation, no manual alternative.
11. **Never pause during dashboards** — Screens 2, 4 (scaffolding phase), and 5 run to completion without any user interaction. Do NOT stop between iterations to show results, ask questions, or wait for feedback. Generate all hypotheses back-to-back, scaffold all experiments back-to-back, run all tests back-to-back. The user sees progress only through task updates.
12. **Multi-question navigation** — Config screens (1, 3) use a single AskUserQuestion with multiple questions so users can navigate left/right between questions before submitting.
13. **Zero-talk transitions** — After a screen completes, immediately execute the next screen. No recaps, no summaries, no "let me now...", no asking permission to continue. The only user-facing output between screens is the next AskUserQuestion or task progress updates.

## Edge Cases

### 0 hypotheses selected (Screen 3, "Select" question)
If user deselects all: show "Please select at least one hypothesis." Re-show Screen 3.

### 0 experiments approved (Screen 4)
If user deselects all designs: show "No experiments approved. Skipping to commit." Jump to Screen 6.

### All experiments fail
Screen 5 dashboard shows all tasks as failed. Screen 6 summary includes failure count. Commit screen still shown.

### Experiment timeout
After 5 minutes + 3 retries, mark as `Failed` with reason "experiment timeout".

### Invalid project path
If the user-provided path doesn't exist or isn't a directory: show error, re-show Screen 1.

### Background agent crash or timeout
Each background agent has a 5-minute timeout. On timeout or crash: mark the task as `Failed`, log the error from TaskOutput, and continue the dashboard. Failed agents do not block other agents or subsequent screens.

### Agent returns unparseable output
If an agent doesn't return the expected format (e.g., missing `HYPOTHESIS:` or `VERDICT:` line): mark as `Failed` with reason "invalid output format". The dashboard continues with successful results.

### Empty project (no source files)
If `[PROJECT_ROOT]` contains no recognized source files after scanning: show "No source files found at [PROJECT_ROOT]." Re-show Screen 1.

### Malformed problem-context.md
If the problem context file exists but is empty or unreadable: log a warning and proceed without background context. Do not fail the flow.

---

## Pre-Screen Detection (silent, before Screen 1)

Before presenting Screen 1, silently check the current working directory for existing background files:

```
Glob("./research.md")
Glob("./hypotheses/problem-context.md")
```

Store:
- `[HAS_RESEARCH_MD]` = true if research.md exists and contains a `# Background` section
- `[HAS_PROBLEM_CONTEXT]` = true if hypotheses/problem-context.md exists and is non-empty

---

## Screen 1: Setup

Present all four config questions in a **single AskUserQuestion** so the user can navigate left/right between them:

```
AskUserQuestion:
  questions:
    - question: "Which project should we generate and test hypotheses for?"
      header: "Project"
      multiSelect: false
      options:
        - label: "Current directory (Recommended)"
          description: "Use the current working directory as the project"
        - label: "Enter a path"
          description: "Select 'Other' and type the absolute path to the project root"
    - question: "What area of the project should we generate hypotheses for?"
      header: "Focus"
      multiSelect: false
      options:
        - label: "Entire project (Recommended)"
          description: "Scan everything — README, tests, source, recent changes"
        - label: "Performance"
          description: "Focus on latency, throughput, resource usage, scaling"
        - label: "Correctness"
          description: "Focus on edge cases, error handling, boundary conditions"
        - label: "Specific component"
          description: "Select 'Other' and name the file, module, or feature"
    - question: "How many hypotheses should I generate?"
      header: "Count"
      multiSelect: false
      options:
        - label: "3 (Recommended)"
          description: "Quick exploration — good for getting started"
        - label: "5"
          description: "Moderate depth — covers more ground"
        - label: "10"
          description: "Thorough exploration — takes longer to test all"
    - question: "Select background sources for hypothesis generation:"
      header: "Background"
      multiSelect: true
      options:
        # Conditional — only if [HAS_RESEARCH_MD] = true:
        - label: "Use existing research.md (Recommended)"
          description: "Reuse background from a previous /research-ideas session"
        # Conditional — only if [HAS_PROBLEM_CONTEXT] = true:
        - label: "Use existing problem-context.md (Recommended)"
          description: "Reuse background from a previous /hypothesis-test session"
        # Always shown:
        - label: "Current repository"
          description: "Analyze the codebase for relevant context"
        - label: "Other local repositories"
          description: "Include related code from other local directories"
        - label: "GitHub repositories"
          description: "Include remote GitHub repos (fetched via API)"
        - label: "Remote papers or URLs"
          description: "Include arXiv papers, docs, blog posts, or web content"
        - label: "Web search"
          description: "Search the web for relevant papers and resources"
        - label: "Skip background"
          description: "Generate hypotheses without background context"
```

**If neither [HAS_RESEARCH_MD] nor [HAS_PROBLEM_CONTEXT] is true:** Omit the reuse options from the Background question. Only source types and "Skip" are shown.

**After submission:**

1. If "Enter a path" or "Other" selected for Project: use the user's typed path. If "Current directory": use CWD.
2. **Validate** the path exists and is a directory (`Bash: ls <path>`). If invalid, show error and re-show Screen 1.
3. Store project as `[PROJECT_ROOT]` (absolute path, no trailing slash).
4. If "Specific component" or "Other" selected for Focus and user provided text: store that as `[FOCUS_AREA]`. Otherwise store the selected label.
5. Store count as `[COUNT]`.
6. Store background selections as `[BACKGROUND_SELECTIONS]`.

**→ Immediately proceed to project detection + background processing + Screen 2 (Generation). No commentary.**

---

## Post-Screen 1: Detect Project Context (silent)

After the user submits Screen 1, silently gather context from `[PROJECT_ROOT]`:

```
Glob("[PROJECT_ROOT]/README*", "[PROJECT_ROOT]/go.mod", "[PROJECT_ROOT]/pyproject.toml", "[PROJECT_ROOT]/package.json", "[PROJECT_ROOT]/Makefile")
Glob("[PROJECT_ROOT]/**/*.go", "[PROJECT_ROOT]/**/*.py", "[PROJECT_ROOT]/**/*.ts", "[PROJECT_ROOT]/**/*.js")
Glob("[PROJECT_ROOT]/hypotheses/h*")
```

Store:
- `[LANGUAGE]` — detected from file extensions (go, python, node, other)
- `[BUILD_CMD]` — from go.mod, pyproject.toml, package.json, Makefile
- `[ENTRY_POINT]` — main binary/script
- `[EXISTING_COUNT]` — number of existing hypothesis directories
- `[EXISTING_CLAIMS]` — claims from existing hypotheses (to avoid duplicates)
- `[PENDING_HYPOTHESES]` — any with Status: Pending from previous runs

### Process Background Selections

Based on `[BACKGROUND_SELECTIONS]` from Screen 1:

**If "Skip background" is selected (alone or with others):** No action needed. Agents will skip background if the file doesn't exist.

**If a reuse option is selected:**

1. If "Use existing research.md": Read `[PROJECT_ROOT]/research.md`, extract the `# Background` section (everything from `# Background` to the next `---` or `# Idea`), write to `[PROJECT_ROOT]/hypotheses/problem-context.md`
2. If "Use existing problem-context.md": No action needed — file already exists at `[PROJECT_ROOT]/hypotheses/problem-context.md`
3. If a reuse option is selected alongside source types, the reuse content is used as-is — ignore other source selections.

**If only source types selected (no reuse, no skip):**

Invoke `_summarize-problem-context` as a background agent. The skill handles its own path/URL collection prompts for source types that need them (local repos, GitHub, papers).

```
Task tool:
  description: "Generate background summary"
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    Run the /_summarize-problem-context skill with these arguments:

    Problem file: Create a temporary problem statement from the focus area:
      "[FOCUS_AREA] for project at [PROJECT_ROOT]"

    OUTPUT_FILE: [PROJECT_ROOT]/hypotheses/problem-context.md
    DOCUMENT_TITLE: "Problem Context"

    Source types selected by the user:
    - [INCLUDE_CURRENT_REPO] = true/false
    - [ADD_LOCAL_REPOS] = true/false
    - [ADD_GITHUB_REPOS] = true/false
    - [ADD_REMOTE_URLS] = true/false
    - [ADD_WEB_SEARCH] = true/false

    The skill will prompt the user for specific paths/URLs as needed.
    Write the output to [PROJECT_ROOT]/hypotheses/problem-context.md
```

Wait for completion. The file is now at `[PROJECT_ROOT]/hypotheses/problem-context.md` for agents to read.

---

## Screen 2: Generation Dashboard

**CRITICAL: This entire screen is fully autonomous. Do NOT pause, ask questions, show intermediate results, or wait for user input. Generate ALL [COUNT] hypotheses in parallel using background agents. The user sees progress only via task updates — never stop to discuss, confirm, or display individual results.**

**Create all tasks upfront:**

```
TaskCreate: "Generate hypothesis 1 of [COUNT]"  (activeForm: "Generating hypothesis 1")
TaskCreate: "Generate hypothesis 2 of [COUNT]"  (activeForm: "Generating hypothesis 2")
...
TaskCreate: "Generate hypothesis [COUNT] of [COUNT]"
```

**Each hypothesis runs in its own background agent.** Launch ALL agents in a **single message** with multiple `Task` tool calls:

```
Task(run_in_background: true): "Generate hypothesis 1"
Task(run_in_background: true): "Generate hypothesis 2"
Task(run_in_background: true): "Generate hypothesis 3"
...
```

### Hypothesis Agent Prompt Template

```
Task:
  description: "Generate hypothesis <I> of [COUNT]"
  subagent_type: hypothesis-agent
  run_in_background: true
  prompt: |
    Run /_formulate-hypothesis "[PROJECT_ROOT]" "[FOCUS_AREA]" "[EXISTING_CLAIMS]" "[LANGUAGE]"

    You are agent <I> of [COUNT]. To ensure diversity, use your index:
    - Agent 1: most obvious untested behavior or gap
    - Agent 2: performance or resource-related claims
    - Agent 3: edge cases or error handling
    - Agent 4+: config options, integration boundaries, recently changed code

    Return exactly:
    HYPOTHESIS: [testable claim]
    REFUTED_IF: [falsifiability condition]
```

Collect results using `TaskOutput`. As each agent completes:
1. Parse `HYPOTHESIS` and `REFUTED_IF` from the agent's output
2. Update the corresponding dashboard task → `completed`

**After ALL agents complete:**

1. Deduplicate: if any two hypotheses are substantially the same, discard the later one
2. For each unique hypothesis, assign sequential numbers starting from `[EXISTING_COUNT] + 1`
3. Write stub to `[PROJECT_ROOT]/hypotheses/h<N>-<slug>/HYPOTHESIS.md`:
   ```markdown
   # H<N>: <Short Title>

   **Status**: Pending
   **Date**: <today>

   ## Hypothesis

   > <testable claim>

   **Refuted if:** <falsifiability condition>
   ```
4. Store generated hypotheses as `[NEW_HYPOTHESES]`

**→ Immediately proceed to Screen 3. No commentary, no recap of generated hypotheses.**

---

## Screen 3: Select & Execute

Combine `[NEW_HYPOTHESES]` with `[PENDING_HYPOTHESES]` from the post-Screen 1 detection.

Present both questions in a **single AskUserQuestion** so the user can navigate left/right between them:

```
AskUserQuestion:
  questions:
    - question: "Which hypotheses should we test? ([N] new, [M] previously pending)"
      header: "Select"
      multiSelect: true
      options:
        - label: "All of them (Recommended)"
          description: "Test all [N+M] hypotheses"
        - label: "H<N>: <short claim> (new)"
          description: "<full claim>. Refuted if: <condition>"
        - label: "H<N>: <short claim> (pending)"
          description: "<full claim from previous run>"
        - ...
    - question: "How should experiments run? Parallel is faster but uses more resources."
      header: "Execution"
      multiSelect: false
      options:
        - label: "Parallel (Recommended)"
          description: "Run all experiments simultaneously in background agents. Fastest."
        - label: "Sequential"
          description: "Run one at a time. Use when experiments compete for shared resources (GPU, ports, DB)."
```

If no previously pending hypotheses exist, omit the "(pending)" entries but still show the screen with just the new ones.

If user selects nothing for "Select": show "Please select at least one hypothesis." Re-show Screen 3.

Store selections as `[SELECTED]` and execution mode as `[EXEC_MODE]`.

**→ Immediately proceed to Screen 4 scaffolding. No commentary.**

---

## Screen 4: Approve Experiment Designs

### Phase 1: Scaffolding Dashboard

**Create scaffolding tasks upfront:**

```
For each hypothesis in [SELECTED]:
  TaskCreate: "H<N>: Scaffold experiment"  (activeForm: "Scaffolding H<N>: <short claim>")
```

**Each scaffolding runs in its own background agent.** Launch ALL agents in a **single message** with multiple `Task` tool calls:

```
Task(run_in_background: true): "Scaffold H1: <claim>"
Task(run_in_background: true): "Scaffold H2: <claim>"
Task(run_in_background: true): "Scaffold H3: <claim>"
```

#### Scaffolding Agent Prompt Template

```
Task:
  description: "Scaffold H<N>: <short claim>"
  subagent_type: hypothesis-agent
  run_in_background: true
  prompt: |
    Run /_scaffold-experiment "[PROJECT_ROOT]" "[HYPOTHESIS_DIR]" "[CLAIM]" "[REFUTED_IF]" "[LANGUAGE]" "[BUILD_CMD]" "[ENTRY_POINT]"

    Return exactly:
    HYPOTHESIS_DIR: hypotheses/h<N>-<slug>
    FILES_CREATED: run.sh, analyze.py, FINDINGS.md
    DESIGN_SUMMARY: "Vary: <independent var>. Measure: <dependent var>. Control: <controlled vars>."
```

Collect results using `TaskOutput`. Update dashboard tasks as each completes. Parse `DESIGN_SUMMARY` from each agent's output.

### Phase 2: Batch Approval

Present all designs for batch approval:

```
AskUserQuestion:
  header: "Approve"
  question: "Review experiment designs. Which should we run?"
  multiSelect: true
  options:
    - label: "All of them (Recommended)"
      description: "Run all [N] experiments"
    - label: "H<N>: <short claim>"
      description: "Vary: <independent var>. Measure: <dependent var>. Control: <controlled vars>"
    - ...
```

If user approves nothing: show "No experiments approved. Skipping to commit." Jump to Screen 6.

Store approved hypotheses as `[APPROVED]`.

**→ Immediately proceed to Screen 5 testing. No commentary.**

---

## Screen 5: Testing Dashboard

**Create one task per approved hypothesis:**

```
For each hypothesis in [APPROVED]:
  TaskCreate: "H<N>: Run & analyze"  (activeForm: "Testing H<N>: <short claim>")

TaskCreate: "Update hypothesis catalog"  (activeForm: "Updating catalog")
```

**Each hypothesis runs in its own background agent.** Since scaffolding and approval already happened in Screen 4, agents only run experiments and document results.

### Background Agent Prompt Template

```
Task:
  description: "Test H<N>: <short claim>"
  subagent_type: hypothesis-agent
  run_in_background: true
  prompt: |
    Test hypothesis H<N> at <PROJECT_ROOT>/hypotheses/h<N>-<slug>.
    The directory contains scaffolded run.sh, analyze.py, FINDINGS.md.

    1. Run /_run-and-analyze "hypotheses/h<N>-<slug>" "<CLAIM>"
    2. Parse VERDICT, SUMMARY, METRICS_TABLE, ANALYSIS_OUTPUT from the result
    3. Run /_document-findings "hypotheses/h<N>-<slug>" "<verdict>" "<summary>" "<metrics>" "<analysis>"

    Do NOT update <PROJECT_ROOT>/hypotheses/README.md — the orchestrator
    handles catalog updates after all agents complete.

    Return exactly:
    VERDICT: <Confirmed|Refuted|Inconclusive|Failed>
    SUMMARY: <2-3 sentence interpretation>
```

### Parallel Mode

Launch ALL agents in a **single message** with multiple `Task` tool calls:

```
Task(run_in_background: true): "Test H1: <claim>"
Task(run_in_background: true): "Test H2: <claim>"
Task(run_in_background: true): "Test H3: <claim>"
```

Collect results using `TaskOutput`. Update dashboard as each completes.

### Sequential Mode

Launch ONE agent at a time, wait for completion before launching next:

```
Task(run_in_background: true): "Test H1: <claim>"
TaskOutput(block: true):       wait for H1 → parse verdict, update task

Task(run_in_background: true): "Test H2: <claim>"
TaskOutput(block: true):       wait for H2 → parse verdict, update task
...
```

### After All Agents Complete

**Catalog update** (orchestrator — single atomic write):
1. Read each `[PROJECT_ROOT]/hypotheses/h<N>-<slug>/HYPOTHESIS.md` for the verdict
2. Create or update `[PROJECT_ROOT]/hypotheses/README.md` with all new entries at once
3. Update catalog task → `completed`

Store all verdicts as `[RESULTS]`.

**→ Immediately proceed to Screen 6. No commentary, no recap of results.**

---

## Screen 6: Commit

```
AskUserQuestion:
  header: "Commit"
  question: "Commit all experiment results?"
  multiSelect: false
  options:
    - label: "Commit all (Recommended)"
      description: "Stage and commit all hypothesis directories + catalog"
    - label: "Commit successful only"
      description: "Exclude failed experiments from the commit"
    - label: "I'll commit later"
      description: "Leave changes unstaged"
```

If committing:
```bash
git -C [PROJECT_ROOT] add hypotheses/
git -C [PROJECT_ROOT] commit -m "hypothesis: test [N] hypotheses — [summary of verdicts]"
```

**Final summary:**

```
Hypothesis Experiment Complete!

Project: [PROJECT_ROOT]
Generated: [G] hypotheses
Tested: [T] experiments
  Confirmed:    [C]
  Refuted:      [R]
  Inconclusive: [I]
  Failed:       [F]

Findings: [PROJECT_ROOT]/hypotheses/
Catalog: [PROJECT_ROOT]/hypotheses/README.md
```
