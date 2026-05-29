#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
echo "=== [04] Phase Lock ==="
cd "$ROOT/agentmesh"
bun test packages/engine/src/phase-lock/__tests__/phase-lock.test.ts 2>&1 | tail -3
echo "PASS"
