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

Set environment variables for your API provider:

**Option 1 - OpenAI (primary):**
```bash
export OPENAI_API_KEY='your-key'
export OPENAI_BASE_URL='https://api.openai.com'  # optional, also accepts OPENAI_URL
```

**Option 2 - Anthropic (fallback):**
```bash
export ANTHROPIC_AUTH_TOKEN='your-key'
export ANTHROPIC_BASE_URL='https://api.anthropic.com'  # optional
```

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
- **Flags**: `--dry-run`, `--help`, `--no-redact`

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
