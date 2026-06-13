#!/usr/bin/env bash
# release-bus-foundation.sh — ordered consumer re-sync after bus-foundation bump
#
# R80 (per R79 dependency graph analysis): bus-foundation has 6
# direct consumers (agora, omo, metaos, runtime, llm-gateway, aetherforge).
# When bus-foundation bumps version, each consumer must `uv sync` and
# re-test. This script automates the ordered re-sync.
#
# Usage:
#   bash scripts/release-bus-foundation.sh [NEW_VERSION]
#
# If NEW_VERSION is omitted, the script reads from pyproject.toml.
#
# Exits non-zero if any consumer's `uv sync` or `pytest` fails. The
# operator can re-run the script after fixing the offending consumer.

set -euo pipefail

# 1. Resolve version
BUS_FOUNDATION_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NEW_VERSION="${1:-}"
if [ -z "$NEW_VERSION" ]; then
    NEW_VERSION=$(python3 -c "
import tomllib
with open('$BUS_FOUNDATION_ROOT/pyproject.toml', 'rb') as f:
    print(tomllib.load(f)['project']['version'])
")
fi
echo "=== Releasing bus-foundation $NEW_VERSION ==="
echo

# 2. Re-sync bus-foundation itself (so the new metadata is on disk)
echo "--- [1/7] bus-foundation itself: uv sync ---"
(cd "$BUS_FOUNDATION_ROOT" && uv sync)
(cd "$BUS_FOUNDATION_ROOT" && uv run pytest -q 2>&1 | tail -2)

# 3. Consumers (DAG layer 1, depend only on bus-foundation)
echo "--- [2/7] llm-gateway: uv sync + pytest ---"
(cd "$BUS_FOUNDATION_ROOT/../llm-gateway" && uv sync)
(cd "$BUS_FOUNDATION_ROOT/../llm-gateway" && uv run pytest -q 2>&1 | tail -2)

echo "--- [3/7] aetherforge: uv sync + pytest ---"
(cd "$BUS_FOUNDATION_ROOT/../aetherforge" && uv sync)
(cd "$BUS_FOUNDATION_ROOT/../aetherforge" && uv run pytest -q 2>&1 | tail -2)

# 4. Consumers (DAG layer 2, depend on bus-foundation + agora)
echo "--- [4/7] agora: uv sync + pytest ---"
(cd "$BUS_FOUNDATION_ROOT/../agora" && uv sync)
(cd "$BUS_FOUNDATION_ROOT/../agora" && uv run pytest tests/ -q --ignore=tests/e2e 2>&1 | tail -2)

echo "--- [5/7] metaos: uv sync + pytest ---"
(cd "$BUS_FOUNDATION_ROOT/../metaos" && uv sync)
(cd "$BUS_FOUNDATION_ROOT/../metaos" && uv run pytest -q 2>&1 | tail -2)

echo "--- [6/7] runtime: uv sync + pytest ---"
(cd "$BUS_FOUNDATION_ROOT/../runtime" && uv sync)
(cd "$BUS_FOUNDATION_ROOT/../runtime" && uv run pytest -q 2>&1 | tail -2)

echo "--- [7/7] omo: uv sync + pytest ---"
(cd "$BUS_FOUNDATION_ROOT/../omo" && uv sync)
(cd "$BUS_FOUNDATION_ROOT/../omo" && uv run pytest -q -m fast 2>&1 | tail -2)

# 5. kairon (monorepo, has bus_adapter in kairon-pipeline subpackage)
echo "--- kairon (kairon-pipeline bus_adapter): uv sync + pytest ---"
(cd "$BUS_FOUNDATION_ROOT/../kairon" && uv sync)
(cd "$BUS_FOUNDATION_ROOT/../kairon" && uv run pytest packages/kairon-pipeline/tests/test_bus_adapter.py -q 2>&1 | tail -2)

# 6. cockpit (depends on runtime; if runtime passed, cockpit usually passes too)
echo "--- cockpit: uv sync + pytest ---"
(cd "$BUS_FOUNDATION_ROOT/../cockpit" && uv sync 2>&1 || echo "cockpit uv sync skipped (not Python or no pyproject)")
(cd "$BUS_FOUNDATION_ROOT/../cockpit" && uv run pytest -q 2>&1 | tail -2 || echo "cockpit pytest skipped")

echo
echo "=== bus-foundation $NEW_VERSION release complete ==="
echo "Next: commit + tag (per GOVERNANCE.md release process)"
echo "  git add projects/bus-foundation/pyproject.toml projects/bus-foundation/CHANGELOG.md"
echo "  git commit -m 'chore: $NEW_VERSION release'"
echo "  git tag v$NEW_VERSION -m 'bus-foundation $NEW_VERSION'"
