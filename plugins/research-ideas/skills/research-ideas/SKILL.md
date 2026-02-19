---
name: research-ideas
description: Generate iteratively-reviewed research ideas from a problem statement. Fully guided - no arguments required.
allowed-tools:
  - Task
  - AskUserQuestion
  - TaskCreate
  - TaskUpdate
  - TaskList
  - TaskGet
  - Glob
  - Read
  - Write
  - Skill(_summarize-problem-context *)
  - Skill(_generate-ideas *)
  - Skill(_review-plan *)
  - Bash(.claude/skills/review-plan/scripts/review.sh *)
  - Bash(python3 *)
  - Bash(curl *)
  - Bash(jq *)
---
# TASK

Generate creative, novel, and practical research ideas for a problem statement. Each idea is reviewed by multiple AI models and feedback is used to improve subsequent ideas. Everything is written to a single research document.

**This skill is fully guided** - it will help you set up everything needed without requiring any upfront arguments.

**All stages run as background agents** to provide progress visibility and enable parallel execution where possible.

# DERIVED PATHS

- `[PROBLEM_DIR]` = directory containing the problem file
- `[RESEARCH_FILE]` = `[PROBLEM_DIR]/research.md`
- `[NUM_ITERATIONS]` = 3 (default)

# UI CONTRACT (DETERMINISTIC)

**CRITICAL:** This skill MUST present the same UI flow every time. The user experience must be predictable and consistent.

## Fixed Screen Sequence

Every invocation of `/research-ideas` presents exactly 5 screens in this order:

| Screen | Header | Purpose | Never Skip |
|--------|--------|---------|------------|
| 1 | "Problem" | Locate/create problem statement | Always show |
| 2 | "Background" | Select sources and provide paths/URLs | Always show |
| 3 | "Judges" | Select review models | Always show |
| 4 | "Iterations" | Set iteration count | Always show |
| 5 | Dashboard | Show progress tracker | Always show |

## Rules

1. **No conditional skipping** - All 5 screens are shown regardless of detected files or API availability
2. **Same option order** - Options within each screen are always in the same order
3. **Defaults clearly marked** - Recommended options always have "(Recommended)" suffix
4. **Auto-detection informs, doesn't skip** - If a problem.md is found, it becomes the recommended option, but the question is still asked
5. **API status shown inline** - Unavailable models show "(unavailable)" but remain as options for user awareness

# STEPS

## Step 0: Find or Create Problem Statement

**Start by locating or creating the problem file.**

### Step 0.1: Search for Existing Problem Files

Look for existing problem statement files in the current directory:

```
Glob: problem*.md, problem*.txt, *.md
```

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

If user chooses to create new:
- Ask them to describe their problem
- Write it to `problem.md` in the current directory

Store result as `[PROBLEM_FILE_PATH]`.

---

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

---

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

---

## Step 3: Background Context Configuration (SCREEN 2 - Always Show)

**Always show this screen.** Collect background sources with their paths/URLs.

### Step 3.1: Select Source Types

```
AskUserQuestion:
  questions:
    - question: "Which sources should be used to gather background context?"
      header: "Background"
      multiSelect: true
      options:
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

**Store source type selections:**
- `[INCLUDE_CURRENT_REPO]` = true if "Current repository" selected
- `[ADD_LOCAL_REPOS]` = true if "Other local repositories" selected
- `[ADD_GITHUB_REPOS]` = true if "GitHub repositories" selected
- `[ADD_LOCAL_DOCS]` = true if "Local documents" selected
- `[ADD_REMOTE_URLS]` = true if "Remote papers or URLs" selected
- `[ADD_WEB_SEARCH]` = true if "Web search" selected
- `[SKIP_BACKGROUND]` = true if "Skip background entirely" selected

**If "Skip background entirely" or no sources selected:**
- Set `[BACKGROUND_MODE]` = "skip"
- Skip to Step 4

### Step 3.2: Collect Paths for Selected Sources

**For each selected source type, prompt for paths/URLs:**

**If `[ADD_LOCAL_REPOS]` = true:**
```
AskUserQuestion:
  questions:
    - question: "Enter paths to local repositories (one per line or comma-separated)"
      header: "Local Repos"
      multiSelect: false
      options:
        - label: "I'll provide the paths"
          description: "Enter absolute paths like /Users/me/projects/my-repo"
