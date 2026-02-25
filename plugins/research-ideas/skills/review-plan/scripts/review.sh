#!/bin/bash

################################################################################
# review.sh - Zero-Config Plan Reviewer for Claude Code
#
# Design philosophy: WORKS OUT-OF-THE-BOX with sensible defaults.
# Fails loudly and helpfully when safety requires it.
#
# Usage:
#   review.sh [plan_path] [model] [--dry-run]
#
# All arguments are optional. Defaults work for common setups.
#
# Dependencies:
#   - python3 (for helper scripts)
#   - curl (for API calls)
#   - jq (for JSON parsing)
#
################################################################################

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================
# CONFIGURATION
# ============================================================

# API path (appended to base URL)
API_PATH="/v1/chat/completions"

# Default model (LiteLLM format: provider/model)
DEFAULT_MODEL="Azure/gpt-4o"

# Plans directory
PLANS_DIR="$HOME/.claude/plans"

# Redaction enabled by default
REDACTION_ENABLED=true

# Dry-run mode off by default
DRY_RUN=false

# Check-models mode off by default
CHECK_MODELS=false
MODELS_TO_CHECK=()

# Script directory (for helper scripts)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ============================================================
# PARSE ARGUMENTS (SIMPLE, DETERMINISTIC)
# ============================================================

