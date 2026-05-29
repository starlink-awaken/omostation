#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
echo "=== [06] Pipeline Trace ==="
cd "$ROOT/agentmesh"
bun test packages/engine/src/observability/__tests__/pipeline-tracer.test.ts 2>&1 | tail -3
echo "PASS"
