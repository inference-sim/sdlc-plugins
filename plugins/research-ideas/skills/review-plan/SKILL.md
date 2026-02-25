---
name: review-plan
description: Send Claude plan to an LLM for external technical review
user-invocable: true
allowed-tools:
  - Bash(**/review.sh *)
  - Bash(python3 *)
  - Bash(curl *)
  - Bash(jq *)
  - Glob
argument-hint: "<plan_path> [model] [--dry-run]"
---

# Review Plan with an LLM

Get independent technical feedback on your Claude Code plan from an LLM.

## Finding the Script

**IMPORTANT:** Before running any commands, locate the `review.sh` script:

```
Glob: **/skills/review-plan/scripts/review.sh
```

Store the result as `[REVIEW_SCRIPT]`. Use this path for all subsequent bash commands.

If the script is not found, tell the user:
```
Error: Could not find review.sh script.
Make sure you're running from the sdlc-plugins directory or that the plugin is properly installed.
```

## Setup

See `README.md` in this directory for setup instructions, available models, and troubleshooting.

## Usage

```
/review-plan                              # auto-detect plan, use Azure/gpt-4o
/review-plan GCP/gemini-2.5-flash         # use Gemini
/review-plan aws/claude-opus-4-6          # use Claude
/review-plan ~/.claude/plans/my-plan.md   # explicit path
/review-plan --dry-run                    # verify config
```

## Arguments

- **Plan path**: Ends with `.md` → treated as plan file
- **Model**: LiteLLM format `provider/model`. Default: `Azure/gpt-4o`. See README.md for available models.
- **Flags**: `--dry-run`, `--check-models`, `--help`, `--no-redact`

### Model Connectivity Check

Test if models are reachable before running a full review:

```
/review-plan --check-models                              # test all 3 models
/review-plan --check-models Azure/gpt-4o                 # test single model
/review-plan --check-models aws/claude-opus-4-6 Azure/gpt-4o  # test specific models
```

## What It Does

1. Check dependencies (python3, curl, jq)
2. Load API credentials from environment
3. Locate plan file (explicit > session pointer > auto-detect)
4. Redact secrets before transmission
5. Send to LLM for review
6. Display feedback

## Security

- ✅ Redacts API keys, private keys, tokens before transmission
- ⚠️  Plan content is sent to external API

## Execution

After finding `[REVIEW_SCRIPT]` using Glob, run:

```bash
[REVIEW_SCRIPT] [arguments]
```

**Examples:**
```bash
# Check model connectivity
[REVIEW_SCRIPT] --check-models aws/claude-opus-4-6 Azure/gpt-4o GCP/gemini-2.5-flash

# Review a plan
[REVIEW_SCRIPT] /path/to/plan.md Azure/gpt-4o

# Dry run
[REVIEW_SCRIPT] --dry-run
```
