---
name: _summarize-problem-context
description: Create research document with problem statement and context from multiple sources (repositories, papers, files)
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - Task
  - WebFetch
  - litellm_web_search
  - AskUserQuestion
  - Bash(gh *)
---

# ARGUMENTS

- `[PROBLEM_FILE_PATH]` (required): Path to a file containing the problem statement

**Optional pre-configured sources** (if provided, skip asking user):
- `[INCLUDE_CURRENT_REPO]` (optional): true/false - include current repository
- `[LOCAL_REPO_PATHS]` (optional): List of local repository paths
- `[GITHUB_REPO_URLS]` (optional): List of GitHub repository URLs
- `[REMOTE_URLS]` (optional): List of paper/documentation URLs
- `[WEB_SEARCH_QUERIES]` (optional): List of web search queries
- `[SKIP_BACKGROUND]` (optional): true to skip background entirely
- `[OUTPUT_FILE]` (optional): Path for the output file. Defaults to `[PROBLEM_DIR]/research.md`. When set, use this path instead of the default.
- `[DOCUMENT_TITLE]` (optional): Top-level heading for the output document. Defaults to `"Research Document"`. Example: `"Problem Context"`.

**If any optional source arguments are provided, skip Steps 2-3 and proceed directly to Step 4 (Launch Agents).**

# DERIVED PATHS

- `[PROBLEM_DIR]` = directory containing the problem file
- `[OUTPUT_FILE]` = argument value if provided, otherwise `[PROBLEM_DIR]/research.md`

# TASK

Read the problem statement from `[PROBLEM_FILE_PATH]`, gather context from multiple sources (current repository, other repositories, online papers, etc.), then create `[OUTPUT_FILE]` containing the problem statement and all relevant background context.

# STEPS

## Step 1: Read the Problem Statement

Read and understand the problem statement from `[PROBLEM_FILE_PATH]`. Identify:
- The core problem being addressed
- Key technical domains involved
- Specific components, modules, or areas that may be relevant

## Step 2: Ask About Context Sources (Skip if pre-configured)

**If source arguments were provided (any of `[INCLUDE_CURRENT_REPO]`, `[LOCAL_REPO_PATHS]`, `[GITHUB_REPO_URLS]`, `[REMOTE_URLS]`, `[WEB_SEARCH_QUERIES]`), skip Steps 2-3 and proceed directly to Step 4.**

**If `[SKIP_BACKGROUND]` = true, skip to Step 5 and create a minimal document with just the problem statement.**

**Otherwise, current repository is included by default.** Ask about additional sources:

```
AskUserQuestion:
  questions:
    - question: "The current repository will be analyzed by default. Do you want to add more context sources?"
      header: "Context"
      multiSelect: true
      options:
        - label: "Add other local repositories"
          description: "Include related code from other local directories"
        - label: "Add GitHub repositories"
          description: "Include remote GitHub repos (will be fetched via API)"
        - label: "Add papers or URLs"
          description: "Include arXiv papers, docs, blog posts, or other web content"
        - label: "Search the web for relevant content"
          description: "Use web search to find papers and resources related to the problem"
```

**Store results:**
- `[INCLUDE_CURRENT_REPO]` = true (always default)
- `[ADD_LOCAL_REPOS]` = true if first option selected
- `[ADD_GITHUB_REPOS]` = true if second option selected
- `[ADD_PAPERS]` = true if third option selected
- `[ADD_WEB_SEARCH]` = true if fourth option selected

## Step 3: Gather Source Details

### 3.1: Collect Local Repository Paths (if `[ADD_LOCAL_REPOS]` is true)

```
AskUserQuestion:
  questions:
    - question: "Enter the paths to local repositories (use 'Other' to type paths, one per line or comma-separated):"
      header: "Local Repos"
      multiSelect: false
      options:
        - label: "I'll provide the paths"
          description: "Enter absolute paths like /Users/me/projects/my-repo"
        - label: "Let me browse first"
          description: "I need to check which local repos are relevant"
```

