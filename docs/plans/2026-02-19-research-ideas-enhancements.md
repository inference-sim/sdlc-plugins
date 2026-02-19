# Research Ideas Plugin Enhancements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enhance the research-ideas plugin with better documentation, multi-source context gathering with parallel web-enabled agents, improved UI flow, and progress dashboard.

**Architecture:** Update README with auto-update instructions and problem.md guidance. Refactor `_summarize-problem-context` to launch parallel background Explore agents with web search for each context source. Add comprehensive UI flow in main skill for problem location, background options, judge configuration, and iteration count. Create task-based progress dashboard.

**Tech Stack:** Claude Code skills (YAML frontmatter + markdown), AskUserQuestion tool, Task tool (background agents with WebSearch), TaskCreate/TaskUpdate for dashboard.

---

## Task 1: Update README with Auto-Update Instructions

**Files:**
- Modify: `README.md:14-24`

**Step 1: Read current README**

Run: `Read README.md` (already done - see context)

**Step 2: Write updated README with auto-update section**

Add new section after the Setup section:

```markdown
## Auto-Updates

To enable automatic plugin updates when new versions are released:

```bash
# Check for updates manually
/plugin marketplace update sdlc-plugins

# Or reinstall to get latest version
/plugin install research-ideas@sdlc-plugins
```

**Recommended:** Run `/plugin marketplace update sdlc-plugins` periodically to get the latest features and fixes.
```

**Step 3: Verify change**

Run: `Read README.md` to confirm changes
Expected: New "Auto-Updates" section visible

**Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add auto-update instructions to README"
```

---

## Task 2: Add Problem Statement Guidance to README

**Files:**
- Modify: `README.md` (append after Available Plugins section)

**Step 1: Add problem.md documentation**

Append after the `/research-ideas` usage section:

```markdown
#### Creating a Problem Statement

Create a `problem.md` file in your project directory:

```markdown
# Problem Statement

## Context
[Describe the background and motivation]

## Problem
[Clearly state what needs to be solved]

## Constraints
[Any limitations or requirements]

## Success Criteria
[How will you know the problem is solved?]
```

**Need help articulating your problem?** Use the brainstorming superpower:

```bash
/brainstorm
```

This will help you explore and refine your problem statement before generating research ideas.
```

**Step 2: Verify change**

Run: `Read README.md`
Expected: Problem statement guidance visible with brainstorming reference

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add problem.md creation guide with brainstorming reference"
```

---

## Task 3: Refactor _summarize-problem-context for Multi-Source Parallel Agents

**Files:**
- Modify: `plugins/research-ideas/skills/_summarize-problem-context/SKILL.md`

**Step 1: Read current skill**

Run: `Read plugins/research-ideas/skills/_summarize-problem-context/SKILL.md` (already done)

**Step 2: Update allowed-tools to include WebSearch**

Replace the frontmatter:

```yaml
---
name: _summarize-problem-context
description: Create research document with problem statement and context from multiple sources (repositories, papers, files)
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - Task
  - WebFetch
  - litellm_web_search
  - AskUserQuestion
  - Bash(gh *)
---
```

**Step 3: Update Step 2 to enable current repo by default**

Replace Step 2 content with:

```markdown
## Step 2: Ask About Context Sources

**Current repository is included by default.** Ask about additional sources:

```
AskUserQuestion:
  questions:
    - question: "The current repository will be analyzed by default. Do you want to add more context sources?"
      header: "Context"
      multiSelect: true
      options:
        - label: "Add other local repositories"
          description: "Include related code from other local directories"
        - label: "Add GitHub repositories"
          description: "Include remote GitHub repos (will be fetched via API)"
        - label: "Add papers or URLs"
          description: "Include arXiv papers, docs, blog posts, or other web content"
        - label: "Search the web for relevant content"
          description: "Use web search to find papers and resources related to the problem"
```

**Store results:**
- `[INCLUDE_CURRENT_REPO]` = true (always default)
- `[ADD_LOCAL_REPOS]` = true if first option selected
- `[ADD_GITHUB_REPOS]` = true if second option selected
- `[ADD_PAPERS]` = true if third option selected
- `[ADD_WEB_SEARCH]` = true if fourth option selected
```

**Step 4: Update Step 3 to handle web search**

Add new section 3.4 for web search:

```markdown
### 3.4: Configure Web Search (if `[ADD_WEB_SEARCH]` is true)

```
AskUserQuestion:
  questions:
    - question: "What topics should I search for? (Enter custom queries or use auto-generated)"
      header: "Web Search"
      multiSelect: false
      options:
        - label: "Auto-generate search queries (Recommended)"
          description: "I'll derive search terms from your problem statement"
        - label: "I'll provide specific queries"
          description: "Enter your own search terms in the text field"
