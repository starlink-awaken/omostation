#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "==============================="
echo " End-to-End Integration Tests"
echo "==============================="
TOTAL=0
PASS=0
for t in "$ROOT"/integration/test-*.sh; do
  TOTAL=$((TOTAL + 1))
  name="$(basename "$t")"
  if bash "$t" 2>&1; then
    PASS=$((PASS + 1))
    echo "✅ $name"
  else
    echo "❌ $name"
  fi
  echo "---"
done
echo "==============================="
echo "Results: $PASS/$TOTAL passed"
[ "$PASS" = "$TOTAL" ]
