# SDLC Plugins

Private Claude Code plugins for the AI Platform Optimization team.

## Setup

Adding the marketplace registers this repo as a plugin source. Plugins are then installed individually — install whichever ones you need.

```bash
# 1. Add marketplace (one-time)
/plugin marketplace add https://github.com/inference-sim/sdlc-plugins

# 2. Install plugins (pick what you need)
/plugin install research-ideas@sdlc-plugins
/plugin install hypothesis-test@sdlc-plugins
```

## Auto-Updates

To enable automatic plugin updates when new versions are released, go to `/plugin` > Marketplaces > sdlc-plugins and enable auto-update

## Manual Install / Update / Remove

```bash
# Install individual plugins
/plugin install research-ideas@sdlc-plugins
/plugin install hypothesis-test@sdlc-plugins

# Update all installed plugins to latest versions
/plugin marketplace update sdlc-plugins

# Remove a plugin
/plugin uninstall research-ideas@sdlc-plugins
/plugin uninstall hypothesis-test@sdlc-plugins
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

### hypothesis-test

Guided hypothesis-driven experimentation with auto-analysis.

```bash
/hypothesis-test
```

**Features:**
- **6-screen guided flow** - project setup, hypothesis generation, selection, experiment design, testing, commit
- **Parallel hypothesis generation** - background agents generate all hypotheses simultaneously
- **Parallel experiment scaffolding & testing** - each hypothesis gets its own background agent
- **Batch approval** - review all experiment designs at once before any tests run
- **Auto-analysis** - experiments run, analyze results, and determine verdicts automatically

Just run the command and it will:
1. Ask you to pick a project, focus area, and hypothesis count
2. Generate hypotheses in parallel (background agents scan the project for untested behaviors)
3. Let you select which hypotheses to test and execution mode (parallel/sequential)
4. Scaffold experiments, present designs for batch approval
5. Run approved experiments and document findings with verdicts (Confirmed/Refuted/Inconclusive/Failed)
6. Optionally commit all results to git

Outputs per-hypothesis directories under `hypotheses/` with `HYPOTHESIS.md`, `run.sh`, `analyze.py`, and `FINDINGS.md`, plus a `hypotheses/README.md` catalog.

## Authentication

For private repo access, use SSH keys or set `GITHUB_TOKEN`:
```bash
export GITHUB_TOKEN=$(gh auth token)
```

## Examples
See example output [here](examples/).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for plugin development.