EXPLICIT_PLAN_PATH=""
MODEL="$DEFAULT_MODEL"
MODEL_OVERRIDE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --no-redact)
            REDACTION_ENABLED=false
            shift
            ;;
        --check-models)
            CHECK_MODELS=true
            shift
            # Collect all following arguments as models until we hit another flag
            while [[ $# -gt 0 ]] && [[ "$1" != --* ]]; do
                MODELS_TO_CHECK+=("$1")
                shift
            done
            # If no models specified, use defaults
            if [ ${#MODELS_TO_CHECK[@]} -eq 0 ]; then
                MODELS_TO_CHECK=("aws/claude-opus-4-6" "Azure/gpt-4o" "GCP/gemini-2.5-flash")
            fi
            ;;
        --help|-h)
            cat <<'HELP'
review.sh - Plan Reviewer (Zero-Config)

Usage:
  review.sh [plan_path] [model] [flags]

Arguments (all optional):
  plan_path    Path to plan file (auto-detected if omitted)
               Detected by: ends with ".md"
  model        LiteLLM model name (default: Azure/gpt-4o)

Available models (via LiteLLM):
  Azure/gpt-4o           - GPT-4o on Azure
  GCP/gemini-2.5-flash   - Gemini 2.5 Flash on GCP
  aws/claude-opus-4-6    - Claude Opus 4.6 on AWS

Flags:
  --dry-run       Show config without calling API
  --check-models  Test connectivity to models (default: all 3 models)
                  Optionally specify models: --check-models Azure/gpt-4o aws/claude-opus-4-6
  --no-redact     Disable secret redaction (not recommended)
  --help          Show this help

Examples:
  review.sh
  review.sh GCP/gemini-2.5-flash
  review.sh aws/claude-opus-4-6
  review.sh ~/plans/my-plan.md Azure/gpt-4o
  review.sh --dry-run
  review.sh --check-models                           # Test all 3 models
  review.sh --check-models Azure/gpt-4o              # Test only GPT-4o

HELP
            exit 0
            ;;
        *)
            # Positional argument
            # Rule: Ends with ".md" → plan_path (LiteLLM models use "/" so we can't use that)
            #       Otherwise → model
            if [ -z "$EXPLICIT_PLAN_PATH" ] && [[ "$1" == *".md" ]]; then
                EXPLICIT_PLAN_PATH="$1"
            elif [ "$MODEL_OVERRIDE" = false ]; then
                MODEL="$1"
                MODEL_OVERRIDE=true
            fi
            shift
            ;;
    esac
done

# ============================================================
# DISPLAY HEADER
# ============================================================

echo "═══════════════════════════════════════════════════════════"
echo "  Plan Review"
echo "═══════════════════════════════════════════════════════════"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo "  [DRY-RUN MODE - No API call will be made]"
    echo ""
fi

# ============================================================
# STEP 1: DEPENDENCY CHECK
# ============================================================

echo "[1/6] Checking dependencies..."

MISSING_DEPS=()

if ! command -v python3 &> /dev/null; then
    MISSING_DEPS+=("python3")
fi

if ! command -v curl &> /dev/null; then
    MISSING_DEPS+=("curl")
fi

if ! command -v jq &> /dev/null; then
    MISSING_DEPS+=("jq")
fi

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo ""
    echo "ERROR: Missing required dependencies: ${MISSING_DEPS[*]}"
    echo ""
    echo "Install them:"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  brew install python3 curl jq"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "  sudo apt-get install python3 curl jq"
    fi
    echo ""
    exit 1
fi

echo "   ✓ python3: $(python3 --version | cut -d' ' -f2)"
echo "   ✓ curl: $(curl --version | head -1 | cut -d' ' -f2)"
echo "   ✓ jq: $(jq --version | cut -d'-' -f2)"
echo ""

# ============================================================
# STEP 2: LOAD API KEY (from environment variables)
# ============================================================

echo "[2/6] Loading API credentials..."

# Check OPENAI_API_KEY first, fall back to ANTHROPIC_AUTH_TOKEN
API_KEY=""
API_BASE_URL=""
KEY_SOURCE=""

if [ -n "${OPENAI_API_KEY:-}" ]; then
    API_KEY="$OPENAI_API_KEY"
    API_BASE_URL="${OPENAI_BASE_URL:-${OPENAI_URL:-https://api.openai.com}}"
    KEY_SOURCE="OPENAI_API_KEY"
elif [ -n "${ANTHROPIC_AUTH_TOKEN:-}" ]; then
    API_KEY="$ANTHROPIC_AUTH_TOKEN"
    API_BASE_URL="${ANTHROPIC_BASE_URL:-https://api.anthropic.com}"
    KEY_SOURCE="ANTHROPIC_AUTH_TOKEN (fallback)"
fi

if [ -z "$API_KEY" ]; then
    echo ""
    echo "ERROR: No API key found in environment"
    echo ""
    echo "Set one of these environment variable pairs:"
    echo ""
    echo "  Option 1 (OpenAI):"
    echo "    export OPENAI_API_KEY='your-key'"
    echo "    export OPENAI_URL='https://api.openai.com'  # optional"
    echo ""
    echo "  Option 2 (Anthropic - used as fallback):"
    echo "    export ANTHROPIC_AUTH_TOKEN='your-key'"
    echo "    export ANTHROPIC_BASE_URL='https://api.anthropic.com'  # optional"
    echo ""
    echo "Tip: Add these to your shell profile or a .env file"
    echo ""
    exit 1
fi

# Construct full endpoint (base + path)
API_ENDPOINT="${API_BASE_URL}${API_PATH}"

# IMPORTANT: Warn if using Anthropic credentials with non-Claude models or direct Anthropic API
if [ "$KEY_SOURCE" = "ANTHROPIC_AUTH_TOKEN (fallback)" ]; then
    # Check if pointing directly to Anthropic's API (not a proxy)
    if [[ "$API_BASE_URL" == *"api.anthropic.com"* ]]; then
        README_PATH="$SCRIPT_DIR/../README.md"
        cat <<'ERRMSG'

═══════════════════════════════════════════════════════════
  ⚠️  CONFIGURATION ISSUE DETECTED
═══════════════════════════════════════════════════════════

  ANTHROPIC_BASE_URL points to api.anthropic.com, but this
  skill requires an OpenAI-compatible endpoint (/v1/chat/completions).

  Quick fix:
    export ANTHROPIC_BASE_URL='http://localhost:4000'  # LiteLLM proxy
    # or use OpenAI credentials instead:
    export OPENAI_API_KEY='your-key'

ERRMSG
        if [ -f "$README_PATH" ]; then
            echo "  See $README_PATH for full troubleshooting details."
        else
            echo "  See review-plan README.md for full troubleshooting details."
        fi
        cat <<'ERRMSG'

═══════════════════════════════════════════════════════════

ERRMSG
        exit 1
    fi

    # Warn if using GPT/Gemini models with Anthropic credentials (likely misconfigured)
    if [[ "$MODEL" != *"claude"* ]] && [[ "$MODEL" != *"anthropic"* ]]; then
        echo ""
        echo "   ⚠️  WARNING: Using Anthropic credentials with model: $MODEL"
        echo "      This may fail unless your proxy routes $MODEL correctly."
        echo "      Consider using a Claude model (e.g., aws/claude-opus-4-6)"
        echo "      or setting OPENAI_API_KEY instead."
        echo ""
    fi
fi

echo "   ✓ Using: $KEY_SOURCE"
echo "   ✓ Endpoint: $API_BASE_URL"
echo ""

# ============================================================
# CHECK-MODELS MODE: Test connectivity to models
# ============================================================

if [ "$CHECK_MODELS" = true ]; then
    echo "═══════════════════════════════════════════════════════════"
    echo "  Model Connectivity Check"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "  Testing ${#MODELS_TO_CHECK[@]} model(s) with minimal API request..."
    echo ""

    PASSED=0
    FAILED=0
    FAILED_MODELS=()

    for CHECK_MODEL in "${MODELS_TO_CHECK[@]}"; do
        echo -n "  • $CHECK_MODEL ... "

        # Build minimal test request
        TEST_REQUEST=$(cat <<EOF
{
  "model": "$CHECK_MODEL",
  "messages": [{"role": "user", "content": "Say 'OK' and nothing else."}],
  "max_tokens": 10
}
EOF
)

        # Make API call with short timeout
        TEST_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_ENDPOINT" \
            --connect-timeout 10 \
            --max-time 30 \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $API_KEY" \
            -d "$TEST_REQUEST" 2>&1)

        # Extract HTTP status code
        TEST_HTTP_CODE=$(echo "$TEST_RESPONSE" | tail -n1)
        TEST_BODY=$(echo "$TEST_RESPONSE" | sed '$d')

        if [ "$TEST_HTTP_CODE" = "200" ]; then
            echo "✅ OK"
            ((PASSED++))
        else
            echo "❌ FAILED (HTTP $TEST_HTTP_CODE)"
            ((FAILED++))
            FAILED_MODELS+=("$CHECK_MODEL")

            # Show brief error info
            case "$TEST_HTTP_CODE" in
                000)
                    echo "      → Connection failed (check endpoint URL)"
                    ;;
                401)
                    echo "      → Authentication failed (check API key)"
                    ;;
                404)
                    echo "      → Model not found or endpoint invalid"
                    if [[ "$API_ENDPOINT" == *"anthropic.com"* ]]; then
                        echo "      → NOTE: api.anthropic.com doesn't support /v1/chat/completions"
                    fi
                    ;;
                400)
                    echo "      → Bad request (API format mismatch)"
                    ;;
                429)
                    echo "      → Rate limited"
                    ;;
                *)
                    # Try to extract error message
                    ERROR_MSG=$(echo "$TEST_BODY" | jq -r '.error.message // .message // empty' 2>/dev/null | head -c 80)
                    if [ -n "$ERROR_MSG" ]; then
                        echo "      → $ERROR_MSG"
                    fi
                    ;;
            esac
        fi
    done

    echo ""
    echo "───────────────────────────────────────────────────────────"
    echo "  Results: $PASSED passed, $FAILED failed"
    echo "───────────────────────────────────────────────────────────"

    if [ $FAILED -gt 0 ]; then
        echo ""
        echo "  Failed models: ${FAILED_MODELS[*]}"
        echo ""
        echo "  Troubleshooting:"
        echo "  • Run '/review-plan --dry-run' to verify your configuration"
        echo "  • Check that your API key has access to these models"
        echo "  • If using a proxy, verify it routes these model names correctly"
        echo ""

        if [ "$KEY_SOURCE" = "ANTHROPIC_AUTH_TOKEN (fallback)" ]; then
            echo "  ⚠️  You're using Anthropic credentials."
            echo "     Make sure ANTHROPIC_BASE_URL points to a LiteLLM proxy,"
            echo "     NOT directly to api.anthropic.com."
            echo ""
        fi

        echo "═══════════════════════════════════════════════════════════"
        exit 1
    else
        echo ""
        echo "  ✅ All models are reachable!"
        echo ""
        echo "═══════════════════════════════════════════════════════════"
        exit 0
    fi
