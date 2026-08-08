#!/usr/bin/env bash
# test_pasw_coverage.sh — verify PASW covers all submodules from .gitmodules
#
# T1-06: PASW 覆盖 3→18 验证

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source PASW core
source "$ROOT/lib/pasw-core.sh"

# Count submodules from .gitmodules
expected=$(git -C "$ROOT" config --file .gitmodules --get-regexp path 2>/dev/null | awk '{ print $2 }' | wc -w | tr -d ' ')
actual=$(echo "$PASW_ISOLATED_SUBS" | wc -w | tr -d ' ')

echo "Expected submodules: $expected"
echo "PASW_ISOLATED_SUBS count: $actual"

if [ "$expected" -ne "$actual" ]; then
    echo "❌ PASW coverage mismatch: expected $expected, got $actual"
    exit 1
fi

if [ "$actual" -lt 18 ]; then
    echo "❌ PASW coverage too low: $actual < 18"
    exit 1
fi

# Verify each submodule is in the list
for sub in $(git -C "$ROOT" config --file .gitmodules --get-regexp path 2>/dev/null | awk '{ print $2 }'); do
    if ! echo "$PASW_ISOLATED_SUBS" | grep -q "$sub"; then
        echo "❌ Missing submodule: $sub"
        exit 1
    fi
done

echo "✅ PASW covers all $actual submodules"
echo "   Submodules: $PASW_ISOLATED_SUBS"
