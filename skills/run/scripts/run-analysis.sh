#!/usr/bin/env bash
# Run session analysis and optionally commit the report.
#
# Usage:
#   run-analysis.sh [--scope session|project] [--project PATH] [--commit] [--fix] [--apply]
#
# Can be used standalone or wired to a Claude Code hook (e.g., Stop hook).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCOPE="session"
PROJECT="$(pwd)"
OUTPUT="./SESSION-ANALYSIS.md"
COMMIT=false
FIX=false
APPLY=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --scope)   SCOPE="$2"; shift 2 ;;
        --project) PROJECT="$2"; shift 2 ;;
        --output)  OUTPUT="$2"; shift 2 ;;
        --commit)  COMMIT=true; shift ;;
        --fix)     FIX=true; shift ;;
        --apply)   APPLY=true; FIX=true; shift ;;
        *)         shift ;;
    esac
done

echo "=== Analyze Session ==="
echo "Scope:   $SCOPE"
echo "Project: $PROJECT"
echo "Output:  $OUTPUT"
echo ""

# Run analysis
python3 "$SCRIPT_DIR/analyze.py" \
    --session-id latest \
    --project "$PROJECT" \
    --scope "$SCOPE" \
    --output "$OUTPUT"

echo ""

# Run fix mode if requested
if $FIX; then
    echo "=== Fix Mode ==="
    FIX_ARGS="--report $OUTPUT --output ./fix-plan.md"
    if $APPLY; then
        FIX_ARGS="$FIX_ARGS --apply"
    fi
    python3 "$SCRIPT_DIR/fix-report.py" $FIX_ARGS
    echo ""
fi

# Commit report if requested
if $COMMIT; then
    if command -v git &>/dev/null && git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
        git add "$OUTPUT"
        if $FIX && [[ -f "./fix-plan.md" ]]; then
            git add ./fix-plan.md
        fi
        git commit -m "chore: update session analysis report

Co-Authored-By: analyze-session plugin"
        echo "Report committed."
    else
        echo "Not a git repo — skipping commit."
    fi
fi

echo "Done."