fi

# ============================================================
# STEP 3: LOCATE PLAN FILE (THREE-TIER RESOLUTION)
# ============================================================

echo "[3/6] Locating plan file..."

PLAN_FILE=""

# Tier 1: Explicit path argument
if [ -n "$EXPLICIT_PLAN_PATH" ]; then
    echo "   [Tier 1] Using explicit path"
    PLAN_FILE="$EXPLICIT_PLAN_PATH"

    if [ ! -f "$PLAN_FILE" ]; then
        echo ""
        echo "ERROR: Plan file not found at: $PLAN_FILE"
        exit 1
    fi
    echo "   ✓ Plan: $PLAN_FILE"

# Tier 2: Session pointer file
elif [ -n "${CLAUDE_SESSION_ID:-}" ]; then
    echo "   [Tier 2] Checking session pointer..."

    POINTER_FILE="$PLANS_DIR/current-${CLAUDE_SESSION_ID}.path"

    if [ -f "$POINTER_FILE" ]; then
        PLAN_FILE=$(head -1 "$POINTER_FILE" | tr -d '\n')

        if [ -f "$PLAN_FILE" ]; then
            echo "   ✓ Found pointer: $POINTER_FILE"
            echo "   ✓ Plan: $PLAN_FILE"
        else
            echo "   ✗ Pointer exists but plan not found: $PLAN_FILE"
            echo "   Falling back to Tier 3..."
            PLAN_FILE=""
        fi
    else
        echo "   ✗ No pointer file at: $POINTER_FILE"
        echo "   Falling back to Tier 3..."
    fi
