---
name: bump-version
description: Bump the version for the marketplace and all plugins (major, minor, or patch)
argument-hint: <major|minor|patch>
allowed-tools:
  - Read
  - Edit
  - Glob
---

# Bump Version

Update the version across the marketplace and all plugins to keep CI validation passing.

## Argument

**Required:** One of `major`, `minor`, or `patch`

- `major`: 1.2.3 → 2.0.0
- `minor`: 1.2.3 → 1.3.0
- `patch`: 1.2.3 → 1.2.4

## Files to Update

1. **`.claude-plugin/marketplace.json`**
   - `plugins[*].version` - version for each plugin entry

2. **Each plugin's `plugin.json`**
   - `plugins/<name>/.claude-plugin/plugin.json` → `version`

**Note:** Do NOT update `metadata.version` - that is the marketplace version, not plugin versions.

## Steps

### Step 1: Validate Argument

If argument is not one of `major`, `minor`, or `patch`:
```
Error: Invalid argument. Usage: /bump-version <major|minor|patch>
```

### Step 2: Read Current Version

Read `.claude-plugin/marketplace.json` and extract current version from `plugins[0].version` (the authoritative source).

Parse as semver: `MAJOR.MINOR.PATCH`

### Step 3: Calculate New Version

Based on argument:
- `major`: increment MAJOR, reset MINOR and PATCH to 0
- `minor`: increment MINOR, reset PATCH to 0
- `patch`: increment PATCH

### Step 4: Update marketplace.json

Update `.claude-plugin/marketplace.json`:
- Set `version` for ALL entries in `plugins[]` array to new version
- Do NOT change `metadata.version`

### Step 5: Update All Plugin Files

Find all plugin.json files:
```
Glob: plugins/*/.claude-plugin/plugin.json
```

For each file, update the `version` field to the new version.

### Step 6: Summary

Output:
```
Version bumped: [OLD_VERSION] → [NEW_VERSION]

Updated files:
  - .claude-plugin/marketplace.json (plugins[*].version)
  - plugins/<name>/.claude-plugin/plugin.json

Next steps:
  1. Review changes: git diff
  2. Commit: git commit -am "chore: bump version to [NEW_VERSION]"
  3. Tag for release: git tag v[NEW_VERSION]
  4. Push: git push && git push --tags
```