**If user selects "I'll provide the paths":**
- The user will type paths in the "Other" text field
- Parse the input (split by newlines or commas)
- Validate each path exists and is a directory
- Store as `[LOCAL_REPO_PATHS]` (list of valid paths)
- Report any invalid paths to the user

### 3.2: Collect GitHub Repository URLs (if `[ADD_GITHUB_REPOS]` is true)

```
AskUserQuestion:
  questions:
    - question: "Enter GitHub repository URLs (use 'Other' to type URLs, one per line or comma-separated):"
      header: "GitHub Repos"
      multiSelect: false
      options:
        - label: "I'll provide the URLs"
          description: "Enter URLs like https://github.com/owner/repo or owner/repo shorthand"
        - label: "Let me look them up first"
          description: "I need to find the relevant GitHub repos"
```

**If user selects "I'll provide the URLs":**
- The user will type URLs in the "Other" text field
- Parse the input (split by newlines or commas)
- Normalize URLs (e.g., "owner/repo" → "https://github.com/owner/repo")
- Store as `[GITHUB_REPO_URLS]` (list of normalized URLs)

### 3.3: Collect Paper/Documentation URLs (if `[ADD_PAPERS]` is true)

```
AskUserQuestion:
  questions:
    - question: "Enter URLs to papers or documentation (use 'Other' to type URLs, one per line or comma-separated):"
      header: "Paper URLs"
      multiSelect: false
      options:
        - label: "I'll provide the URLs"
          description: "Enter URLs to arXiv, papers, docs, blog posts, etc."
        - label: "I'll paste content instead"
          description: "I'll copy-paste the relevant content directly in a follow-up"
```

**If user selects "I'll provide the URLs":**
- The user will type URLs in the "Other" text field
- Parse the input (split by newlines or commas)
- Store as `[PAPER_URLS]` (list of URLs)

**If user selects "I'll paste content instead":**
- Set `[PASTE_PAPER_CONTENT]` = true
- After all questions, prompt user: "Please paste the paper/documentation content:"
- Store pasted content as `[PASTED_CONTENT]`

### 3.4: Configure Web Search (if `[ADD_WEB_SEARCH]` is true)

```
AskUserQuestion:
  questions:
    - question: "What topics should I search for? (Enter custom queries or use auto-generated)"
      header: "Web Search"
      multiSelect: false
      options:
        - label: "Auto-generate search queries (Recommended)"
          description: "I'll derive search terms from your problem statement"
        - label: "I'll provide specific queries"
          description: "Enter your own search terms in the text field"
```

**If auto-generate selected:**
- Generate 3-5 search queries based on problem statement keywords
- Store as `[WEB_SEARCH_QUERIES]` (list of query strings)

**If user provides queries:**
- Parse user input (split by newlines or commas)
- Store as `[WEB_SEARCH_QUERIES]`

## Step 3.5: Confirm Sources Summary

**Display a summary of collected sources and ask for confirmation:**

```
Summarize what will be analyzed:
- Current repository: [Yes/No]
- Local repositories: [count] paths
  - /path/to/repo1
  - /path/to/repo2
- GitHub repositories: [count] URLs
  - https://github.com/owner/repo1
  - https://github.com/owner/repo2
- Papers/Documentation: [count] URLs
  - https://arxiv.org/...
  - https://...

AskUserQuestion:
  questions:
    - question: "Does this look correct? Ready to generate background?"
      header: "Confirm"
      multiSelect: false
      options:
        - label: "Yes, proceed"
          description: "Generate background from these sources"
        - label: "No, let me modify"
          description: "Go back and change the source list"
```

**If user selects "No, let me modify":**
- Return to Step 2 to re-collect sources

**Validation:** At least one source must be selected. If no sources are selected (current repo is off, no other repos, no papers), prompt:
```
AskUserQuestion:
  questions:
    - question: "No context sources selected. What would you like to do?"
      header: "No Sources"
      multiSelect: false
      options:
        - label: "Include current repository"
          description: "Add the current repo as the only context source"
        - label: "Let me add sources"
          description: "Go back and specify repositories or papers to include"
        - label: "Skip background entirely"
          description: "Generate ideas without any background context"
```

