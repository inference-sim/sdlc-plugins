# Contributing

Guide for developing plugins in this marketplace.

## Plugin Structure

```
plugins/
└── my-plugin/
    ├── .claude-plugin/
    │   └── plugin.json
    └── skills/
        └── my-skill/
            └── SKILL.md
```

### plugin.json

```json
{
  "name": "my-plugin",
  "description": "What this plugin does",
  "version": "1.0.0",
  "author": { "name": "Your Name" }
}
```

### Register in Marketplace

Add to `.claude-plugin/marketplace.json`:
```json
{
  "name": "my-plugin",
  "source": "./plugins/my-plugin",
  "description": "What this plugin does",
  "version": "1.0.0"
}
```

## Local Development

Use `scripts/dev.sh` to launch Claude Code with your local plugin versions instead of the marketplace-installed ones:

```bash
./scripts/dev.sh
```

This script:
1. Disables any marketplace-installed sdlc-plugins in `~/.claude/settings.json`
2. Loads all local plugins from `plugins/` via `--plugin-dir`
3. Launches Claude Code
4. Restores your marketplace plugins on exit (normal exit, error, or interrupt)

Extra arguments are forwarded to `claude`:

```bash
./scripts/dev.sh --verbose
./scripts/dev.sh -p "test my skill"
```

**Requirements:** `python3`, Claude CLI

## Local Testing

```bash
# Validate structure (no CLI needed)
./scripts/test-local.sh

# Test installation (requires Claude CLI)
./scripts/test-install-local.sh
```

| Script | Tests | Requirements |
|--------|-------|--------------|
| `test-local.sh` | JSON validity, structure, version consistency | `jq` |
| `test-install-local.sh` | Marketplace add, discovery, installation | Claude CLI |

## Releasing

### Bump Version

**Option 1: Claude Code command (recommended)**
```
/bump-version patch   # 1.2.3 → 1.2.4
/bump-version minor   # 1.2.3 → 1.3.0
/bump-version major   # 1.2.3 → 2.0.0
```

**Option 2: Shell script**
```bash
./scripts/bump-version.sh my-plugin 1.1.0
```

### Commit and Release

```bash
# Commit and tag
git add -A && git commit -m "chore: bump version to 1.1.0"
git tag v1.1.0

# Push (triggers release workflow)
git push && git push --tags
```

## CI/CD

PRs run:
- **validate.yml** - Plugin structure and version consistency
- **test-install.yml** - Plugin installation via Claude CLI

Tagged releases (`v*`) run:
- **release.yml** - Creates GitHub release with changelog

## Directory Structure

```
sdlc-plugins/
├── .claude-plugin/
│   └── marketplace.json          # Plugin catalog
├── .github/workflows/
│   ├── validate.yml
│   ├── test-install.yml
│   └── release.yml
├── plugins/
│   └── <plugin-name>/
│       ├── .claude-plugin/
│       │   └── plugin.json
│       └── skills/
│           └── <skill-name>/
│               └── SKILL.md
├── scripts/
│   ├── bump-version.sh
│   ├── dev.sh
│   ├── test-local.sh
│   └── test-install-local.sh
├── CLAUDE.md
├── CONTRIBUTING.md
└── README.md
```
