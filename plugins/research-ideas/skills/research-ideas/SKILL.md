---
name: research-ideas
description: Generate iteratively-reviewed research ideas from a problem statement. One command creates a complete research document.
argument-hint: <problem_file_path> [num_iterations]
allowed-tools:
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

# STEPS

## Step 1: Create Research Document with Background

Invoke the _background-summary skill:

```
/_background-summary [PROBLEM_FILE_PATH]
```

This creates `[RESEARCH_FILE]` containing:
- The problem statement (copied from input file)
- Background context from exploring the repository

## Step 2: Generate and Review Ideas

Invoke the _generate-ideas skill:

```
/_generate-ideas [RESEARCH_FILE] [NUM_ITERATIONS]
```

This appends to `[RESEARCH_FILE]`:
- Each idea with full content
- Reviews from 3 AI models (Claude, GPT-4o, Gemini) for each idea
- Executive summary with recommendations

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
