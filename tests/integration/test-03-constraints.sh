#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
echo "=== [03] All Constraints ==="
FAIL=0
SCRIPTS=(
  validate-A1-identity validate-A2-agent-safety validate-A3-agent-execution-trace
  validate-A4-agent-capability validate-A5-agent-auth-chain validate-A6-agent-resource-isolation
  validate-A7-agent-context-integrity validate-A8-agent-resource-accounting
  validate-A9-agent-authorization-isolation validate-A10-agent-idempotency
  validate-EG1-engineering-init validate-EG2-architecture-design validate-EG3-structural-scaffold
  validate-EG4-runtime-orchestration validate-EG5-phase-lock validate-EG6-external-interface
  validate-R-pricing
)
for s in "${SCRIPTS[@]}"; do
  SCRIPT="$HOME/.hermes/scripts/$s"
  if [ ! -f "$SCRIPT" ]; then echo "MISSING: $s"; FAIL=1; continue; fi
  echo "  EXISTS: $s"
done
[ "$FAIL" = "0" ] && echo "All 17 scripts present" || echo "Some scripts missing"
[ "$FAIL" = "0" ]
echo "PASS"