fi

# Tier 3: Safe default detection
if [ -z "$PLAN_FILE" ]; then
    echo "   [Tier 3] Safe default detection..."

    PLAN_COUNT=$(find "$PLANS_DIR" -maxdepth 1 -name "*.md" -type f 2>/dev/null | wc -l | tr -d ' ')

    if [ "$PLAN_COUNT" -eq 0 ]; then
        echo ""
        echo "ERROR: No plan files found in $PLANS_DIR"
        echo ""
        echo "Create a plan first by asking Claude to enter plan mode."
        exit 1

    elif [ "$PLAN_COUNT" -eq 1 ]; then
        PLAN_FILE=$(find "$PLANS_DIR" -maxdepth 1 -name "*.md" -type f 2>/dev/null)
        echo "   ✓ Found exactly one plan: $(basename "$PLAN_FILE")"

        # Attempt to create pointer for future use
        if [ -n "${CLAUDE_SESSION_ID:-}" ]; then
            POINTER_FILE="$PLANS_DIR/current-${CLAUDE_SESSION_ID}.path"
            if echo "$PLAN_FILE" > "$POINTER_FILE" 2>/dev/null; then
                echo "   ✓ Created session pointer for next time"
            else
                echo "   ✗ Could not create pointer (permission denied)"
                echo "   To set manually:"
                echo "     echo \"$PLAN_FILE\" > $POINTER_FILE"
            fi
        fi

    else
        echo ""
        echo "ERROR: Multiple plans found, cannot auto-detect safely"
        echo ""
        echo "Plans in $PLANS_DIR:"
        find "$PLANS_DIR" -maxdepth 1 -name "*.md" -type f -exec ls -lh {} \; 2>/dev/null | \
            awk '{print "  • " $9 " (modified " $6 " " $7 " " $8 ")"}'
        echo ""

        if [ -n "${CLAUDE_SESSION_ID:-}" ]; then
            echo "Current session: $CLAUDE_SESSION_ID"
            echo ""
            echo "Choose one explicitly:"
            echo "  /review-plan $PLANS_DIR/<plan-name>.md"
            echo ""
            echo "Or set session pointer:"
            echo "  echo \"$PLANS_DIR/<plan-name>.md\" > $PLANS_DIR/current-${CLAUDE_SESSION_ID}.path"
        else
            echo "Specify plan explicitly:"
            echo "  /review-plan $PLANS_DIR/<plan-name>.md"
        fi
        echo ""
        exit 1
    fi