## Step 4: Launch Parallel Background Agents

**Launch independent background agents for each context source.** This allows concurrent summarization for faster results.

### 4.1: Current Repository Agent (if `[INCLUDE_CURRENT_REPO]` is true)

```
Task tool:
  description: "Summarize current repository"
  subagent_type: Explore
  run_in_background: true
  prompt: |
    Analyze the current repository to gather context relevant to this problem:

    [Insert problem statement summary here]

    Explore and summarize:
    1. Repository Structure: Top-level directories, technology stack
    2. Relevant Code Areas: Components related to the problem
    3. Documentation: README, architecture docs, API docs
    4. Patterns and Conventions: Code patterns relevant to the problem

    Return a structured summary in markdown format with sections:
    - Repository Overview
    - Technology Stack
    - Relevant Architecture
    - Key Files and Components
    - Existing Patterns
```

Store agent ID as `[CURRENT_REPO_AGENT_ID]` (or null if not included).

### 4.2: Local Repository Agents (if `[LOCAL_REPO_PATHS]` is non-empty)

**For each path in `[LOCAL_REPO_PATHS]`:**
```
Task tool:
  description: "Summarize local repo: [REPO_NAME]"
  subagent_type: Explore
  run_in_background: true
  prompt: |
    Analyze the repository at [REPO_PATH] to gather context relevant to this problem:

    [Insert problem statement summary here]

    Explore and summarize:
    1. Repository purpose and structure
    2. Technology stack and dependencies
    3. Components or patterns relevant to the problem
    4. How this repository relates to the main problem

    Return a structured summary in markdown format.
```

Store agent IDs as `[LOCAL_REPO_AGENT_IDS]` (list).

### 4.3: GitHub Repository Agents (if `[GITHUB_REPO_URLS]` is non-empty)

**For each URL in `[GITHUB_REPO_URLS]`:**
```
Task tool:
  description: "Summarize GitHub repo: [REPO_NAME]"
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    Explore and summarize the GitHub repository at: [GITHUB_URL]

    Use the GitHub CLI to explore the remote repository:
    1. `gh repo view [OWNER/REPO] --json description,readme` - get basic info and README
    2. `gh api repos/[OWNER]/[REPO]/contents` - list top-level structure
    3. `gh api repos/[OWNER]/[REPO]/contents/[PATH]` - fetch specific files
    4. Look for key files: README.md, package.json, requirements.txt, go.mod, pyproject.toml, etc.

    Focus on extracting information relevant to this problem:
    [Insert problem statement summary here]

    Explore and summarize:
    1. Repository purpose and description
    2. Technology stack and dependencies
    3. Architecture and key components
    4. How this repository relates to the main problem

    Return a structured summary in markdown format with sections:
    - Repository Overview
    - Technology Stack
    - Relevant Architecture
    - Key Files and Components
```

Store agent IDs as `[GITHUB_REPO_AGENT_IDS]` (list).

### 4.4: Paper/URL Agents (if `[PAPER_URLS]` is non-empty)

**For each URL in `[PAPER_URLS]`:**
```
Task tool:
  description: "Summarize paper: [URL_TITLE]"
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    Fetch and summarize the content at this URL: [URL]

    Use the WebFetch tool to retrieve the content.

    Focus on extracting information relevant to this problem:
    [Insert problem statement summary here]

    Summarize:
    1. Paper/document title and authors (if applicable)
    2. Key concepts and findings
    3. Technical approaches or methods described
    4. How this relates to the problem at hand

    Return a structured summary in markdown format.
```

Store agent IDs as `[PAPER_AGENT_IDS]` (list).

### 4.5: Web Search Agents (if `[WEB_SEARCH_QUERIES]` is non-empty)