```

**If auto-generate selected:**
- Generate 3-5 search queries based on problem statement keywords
- Store as `[WEB_SEARCH_QUERIES]` (list of query strings)

**If user provides queries:**
- Parse user input (split by newlines or commas)
- Store as `[WEB_SEARCH_QUERIES]`
```

**Step 5: Update Step 4 to launch parallel agents with web search**

Add new section 4.5:

```markdown
### 4.5: Web Search Agents (if `[WEB_SEARCH_QUERIES]` is non-empty)

**For each query in `[WEB_SEARCH_QUERIES]`:**
```
Task tool:
  description: "Web search: [QUERY_PREVIEW]"
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    Search the web for information related to: "[QUERY]"

    Use the litellm_web_search tool with this query.

    Then use WebFetch to retrieve the most relevant 2-3 results.

    Focus on extracting information relevant to this problem:
    [Insert problem statement summary here]

    Summarize:
    1. Key findings from search results
    2. Relevant papers, articles, or documentation found
    3. Technical approaches or methods mentioned
    4. How this relates to the problem at hand

    Return a structured summary in markdown format.
```

Store agent IDs as `[WEB_SEARCH_AGENT_IDS]` (list).
```

**Step 6: Update Step 5 to include web search results**

Update the research.md template to include web search section:

```markdown
[If [WEB_SEARCH_QUERIES] is non-empty:]
## Web Research

### Search: "[Query 1]"
[Insert summary from first web search agent]

### Search: "[Query 2]"
[Insert summary from second web search agent]
...
```

**Step 7: Verify changes**

Run: `Read plugins/research-ideas/skills/_summarize-problem-context/SKILL.md`
Expected: All updates visible

**Step 8: Commit**

```bash
git add plugins/research-ideas/skills/_summarize-problem-context/SKILL.md
git commit -m "feat: add web search and parallel multi-source context gathering"
```

---

## Task 4: Implement Deterministic UI Flow

**Files:**
- Modify: `plugins/research-ideas/skills/research-ideas/SKILL.md`

**Goal:** Ensure the UI is 100% deterministic - every time a user runs `/research-ideas`, they see the exact same sequence of prompts in the exact same order, regardless of detected files or environment state.

**Step 1: Define the fixed UI sequence**

The UI MUST always present these 5 screens in this exact order:

```
Screen 1: Problem Statement Location
Screen 2: Background Context Sources
Screen 3: Judge Configuration
Screen 4: Iteration Count
Screen 5: Confirmation + Dashboard Display
```

**Step 2: Add UI contract section to skill**

Insert at the top of the STEPS section:

```markdown
# UI CONTRACT (DETERMINISTIC)

**CRITICAL:** This skill MUST present the same UI flow every time. The user experience must be predictable and consistent.

## Fixed Screen Sequence

Every invocation of `/research-ideas` presents exactly 5 screens in this order:

| Screen | Header | Purpose | Never Skip |
|--------|--------|---------|------------|
| 1 | "Problem" | Locate/create problem statement | Always show |
| 2 | "Background" | Configure context sources | Always show |
| 3 | "Judges" | Select review models | Always show |
| 4 | "Iterations" | Set iteration count | Always show |
| 5 | Dashboard | Show progress tracker | Always show |

## Rules

1. **No conditional skipping** - All 5 screens are shown regardless of detected files or API availability
2. **Same option order** - Options within each screen are always in the same order
3. **Defaults clearly marked** - Recommended options always have "(Recommended)" suffix
4. **Auto-detection informs, doesn't skip** - If a problem.md is found, it becomes the recommended option, but the question is still asked
5. **API status shown inline** - Unavailable models show "(unavailable)" but remain as options for user awareness
```

**Step 3: Update allowed-tools to ensure determinism**

Verify the skill doesn't use tools that could cause non-deterministic behavior mid-flow.

**Step 4: Verify by tracing two hypothetical runs**

Document expected behavior:
- Run 1: Fresh directory, no problem.md, all APIs available
- Run 2: Has problem.md, some APIs unavailable

Both runs should show identical screen sequence with only option labels/descriptions varying.

**Step 5: Commit**

```bash
git add plugins/research-ideas/skills/research-ideas/SKILL.md
git commit -m "feat: add deterministic UI contract for consistent user experience"
```

---

## Task 5: Enhance Main Skill UI Flow for Problem Location

