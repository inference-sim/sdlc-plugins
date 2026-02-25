# CLAUDE.md

Private Claude Code plugin marketplace for the AI Platform Optimization team. Plugins live under `plugins/` and are registered in `.claude-plugin/marketplace.json`.

## Language & Standards

- **Python**: PEP8, type hints where practical
- **Shell**: Follow ShellCheck recommendations

## Plugin & Skill Structure

Key paths:
- `plugins/<plugin-name>/.claude-plugin/plugin.json` — Plugin metadata
- `plugins/<plugin-name>/skills/<skill-name>/SKILL.md` — Skill definition

SKILL.md files use YAML frontmatter (`name`, `description`, `allowed-tools`) followed by markdown content.

### Naming Conventions

- **Plugin names**: lowercase, hyphenated (e.g., `generate-great-ideas`)
- **Skill names**: lowercase, hyphenated, action-oriented (e.g., `review-plan`, `generate-ideas`)
- **Internal skills**: prefixed with `_` (e.g., `_scaffold-experiment`) — these are NOT user-invocable and are only called by other skills via `Skill()` references
- **Skill files**: Always `SKILL.md` (uppercase)
- **Scripts**: lowercase, underscored Python files (e.g., `build_request.py`)

## Change Checklist

When adding or modifying a plugin, skill, or feature, **always** update these:

1. **`README.md`** — Update available skills, usage examples, and feature lists
2. **`CONTRIBUTING.md`** — Update directory structure, local dev instructions, or release steps if affected
3. **CI workflows** (`.github/workflows/`) — Add validation for new skills/plugins (e.g., screen flow checks, structure validation)
4. **`marketplace.json`** — Register new plugins in `.claude-plugin/marketplace.json`
5. **`plugin.json`** — Ensure version matches `marketplace.json` entry

## Testing

Always run local validation before submitting changes:

```bash
./scripts/test-local.sh
```

For interactive testing of a plugin:

```bash
./scripts/dev.sh                    # Launch Claude Code with all local plugins
./scripts/dev.sh -p "test my skill" # Pass arguments to claude
```

## CI/CD

PRs automatically run:
- **`validate.yml`** — Marketplace JSON validity, plugin structure, skill frontmatter, cross-plugin `Skill()` references, version consistency
- **`test-install.yml`** — YAML frontmatter parsing, hypothesis-test screen flow validation, plugin structure compatibility

Tagged releases (`v*`) run:
- **`release.yml`** — Validates tag matches marketplace version, generates changelog, creates GitHub release

## Common Tasks

### Adding a New Skill

1. Create `plugins/<plugin>/skills/<skill-name>/SKILL.md` (or `_<skill-name>/` for internal skills)
2. Define frontmatter with `name`, `description`, `allowed-tools`
3. Run `./scripts/test-local.sh` to validate
4. Test interactively with `./scripts/dev.sh`
5. Follow the [Change Checklist](#change-checklist) above

### Registering a New Plugin

1. Add entry to `.claude-plugin/marketplace.json` under `plugins` array
2. Ensure `plugin.json` version matches the marketplace entry
3. Follow the [Change Checklist](#change-checklist) above
