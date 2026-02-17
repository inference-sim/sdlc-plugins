# `/review-plan` - Plan Reviewer

Send your Claude Code implementation plans to an LLM for independent technical review.

## Setup

Set environment variables for your API provider:

### Option 1: OpenAI (checked first)

```bash
export OPENAI_API_KEY='your-openai-key'
export OPENAI_URL='https://api.openai.com'  # optional, this is the default
```

### Option 2: Anthropic (fallback)

```bash
export ANTHROPIC_AUTH_TOKEN='your-anthropic-key'
export ANTHROPIC_BASE_URL='https://api.anthropic.com'  # optional, this is the default
```

**Tip:** Add these to your shell profile (`~/.bashrc`, `~/.zshrc`) or a `.env` file that gets sourced.

## Usage

```bash
# Auto-detect plan (if exactly one .md file in ~/.claude/plans/)
/review-plan

# Specify a model
/review-plan gpt-4-turbo
/review-plan claude-3-opus

# Explicit plan path
/review-plan ~/.claude/plans/my-plan.md

# Verify configuration without API call
/review-plan --dry-run
```

## Arguments

All arguments are optional:

| Argument | Description |
|----------|-------------|
| `plan_path` | Path to plan file (detected by `/` or `.md` suffix) |
| `model` | Model name (default: `gpt-4o`) |
| `--dry-run` | Show config without calling API |
| `--no-redact` | Disable secret redaction (not recommended) |
| `--help` | Show usage help |

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

**"Multiple plans found"**
→ Specify path: `/review-plan ~/.claude/plans/specific-plan.md`

**"python3 not found"**
→ Install Python 3: `brew install python3` or `apt install python3`

**Verify your setup:**
```bash
/review-plan --dry-run
```

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
