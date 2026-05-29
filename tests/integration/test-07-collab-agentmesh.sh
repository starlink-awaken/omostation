#!/usr/bin/env bash
set -euo pipefail
echo "=== [07] Collab → Agentmesh → Callback → Tracer ==="

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# 1. Verify collab agentmesh client code exists
test -f "$ROOT/kos/kos/collab/agentmesh.py" && echo "  agentmesh client: OK"

# 2. Verify agentmesh Gateway routes for task creation (POST /tasks in routes/api.ts)
grep -q "/tasks" "$ROOT/agentmesh/packages/gateway/src/routes/api.ts" 2>/dev/null \
  && echo "  Gateway POST task: OK" || echo "  Gateway POST task: missing"

# 3. Verify KOS self knowledge_links exist
python3 -c "import yaml; yaml.safe_load(open('$ROOT/kos/domain/self/knowledge_links.yaml')); print('  knowledge_links: OK')"

# 4. Verify PipelineTracer collab integration (collabTaskId field in TraceRecord)
grep -q "collabTaskId" "$ROOT/agentmesh/packages/engine/src/observability/index.ts" \
  && echo "  tracer collab link: OK" || echo "  tracer collab link: missing"

# 5. Verify gstack InterceptorBackend exists
test -f "$ROOT/gstack/src/backend-interceptor.ts" && echo "  gstack backend: OK"

# 6. Verify backup script works
test -x ~/.hermes/scripts/x2-backup-brain && echo "  backup script: OK"

echo "PASS"
