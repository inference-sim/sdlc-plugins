# SDLC Plugins

Private Claude Code plugins for the AI Platform Optimization team.

## Setup

```bash
# Add marketplace (one-time)
/plugin marketplace add https://github.com/inference-sim/sdlc-plugins
/plugin install research-ideas@sdlc-plugins
```

## Auto-Updates

To enable automatic plugin updates when new versions are released, go to `/plugin` > Marketplaces > sdlc-plugins and enable auto-update

## Manual Install / Update / Remove

```bash
# Install a plugin
/plugin install research-ideas@sdlc-plugins

# Update to latest versions
/plugin marketplace update sdlc-plugins

# Remove a plugin
/plugin uninstall research-ideas@sdlc-plugins
```

## Available skills

### research-ideas

Generates research ideas with multi-model AI review (Claude, GPT-4o, Gemini).

```bash
/research-ideas
```

**Features:**
- **Guided workflow** - step-by-step configuration for problem, background, judges
- **Multi-source context** - gather background from repos, papers, and web search
- **Parallel processing** - background agents fetch context simultaneously
- **Configurable judges** - choose which AI models review your ideas
- **Progress dashboard** - visual task tracking throughout the process

Just run the command and let it guide you. The plugin will:
1. Help you create or locate a problem statement
2. Gather background from multiple sources (repos, papers, web)
3. Configure review judges (3 models by default)
4. Generate iteratively-reviewed ideas with visual progress tracking

Outputs a single `research.md` with problem, background, all ideas, reviews, and executive summary.

#### Creating a Problem Statement

Create a `problem.md` file in your project directory. Some questions you can consider to help drive the problem statement:
- Briefly describe the background and motivation
- State what is needed to be solved
- Any limitations or requirements
- How will you define success?

**Need help articulating your problem?** Use the brainstorming superpower:

```bash
/superpowers:brainstorm brainstorm problem statements for the /research-ideas skill
```

This will help you explore and refine your problem statement before generating research ideas.

## Authentication

For private repo access, use SSH keys or set `GITHUB_TOKEN`:
```bash
export GITHUB_TOKEN=$(gh auth token)
```

## Examples
See example output [here](examples/).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for plugin development.