```
- User enters paths in the "Other" text field
- Parse input (split by newlines or commas)
- Validate each path exists
- Store as `[LOCAL_REPO_PATHS]` (list)

**If `[ADD_GITHUB_REPOS]` = true:**
```
AskUserQuestion:
  questions:
    - question: "Enter GitHub repository URLs (one per line or comma-separated)"
      header: "GitHub Repos"
      multiSelect: false
      options:
        - label: "I'll provide the URLs"
          description: "Enter URLs like https://github.com/owner/repo or owner/repo"
```
- User enters URLs in the "Other" text field
- Parse and normalize URLs (e.g., "owner/repo" → "https://github.com/owner/repo")
- Store as `[GITHUB_REPO_URLS]` (list)

**If `[ADD_LOCAL_DOCS]` = true:**
```
AskUserQuestion:
  questions:
    - question: "Enter paths to local documents (one per line or comma-separated)"
      header: "Local Docs"
      multiSelect: false
      options:
        - label: "I'll provide the paths"
          description: "Enter paths to PDFs, markdown, or text files"
```
- User enters file paths in the "Other" text field
- Parse input (split by newlines or commas)
- Validate each file exists
- Store as `[LOCAL_DOC_PATHS]` (list)

**If `[ADD_REMOTE_URLS]` = true:**
```
AskUserQuestion:
  questions:
    - question: "Enter URLs to papers or documentation (one per line or comma-separated)"
      header: "URLs"
      multiSelect: false
      options:
        - label: "I'll provide the URLs"
          description: "Enter URLs to arXiv, papers, docs, blog posts, etc."
```
- User enters URLs in the "Other" text field
- Parse input (split by newlines or commas)
- Store as `[REMOTE_URLS]` (list)

**If `[ADD_WEB_SEARCH]` = true:**
```
AskUserQuestion:
  questions:
    - question: "What topics should I search for?"
      header: "Web Search"
      multiSelect: false
      options:
        - label: "Auto-generate search queries (Recommended)"
          description: "I'll derive search terms from your problem statement"
        - label: "I'll provide specific queries"
          description: "Enter your own search terms"
```
- If auto-generate: derive 3-5 queries from problem statement
- If user provides: parse input from "Other" text field
- Store as `[WEB_SEARCH_QUERIES]` (list)

### Step 3.3: Confirm Sources Summary

Display collected sources:
```
Background Sources Summary:
- Current repo: [Yes/No]
- Local repos: [count] paths
- GitHub repos: [count] URLs
- Local docs: [count] files
- Remote URLs: [count] URLs
- Web search: [count] queries
```

Set `[BACKGROUND_MODE]` = "auto" and pass all collected paths to `/_summarize-problem-context`

---

## Step 4: Create Progress Dashboard (SCREEN 5 - Always Show)

**Create all tasks upfront** to show the user the complete workflow. Use `TaskCreate` to build the task list:

```
# Create configuration summary task (already completed)
TaskCreate:
  subject: "Configuration complete"
  description: |
    - Problem: [PROBLEM_FILE_PATH]
    - Judges: [REVIEW_MODELS count] model(s)
    - Iterations: [NUM_ITERATIONS]
    - Background: [total source count] sources configured
  activeForm: "Configuring"

# Mark it completed immediately
TaskUpdate:
  taskId: [CONFIG_TASK_ID]
  status: completed

# Create background task (skip if [SKIP_BACKGROUND] = true)
TaskCreate:
  subject: "Gather background context"
  description: |
    Sources:
    - Current repo: [Yes/No]
    - Local repos: [LOCAL_REPO_PATHS count] paths
    - GitHub repos: [GITHUB_REPO_URLS count] URLs
    - Local docs: [LOCAL_DOC_PATHS count] files
    - Remote URLs: [REMOTE_URLS count] URLs
    - Web search: [WEB_SEARCH_QUERIES count] queries
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
- `[CONFIG_TASK_ID]` = ID of the configuration task
- `[BACKGROUND_TASK_ID]` = ID of the background task
- `[IDEA_TASK_IDS]` = list of idea task IDs
- `[SUMMARY_TASK_ID]` = ID of the summary task

---

## Step 5: Create Research Document with Background (Background Agent)

**First, mark the background task as in-progress:**
```
TaskUpdate:
  taskId: [BACKGROUND_TASK_ID]
  status: in_progress
```

**Conditional based on `[BACKGROUND_MODE]`:**

### If `[BACKGROUND_MODE]` = "skip":
Create a minimal research document with just the problem statement:
```
Task tool:
  description: "Create minimal research doc"
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    Create [RESEARCH_FILE] with:
    - Problem statement from [PROBLEM_FILE_PATH]
    - Empty "# Background" section (user chose to skip)
```

