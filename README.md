# SDLC Plugins Marketplace

Private Claude Code plugin marketplace for the AI Platform Optimization team.

## Quick Start

### 1. Add the Marketplace

```bash
/plugin marketplace add https://github.com/inference-sim/sdlc-plugins
```

### 2. Install a Plugin

```bash
/plugin install research-ideas@sdlc-plugins
```

### 3. Use It

```bash
/research-ideas /path/to/problem.md 3
```

---

## Available Plugins

### research-ideas

Generate iteratively-reviewed research ideas from a problem statement. One command creates a complete research document with multi-model feedback.

**Install:**
```bash
/plugin install research-ideas@sdlc-plugins
```

**Usage:**
```bash
/research-ideas <problem_file_path> [num_iterations]
```

**What it does:**
1. Reads your problem statement
2. Gathers relevant background context from the repository
3. Generates N ideas, each reviewed by 3 AI models (Claude, GPT-4o, Gemini)
4. Each iteration improves based on previous feedback
5. Outputs a single `research.md` with the complete progression

**Example:**
```bash
# Create a problem statement
echo "How can we reduce GPU inference latency for transformer models?" > ~/research/problem.md

# Generate 3 ideas with reviews
/research-ideas ~/research/problem.md 3

# Output: ~/research/research.md
```

**Output structure:**
```
research.md
├── Problem Statement
├── Background (auto-generated from repo)
├── Idea 1 + Reviews (Claude, GPT-4o, Gemini)
├── Idea 2 + Reviews (improved based on Idea 1 feedback)
├── Idea 3 + Reviews (further refined)
└── Executive Summary (comparison, recommendation)
```

---

## Managing Plugins

### Update Marketplace

Pull latest plugin versions:
```bash
/plugin marketplace update sdlc-plugins
```

### List Installed Plugins

```bash
/plugin
```

### Uninstall a Plugin

```bash
/plugin uninstall research-ideas@sdlc-plugins
```

---

## Authentication

For private repository access, ensure you have one of:

**Option 1: SSH keys** (recommended)
```bash
# Verify SSH is configured
ssh -T git@github.com
```

**Option 2: GitHub token**
```bash
# Add to ~/.bashrc or ~/.zshrc
export GITHUB_TOKEN=$(gh auth token)
```

---

## For Plugin Developers

### Adding a New Plugin

1. Create plugin structure:
   ```
   plugins/
   └── my-plugin/
       ├── .claude-plugin/
       │   └── plugin.json
       └── skills/
           └── my-skill/
               └── SKILL.md
   ```

2. Create `plugin.json`:
   ```json
   {
     "name": "my-plugin",
     "description": "What this plugin does",
     "version": "1.0.0",
     "author": { "name": "Your Name" }
   }
   ```

3. Register in `.claude-plugin/marketplace.json`:
   ```json
   {
     "name": "my-plugin",
     "source": "./plugins/my-plugin",
     "description": "What this plugin does",
     "version": "1.0.0"
   }
   ```

4. Test locally:
   ```bash
   /plugin marketplace add /path/to/sdlc-plugins
   /plugin install my-plugin@sdlc-plugins
   ```

### Releasing a New Version

```bash
# Bump version (updates plugin.json and marketplace.json)
./scripts/bump-version.sh research-ideas 1.1.0

# Commit and tag
git add -A && git commit -m "Bump research-ideas to 1.1.0"
git tag v1.1.0

# Push (triggers release workflow)
git push && git push --tags
```

### Local Testing

Run validation tests locally (no Claude CLI required):
```bash
./scripts/test-local.sh
```

Test plugin installation with Claude CLI:
```bash
./scripts/test-install-local.sh
```

| Script | What it tests | Requirements |
|--------|---------------|--------------|
| `test-local.sh` | JSON validity, plugin structure, frontmatter, version consistency | `jq` |
| `test-install-local.sh` | Marketplace add, plugin discovery, installation | Claude CLI |

### CI/CD

All PRs run:
- **validate.yml** - Checks plugin structure and version consistency
- **test-install.yml** - Tests plugin installation via Claude CLI

Tagged releases (`v*`) run:
- **release.yml** - Creates GitHub release with changelog

---

## Directory Structure

```
sdlc-plugins/
├── .claude-plugin/
│   └── marketplace.json          # Plugin catalog
├── .github/workflows/
│   ├── validate.yml              # Structure validation
│   ├── test-install.yml          # Installation tests
│   └── release.yml               # Release automation
├── plugins/
│   └── research-ideas/     # Plugin directory
│       ├── .claude-plugin/
│       │   └── plugin.json
│       └── skills/
│           ├── research-ideas/
│           │   └── SKILL.md      # Main entry point
│           ├── background-summary/
│           │   └── SKILL.md
│           ├── generate-ideas/
│           │   └── SKILL.md
│           └── review-plan/
│               ├── SKILL.md
│               └── scripts/
├── scripts/
│   ├── bump-version.sh           # Version helper
│   ├── test-local.sh             # Local validation tests
│   └── test-install-local.sh     # Installation tests
└── README.md
```

---

## Support

Questions or issues? Contact the AI Platform Optimization team or open an issue in this repository.
