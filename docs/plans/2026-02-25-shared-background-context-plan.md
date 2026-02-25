# Shared Background Context Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract `_summarize-problem-context` into a shared plugin and add background context support to hypothesis-test, with bidirectional reuse between both plugins.

**Architecture:** Create `plugins/shared-skills/` as a hidden plugin holding the shared skill. Both `hypothesis-test` and `research-ideas` invoke it via `Skill(_summarize-problem-context *)`. Each plugin detects the other's output files and offers reuse.

**Tech Stack:** Claude Code plugin system (SKILL.md files with YAML frontmatter + markdown)

**Design doc:** `docs/plans/2026-02-25-shared-background-context-design.md`

---

### Task 1: Create shared-skills plugin scaffolding

**Files:**
- Create: `plugins/shared-skills/.claude-plugin/plugin.json`

**Step 1: Create plugin directory and metadata**

```bash
mkdir -p plugins/shared-skills/.claude-plugin
```

Write `plugins/shared-skills/.claude-plugin/plugin.json`:

```json
{
  "name": "shared-skills",
  "description": "Internal shared skills used by other plugins",
  "version": "0.1.0",
  "author": {
    "name": "BLIS team"
  }
}
```

**Step 2: Register in marketplace.json**

Edit `.claude-plugin/marketplace.json` — add to the `plugins` array:

```json
{
  "name": "shared-skills",
  "source": "./plugins/shared-skills",
  "description": "Internal shared skills for cross-plugin use",
  "version": "0.1.0"
}
```

**Step 3: Commit**

```bash
git add plugins/shared-skills/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "feat: create shared-skills plugin scaffolding"
```

---

### Task 2: Move _summarize-problem-context to shared-skills with OUTPUT_FILE support

**Files:**
- Create: `plugins/shared-skills/skills/_summarize-problem-context/SKILL.md`
- Delete: `plugins/research-ideas/skills/_summarize-problem-context/SKILL.md`

**Step 1: Copy the skill to shared-skills**

```bash
mkdir -p plugins/shared-skills/skills/_summarize-problem-context
cp plugins/research-ideas/skills/_summarize-problem-context/SKILL.md \
   plugins/shared-skills/skills/_summarize-problem-context/SKILL.md
```

**Step 2: Add `[OUTPUT_FILE]` argument and header logic**

Edit `plugins/shared-skills/skills/_summarize-problem-context/SKILL.md`.

In the `# ARGUMENTS` section, add after `[SKIP_BACKGROUND]`:

```markdown
- `[OUTPUT_FILE]` (optional): Path for the output file. Defaults to `[PROBLEM_DIR]/research.md`. When set, use this path instead of the default.
- `[DOCUMENT_TITLE]` (optional): Top-level heading for the output document. Defaults to `"Research Document"`. Example: `"Problem Context"`.
```

In the `# DERIVED PATHS` section, change:

```markdown
- `[OUTPUT_FILE]` = argument value if provided, otherwise `[PROBLEM_DIR]/research.md`
```

In `## Step 5: Collect Results and Create research.md`, update the section heading to reference `[OUTPUT_FILE]` instead of hardcoded `research.md`:

Change:
```markdown
## Step 5: Collect Results and Create research.md
```
To:
```markdown
## Step 5: Collect Results and Create Output File
```

And in the template within Step 5, change:

```markdown
# Research Document
```

To:

```markdown
# [DOCUMENT_TITLE]
```

**Step 3: Delete the old skill from research-ideas**

```bash
rm -rf plugins/research-ideas/skills/_summarize-problem-context
```

**Step 4: Verify no broken references**

Search for any hardcoded references to the old location:

```bash
grep -r "_summarize-problem-context" plugins/research-ideas/
```

Expected: Only references in `plugins/research-ideas/skills/research-ideas/SKILL.md` via `Skill(_summarize-problem-context *)` — these still work because the skill name hasn't changed, just its plugin home.

**Step 5: Commit**