fi

echo ""

# ============================================================
# STEP 4: REDACT SENSITIVE CONTENT
# ============================================================

echo "[4/6] Redacting sensitive content..."

if [ "$REDACTION_ENABLED" = false ]; then
    echo "   ⚠️  Redaction DISABLED (--no-redact flag)"
    REDACTED_PLAN="$PLAN_FILE"
    REDACTION_COUNT=0
else
    # Create temporary files (using mktemp for security)
    REDACTED_PLAN=$(mktemp /tmp/claude-plan-redacted.XXXXXX)
    chmod 600 "$REDACTED_PLAN"

    # Use helper script for clean redaction
    python3 "$SCRIPT_DIR/redact.py" "$PLAN_FILE" "$REDACTED_PLAN"

    # Read metadata
    REDACTION_COUNT=$(grep "redaction_count=" "$REDACTED_PLAN.meta" | cut -d= -f2)

    if [ "$REDACTION_COUNT" -gt 0 ]; then
        echo "   ✓ Redacted $REDACTION_COUNT sensitive item(s)"
    else
        echo "   ✓ No sensitive content detected"
    fi

    # Ensure cleanup on exit
    trap "rm -f $REDACTED_PLAN $REDACTED_PLAN.meta" EXIT
fi

echo ""

# ============================================================
# DRY-RUN MODE: SHOW CONFIG AND EXIT
# ============================================================

if [ "$DRY_RUN" = true ]; then
    echo "═══════════════════════════════════════════════════════════"
    echo "  DRY-RUN SUMMARY"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "Configuration:"
    echo "  Plan file:    $PLAN_FILE"
    echo "  Model:        $MODEL"
    echo "  API endpoint: $API_ENDPOINT"
    echo "  Key source:   $KEY_SOURCE"
    echo "  Redaction:    $([ "$REDACTION_ENABLED" = true ] && echo "ENABLED ($REDACTION_COUNT items redacted)" || echo "DISABLED")"
    echo ""

    if [ "$REDACTION_ENABLED" = true ]; then
        echo "Redaction preview (first 500 chars):"
        echo "────────────────────────────────────────────────────────────"
        head -c 500 "$REDACTED_PLAN"
        echo ""
        echo "────────────────────────────────────────────────────────────"
        echo ""
    fi

    echo "✓ Dry-run complete (no API call made)"
    echo ""
    echo "To perform actual review:"
    echo "  /review-plan"
    exit 0
fi

# ============================================================
# STEP 5: BUILD JSON REQUEST AND CALL API
# ============================================================

echo "[5/6] Sending to $MODEL for review..."

# Build request using helper script
REQUEST_JSON=$(python3 "$SCRIPT_DIR/build_request.py" "$REDACTED_PLAN" "$MODEL")

# Make API call (5-minute timeout for LLM response)
CURL_EXIT=0
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_ENDPOINT" \
    --connect-timeout 30 \
    --max-time 300 \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $API_KEY" \
    -d "$REQUEST_JSON" 2>&1) || CURL_EXIT=$?

if [ $CURL_EXIT -ne 0 ]; then
    echo ""
    echo "ERROR: API request failed (curl exit code $CURL_EXIT)"
    if [ $CURL_EXIT -eq 28 ]; then
        echo "  Request timed out after 5 minutes."
        echo "  The model may be overloaded or the plan too large."
        echo "  Try a faster model: GCP/gemini-2.5-flash"
    else
        echo "  Connection error. Check your endpoint URL and network."
        echo "  Endpoint: $API_ENDPOINT"
    fi
    echo ""
    exit 1
fi

# Extract HTTP status code
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$RESPONSE" | sed '$d')

