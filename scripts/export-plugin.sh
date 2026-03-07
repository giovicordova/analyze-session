#!/usr/bin/env bash
# Export analyze-session plugin as a distributable zip.
#
# Usage:
#   ./scripts/export-plugin.sh              # creates analyze-session-<version>.zip
#   ./scripts/export-plugin.sh --output dir # writes zip to dir/

set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION=$(python3 -c "import json; print(json.load(open('$PLUGIN_ROOT/.claude-plugin/plugin.json'))['version'])")
OUTPUT_DIR="${PLUGIN_ROOT}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output) OUTPUT_DIR="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

ZIPFILE="${OUTPUT_DIR}/analyze-session-${VERSION}.zip"

cd "$PLUGIN_ROOT"
zip -r "$ZIPFILE" \
  .claude-plugin/ \
  skills/ \
  hooks/hooks.json \
  tests/ \
  CLAUDE.md \
  CHANGELOG.md \
  README.md \
  LICENSE \
  -x '*.pyc' '__pycache__/*' '.git/*' '*.zip' 'hooks/hooks.json.example'

echo "Exported: $ZIPFILE"