```bash
git add plugins/shared-skills/skills/_summarize-problem-context/SKILL.md
git add -u plugins/research-ideas/skills/_summarize-problem-context/
git commit -m "refactor: move _summarize-problem-context to shared-skills plugin

Add [OUTPUT_FILE] and [DOCUMENT_TITLE] arguments for flexible output.
Delete original from research-ideas plugin."
```

---

### Task 3: Update research-ideas to detect and reuse problem-context.md

**Files:**
- Modify: `plugins/research-ideas/skills/research-ideas/SKILL.md`

**Step 1: Add cross-detection before Screen 2**

Edit `plugins/research-ideas/skills/research-ideas/SKILL.md`.

In `## Step 1: Background Context Configuration (SCREEN 2 - Always Show)`, add a new sub-step before Step 1.1:

Insert before `### Step 1.1: Select Source Types`:

```markdown
### Step 1.0: Detect Existing Background (silent)

Check for existing background files that can be reused:

```
Glob: [CWD]/hypotheses/problem-context.md
```

Store:
- `[HAS_PROBLEM_CONTEXT]` = true if file exists and is non-empty
- `[PROBLEM_CONTEXT_PATH]` = path to the file (if found)
```

**Step 2: Add reuse option to Screen 2 source selection**

In `### Step 1.1: Select Source Types`, modify the AskUserQuestion to conditionally include the reuse option.

Replace the existing options block with:

```markdown
```
AskUserQuestion:
  questions:
    - question: "Which sources should be used to gather background context?"
      header: "Background"
      multiSelect: true
      options:
        # NEW — only shown if [HAS_PROBLEM_CONTEXT] = true:
        - label: "Use existing problem-context.md (Recommended)"
          description: "Reuse background from a previous /hypothesis-test session"
        # Existing options (always shown):
        - label: "Current repository (Recommended)"
          description: "Analyze the codebase in the current working directory"
        - label: "Other local repositories"
          description: "Include related code from other local directories"
        - label: "GitHub repositories"
          description: "Include remote GitHub repos (fetched via API)"
        - label: "Local documents"
          description: "Include local files (PDFs, markdown, text files)"
        - label: "Remote papers or URLs"
          description: "Include arXiv papers, docs, blog posts, or web content"
        - label: "Web search"
          description: "Search the web for relevant papers and resources"
        - label: "Skip background entirely"
          description: "Start generating ideas without background context"
```

**If [HAS_PROBLEM_CONTEXT] = false:** Omit the first option. Screen looks identical to current behavior.
```

**Step 3: Add handling for reuse selection in Step 5**

In `## Step 5: Create Research Document with Background`, add a new conditional before the existing `### If [BACKGROUND_MODE] = "skip":` block:

```markdown
### If "Use existing problem-context.md" was selected:

Set `[BACKGROUND_MODE]` = "reuse"

```
Task tool:
  description: "Create research doc from existing background"
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    1. Read the problem statement from [PROBLEM_FILE_PATH]
    2. Read the existing background from [PROBLEM_CONTEXT_PATH]
    3. Extract the "# Background" section and everything under it (up to the end of the file or next top-level heading that isn't under Background)
    4. Create [RESEARCH_FILE] with:
       - "# Research Document"
       - "## Problem Statement" with the problem content
       - "---"
       - The extracted Background section
       - "---"
       - A trailing blank line (for subsequent idea appending)
```
```

**Step 4: Commit**

```bash
git add plugins/research-ideas/skills/research-ideas/SKILL.md
git commit -m "feat(research-ideas): detect and reuse problem-context.md from hypothesis-test

Add Step 1.0 to detect existing hypotheses/problem-context.md.
Add reuse option to Screen 2 source selection.
Add reuse handling in Step 5 background generation."
```

---

### Task 4: Add Screen 2 (Background) to hypothesis-test and update to 7-screen flow

**Files:**
- Modify: `plugins/hypothesis-test/skills/hypothesis-test/SKILL.md`

This is the largest task. It involves:
1. Updating the screen table from 6 to 7 screens
2. Adding Screen 2: Background with cross-detection
3. Renumbering all subsequent screens
4. Adding `_summarize-problem-context` to allowed-tools
5. Feeding background to hypothesis agents

**Step 1: Update allowed-tools in frontmatter**

Add to the `allowed-tools` list:

```yaml
  - Skill(_summarize-problem-context *)
```

**Step 2: Update the Fixed Screen Sequence table**

Replace the 6-screen table with:

```markdown
| Screen | Headers | Type | Purpose | Never Skip |
|--------|---------|------|---------|------------|
| 1 | "Project" + "Focus" + "Count" | Config (3 questions) | Setup: project, focus area, hypothesis count | Always show |
| 2 | "Background" | Config | Background context: reuse existing or generate new | Always show |
| 3 | — | Dashboard | Hypothesis generation progress | Always show |
| 4 | "Select" + "Execution" | Config (2 questions) | Pick hypotheses to test + execution mode | Always show |
| 5 | "Approve" | Dashboard + Config | Scaffold experiments (dashboard), then batch approve | Always show |
| 6 | — | Dashboard | Experiment progress (background agents) | Always show |
| 7 | "Commit" | Config | Commit results | Always show |
```

**Step 3: Insert Screen 2: Background section**

After the `Screen 1: Setup` section and before what was `Screen 2: Generation Dashboard`, insert:

```markdown
---

## Screen 1.5: Detect Existing Background (silent, after Step 0)

After Step 0 completes, check for existing background files:

```
Glob("[PROJECT_ROOT]/research.md")
Glob("[PROJECT_ROOT]/hypotheses/problem-context.md")
```

Store:
- `[HAS_RESEARCH_MD]` = true if research.md exists and contains a `# Background` section
- `[HAS_PROBLEM_CONTEXT]` = true if hypotheses/problem-context.md exists and is non-empty
- `[RESEARCH_MD_PATH]` = `[PROJECT_ROOT]/research.md` (if found)
- `[PROBLEM_CONTEXT_PATH]` = `[PROJECT_ROOT]/hypotheses/problem-context.md` (if found)

---

## Screen 2: Background (SCREEN 2 — Always Show)

Present background options based on what was detected:

```
AskUserQuestion:
  questions:
    - question: "How should we gather background context for hypothesis generation?"
      header: "Background"
      multiSelect: false
      options:
        # Conditional — only if [HAS_RESEARCH_MD] = true:
        - label: "Use existing research.md background (Recommended)"
          description: "Reuse background from a previous /research-ideas session"
        # Conditional — only if [HAS_PROBLEM_CONTEXT] = true:
        - label: "Use existing problem-context.md (Recommended)"
          description: "Reuse background from a previous /hypothesis-test session"
        # Always shown:
        - label: "Generate new background"
          description: "Select sources (repos, papers, URLs) and generate fresh context"
        - label: "Skip background"
          description: "Generate hypotheses without background context"
```

**If neither [HAS_RESEARCH_MD] nor [HAS_PROBLEM_CONTEXT] is true:** Only show "Generate new background" and "Skip background".

### If "Use existing research.md background" selected:

1. Read `[RESEARCH_MD_PATH]`
2. Extract the `# Background` section (everything from `# Background` to the next `---` or `# Idea`)
3. Write to `[PROJECT_ROOT]/hypotheses/problem-context.md`:
   ```markdown
   # Problem Context

   ## Problem Statement

   [FOCUS_AREA description or extracted problem statement]

   ---

   [Extracted Background section]
   ```
4. Store extracted background as `[BACKGROUND_CONTENT]`

### If "Use existing problem-context.md" selected:

1. Read `[PROBLEM_CONTEXT_PATH]`
2. Extract background content
3. Store as `[BACKGROUND_CONTENT]`

### If "Generate new background" selected:

Show source selection sub-screens (same as research-ideas Step 1.1-1.3):

```
AskUserQuestion:
  questions:
    - question: "Which sources should be used to gather background context?"
      header: "Sources"
      multiSelect: true
      options:
        - label: "Current repository (Recommended)"
          description: "Analyze the codebase in the current working directory"
        - label: "Other local repositories"
          description: "Include related code from other local directories"
        - label: "GitHub repositories"
          description: "Include remote GitHub repos (fetched via API)"
        - label: "Remote papers or URLs"
          description: "Include arXiv papers, docs, blog posts, or web content"
        - label: "Web search"
          description: "Search the web for relevant papers and resources"
```

For each selected source type, prompt for paths/URLs using the same sub-screens as research-ideas (Step 1.2 patterns).

Then invoke `_summarize-problem-context`:

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

    Pre-configured sources (DO NOT ask user again):
    - [INCLUDE_CURRENT_REPO] = [value]
    - [LOCAL_REPO_PATHS] = [list, if any]
    - [GITHUB_REPO_URLS] = [list, if any]
    - [REMOTE_URLS] = [list, if any]
    - [WEB_SEARCH_QUERIES] = [list, if any]

    Write the output to [PROJECT_ROOT]/hypotheses/problem-context.md
```

Wait for completion. Read the file and store as `[BACKGROUND_CONTENT]`.

### If "Skip background" selected:

Set `[BACKGROUND_CONTENT]` = empty. Agents scan project independently.

**→ Immediately proceed to Screen 3 (Generation Dashboard). No commentary.**
```

**Step 4: Renumber all subsequent screens**

Find-and-replace in the SKILL.md:
- `Screen 2: Generation Dashboard` → `Screen 3: Generation Dashboard`
- `SCREEN 2` → `SCREEN 3`
- `Screen 3: Select & Execute` → `Screen 4: Select & Execute`
- `SCREEN 3` → `SCREEN 4`
- `Screen 4: Approve Experiment` → `Screen 5: Approve Experiment`
- `SCREEN 4` → `SCREEN 5`
- `Screen 5: Testing Dashboard` → `Screen 6: Testing Dashboard`
- `SCREEN 5` → `SCREEN 6`
- `Screen 6: Commit` → `Screen 7: Commit`
- `SCREEN 6` → `SCREEN 7`

Also update cross-references:
- "proceed to Screen 2" → "proceed to Screen 3"
- "proceed to Screen 3" → "proceed to Screen 4"
- "proceed to Screen 4" → "proceed to Screen 5"  (in edge cases section too)
- "proceed to Screen 5" → "proceed to Screen 6"
- "proceed to Screen 6" → "proceed to Screen 7"
- Screen references in edge cases section
- "6-screen flow" → "7-screen flow" in the intro

**Step 5: Feed background to hypothesis agents in Screen 3**

In the `Hypothesis Agent Prompt Template` (now Screen 3), add a new field after `EXISTING_CLAIMS`:

```
BACKGROUND_CONTEXT: |
  [BACKGROUND_CONTENT or "No background context provided. Scan the project independently."]
```

Add to the agent prompt instructions after the diversity guidance:

```
Background Context:
Use the following background context to inform your hypothesis generation.
This provides domain knowledge and project understanding beyond what you
find by scanning files. Leverage it to generate more targeted hypotheses.

[BACKGROUND_CONTEXT]
```

**Step 6: Update the "→ Immediately proceed" line after Screen 1**

Change:
```
**→ Immediately proceed to Step 0 + Screen 2. No commentary.**
```
To:
```
**→ Immediately proceed to Step 0 + Screen 2 (Background). No commentary.**
```

**Step 7: Commit**

```bash
git add plugins/hypothesis-test/skills/hypothesis-test/SKILL.md
git commit -m "feat(hypothesis-test): add Screen 2 (Background) and update to 7-screen flow

Add background context screen with cross-detection for research.md and
problem-context.md. Feed background to hypothesis generation agents.
Renumber all screens from 6 to 7."
```

---

### Task 5: Update _formulate-hypothesis to accept BACKGROUND_CONTEXT

**Files:**
- Modify: `plugins/hypothesis-test/skills/_formulate-hypothesis/SKILL.md`

**Step 1: Add argument**

In `## Invocation`, update the invocation signature:

```markdown
Skill(_formulate-hypothesis "<project_root>" "<focus_area>" "<existing_claims>" "<language>" "<background_context>")
```

Add to arguments list:

```markdown
- `background_context` (optional) — background context gathered from repos, papers, and other sources. Empty string if none provided.
```

**Step 2: Update process to use background**

In `## Process`, after step 1 (Scan the project), add:

```markdown
1b. **Review background context** (if `[BACKGROUND_CONTEXT]` is non-empty):
    - Read the provided background for domain knowledge, architectural patterns, and known issues
    - Use background insights to identify more targeted testable gaps
    - Cross-reference background claims with what the project actually implements
```

**Step 3: Commit**

```bash
git add plugins/hypothesis-test/skills/_formulate-hypothesis/SKILL.md
git commit -m "feat(_formulate-hypothesis): add optional background_context argument

Agents use background context to generate more targeted hypotheses."
```

---

### Task 6: Bump versions

**Files:**
- Modify: `plugins/hypothesis-test/.claude-plugin/plugin.json`
- Modify: `plugins/research-ideas/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

**Step 1: Bump hypothesis-test version**

In `plugins/hypothesis-test/.claude-plugin/plugin.json`, change version from `"0.1.0"` to `"0.2.0"` (minor bump — new feature).

**Step 2: Bump research-ideas version**

In `plugins/research-ideas/.claude-plugin/plugin.json`, change version from `"1.2.3"` to `"1.3.0"` (minor bump — new cross-detection feature).

**Step 3: Update marketplace.json versions**

Update the version fields for both plugins in `.claude-plugin/marketplace.json` to match.

**Step 4: Commit**

```bash
git add plugins/hypothesis-test/.claude-plugin/plugin.json \
       plugins/research-ideas/.claude-plugin/plugin.json \
       .claude-plugin/marketplace.json
git commit -m "chore: bump versions for shared background context feature

hypothesis-test: 0.1.0 → 0.2.0
research-ideas: 1.2.3 → 1.3.0
shared-skills: 0.1.0 (new)"
```

---

### Task 7: Verify all cross-references are consistent

**Step 1: Search for stale references**

```bash
# Check no references to old _summarize-problem-context location
grep -r "research-ideas/skills/_summarize-problem-context" plugins/

# Check all Skill() references use correct name
grep -r "Skill(_summarize-problem-context" plugins/

# Check screen numbers are consistent in hypothesis-test
grep -n "Screen [0-9]" plugins/hypothesis-test/skills/hypothesis-test/SKILL.md

# Check all plugins registered in marketplace
cat .claude-plugin/marketplace.json
```

**Step 2: Read each modified file end-to-end**

Read these files fully to verify internal consistency:
- `plugins/shared-skills/skills/_summarize-problem-context/SKILL.md`
- `plugins/hypothesis-test/skills/hypothesis-test/SKILL.md`
- `plugins/hypothesis-test/skills/_formulate-hypothesis/SKILL.md`
- `plugins/research-ideas/skills/research-ideas/SKILL.md`

**Step 3: Verify file structure**

```bash
find plugins/ -name "SKILL.md" | sort
find plugins/ -name "plugin.json" | sort
```

Expected structure:
```
plugins/hypothesis-test/.claude-plugin/plugin.json
plugins/hypothesis-test/skills/_document-findings/SKILL.md
plugins/hypothesis-test/skills/_formulate-hypothesis/SKILL.md
plugins/hypothesis-test/skills/_run-and-analyze/SKILL.md
plugins/hypothesis-test/skills/_scaffold-experiment/SKILL.md
plugins/hypothesis-test/skills/hypothesis-test/SKILL.md
plugins/research-ideas/.claude-plugin/plugin.json
plugins/research-ideas/skills/_generate-ideas/SKILL.md
plugins/research-ideas/skills/research-ideas/SKILL.md
plugins/research-ideas/skills/review-plan/SKILL.md
plugins/shared-skills/.claude-plugin/plugin.json
plugins/shared-skills/skills/_summarize-problem-context/SKILL.md
```

Note: `plugins/research-ideas/skills/_summarize-problem-context/` should NOT exist.
