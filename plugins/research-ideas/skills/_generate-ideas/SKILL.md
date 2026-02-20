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
- `[REVIEW_MODELS]` (required): List of model IDs selected by user (e.g., ["aws/claude-opus-4-6", "Azure/gpt-4o"])

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

**IMPORTANT - Holistic Coverage:**
- If the problem statement contains multiple goals, requirements, or objectives, each idea MUST address ALL of them together
- If the problem statement contains limitations, constraints, or challenges, each idea MUST address ALL of them together
- Do NOT generate separate ideas for each goal or limitation - instead, create a single cohesive solution that satisfies all goals and addresses all limitations simultaneously
- The idea should explain how it addresses each goal, how it overcomes each limitation, and how the different aspects work together

The new idea should address weaknesses identified in previous ideas' reviews.

## Step 3: Append Idea i

Append the idea to `[RESEARCH_FILE_PATH]` using this format:

```markdown
# Idea <i>

[Full idea content here]

## Reviews for Idea <i>

```

## Step 4: Get Reviews (parallel background agents)

**Update task to show review collection in progress:**
```
TaskUpdate:
  taskId: [IDEA_TASK_IDS][i-1]
  description: "Collecting reviews: 0/[NUM_REVIEWERS] complete"
```

Launch background agents **in parallel** for ALL models in `[REVIEW_MODELS]`.

**CRITICAL: Launch all reviews in ONE message with MULTIPLE Task tool calls to run them in parallel.**

Example if `[REVIEW_MODELS]` = ["aws/claude-opus-4-6", "Azure/gpt-4o"]:

```
# In a SINGLE message, include MULTIPLE Task tool calls (one per model):

Task tool #1:
  description: "Review with aws/claude-opus-4-6"
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    Run /review-plan [RESEARCH_FILE_PATH] aws/claude-opus-4-6

    IMPORTANT: Return your response in this exact format:
    ---
    MODEL_USED: [the actual model ID that provided this review]
    REVIEW_CONTENT:
    [the full review content]
    ---

    If the requested model fails and you fall back to a different model,
    report the ACTUAL model used, not the originally requested one.

Task tool #2:
  description: "Review with Azure/gpt-4o"
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    Run /review-plan [RESEARCH_FILE_PATH] Azure/gpt-4o

    IMPORTANT: Return your response in this exact format:
    ---
    MODEL_USED: [the actual model ID that provided this review]
    REVIEW_CONTENT:
    [the full review content]
    ---

    If the requested model fails and you fall back to a different model,
    report the ACTUAL model used, not the originally requested one.

# ... one Task tool call per model in [REVIEW_MODELS]
```

**IMPORTANT**:
- **PARALLEL EXECUTION**: All Task tool calls MUST be in ONE message to run concurrently
- Pass the ENTIRE `[RESEARCH_FILE_PATH]` to each reviewer (contains problem + background + new idea)
- Only launch reviews for models in `[REVIEW_MODELS]` (user's selection)
- Each agent MUST report the actual model used in case of fallbacks

## Step 5: Collect and Append Reviews

**WAIT for ALL background agents to complete** using `TaskOutput` for each task_id.

**As each review completes, update the task description:**
```
# After each TaskOutput returns successfully:
TaskUpdate:
  taskId: [IDEA_TASK_IDS][i-1]
  description: "Collecting reviews: [COMPLETED]/[NUM_REVIEWERS] complete"
```

**Parse each response to extract the ACTUAL model used:**
- Look for `MODEL_USED:` in the response to get the actual model ID
- If not found, use the originally requested model ID
- This ensures accuracy when API failures cause fallbacks to different models

Once all reviews are collected, append each reviewer's feedback to `[RESEARCH_FILE_PATH]`:

```markdown
### Review by [ACTUAL_MODEL_USED]

[Review content]

```

**CRITICAL - Truthful Attribution:**
- Use the ACTUAL model that provided the review in the header
- Do NOT use the originally requested model if a different model was used
- If a model was unavailable and another was substituted, reflect the substitution accurately
- Example: If `Azure/gpt-4o` failed and `aws/claude-opus-4-6` was used instead, write "Review by aws/claude-opus-4-6", NOT "Review by Azure/gpt-4o"

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

## Goal Coverage Matrix
[For each goal/requirement in the problem statement, show how each idea addresses it]

## Limitations Coverage Matrix
[For each limitation/constraint in the problem statement, show how each idea addresses it]

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
### Review by [actual-model-1]
### Review by [actual-model-2]
... (one per model in [REVIEW_MODELS] that was actually used)

---

# Idea 2
[idea content - addresses feedback from Idea 1]
## Reviews for Idea 2
...

---

# Executive Summary
[goal coverage matrix, limitations coverage matrix, comparison, and recommendations]
```
