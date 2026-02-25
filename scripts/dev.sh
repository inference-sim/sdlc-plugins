#!/bin/bash
# Launch Claude Code with local plugin versions for development.
#
# Temporarily disables marketplace-installed sdlc-plugins in
# ~/.claude/settings.json, loads all local plugins via --plugin-dir,
# and restores settings on exit.
#
# Usage: ./scripts/dev.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SETTINGS="$HOME/.claude/settings.json"
MARKETPLACE_NAME="sdlc-plugins"

# --- helpers ---

# Find all marketplace-installed plugin keys for our marketplace
get_installed_keys() {
  python3 -c "
import json, sys
with open('$SETTINGS') as f:
    settings = json.load(f)
enabled = settings.get('enabledPlugins', {})
for key in enabled:
    if key.endswith('@$MARKETPLACE_NAME'):
        print(key)
"
}

# Set enabledPlugins entries to a given value (true/false)
set_plugins_enabled() {
  local value="$1"
  shift
  local keys=("$@")
  if [ ${#keys[@]} -eq 0 ]; then
    return
  fi
  python3 -c "
import json
keys = $(printf '%s\n' "${keys[@]}" | python3 -c "import sys,json; print(json.dumps([l.strip() for l in sys.stdin]))")
with open('$SETTINGS') as f:
    settings = json.load(f)
for key in keys:
    if key in settings.get('enabledPlugins', {}):
        settings['enabledPlugins'][key] = $value
with open('$SETTINGS', 'w') as f:
    json.dump(settings, f, indent=4)
    f.write('\n')
"
}

# --- main ---

if [ ! -f "$SETTINGS" ]; then
  echo "Error: $SETTINGS not found"
  exit 1
fi

# Discover which sdlc-plugins are marketplace-installed
INSTALLED_KEYS=()
while IFS= read -r key; do
  INSTALLED_KEYS+=("$key")
done < <(get_installed_keys)

if [ ${#INSTALLED_KEYS[@]} -gt 0 ]; then
  echo "Disabling marketplace plugins for dev session:"
  for key in "${INSTALLED_KEYS[@]}"; do
    echo "  - $key"
  done
  set_plugins_enabled "False" "${INSTALLED_KEYS[@]}"
else
  echo "No marketplace sdlc-plugins to disable."
fi

# Build --plugin-dir flags for every local plugin
PLUGIN_DIRS=()
for dir in "$ROOT_DIR"/plugins/*/; do
  if [ -f "$dir/.claude-plugin/plugin.json" ]; then
    PLUGIN_DIRS+=("--plugin-dir" "$dir")
  fi
done

if [ ${#PLUGIN_DIRS[@]} -eq 0 ]; then
  echo "Error: No plugins found in $ROOT_DIR/plugins/"
  set_plugins_enabled "True" "${INSTALLED_KEYS[@]}"
  exit 1
fi

echo ""
echo "Loading local plugins:"
for dir in "$ROOT_DIR"/plugins/*/; do
  if [ -f "$dir/.claude-plugin/plugin.json" ]; then
    echo "  - $(basename "$dir")"
  fi
done
echo ""

# Restore marketplace plugins on exit (normal or error)
restore() {
  if [ ${#INSTALLED_KEYS[@]} -gt 0 ]; then
    echo ""
    echo "Restoring marketplace plugins..."
    set_plugins_enabled "True" "${INSTALLED_KEYS[@]}"
    echo "Done."
  fi
}
trap restore EXIT

# Launch Claude with local plugins
claude "${PLUGIN_DIRS[@]}" "$@"
