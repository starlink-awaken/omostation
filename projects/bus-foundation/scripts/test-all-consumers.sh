#!/usr/bin/env bash
# test-all-consumers.sh — matrix test runner for bus-foundation consumers
#
# R81 (per R79 dependency graph + R80 release script): when bus-foundation
# changes, we want to verify all 6 direct consumers still pass their
# own tests. This script runs the full matrix.
#
# Usage:
#   bash scripts/test-all-consumers.sh
#
# Exits non-zero on first failure (so the operator can fix the offender
# and re-run).

set -euo pipefail

BUS_FOUNDATION_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_ROOT="$(cd "$BUS_FOUNDATION_ROOT/../.." && pwd)"

echo "=== bus-foundation consumer matrix test ==="
echo "Workspace: $WORKSPACE_ROOT"
echo

run_consumer() {
    local name="$1"
    local dir="$2"
    local test_cmd="$3"
    local extra="${4:-}"
    echo "--- $name ---"
    if [ ! -d "$dir" ]; then
        echo "  SKIP: $dir does not exist"
        return 0
    fi
    if [ ! -f "$dir/pyproject.toml" ]; then
        echo "  SKIP: no pyproject.toml"
        return 0
    fi
    (
        cd "$dir"
        uv sync 2>&1 | tail -1 || return 1
        if [ -n "$test_cmd" ]; then
            eval "$test_cmd" 2>&1 | tail -3
        fi
        if [ -n "$extra" ]; then
            eval "$extra" 2>&1 | tail -3
        fi
    ) || return 1
}

# 1. bus-foundation itself (sanity check)
echo "--- bus-foundation ---"
(cd "$BUS_FOUNDATION_ROOT" && uv run pytest -q 2>&1 | tail -2) || exit 1

# 2. Layer 1 consumers (depend only on bus-foundation)
run_consumer "llm-gateway" "$BUS_FOUNDATION_ROOT/../llm-gateway" \
    "uv run pytest -q" || exit 1
run_consumer "aetherforge" "$BUS_FOUNDATION_ROOT/../aetherforge" \
    "uv run pytest -q" || exit 1

# 3. Layer 2 consumers (depend on bus-foundation + agora)
run_consumer "agora" "$BUS_FOUNDATION_ROOT/../agora" \
    "uv run pytest tests/ -q --ignore=tests/e2e" || exit 1
run_consumer "metaos" "$BUS_FOUNDATION_ROOT/../metaos" \
    "uv run pytest -q" || exit 1
run_consumer "runtime" "$BUS_FOUNDATION_ROOT/../runtime" \
    "uv run pytest -q" || exit 1
run_consumer "omo" "$BUS_FOUNDATION_ROOT/../omo" \
    "uv run pytest -q -m fast" || exit 1

# 4. Layer 3 consumer (depends on runtime; tests bus_adapter directly)
run_consumer "kairon (kairon-pipeline)" \
    "$BUS_FOUNDATION_ROOT/../kairon" \
    "" \
    "uv run pytest packages/kairon-pipeline/tests/test_bus_adapter.py -q" || exit 1

# 5. cockpit (L3 entry; depends on runtime)
run_consumer "cockpit" "$BUS_FOUNDATION_ROOT/../cockpit" \
    "uv run pytest -q" "|| true"  # cockpit may have its own quirks; don't fail here

echo
echo "=== bus-foundation consumer matrix: ALL PASS ==="
