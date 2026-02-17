#!/bin/bash
# Usage: ./scripts/bump-version.sh <plugin-name> <new-version>
# Example: ./scripts/bump-version.sh generate-great-ideas 1.1.0

set -e

PLUGIN_NAME=$1
NEW_VERSION=$2

if [ -z "$PLUGIN_NAME" ] || [ -z "$NEW_VERSION" ]; then
  echo "Usage: $0 <plugin-name> <new-version>"
  echo "Example: $0 generate-great-ideas 1.1.0"
  exit 1
fi

PLUGIN_DIR="plugins/$PLUGIN_NAME"

if [ ! -d "$PLUGIN_DIR" ]; then
  echo "Error: Plugin directory not found: $PLUGIN_DIR"
  exit 1
fi

echo "Bumping $PLUGIN_NAME to version $NEW_VERSION..."

# Update plugin.json
PLUGIN_JSON="$PLUGIN_DIR/.claude-plugin/plugin.json"
if [ -f "$PLUGIN_JSON" ]; then
  jq ".version = \"$NEW_VERSION\"" "$PLUGIN_JSON" > "$PLUGIN_JSON.tmp"
  mv "$PLUGIN_JSON.tmp" "$PLUGIN_JSON"
  echo "✓ Updated $PLUGIN_JSON"
fi

# Update marketplace.json
MARKETPLACE_JSON=".claude-plugin/marketplace.json"
jq "(.plugins[] | select(.name == \"$PLUGIN_NAME\")).version = \"$NEW_VERSION\"" "$MARKETPLACE_JSON" > "$MARKETPLACE_JSON.tmp"
mv "$MARKETPLACE_JSON.tmp" "$MARKETPLACE_JSON"
echo "✓ Updated $MARKETPLACE_JSON"

echo ""
echo "Done! Next steps:"
echo "  1. git add -A && git commit -m 'Bump $PLUGIN_NAME to $NEW_VERSION'"
echo "  2. git tag v$NEW_VERSION"
echo "  3. git push && git push --tags"
