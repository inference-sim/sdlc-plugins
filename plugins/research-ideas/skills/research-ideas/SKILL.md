---
name: research-ideas
description: Generate iteratively-reviewed research ideas from a problem statement. One command creates a complete research document.
argument-hint: <problem_file_path> [num_iterations]
allowed-tools:
  - Task
  - AskUserQuestion
  - TaskCreate
  - TaskUpdate
  - TaskList
  - TaskGet
  - Skill(_summarize-problem-context *)
  - Skill(_generate-ideas *)
  - Skill(_review-plan *)
  - Bash(.claude/skills/review-plan/scripts/review.sh *)
  - Bash(python3 *)
  - Bash(curl *)
  - Bash(jq *)
---
# ARGUMENTS

- `[PROBLEM_FILE_PATH]` (required): Path to a markdown file containing the problem statement
- `[NUM_ITERATIONS]` (optional, default: 3): Number of ideas to generate and review

# DERIVED PATHS

- `[PROBLEM_DIR]` = directory containing the problem file
- `[RESEARCH_FILE]` = `[PROBLEM_DIR]/research.md`

# TASK

Generate creative, novel, and practical research ideas for the given problem statement. Each idea is reviewed by multiple AI models and feedback is used to improve subsequent ideas. Everything is written to a single research document.

**All stages run as background agents** to provide progress visibility and enable parallel execution where possible.

# STEPS

## Step 0: Prerequisites Questionnaire

**IMPORTANT: Always start by asking these questions using `AskUserQuestion`.**

Ask the user these questions to configure the workflow:

### Question 1: Background Context

```
AskUserQuestion:
  questions:
    - question: "Do you already have background context to include in the research document?"
      header: "Background"
      multiSelect: false
      options:
        - label: "No, auto-generate from repository (Recommended)"
          description: "Analyze the codebase to generate relevant context automatically"
        - label: "Yes, I'll provide my own background"
          description: "Skip auto-generation; I have context to paste or reference"
        - label: "Skip background entirely"
          description: "Start generating ideas without background context"
```

### Question 2: API Configuration

```
AskUserQuestion:
  questions:
    - question: "Which API configuration do you have for external reviews?"
      header: "API Setup"
      multiSelect: false
      options:
        - label: "LiteLLM proxy (Recommended)"
          description: "I have a LiteLLM proxy that can route to Claude, GPT, and Gemini"
        - label: "OpenAI API key only"
          description: "I have OPENAI_API_KEY set; use only GPT models for review"
        - label: "Anthropic via proxy"
          description: "I have ANTHROPIC_AUTH_TOKEN with an OpenAI-compatible proxy (NOT api.anthropic.com)"
        - label: "Skip external reviews"
          description: "Generate ideas without external model reviews"
```

### Question 3: Review Models (based on API config)

If user selected "LiteLLM proxy":
```
AskUserQuestion:
  questions:
    - question: "Which models should review each idea?"
      header: "Reviewers"
      multiSelect: true
      options:
        - label: "Claude (aws/claude-opus-4-6)"
          description: "Anthropic's Claude Opus for thorough analysis"
        - label: "GPT-4o (Azure/gpt-4o)"
          description: "OpenAI's GPT-4o for alternative perspective"
        - label: "Gemini (GCP/gemini-2.5-flash)"
          description: "Google's Gemini for fast, diverse feedback"
```

If user selected "OpenAI API key only":
- Default to using only `Azure/gpt-4o` (or `gpt-4o` if using api.openai.com directly)

If user selected "Anthropic via proxy":
- Default to using only `aws/claude-opus-4-6`
- **Warn the user**: "Make sure ANTHROPIC_BASE_URL points to your LiteLLM proxy, NOT api.anthropic.com"

If user selected "Skip external reviews":
- Skip the review step entirely; just generate ideas

### Step 0.4: Verify Model Connectivity (if not skipping reviews)

**IMPORTANT: Run this check before proceeding to idea generation.**

If `[API_CONFIG]` is NOT "skip", run the connectivity check:

```bash
# Test connectivity to selected models
~/.claude/skills/review-plan/scripts/review.sh --check-models [REVIEW_MODELS...]
```

For example:
- LiteLLM proxy with all models: `--check-models aws/claude-opus-4-6 Azure/gpt-4o GCP/gemini-2.5-flash`
- OpenAI only: `--check-models Azure/gpt-4o`
- Anthropic proxy: `--check-models aws/claude-opus-4-6`

**If any models fail:**
1. Show the user the error output
2. Ask if they want to:
   - Fix their configuration and retry
   - Remove the failing model(s) from the review list
   - Skip external reviews entirely

