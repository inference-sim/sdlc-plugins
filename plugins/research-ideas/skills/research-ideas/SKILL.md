---
name: research-ideas
description: Generate iteratively-reviewed research ideas from a problem statement. One command creates a complete research document.
argument-hint: <problem_file_path> [num_iterations]
allowed-tools:
  - Task
  - Skill(_background-summary *)
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

## Step 1: Create Research Document with Background (Background Agent)

Launch a background agent to create the initial research document:

```
Task tool:
  description: "Generate background summary"
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    Run the /_background-summary skill with argument: [PROBLEM_FILE_PATH]

    This will create [RESEARCH_FILE] containing the problem statement and repository context.
```

**Wait for the background agent to complete** before proceeding. Use `Read` to verify `[RESEARCH_FILE]` exists.

## Step 2: Generate and Review Ideas (Background Agent)

Launch a background agent to generate ideas and collect reviews:

```
Task tool:
  description: "Generate and review ideas"
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    Run the /_generate-ideas skill with arguments: [RESEARCH_FILE] [NUM_ITERATIONS]

    For each idea iteration, launch 3 review agents IN PARALLEL using the Task tool:

    For each of these models: aws/claude-opus-4-6, Azure/gpt-4o, GCP/gemini-2.5-flash
      Task tool:
        description: "Review idea with [MODEL_NAME]"
        subagent_type: general-purpose
        run_in_background: true
        prompt: |
          Run /_review-plan [RESEARCH_FILE] [MODEL_NAME]
          Return the review content.

    Wait for all 3 review agents to complete, then append their feedback to [RESEARCH_FILE].

    IMPORTANT: Complete all reviews for idea N before generating idea N+1.
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