**Files:**
- Modify: `plugins/research-ideas/skills/research-ideas/SKILL.md:38-71`

**Step 1: Read current skill**

Run: `Read plugins/research-ideas/skills/research-ideas/SKILL.md` (already done)

**Step 2: Update Step 0 for clearer problem location UI (Screen 1)**

Replace Step 0.2 with enhanced version that always shows all options:

```markdown
### Step 0.2: Present Problem Statement Options (SCREEN 1 - Always Show)

**Always present all 4 options.** If a problem file is detected, mark it as recommended. If not detected, show "No file detected" variant.

```
AskUserQuestion:
  questions:
    - question: "Where is your research problem defined?"
      header: "Problem"
      multiSelect: false
      options:
        # Option 1: Dynamic label based on detection
        - label: "Use [detected_file] (Recommended)" | "Use existing file (none detected)"
          description: "Use a problem statement file in the current directory"
        - label: "Create new problem.md"
          description: "I'll guide you through writing a problem statement"
        - label: "Point to another file"
          description: "My problem statement is in a different location"
        - label: "I need help defining my problem"
          description: "Use /brainstorm to explore and articulate the problem first"
```

**If user needs help defining problem:**
```
Output:
  "Great! Let's use the brainstorming skill to help you articulate your problem.

  Run: /brainstorm

  Once you have a clear problem statement saved to a file, run /research-ideas again."

Exit skill.
```
```

**Step 3: Verify changes**

Run: `Read plugins/research-ideas/skills/research-ideas/SKILL.md`
Expected: Enhanced problem location options

**Step 4: Commit**

```bash
git add plugins/research-ideas/skills/research-ideas/SKILL.md
git commit -m "feat: enhance problem location UI with brainstorming option"
```

---

## Task 6: Update Background Context UI (Screen 2)

**Files:**
- Modify: `plugins/research-ideas/skills/research-ideas/SKILL.md:115-136`

**Step 1: Update Step 2 for deterministic background configuration**

Replace Step 2 with:

```markdown
## Step 2: Background Context Configuration (SCREEN 2 - Always Show)

**Always show this screen.** Present background options regardless of detected state.

```
AskUserQuestion:
  questions:
    - question: "How should background context be gathered for your research?"
      header: "Background"
      multiSelect: false
      options:
        - label: "Auto-generate from sources (Recommended)"
          description: "I'll guide you through selecting repositories, papers, and web search"
        - label: "I'll provide my own background"
          description: "Skip auto-generation; I have context to paste or reference"
        - label: "Skip background entirely"
          description: "Start generating ideas without background context"
```

Store result:
- `[BACKGROUND_MODE]` = "auto" | "user" | "skip"
```

**Step 2: Verify changes**

Run: `Read plugins/research-ideas/skills/research-ideas/SKILL.md`

**Step 3: Commit**

```bash
git add plugins/research-ideas/skills/research-ideas/SKILL.md
git commit -m "feat: make background context UI deterministic (Screen 2)"
```

---

## Task 7: Add Judge Configuration UI (Screen 3)

**Files:**
- Modify: `plugins/research-ideas/skills/research-ideas/SKILL.md:75-113`

**Step 1: Update Step 1 to add judge configuration**

Insert new step after API auto-detection. Replace Step 1 with:

```markdown
## Step 1: Auto-Detect and Configure Review Models (SCREEN 3 - Always Show)

**Always show this screen.** Auto-detection runs silently first, then results inform the UI but don't skip it.

**Step 1.1: Auto-detect available models (silent)**

Run this check silently to discover which models are accessible:

```bash
~/.claude/skills/review-plan/scripts/review.sh --check-models aws/claude-opus-4-6 Azure/gpt-4o GCP/gemini-2.5-flash 2>&1
```

Parse the output to determine which models passed. Store as `[AVAILABLE_MODELS]`.

**Step 1.2: Present judge configuration (SCREEN 3)**

**Always show all 4 options.** Append availability status to each model option based on Step 1.1 results.

```
AskUserQuestion:
  questions:
    - question: "Which AI models should review your ideas? (3 recommended for diverse feedback)"
      header: "Judges"
      multiSelect: true
      options:
        # Labels show availability status inline - NEVER hide options
        - label: "Claude Opus (aws/claude-opus-4-6) [✓ available]" | "[✗ unavailable]"
          description: "Strong reasoning and nuanced feedback"
        - label: "GPT-4o (Azure/gpt-4o) [✓ available]" | "[✗ unavailable]"
          description: "Broad knowledge and practical suggestions"
        - label: "Gemini 2.5 Flash (GCP/gemini-2.5-flash) [✓ available]" | "[✗ unavailable]"
          description: "Fast with good technical insights"
        - label: "Skip external reviews"
          description: "Generate ideas without external model reviews"