```
AskUserQuestion:
  questions:
    - question: "Some models failed connectivity check. How would you like to proceed?"
      header: "Fix Config"
      multiSelect: false
      options:
        - label: "I'll fix my configuration and retry"
          description: "Exit and reconfigure your API credentials/proxy"
        - label: "Continue without failed models"
          description: "Use only the models that passed the check"
        - label: "Skip external reviews"
          description: "Generate ideas without any external model reviews"
```

### Store User Selections

After questions, store selections as:
- `[HAS_CUSTOM_BACKGROUND]` = true/false
- `[SKIP_BACKGROUND]` = true/false
- `[API_CONFIG]` = "litellm" | "openai" | "anthropic-proxy" | "skip"
- `[REVIEW_MODELS]` = list of models to use (e.g., ["aws/claude-opus-4-6", "Azure/gpt-4o"])

---

## Step 0.5: Create Progress Dashboard

**Create all tasks upfront** to show the user what stages will execute. Use `TaskCreate` to build the task list:

```
# Create background task
TaskCreate:
  subject: "Generate background context"
  description: "Analyze repository and create research document with problem statement and context"
  activeForm: "Generating background context"

# Create idea tasks (one per iteration)
For i = 1 to [NUM_ITERATIONS]:
  TaskCreate:
    subject: "Idea [i]"
    description: "Generate idea [i] and collect reviews"
    activeForm: "Working on Idea [i]"

# Create summary task
TaskCreate:
  subject: "Executive summary"
  description: "Synthesize all ideas and reviews into final recommendations"
  activeForm: "Writing executive summary"
```

**Store the task IDs** for later updates:
- `[BACKGROUND_TASK_ID]` = ID of the background task
- `[IDEA_TASK_IDS]` = list of idea task IDs (e.g., [2, 3, 4] for 3 iterations)
- `[SUMMARY_TASK_ID]` = ID of the summary task

---

## Step 1: Create Research Document with Background (Background Agent)

**First, mark the background task as in-progress:**
```
TaskUpdate:
  taskId: [BACKGROUND_TASK_ID]
  status: in_progress
```

**Conditional based on `[HAS_CUSTOM_BACKGROUND]` and `[SKIP_BACKGROUND]`:**

### If `[SKIP_BACKGROUND]` = true:
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

### If `[HAS_CUSTOM_BACKGROUND]` = true:
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

### If `[HAS_CUSTOM_BACKGROUND]` = false and `[SKIP_BACKGROUND]` = false (default):
Launch a background agent to auto-generate background:

```
Task tool:
  description: "Generate background summary"
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    Run the /_summarize-problem-context skill with argument: [PROBLEM_FILE_PATH]

    This will create [RESEARCH_FILE] containing the problem statement and repository context.
```

**Wait for the background agent to complete** before proceeding. Use `Read` to verify `[RESEARCH_FILE]` exists.

**Mark background task as completed:**
```
TaskUpdate:
  taskId: [BACKGROUND_TASK_ID]
  status: completed
```

## Step 2: Generate and Review Ideas (Background Agent)

**Conditional based on `[API_CONFIG]` and `[REVIEW_MODELS]`:**

### If `[API_CONFIG]` = "skip":
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

### Otherwise (with reviews):
Launch a background agent to generate ideas and collect reviews:

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

    For each model in [REVIEW_MODELS]:
      Task tool:
        description: "Review idea with [MODEL_NAME]"
        subagent_type: review-agent  # Custom agent with scoped permissions for _review-plan skill
        run_in_background: true
        prompt: |
          Run /_review-plan [RESEARCH_FILE] [MODEL_NAME]

          Return the review content.

    Wait for all review agents to complete, then append their feedback to [RESEARCH_FILE].

    IMPORTANT: Complete all reviews for idea N before generating idea N+1.
    Update the corresponding idea task description with sub-status as reviews complete.
```

**Note for "anthropic-proxy" users:** If reviews fail with 404 or 400 errors, display:
```
═══════════════════════════════════════════════════════════
  ⚠️  Review Failed - Check Your Configuration
═══════════════════════════════════════════════════════════

  Make sure ANTHROPIC_BASE_URL points to your LiteLLM proxy,
  NOT directly to api.anthropic.com.

  Example:
    export ANTHROPIC_BASE_URL='http://localhost:4000'

  Run '/review-plan --dry-run' to verify your setup.
═══════════════════════════════════════════════════════════
```

## Step 3: Monitor Progress

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
