---
name: _background-summary
description: Create research document with problem statement and repository context
user-invocable: false
---

# ARGUMENTS

- `[PROBLEM_FILE_PATH]` (required): Path to a file containing the problem statement

# DERIVED PATHS

- `[PROBLEM_DIR]` = directory containing the problem file
- `[OUTPUT_FILE]` = `[PROBLEM_DIR]/research.md`

# TASK

Read the problem statement from `[PROBLEM_FILE_PATH]`, explore the repository to understand its structure and relevant code, then create `[OUTPUT_FILE]` containing both the problem statement and background context.

# STEPS

## Step 1: Read the Problem Statement

Read and understand the problem statement from `[PROBLEM_FILE_PATH]`. Identify:
- The core problem being addressed
- Key technical domains involved
- Specific components, modules, or areas that may be relevant

## Step 2: Explore the Repository

Using the problem statement as your guide, explore the repository to gather relevant context:

1. **Repository Structure**: Get an overview of the project layout
   - List top-level directories and key files
   - Identify the technology stack (languages, frameworks, tools)

2. **Relevant Code Areas**: Based on the problem statement, identify and explore:
   - Components directly related to the problem
   - Dependencies and integrations that may be affected
   - Configuration files relevant to the problem domain

3. **Documentation**: Check for existing documentation that provides context:
   - README files
   - Architecture documents
   - API documentation
   - Inline code comments in relevant areas

## Step 3: Create research.md

Create `[OUTPUT_FILE]` with the following structure:

```markdown
# Research Document

## Problem Statement

[Copy the ENTIRE content from [PROBLEM_FILE_PATH] verbatim here]

---

# Background

## Repository Overview
[Brief description of what this repository is and its purpose]

## Technology Stack
[Languages, frameworks, key dependencies]

## Relevant Architecture
[High-level architecture relevant to the problem - components, data flow, etc.]

## Key Files and Components
[List of files/modules most relevant to the problem with brief descriptions]

## Existing Patterns and Conventions
[Code patterns, naming conventions, or architectural decisions relevant to the problem]

## Dependencies and Integrations
[External systems, APIs, or services relevant to the problem]

## Additional Context
[Any other information that would help someone understand the codebase in relation to the problem]

---

```

**IMPORTANT**: The file ends with `---` followed by a blank line. This is where subsequent ideas and reviews will be appended.

# GUIDELINES

- **Stay focused**: Only include information relevant to the problem statement. Avoid documenting unrelated parts of the codebase.
- **Be concise**: Provide enough context to understand the problem space without overwhelming detail.
- **Be specific**: Reference actual file paths, function names, and code patterns found in the repository.
- **Prioritize**: Put the most important context first. Someone reading should quickly understand the relevant parts of the codebase.