```

**IMPORTANT:**
- All 4 options are ALWAYS shown (deterministic UI)
- Availability status is shown inline, not used to hide options
- If user selects an unavailable model, warn them and suggest configuring API access
- Default: Pre-select all available models (up to 3)

Store selected models as `[REVIEW_MODELS]` (list of available selections only).
```

**Step 2: Verify changes**

Run: `Read plugins/research-ideas/skills/research-ideas/SKILL.md`

**Step 3: Commit**

```bash
git add plugins/research-ideas/skills/research-ideas/SKILL.md
git commit -m "feat: add configurable judge selection UI"
```

---

## Task 8: Add Iteration Count Configuration (Screen 4)

**Files:**
- Modify: `plugins/research-ideas/skills/research-ideas/SKILL.md`

**Step 1: Add iteration configuration after judge selection**

Insert new step (becomes Step 2):

```markdown
## Step 2: Configure Iteration Count (SCREEN 4 - Always Show)

```
AskUserQuestion:
  questions:
    - question: "How many idea iterations would you like to generate?"
      header: "Iterations"
      multiSelect: false
      options:
        - label: "3 iterations (Recommended)"
          description: "Good balance of exploration and refinement"
        - label: "5 iterations"
          description: "More thorough exploration, takes longer"
        - label: "1 iteration"
          description: "Quick single idea generation"
        - label: "Custom number"
          description: "Enter a specific number in the text field"
```

Store as `[NUM_ITERATIONS]` (parse custom if provided, default to 3).
```

**Step 2: Verify changes**

Run: `Read plugins/research-ideas/skills/research-ideas/SKILL.md`

**Step 3: Commit**

```bash
git add plugins/research-ideas/skills/research-ideas/SKILL.md
git commit -m "feat: add configurable iteration count"
```

---

## Task 9: Enhance Progress Dashboard (Screen 5)

**Files:**
- Modify: `plugins/research-ideas/skills/research-ideas/SKILL.md:139-168`

**Step 1: Update Step 3 for enhanced dashboard**

Replace Step 3 with comprehensive dashboard:

```markdown
## Step 3: Create Progress Dashboard (SCREEN 5 - Always Show)

**Create all tasks upfront** to show the user the complete workflow. Use `TaskCreate` to build the task list:

```
# Create configuration summary task (already completed)
TaskCreate:
  subject: "Configuration complete"
  description: |
    - Problem: [PROBLEM_FILE_PATH]
    - Judges: [REVIEW_MODELS count] model(s)
    - Iterations: [NUM_ITERATIONS]
    - Background: [auto/user/skip]
  activeForm: "Configuring"

# Mark it completed immediately
TaskUpdate:
  taskId: [CONFIG_TASK_ID]
  status: completed

# Create background task
TaskCreate:
  subject: "Gather background context"
  description: |
    Sources:
    - Current repo: Yes
    - Additional repos: [count]
    - Papers/URLs: [count]
    - Web search: [Yes/No]
  activeForm: "Gathering background context"

# Create idea tasks (one per iteration)
For i = 1 to [NUM_ITERATIONS]:
  TaskCreate:
    subject: "Idea [i]: Generate and review"
    description: |
      1. Generate idea based on problem + previous feedback
      2. Send to [REVIEW_MODELS count] judges for review
      3. Collect and append feedback
    activeForm: "Working on Idea [i]"

# Create summary task
TaskCreate:
  subject: "Executive summary"
  description: "Synthesize all ideas, compare approaches, provide recommendation"
  activeForm: "Writing executive summary"
```

**Display dashboard summary to user:**
```
═══════════════════════════════════════════════════════════
  Research Ideas - Progress Dashboard
═══════════════════════════════════════════════════════════

  [✓] Configuration complete
  [ ] Gather background context
  [ ] Idea 1: Generate and review
  [ ] Idea 2: Generate and review
  [ ] Idea 3: Generate and review
  [ ] Executive summary

  Output: [RESEARCH_FILE]
═══════════════════════════════════════════════════════════
```

**Store the task IDs** for later updates:
- `[BACKGROUND_TASK_ID]` = ID of the background task
- `[IDEA_TASK_IDS]` = list of idea task IDs
- `[SUMMARY_TASK_ID]` = ID of the summary task
```

**Step 2: Verify changes**

