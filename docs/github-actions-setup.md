# Claude Code GitHub Actions Setup

Setup guide for enabling Claude Code on GitHub repos using a self-hosted runner with a LiteLLM gateway.

## Prerequisites

- macOS machine (Apple Silicon) with network access to your LiteLLM endpoint
- `node` and `bun` installed (`brew install node oven-sh/bun/bun`)
- GitHub repo admin access

## 1. Set Up Self-Hosted Runner

On the runner machine:

1. Go to your repo **Settings > Actions > Runners > New self-hosted runner**
2. Select **macOS** and **ARM64** or **Windows**
3. Follow the "Download" instructions. Copy each command exact.
4. For the "Configure" instructions, add `--labels self-hosted" to the first command, such that the first command is "./config.sh --url <some url> --token <some-token> --labels self-hosted"
   1. Use Default for every option
   2. Finally, execute `./run.sh` to start the runner each time

5. Add `actions-runner/` to the repo's `.gitignore`

## 2. Add GitHub Secrets

In **Settings > Secrets and variables > Actions**, add:

| Secret | Value |
|--------|-------|
| `LITELLM_BASE_URL` | Your LiteLLM endpoint (e.g. `https://your-host:4000/v1`) |
| `LITELLM_API_KEY` | Your LiteLLM API key. You might consider creating a Service Account on LiteLLM for this purpose |

## 3. Add Workflow File

Create `.github/workflows/claude.yml`:

```yaml
name: Claude Code Action

permissions:
  contents: write
  pull-requests: write
  issues: write
  id-token: write

on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]
  issues:
    types: [opened, assigned]

jobs:
  claude:
    if: |
      (github.event_name == 'issue_comment' && contains(github.event.comment.body, '@claude')) ||
      (github.event_name == 'pull_request_review_comment' && contains(github.event.comment.body, '@claude')) ||
      (github.event_name == 'issues' && contains(github.event.issue.body, '@claude'))
    runs-on: [self-hosted]

    steps:
      - uses: actions/checkout@v4

      - uses: anthropics/claude-code-action@v1
        env:
          ANTHROPIC_BASE_URL: ${{ secrets.LITELLM_BASE_URL }}
        with:
          anthropic_api_key: ${{ secrets.LITELLM_API_KEY }}
          claude_args: '--model aws/claude-opus-4-6 --allowed-tools Skill Agent'
          plugin_marketplaces: |
            https://github.com/anthropics/claude-plugins-official.git
            https://github.com/obra/superpowers-marketplace.git
          plugins: |
            code-review@claude-plugins-official
            code-simplifier@claude-plugins-official
            frontend-design@claude-plugins-official
            superpowers@superpowers-marketplace
```

Adjust `plugins` and `plugin_marketplaces` to include only the plugins you need.

## 4. Verify

1. Confirm the runner is online: **Settings > Actions > Runners** (green dot)
2. Create an issue or comment with `@claude` to trigger the workflow
3. Check **Actions** tab for run logs

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "CPU lacks AVX support" | Wrong runner architecture. Download the runner matching your CPU (ARM64 for Apple Silicon, x64 for Intel/Windows) |
| "ANTHROPIC_API_KEY is required" | Secrets not set, or key passed as `env` instead of `anthropic_api_key` input |
| "No plugins specified" | Add `plugin_marketplaces` and `plugins` inputs to the workflow |
| Skills not invoked | Add `--allowed-tools Skill Agent` to `claude_args` |
| Runner offline | Restart with `cd actions-runner && ./run.sh` |