# Check for errors
if [ "$HTTP_CODE" -ne 200 ]; then
    echo ""
    echo "ERROR: API call failed with HTTP $HTTP_CODE"
    echo ""
    echo "Response:"
    echo "$RESPONSE_BODY" | jq . 2>/dev/null || echo "$RESPONSE_BODY"
    echo ""

    case "$HTTP_CODE" in
        401)
            echo "This usually means your API key is invalid or expired."
            echo "Check your $KEY_SOURCE environment variable."
            echo ""
            # Extra guidance for credential/model mismatches
            if [ "$KEY_SOURCE" = "ANTHROPIC_AUTH_TOKEN (fallback)" ] && [[ "$MODEL" != *"claude"* ]]; then
                echo "NOTE: You're using Anthropic credentials with model '$MODEL'."
                echo "      This will only work if your proxy at $API_BASE_URL"
                echo "      accepts Anthropic tokens for routing to other providers."
                echo ""
                echo "      To use GPT/Gemini directly, set OPENAI_API_KEY instead:"
                echo "        export OPENAI_API_KEY='your-key'"
                echo "        export OPENAI_BASE_URL='your-proxy-url'"
            fi
            ;;
        404)
            ERROR_MSG=$(echo "$RESPONSE_BODY" | jq -r '.error.message // .message // empty' 2>/dev/null)
            echo "Model name invalid or endpoint URL wrong."
            echo "  Model: $MODEL"
            echo "  Endpoint: $API_ENDPOINT"
            if [ -n "$ERROR_MSG" ]; then
                echo "  API error: $ERROR_MSG"
            fi
            if [[ "$API_ENDPOINT" == *"api.anthropic.com"* ]]; then
                echo "  → api.anthropic.com doesn't support /v1/chat/completions."
                echo "    export ANTHROPIC_BASE_URL='http://localhost:4000'  # LiteLLM proxy"
            else
                echo "  Available models: Azure/gpt-4o, GCP/gemini-2.5-flash, aws/claude-opus-4-6"
            fi
            README_PATH="$SCRIPT_DIR/../README.md"
            if [ -f "$README_PATH" ]; then
                echo "  See $README_PATH for full troubleshooting."
            else
                echo "  See review-plan README.md for full troubleshooting."
            fi
            ;;
        400)
            ERROR_MSG=$(echo "$RESPONSE_BODY" | jq -r '.error.message // .message // empty' 2>/dev/null)
            echo "Bad request - the API rejected the request format."
            if [ -n "$ERROR_MSG" ]; then
                echo "  API error: $ERROR_MSG"
            fi
            if [[ "$API_ENDPOINT" == *"anthropic.com"* ]]; then
                echo "  → Wrong API format for Anthropic. Use a LiteLLM proxy instead:"
                echo "    export ANTHROPIC_BASE_URL='http://localhost:4000'"
            fi
            README_PATH="$SCRIPT_DIR/../README.md"
            if [ -f "$README_PATH" ]; then
                echo "  See $README_PATH for full troubleshooting."
            else
                echo "  See review-plan README.md for full troubleshooting."
            fi
            ;;
        429)
            echo "Rate limit exceeded. Wait a moment and try again."
            ;;
    esac
    exit 1
fi

echo "   ✓ Received response from API"
echo ""

# ============================================================
# STEP 6: PARSE AND DISPLAY RESPONSE
# ============================================================

echo "[6/6] Processing review..."
echo ""

# Extract review content
REVIEW_CONTENT=$(echo "$RESPONSE_BODY" | jq -r '.choices[0].message.content // .error.message // "ERROR: Could not parse response"')

if [ "$REVIEW_CONTENT" = "ERROR: Could not parse response" ]; then
    echo "ERROR: Unexpected API response format"
    echo ""
    echo "Raw response:"
    echo "$RESPONSE_BODY" | jq . 2>/dev/null || echo "$RESPONSE_BODY"
    exit 1
fi

# Display review
echo "═══════════════════════════════════════════════════════════"
echo "  REVIEW"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "$REVIEW_CONTENT"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Review Details"
echo "═══════════════════════════════════════════════════════════"
echo "  Plan reviewed: $PLAN_FILE"
echo "  Model used:    $MODEL"
echo "  API endpoint:  $API_ENDPOINT"
echo "  Redaction:     $([ "$REDACTION_ENABLED" = true ] && echo "ON ($REDACTION_COUNT items)" || echo "OFF")"
echo "  ⚠️  Plan content was sent to external API for review"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "✓ Review complete"
