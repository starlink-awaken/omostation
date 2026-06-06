#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo "=================================================="
echo " eCOS v5 (5+3+1) Unified Test Harness"
echo "=================================================="
TOTAL=0
PASS=0

# 1. Run surviving integration sh scripts
for t in "$ROOT"/tests/integration/test-*.sh; do
  if [ -f "$t" ]; then
    TOTAL=$((TOTAL + 1))
    name="$(basename "$t")"
    if bash "$t" > /dev/null 2>&1; then
      PASS=$((PASS + 1))
      echo "  ✅ $name (Legacy Wrapper)"
    else
      echo "  ❌ $name (Legacy Wrapper)"
    fi
  fi
done

# 2. Run Kairon Monorepo Tests (Python)
TOTAL=$((TOTAL + 1))
echo "▸ Kairon Monorepo (Python 3.14 + uv)"
if (cd "$ROOT/projects/kairon" && make test-fast > /dev/null 2>&1); then
  PASS=$((PASS + 1))
  echo "  ✅ Kairon Pytest Suite (31 Packages)"
else
  echo "  ⚠️  Kairon Pytest Suite Failed (Check 'cd projects/kairon && make test' for details)"
fi

# 3. Run Gbrain Tests (TypeScript)
TOTAL=$((TOTAL + 1))
echo "▸ gbrain (TypeScript + bun)"
if (cd "$ROOT/projects/gbrain" && bun test > /dev/null 2>&1); then
  PASS=$((PASS + 1))
  echo "  ✅ gbrain Bun Test Suite"
else
  echo "  ⚠️  gbrain Bun Test Suite Failed (Check 'cd projects/gbrain && bun test' for details)"
fi

# 4. Runtime E2E Health Check (Python)
TOTAL=$((TOTAL + 1))
echo "▸ Runtime E2E Health Check"
if python3 "$ROOT/tests/integration/test_runtime_e2e.py" > /dev/null 2>&1; then
  PASS=$((PASS + 1))
  echo "  ✅ Runtime E2E (9/9 checks)"
else
  echo "  ⚠️  Runtime E2E Failed (Check 'cd tests/integration && python3 test_runtime_e2e.py' for details)"
fi

echo "=================================================="
echo "Results: $PASS/$TOTAL test suites passed"
[ "$PASS" = "$TOTAL" ]
