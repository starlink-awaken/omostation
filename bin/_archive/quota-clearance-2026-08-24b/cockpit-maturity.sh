#!/bin/bash
# cockpit-maturity.sh — Run maturity scorecard and display in cockpit-friendly format

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "Running architecture maturity scorecard..."
echo ""

cd "$REPO_ROOT"
uv run python3 bin/gac/maturity-scorecard.py "$@"

echo ""
echo "To view in cockpit dashboard, integrate with:"
echo "  cockpit maturity"
echo ""
