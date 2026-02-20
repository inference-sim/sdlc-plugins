# `/review-plan` - Plan Reviewer

Send your Claude Code implementation plans to an LLM for independent technical review.

## Setup

This skill uses **OpenAI-compatible API format** (`/v1/chat/completions`). Set environment variables for your provider:

### Option 1: OpenAI (checked first)

```bash
export OPENAI_API_KEY='your-openai-key'
export OPENAI_BASE_URL='https://api.openai.com'  # or your LiteLLM proxy URL
```

### Option 2: Anthropic credentials with a proxy (fallback)

```bash
export ANTHROPIC_AUTH_TOKEN='your-anthropic-key'
export ANTHROPIC_BASE_URL='http://localhost:4000'  # Your LiteLLM proxy - NOT api.anthropic.com!
```

> **⚠️ IMPORTANT:** When using `ANTHROPIC_AUTH_TOKEN`, the `ANTHROPIC_BASE_URL` **must point to an OpenAI-compatible endpoint** (like a LiteLLM proxy), **NOT** directly to `api.anthropic.com`.
>
> Why? Anthropic's native API uses `/v1/messages` with a different request format. This skill uses `/v1/chat/completions` (OpenAI format). Pointing to `api.anthropic.com` will fail with a 404 error.

**Tip:** Add these to your shell profile (`~/.bashrc`, `~/.zshrc`) or a `.env` file that gets sourced.

## Usage

```bash
# Auto-detect plan, use default model (Azure/gpt-4o)
/review-plan

# Specify a model (LiteLLM format: provider/model)
/review-plan GCP/gemini-2.5-flash
/review-plan aws/claude-opus-4-6
/review-plan Azure/gpt-4o

# Explicit plan path
/review-plan ~/.claude/plans/my-plan.md

# Combine plan path and model
/review-plan ~/.claude/plans/my-plan.md GCP/gemini-2.5-flash

# Verify configuration without API call
/review-plan --dry-run
```

## Arguments

All arguments are optional:

| Argument | Description |
|----------|-------------|
| `plan_path` | Path to plan file (detected by `.md` suffix) |
| `model` | LiteLLM model name (default: `Azure/gpt-4o`) |
| `--dry-run` | Show config without calling API |
| `--check-models` | Test connectivity to models (see below) |
| `--no-redact` | Disable secret redaction (not recommended) |
| `--help` | Show usage help |

### Model Connectivity Check

Use `--check-models` to verify your API can reach the review models before starting:

```bash
# Test all 3 default models
/review-plan --check-models

# Test specific models
/review-plan --check-models Azure/gpt-4o aws/claude-opus-4-6

# Test single model
/review-plan --check-models GCP/gemini-2.5-flash
```

This sends a minimal test request to each model and reports success/failure with helpful error messages.

## Available Models

Via LiteLLM proxy:

| Model | Description |
|-------|-------------|
| `Azure/gpt-4o` | GPT-4o on Azure (default) |
| `GCP/gemini-2.5-flash` | Gemini 2.5 Flash on GCP |
| `aws/claude-opus-4-6` | Claude Opus 4.6 on AWS |

## Plan Resolution

1. **Explicit path**: If you specify a path, that's used
2. **Session pointer**: `~/.claude/plans/current-${CLAUDE_SESSION_ID}.path`
3. **Auto-detect**: If exactly one `.md` file in `~/.claude/plans/`

## Security

Before sending to the API, the skill automatically redacts:
- Private key blocks (`-----BEGIN ... PRIVATE KEY-----`)
- API key lines (`API_KEY=...`)
- Bearer tokens (`Bearer xyz`)

⚠️ **Note:** Plan content (after redaction) is sent to the external API.

## Troubleshooting

**"No API key found in environment"**
→ Set `OPENAI_API_KEY` or `ANTHROPIC_AUTH_TOKEN`

**HTTP 404 with api.anthropic.com**
→ This is the most common issue! See the fix below.

**"CONFIGURATION ISSUE DETECTED" or 404 errors with Anthropic credentials**
→ You're pointing `ANTHROPIC_BASE_URL` to `api.anthropic.com`, but this skill needs an OpenAI-compatible endpoint.

**How to fix:**
1. **Use a LiteLLM proxy** (recommended): Start a LiteLLM proxy and point to it:
   ```bash
   export ANTHROPIC_AUTH_TOKEN='your-key'
   export ANTHROPIC_BASE_URL='http://localhost:4000'  # your LiteLLM proxy
   ```
2. **Use OpenAI credentials instead**: If you have an OpenAI API key:
   ```bash
   export OPENAI_API_KEY='your-key'
   # OPENAI_BASE_URL defaults to api.openai.com
   ```
3. **Use a Claude model with an OpenAI-compatible proxy**: Some cloud providers offer OpenAI-compatible endpoints for Claude.

**"Multiple plans found"**
→ Specify path: `/review-plan ~/.claude/plans/specific-plan.md`

**"python3 not found"**
→ Install Python 3: `brew install python3` or `apt install python3`

**401 errors when using GPT/Gemini with Anthropic credentials**
→ Anthropic tokens won't work for GPT/Gemini unless your proxy accepts them. Either:
- Use `OPENAI_API_KEY` instead
- Use a Claude model: `/review-plan aws/claude-opus-4-6`

**Verify your setup:**
```bash
/review-plan --dry-run
```

## Interactive vs Automated Use

This skill supports two usage patterns:

### Interactive Use (via `/review-plan`)

When running reviews manually in your main Claude Code session:

```bash
/review-plan ~/.claude/plans/my-plan.md Azure/gpt-4o
```

This invokes the skill, which provides argument parsing, validation, and a clean interface.

### Automated Use (via `review-agent`)

When running reviews from **background agents** (e.g., in the `/research-ideas` workflow), the workflow uses a custom `review-agent` that has scoped permissions to invoke this skill:

```yaml
Task tool:
  subagent_type: review-agent
  prompt: "Run /review-plan [PLAN_FILE] [MODEL]"
```

**Why a custom agent?** Background agents spawned via the Task tool have restricted permissions by default and cannot invoke Skills. The `review-agent` (defined in `agents/review-agent.md`) has explicit permission to use the `review-plan` skill without requiring `bypassPermissions` mode.

Both approaches use the same skill and produce identical results.

## File Structure

```
~/.claude/skills/review-plan/
├── SKILL.md              # Skill metadata
├── README.md             # This file
└── scripts/
    ├── review.sh         # Main script
    ├── redact.py         # Secret redaction
    └── build_request.py  # JSON request builder
```