Run: `Read plugins/research-ideas/skills/research-ideas/SKILL.md`

**Step 3: Commit**

```bash
git add plugins/research-ideas/skills/research-ideas/SKILL.md
git commit -m "feat: enhance progress dashboard with configuration summary"
```

---

## Task 10: Update Plugin Version

**Files:**
- Modify: `plugins/research-ideas/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

**Step 1: Update plugin.json version**

Change version from `1.1.1` to `1.2.0`:

```json
{
  "name": "research-ideas",
  "description": "Researches and generates ideas for your project that have been iteratively reviewed by different models",
  "version": "1.2.0",
  "author": {
    "name": "BLIS team"
  }
}
```

**Step 2: Update marketplace.json version**

Change version from `1.1.1` to `1.2.0`:

```json
{
  "name": "sdlc-plugins",
  "owner": {
    "name": "AI Platform Optimization",
    "email": "ai-platform-org@ibm.com"
  },
  "metadata": {
    "description": "Internal SDLC plugins for the team",
    "version": "1.0.0",
    "pluginRoot": "./plugins"
  },
  "plugins": [
    {
      "name": "research-ideas",
      "source": "./plugins/research-ideas",
      "description": "Generate iteratively-reviewed research ideas with multi-model feedback",
      "version": "1.2.0"
    }
  ]
}
```

**Step 3: Verify version consistency**

Run:
```bash
jq -r '.version' plugins/research-ideas/.claude-plugin/plugin.json
jq -r '.plugins[0].version' .claude-plugin/marketplace.json
```
Expected: Both show `1.2.0`

**Step 4: Commit**

```bash
git add plugins/research-ideas/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "chore: bump version to 1.2.0"
```

---

## Task 11: Update CI/CD Changelog Notes

**Files:**
- Modify: `.github/workflows/release.yml`

**Step 1: Read current workflow**

(Already done - see context)

**Step 2: No changes needed**

The release workflow already:
- Validates tag matches marketplace version
- Generates changelog from commits
- Creates GitHub release
- Notifies team with update instructions

The workflow is sufficient for the current needs.

**Step 3: Commit (skip if no changes)**

No commit needed - CI/CD is already properly configured.

---

## Task 12: Final README Updates

**Files:**
- Modify: `README.md`

**Step 1: Update plugin description**

Update the research-ideas section with new features:

```markdown
### research-ideas

Generates research ideas with multi-model AI review (Claude, GPT-4o, Gemini).

```bash
/research-ideas
```

**Features:**
- **Guided workflow** - step-by-step configuration for problem, background, judges
- **Multi-source context** - gather background from repos, papers, and web search
- **Parallel processing** - background agents fetch context simultaneously
- **Configurable judges** - choose which AI models review your ideas
- **Progress dashboard** - visual task tracking throughout the process

Just run the command and let it guide you. The plugin will:
1. Help you create or locate a problem statement
2. Gather background from multiple sources (repos, papers, web)
3. Configure review judges (3 models by default)
4. Generate iteratively-reviewed ideas with visual progress tracking

Outputs a single `research.md` with problem, background, all ideas, reviews, and executive summary.
```

**Step 2: Verify final README**

Run: `Read README.md`
Expected: All documentation updates visible

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README with new features and usage guide"
```

---

## Summary of Changes

| Task | Files Modified | Purpose |
|------|----------------|---------|
| 1 | README.md | Auto-update instructions |
| 2 | README.md | Problem.md guidance + brainstorming reference |
| 3 | _summarize-problem-context/SKILL.md | Multi-source parallel agents with web search |
| 4 | research-ideas/SKILL.md | **Deterministic UI contract** |
| 5 | research-ideas/SKILL.md | Enhanced problem location UI (Screen 1) |
| 6 | research-ideas/SKILL.md | Background context UI (Screen 2) |
| 7 | research-ideas/SKILL.md | Judge configuration UI (Screen 3) |
| 8 | research-ideas/SKILL.md | Iteration count configuration (Screen 4) |
| 9 | research-ideas/SKILL.md | Enhanced progress dashboard (Screen 5) |
| 10 | plugin.json, marketplace.json | Version bump to 1.2.0 |
| 11 | release.yml | (No changes needed) |
| 12 | README.md | Final feature documentation |

**Total commits:** 10 (Tasks 1-10 and 12; Task 11 has no changes)

**Version:** 1.1.1 → 1.2.0

**Deterministic UI Guarantee:** Every `/research-ideas` invocation shows exactly 5 screens in the same order:
1. Problem → 2. Background → 3. Judges → 4. Iterations → 5. Dashboard
