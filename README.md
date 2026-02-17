# SDLC Plugins

Private Claude Code plugins for the AI Platform Optimization team.

## Setup

```bash
# Add marketplace (one-time)
/plugin marketplace add https://github.com/inference-sim/sdlc-plugins
```

## Install / Update / Remove

```bash
# Install a plugin
/plugin install research-ideas@sdlc-plugins

# Update to latest versions
/plugin marketplace update sdlc-plugins

# Remove a plugin
/plugin uninstall research-ideas@sdlc-plugins
```

## Available Plugins

### research-ideas

Generates research ideas with multi-model AI review (Claude, GPT-4o, Gemini).

```bash
/research-ideas <problem_file> [iterations]
```

Each iteration improves based on previous feedback. Outputs a single `research.md` with all ideas and reviews.

## Authentication

For private repo access, use SSH keys or set `GITHUB_TOKEN`:
```bash
export GITHUB_TOKEN=$(gh auth token)
```

## Examples
See example output [here](examples/).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for plugin development.
