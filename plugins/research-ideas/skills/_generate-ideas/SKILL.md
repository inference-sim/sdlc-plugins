---
name: _generate-ideas
description: Generate and review research ideas, appending each iteration to the research document
user-invocable: false
allowed-tools:
  - Task
  - TaskUpdate
  - TaskGet
  - Read
  - Write
  - Skill(review-plan *)
---
# ARGUMENTS

- `[RESEARCH_FILE_PATH]` (required): Path to `research.md` (created by `/_summarize-problem-context`)
- `[NUM_ITERATIONS]` (optional, default: 3): Number of ideas to generate

# PROGRESS TRACKING

The parent skill passes task IDs for progress tracking:
- `[IDEA_TASK_IDS]`: List of task IDs, one per idea iteration (e.g., [2, 3, 4])
- `[SUMMARY_TASK_ID]`: Task ID for the executive summary

**Use these to update the dashboard as work progresses.** If task IDs are not provided, skip progress updates.

# PREREQUISITES

The `[RESEARCH_FILE_PATH]` must exist and contain:
- Problem statement
- Background context

This file is created by running `/_summarize-problem-context` first.

# TASK

Generate ideas to solve the problem, appending each idea and its reviews to `[RESEARCH_FILE_PATH]`.

# STEPS

**CRITICAL CONSTRAINT: Each iteration MUST fully complete (including all reviews and feedback) before starting the next iteration. This ensures each new idea can build on feedback from all previous ideas.**

For i = 1 to [NUM_ITERATIONS], execute the following steps **strictly sequentially**:

## Step 1: Read Current Document

Read `[RESEARCH_FILE_PATH]` to understand:
- The problem statement
- Background context
- ALL previously generated ideas and their reviews (if any)

## Step 2: Generate Idea i

**Mark the idea task as in-progress with generating status:**
```
TaskUpdate:
  taskId: [IDEA_TASK_IDS][i-1]  # 0-indexed
  status: in_progress
  description: "Generating idea..."
```

Generate an idea to solve the problem using:
- The problem statement and background from the document
- ALL previously generated ideas AND their reviewer feedback

The new idea should address weaknesses identified in previous ideas' reviews.

## Step 3: Append Idea i

Append the idea to `[RESEARCH_FILE_PATH]` using this format:

```markdown
# Idea <i>

[Full idea content here]

## Reviews for Idea <i>

```

## Step 4: Get Reviews (3 parallel background agents)

**Update task to show review collection in progress:**
```
TaskUpdate:
  taskId: [IDEA_TASK_IDS][i-1]
  description: "Collecting reviews: 0/[NUM_REVIEWERS] complete"
```

Launch 3 background agents **in parallel** to review idea-<i>. Use the Task tool with `run_in_background: true` for each:

```
# Launch all 3 in a SINGLE message with 3 Task tool calls:

Task tool #1:
  description: "Review with Claude"
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    Run /review-plan [RESEARCH_FILE_PATH] aws/claude-opus-4-6
    Return the full review content.

Task tool #2:
  description: "Review with GPT-4o"
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    Run /review-plan [RESEARCH_FILE_PATH] Azure/gpt-4o
    Return the full review content.

Task tool #3:
  description: "Review with Gemini"
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    Run /review-plan [RESEARCH_FILE_PATH] GCP/gemini-2.5-flash
    Return the full review content.
```

**IMPORTANT**:
- Pass the ENTIRE `[RESEARCH_FILE_PATH]` to each reviewer (contains problem + background + new idea)
- Launch all 3 Task calls in a SINGLE message to maximize parallelism
- Each agent runs the /review-plan skill with a different model

## Step 5: Collect and Append Reviews

**WAIT for ALL background agents to complete** using `TaskOutput` for each task_id.

**As each review completes, update the task description:**
```
# After each TaskOutput returns successfully:
TaskUpdate:
  taskId: [IDEA_TASK_IDS][i-1]
  description: "Collecting reviews: [COMPLETED]/[NUM_REVIEWERS] complete"
```

Once all reviews are collected, append each reviewer's feedback to `[RESEARCH_FILE_PATH]`:

```markdown
### Review by Claude (aws/claude-opus-4-6)

[Claude's review feedback]

### Review by GPT-4o (Azure/gpt-4o)

[GPT-4o's review feedback]

### Review by Gemini (GCP/gemini-2.5-flash)

[Gemini's review feedback]

```

## Step 6: Verify Completion (BLOCKING)

**DO NOT proceed to iteration i+1 until:**
- `[RESEARCH_FILE_PATH]` contains Idea <i> AND all reviewer feedback
- You have read and understood the feedback to inform the next idea

**Mark the idea task as completed:**
```
TaskUpdate:
  taskId: [IDEA_TASK_IDS][i-1]
  status: completed
  description: "Idea generated and reviewed"
```

Only after confirming step 6 is complete, proceed to iteration i+1.

---

# FINAL STEP: Executive Summary

**Mark the summary task as in-progress:**
```
TaskUpdate:
  taskId: [SUMMARY_TASK_ID]
  status: in_progress
```

After ALL [NUM_ITERATIONS] iterations are complete, append to `[RESEARCH_FILE_PATH]`:

```markdown
---

# Executive Summary

## Ideas Overview
[One-paragraph summary of each idea generated]

## Comparison Table
[Side-by-side comparison of all ideas across key dimensions]

## Reviewer Consensus
[Key themes and agreements across all reviewer feedback]

## Recommendation
[Which idea (or combination) is recommended and why]

## Next Steps
[Concrete actions to pursue the recommended approach]
```

**Mark the summary task as completed:**
```
TaskUpdate:
  taskId: [SUMMARY_TASK_ID]
  status: completed
```

# FINAL DOCUMENT STRUCTURE

After completion, `[RESEARCH_FILE_PATH]` contains everything in one file:

```
# Research Document
## Problem Statement
[original problem]

---

# Background
[repository context]

---

# Idea 1
[idea content]
## Reviews for Idea 1
### Review by Claude
### Review by GPT-4o
### Review by Gemini

---

# Idea 2
[idea content - addresses feedback from Idea 1]
## Reviews for Idea 2
...

---

# Executive Summary
[comparison and recommendations]
```
