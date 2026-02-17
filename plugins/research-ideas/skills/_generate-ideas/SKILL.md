---
name: _generate-ideas
description: Generate and review research ideas, appending each iteration to the research document
argument-hint: <research_file_path> [num_iterations]
allowed-tools:
  - Skill(_review-plan *)
  - Bash(.claude/skills/review-plan/scripts/review.sh *)
  - Bash(python3 *)
  - Bash(curl *)
  - Bash(jq *)
---
# ARGUMENTS

- `[RESEARCH_FILE_PATH]` (required): Path to `research.md` (created by `/_background-summary`)
- `[NUM_ITERATIONS]` (optional, default: 3): Number of ideas to generate

# PREREQUISITES

The `[RESEARCH_FILE_PATH]` must exist and contain:
- Problem statement
- Background context

This file is created by running `/_background-summary` first.

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

## Step 4: Get Reviews (parallel within this step only)

Ask 3 judges to review idea-<i> **in parallel** using the /_review-plan skill.

**IMPORTANT**: Pass the ENTIRE `[RESEARCH_FILE_PATH]` to each reviewer. The file now contains problem + background + the new idea.

Each judge should use a different model:
- aws/claude-opus-4-6
- Azure/gpt-4o
- GCP/gemini-2.5-flash

YOU MUST USE THE /_review-plan SKILL AND INVOKE ALL THREE MODELS. The judges must provide independent review feedback.

## Step 5: Append Reviews

**WAIT for ALL reviewers to complete.** Then append each reviewer's feedback to `[RESEARCH_FILE_PATH]`:

```markdown
### Review by [Model Name]

[Reviewer feedback]

```

## Step 6: Verify Completion (BLOCKING)

**DO NOT proceed to iteration i+1 until:**
- `[RESEARCH_FILE_PATH]` contains Idea <i> AND all reviewer feedback
- You have read and understood the feedback to inform the next idea

Only after confirming step 6 is complete, proceed to iteration i+1.

---

# FINAL STEP: Executive Summary

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
