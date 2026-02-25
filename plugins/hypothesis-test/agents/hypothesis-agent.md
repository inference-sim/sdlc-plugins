---
name: hypothesis-agent
description: Background agent for hypothesis experimentation. Has scoped access to all internal hypothesis-test skills.
tools: Read, Write, Edit, Glob, Grep, Bash
skills:
  - _formulate-hypothesis
  - _scaffold-experiment
  - _run-and-analyze
  - _document-findings
---

# Hypothesis Agent

A specialized agent for running hypothesis experimentation tasks in the background.

## Purpose

This agent exists to enable parallel background hypothesis generation, experiment scaffolding, and testing in the `/hypothesis-test` workflow. It has scoped permissions to invoke the 4 internal skills without requiring `bypassPermissions` mode.

## Usage

Spawned automatically by the `/hypothesis-test` orchestrator:

```yaml
Task tool:
  subagent_type: hypothesis-agent
  run_in_background: true
  prompt: "Run /_formulate-hypothesis [args]"
```
