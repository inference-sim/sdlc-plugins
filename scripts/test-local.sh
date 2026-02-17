#!/bin/bash
# Run all local validation tests without requiring Claude CLI or network access
# Usage: ./scripts/test-local.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"

echo "========================================"
echo "Running local plugin validation tests"
echo "========================================"
echo ""

# Track failures
FAILED=0

# Test 1: Validate marketplace.json
echo "1. Validating marketplace.json..."
if jq . .claude-plugin/marketplace.json > /dev/null 2>&1; then
  echo "   ✓ Valid JSON"
else
  echo "   ✗ Invalid JSON in marketplace.json"
  FAILED=1
fi
echo ""

# Test 2: Validate plugin structure
echo "2. Validating plugin structure..."
plugins=$(jq -r '.plugins[].source' .claude-plugin/marketplace.json)

for plugin_path in $plugins; do
  echo "   Checking: $plugin_path"

  # Check plugin.json exists and is valid
  if [ ! -f "$plugin_path/.claude-plugin/plugin.json" ]; then
    echo "   ✗ Missing $plugin_path/.claude-plugin/plugin.json"
    FAILED=1
  elif ! jq . "$plugin_path/.claude-plugin/plugin.json" > /dev/null 2>&1; then
    echo "   ✗ Invalid JSON in $plugin_path/.claude-plugin/plugin.json"
    FAILED=1
  else
    echo "   ✓ plugin.json is valid"
  fi

  # Check skills directory exists
  if [ ! -d "$plugin_path/skills" ]; then
    echo "   ✗ Missing $plugin_path/skills directory"
    FAILED=1
  else
    skill_count=$(find "$plugin_path/skills" -name "SKILL.md" | wc -l | tr -d ' ')
    echo "   ✓ Found $skill_count skill(s)"
  fi
done
echo ""

# Test 3: Validate SKILL.md frontmatter
echo "3. Validating SKILL.md files..."
for skill_file in $(find plugins -name "SKILL.md"); do
  skill_name=$(basename "$(dirname "$skill_file")")

  # Check frontmatter exists
  if ! head -1 "$skill_file" | grep -q "^---"; then
    echo "   ✗ $skill_name: Missing frontmatter (must start with ---)"
    FAILED=1
    continue
  fi

  # Check required fields
  if ! head -20 "$skill_file" | grep -q "^name:"; then
    echo "   ✗ $skill_name: Missing 'name:' in frontmatter"
    FAILED=1
  elif ! head -20 "$skill_file" | grep -q "^description:"; then
    echo "   ✗ $skill_name: Missing 'description:' in frontmatter"
    FAILED=1
  else
    echo "   ✓ $skill_name"
  fi
done
echo ""

# Test 4: Check version consistency
echo "4. Checking version consistency..."
jq -r '.plugins[] | "\(.source)|\(.version)"' .claude-plugin/marketplace.json | while IFS='|' read -r source version; do
  plugin_version=$(jq -r '.version' "$source/.claude-plugin/plugin.json")
  if [ "$version" != "$plugin_version" ]; then
    echo "   ✗ Version mismatch for $source"
    echo "     marketplace.json: $version"
    echo "     plugin.json: $plugin_version"
    # Can't set FAILED here due to subshell, will check again below
  else
    echo "   ✓ $source: v$version"
  fi
done

# Re-check version consistency outside subshell
version_mismatch=$(jq -r '.plugins[] | "\(.source)|\(.version)"' .claude-plugin/marketplace.json | while IFS='|' read -r source version; do
  plugin_version=$(jq -r '.version' "$source/.claude-plugin/plugin.json")
  if [ "$version" != "$plugin_version" ]; then
    echo "mismatch"
  fi
done)

if [ -n "$version_mismatch" ]; then
  FAILED=1
fi
echo ""

# Summary
echo "========================================"
if [ $FAILED -eq 0 ]; then
  echo "✓ All tests passed!"
  exit 0
else
  echo "✗ Some tests failed"
  exit 1
fi
