---
name: _review-plan
description: Send Claude plan to an LLM for external technical review
user-invocable: false
allowed-tools:
  - Bash(~/.claude/skills/review-plan/scripts/review.sh *)
  - Bash(python3 *)
  - Bash(curl *)
  - Bash(jq *)
argument-hint: "<plan_path> [model] [--dry-run]"
---

# Review Plan with an LLM

Get independent technical feedback on your Claude Code plan from an LLM.

## Setup

This skill uses OpenAI-compatible API format (`/v1/chat/completions`). Set environment variables for your provider:

**Option 1 - OpenAI (primary):**
```bash
export OPENAI_API_KEY='your-key'
export OPENAI_BASE_URL='https://api.openai.com'  # or your LiteLLM proxy
```

**Option 2 - Using Anthropic credentials with a proxy (fallback):**
```bash
export ANTHROPIC_AUTH_TOKEN='your-key'
export ANTHROPIC_BASE_URL='http://localhost:4000'  # MUST be a LiteLLM proxy or OpenAI-compatible endpoint
```

> **⚠️ Important:** `ANTHROPIC_BASE_URL` must point to an OpenAI-compatible endpoint (like a LiteLLM proxy), NOT directly to `api.anthropic.com`. Anthropic's native API uses `/v1/messages` which is incompatible with this skill.

Add to your `.env` file or shell profile.

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
- **Model**: LiteLLM format `provider/model`. Default: `Azure/gpt-4o`
  - `Azure/gpt-4o` - GPT-4o on Azure
  - `GCP/gemini-2.5-flash` - Gemini 2.5 Flash on GCP
  - `aws/claude-opus-4-6` - Claude Opus 4.6 on AWS
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