**For each query in `[WEB_SEARCH_QUERIES]`:**
```
Task tool:
  description: "Web search: [QUERY_PREVIEW]"
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    Search the web for information related to: "[QUERY]"

    Use the litellm_web_search tool with this query.

    Then use WebFetch to retrieve the most relevant 2-3 results.

    Focus on extracting information relevant to this problem:
    [Insert problem statement summary here]

    Summarize:
    1. Key findings from search results
    2. Relevant papers, articles, or documentation found
    3. Technical approaches or methods mentioned
    4. How this relates to the problem at hand

    Return a structured summary in markdown format.
```

Store agent IDs as `[WEB_SEARCH_AGENT_IDS]` (list).

### 4.6: Pasted Content Processing (if `[PASTED_CONTENT]` exists)

**If user pasted content directly instead of providing URLs:**
```
Task tool:
  description: "Summarize pasted content"
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    Summarize the following content that was provided by the user:

    ---
    [PASTED_CONTENT]
    ---

    Focus on extracting information relevant to this problem:
    [Insert problem statement summary here]

    Summarize:
    1. Document type and source (if identifiable)
    2. Key concepts and findings
    3. Technical approaches or methods described
    4. How this relates to the problem at hand

    Return a structured summary in markdown format.
```

Store agent ID as `[PASTED_CONTENT_AGENT_ID]` (or null if not applicable).

## Step 5: Collect Results and Create Output File

**Wait for all background agents to complete.** Use `TaskOutput` to collect results from each agent. If an agent failed, log a warning noting which source failed and continue with results from successful agents.

**Before writing:** Ensure the output directory exists: `Bash("mkdir -p \"$(dirname '[OUTPUT_FILE]')\"")`

**Create `[OUTPUT_FILE]` with the following structure:**

```markdown
# [DOCUMENT_TITLE]

## Problem Statement

[Copy the ENTIRE content from [PROBLEM_FILE_PATH] verbatim here]

---

# Background

[If [INCLUDE_CURRENT_REPO] is true:]
## Current Repository Context

[Insert summary from [CURRENT_REPO_AGENT_ID]]

[If [LOCAL_REPO_PATHS] is non-empty:]
## Local Repositories

### [Repository Name 1]
**Path:** [LOCAL_PATH]
[Insert summary from first local repo agent]

### [Repository Name 2]
**Path:** [LOCAL_PATH]
[Insert summary from second local repo agent]
...

[If [GITHUB_REPO_URLS] is non-empty:]
## GitHub Repositories

### [Repository Name 1]
**URL:** [GITHUB_URL]
[Insert summary from first GitHub repo agent]

### [Repository Name 2]
**URL:** [GITHUB_URL]
[Insert summary from second GitHub repo agent]
...

[If [PAPER_URLS] is non-empty:]
## Referenced Papers and Documentation

### [Paper/Doc Title 1]
**Source:** [URL]
[Insert summary from first paper agent]

### [Paper/Doc Title 2]
**Source:** [URL]
[Insert summary from second paper agent]
...

[If [WEB_SEARCH_QUERIES] is non-empty:]
## Web Research

### Search: "[Query 1]"
[Insert summary from first web search agent]

### Search: "[Query 2]"
[Insert summary from second web search agent]
...

[If [PASTED_CONTENT] exists:]
## User-Provided Documentation

[Insert summary from [PASTED_CONTENT_AGENT_ID]]

## Cross-Source Insights

[Brief synthesis of how the different sources relate to each other and the problem]

---

```

**IMPORTANT**: The file ends with `---` followed by a blank line. This is where subsequent ideas and reviews will be appended.

# GUIDELINES

- **Stay focused**: Only include information relevant to the problem statement. Avoid documenting unrelated content.
- **Be concise**: Provide enough context to understand the problem space without overwhelming detail.
- **Be specific**: Reference actual file paths, URLs, function names, and patterns found in the sources.
- **Prioritize**: Put the most important context first. Someone reading should quickly understand the relevant context.
- **Parallelize**: Launch all source summarization agents concurrently to minimize wait time.
- **Handle failures gracefully**: If a URL fetch fails or a path doesn't exist, note it and continue with available sources.