### If `[BACKGROUND_MODE]` = "user":
Ask the user for their background context:
```
AskUserQuestion:
  questions:
    - question: "Please provide your background context (paste text or provide a file path):"
      header: "Background"
      multiSelect: false
      options:
        - label: "I'll paste it in the next message"
          description: "Type or paste your background context"
        - label: "Read from file"
          description: "I'll provide a file path to read from"
```

Then create the research document with user-provided background.

### If `[BACKGROUND_MODE]` = "auto":
Launch a background agent to auto-generate background using the `_summarize-problem-context` skill, which will guide the user through selecting multiple context sources (repositories, papers, etc.):

```
Task tool:
  description: "Generate background summary"
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    Run the /_summarize-problem-context skill with argument: [PROBLEM_FILE_PATH]

    This skill will:
    1. Ask the user about context sources (current repo, other repos, papers/URLs)
    2. Launch PARALLEL background agents for each source
    3. Collect and synthesize all summaries into [RESEARCH_FILE]
```

**Wait for the background agent to complete** before proceeding. Use `Read` to verify `[RESEARCH_FILE]` exists.

**Mark background task as completed:**
```
TaskUpdate:
  taskId: [BACKGROUND_TASK_ID]
  status: completed
```

---

## Step 6: Generate and Review Ideas (Background Agents)

**Conditional based on `[REVIEW_MODELS]`:**

### If `[REVIEW_MODELS]` is empty (no external reviews):
Generate ideas without external reviews:
```
Task tool:
  description: "Generate ideas (no reviews)"
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    Run the /_generate-ideas skill with arguments: [RESEARCH_FILE] [NUM_ITERATIONS]

    Generate [NUM_ITERATIONS] ideas, each building on the previous.
    Skip external reviews - just generate and refine ideas based on self-analysis.

    **Progress tracking task IDs:**
    - Idea task IDs: [IDEA_TASK_IDS]  # e.g., [2, 3, 4]
    - Summary task ID: [SUMMARY_TASK_ID]

    Update each idea task status as you work on it.
```

### If `[REVIEW_MODELS]` has models (with reviews):
Launch a background agent to generate ideas and collect reviews **in parallel**:

```
Task tool:
  description: "Generate and review ideas"
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    Run the /_generate-ideas skill with arguments: [RESEARCH_FILE] [NUM_ITERATIONS]

    For each idea iteration, launch review agents IN PARALLEL using the Task tool.

    Models to use: [REVIEW_MODELS]  # e.g., ["aws/claude-opus-4-6", "Azure/gpt-4o"]

    **Progress tracking task IDs:**
    - Idea task IDs: [IDEA_TASK_IDS]  # e.g., [2, 3, 4]
    - Summary task ID: [SUMMARY_TASK_ID]

    For each model in [REVIEW_MODELS], launch IN PARALLEL:
      Task tool:
        description: "Review idea with [MODEL_NAME]"
        subagent_type: general-purpose
        run_in_background: true
        prompt: |
          Run /_review-plan [RESEARCH_FILE] [MODEL_NAME]
          Return the review content.

    Wait for all review agents to complete, then append their feedback to [RESEARCH_FILE].

    IMPORTANT: Complete all reviews for idea N before generating idea N+1.
    Update the corresponding idea task description with sub-status as reviews complete.
```

**If reviews fail with 404 or 400 errors**, display:
```
═══════════════════════════════════════════════════════════
  ⚠️  Review Failed - Check Your Configuration
═══════════════════════════════════════════════════════════

  Make sure your API credentials are configured correctly.
  For LiteLLM proxy users, ensure ANTHROPIC_BASE_URL points
  to your proxy, NOT directly to api.anthropic.com.

  Run the connectivity check again to diagnose:
    ~/.claude/skills/review-plan/scripts/review.sh --check-models
═══════════════════════════════════════════════════════════
```

---

## Step 7: Monitor Progress

While background agents are running:
1. Use `TaskOutput` with `block: false` to check progress
2. Report status updates to the user
3. Wait for completion before reporting final results

# OUTPUT

A single file `[RESEARCH_FILE]` containing the complete research progression:

```
# Research Document

## Problem Statement
[original problem from user]

---

# Background
[repository context]

---

# Idea 1
[first idea]
## Reviews for Idea 1
### Review by Claude
### Review by GPT-4o
### Review by Gemini

---

# Idea 2
[improved idea based on Idea 1 feedback]
## Reviews for Idea 2
...

---

# Idea 3
[further refined idea]
## Reviews for Idea 3
...

---

# Executive Summary
[comparison, consensus, recommendation, next steps]
```

This single document shows the complete evolution of ideas and how each iteration addresses previous feedback.
