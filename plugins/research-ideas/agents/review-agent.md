---
name: review-agent
description: Runs plan reviews via external LLM APIs. Use for background review tasks in research-ideas workflow.
tools: Bash, Read
skills:
  - _review-plan
---

# Review Agent

A specialized agent for running plan reviews against external LLM APIs.

## Purpose

This agent exists to enable parallel background reviews in the `/research-ideas` workflow. It has minimal permissions:
- **Bash**: Required to run `review.sh` if skill invocation fails
- **Read**: To read plan content if needed
- **Skill `_review-plan`**: The primary interface for running reviews

## Usage

Spawned automatically by the `/research-ideas` skill when running parallel reviews:

```yaml
Task tool:
  description: "Review idea with [MODEL_NAME]"
  subagent_type: review-agent
  run_in_background: true
  prompt: |
    Run /_review-plan [RESEARCH_FILE] [MODEL_NAME]
    Return the review content.
```

## Why This Agent Exists

Background agents spawned via the Task tool have restricted permissions by default. The `general-purpose` agent type cannot invoke Skills without `bypassPermissions` mode, which grants overly broad access.

This custom agent provides scoped permissions: only the tools and skills needed for reviews.
