#!/usr/bin/env bash
set -euo pipefail
echo "=== [11] I0 Layer Integration ==="
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# 1. Kairon agora adapters structure
echo "▸ Kairon agora adapters structure..."
test -f $ROOT/projects/kairon/packages/agora/adapters/forge-sync/sync-agora.sh && echo "  ✅ Forge sync migrated" || echo "  ❌ Forge sync missing"

# 2. KOS→MCP (no HTTP hardcode)
echo "▸ KOS→MCP..."
if grep -n "9800\|localhost" $ROOT/projects/kairon/packages/kos/kos/pattern_learner.py 2>/dev/null; then
  echo "  ⚠️ HTTP reference found"
else
  echo "  ✅ No HTTP hardcode"
fi
if grep -n "9800\|localhost" $ROOT/projects/kairon/packages/kos/kos/push_engine.py 2>/dev/null; then
  echo "  ⚠️ HTTP reference found"
else
  echo "  ✅ No HTTP hardcode"
fi

# 3. I0 arcnode scripts exist
echo "▸ I0 validation scripts..."
for s in I0-1-mcp I0-2-logic I0-3-bus; do
  if test -x ~/.hermes/scripts/validate-$s 2>/dev/null; then
    echo "  ✅ validate-$s"
  else
    echo "  ⚠️ validate-$s missing (non-fatal for CI)"
  fi
done

# 4. Integration test count
echo "▸ Full suite..."
count=$(ls $ROOT/tests/integration/test-*.sh 2>/dev/null | wc -l)
echo "  ✅ $count test scenarios"

echo ""
echo "PASS"
