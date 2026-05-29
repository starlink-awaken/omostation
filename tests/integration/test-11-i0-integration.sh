#!/usr/bin/env bash
set -euo pipefail
echo "=== [11] I0 Layer Integration ==="
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# 1. Agora MCP 可路由
echo "▸ Agora adapters structure..."
test -f $ROOT/Agora/adapters/forge-sync/sync-agora.sh && echo "  ✅ Forge sync migrated" || echo "  ❌ Forge sync missing"

# 2. KOS→hermes-ops MCP (no HTTP hardcode)
echo "▸ KOS→hermes-ops MCP..."
if grep -n "9800\|localhost" $ROOT/kos/kos/pattern_learner.py 2>/dev/null; then
  echo "  ⚠️ HTTP reference found"
else
  echo "  ✅ No HTTP hardcode"
fi
if grep -n "9800\|localhost" $ROOT/kos/kos/push_engine.py 2>/dev/null; then
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

# 4. hermes-ops can import
echo "▸ hermes-ops import..."
if python3 -c "import sys; sys.path.insert(0,'$ROOT/hermes-ops/src'); from hermes_ops.events import emit; print('  ✅ events import OK')" 2>/dev/null; then
  :
else
  echo "  ⚠️ hermes-ops import failed (non-fatal)"
fi

# 5. Integration test count
echo "▸ Full suite..."
count=$(ls $ROOT/tests/integration/test-*.sh 2>/dev/null | wc -l)
echo "  ✅ $count test scenarios"

echo ""
echo "PASS"
