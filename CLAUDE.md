# CLAUDE.md

This is a private Claude Code plugin marketplace for the AI Platform Optimization team.

## Project Overview

This repo hosts internal SDLC plugins that extend Claude Code with custom skills for the team. Plugins are organized under `plugins/` and registered in `.claude-plugin/marketplace.json`.

## Development Guidelines

### Language & Standards

- **Primary language**: Python (follow PEP8)
- **Shell scripts**: Follow ShellCheck recommendations
- Use type hints in Python where practical

### Plugin Structure

See `README.md` for the full plugin creation guide. Key paths:
- `plugins/<plugin-name>/.claude-plugin/plugin.json` - Plugin metadata
- `plugins/<plugin-name>/skills/<skill-name>/SKILL.md` - Skill definition

### Skill Conventions

#### SKILL.md Format

Skills use YAML frontmatter followed by markdown content:

```yaml
---
name: skill-name
description: Brief description of what the skill does
argument-hint: <required_arg> [optional_arg]
allowed-tools:
  - Bash(specific-command *)
  - Skill(other-skill *)
---
```

#### Naming Conventions

- **Plugin names**: lowercase, hyphenated (e.g., `generate-great-ideas`)
- **Skill names**: lowercase, hyphenated, action-oriented (e.g., `review-plan`, `generate-ideas`)
- **Skill files**: Always `SKILL.md` (uppercase)
- **Scripts**: lowercase, underscored Python files (e.g., `build_request.py`)

## Testing

<!-- TODO: Document the custom test script when available -->

Run tests before submitting changes:
```bash
# Test script TBD
```

Test plugins locally:
```bash
claude --plugin-dir ./plugins/<plugin-name>
```

## Common Tasks

### Adding a New Skill

1. Create `plugins/<plugin>/skills/<skill-name>/SKILL.md`
2. Define frontmatter with `name`, `description`, `allowed-tools`
3. Test locally with `claude --plugin-dir`

### Registering a Plugin

Add entry to `.claude-plugin/marketplace.json` under `plugins` array.
