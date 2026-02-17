#!/bin/bash
# Test plugin installation using Claude CLI with local marketplace
# Usage: ./scripts/test-install-local.sh
#
# Prerequisites:
# - Claude CLI installed (npm install -g @anthropic-ai/claude-code)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"

echo "========================================"
echo "Testing plugin installation locally"
echo "========================================"
echo ""

# Check Claude CLI is installed
if ! command -v claude &> /dev/null; then
  echo "✗ Claude CLI not found"
  echo ""
  echo "Install with: npm install -g @anthropic-ai/claude-code"
  exit 1
fi
echo "✓ Claude CLI found: $(which claude)"
echo ""

# Test marketplace add
echo "1. Adding local marketplace..."
claude /plugin marketplace add "$ROOT_DIR"
echo "   ✓ Marketplace added"
echo ""

# Test plugin listing
echo "2. Listing available plugins..."
claude /plugin 2>&1 | tee /tmp/plugin-list.txt
echo ""

# Check our plugin appears
if grep -q "research-ideas" /tmp/plugin-list.txt; then
  echo "   ✓ research-ideas plugin found in listing"
else
  echo "   ✗ research-ideas plugin NOT found in listing"
  exit 1
fi
echo ""

# Test plugin install
echo "3. Installing research-ideas plugin..."
claude /plugin install research-ideas@sdlc-plugins
echo "   ✓ Plugin installed"
echo ""

echo "========================================"
echo "✓ All installation tests passed!"
echo ""
echo "You can now use:"
echo "  /research-ideas /path/to/problem.md"
