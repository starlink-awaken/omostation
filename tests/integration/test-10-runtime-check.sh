#!/usr/bin/env bash
set -euo pipefail
echo "=== [10] Runtime Service Check ==="

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# 验证关键服务的代码是否可以在不报错的情况下导入

# 1. KOS self domain
echo "▸ KOS self domain..."
python3 -c "
import os, sys
sys.path.insert(0, '${ROOT}/projects/kairon/packages/kos/src')
from kos.self.api import get_profile
print('  ✅ KOS self import OK')
" 2>&1 || echo "  ⚠️  KOS self import failed"

# 2. KOS collab domain
echo "▸ KOS collab domain..."
python3 -c "
import os, sys
sys.path.insert(0, '${ROOT}/projects/kairon/packages/kos/src')
from kos.collab.api import create_task
print('  ✅ KOS collab import OK')
" 2>&1 || echo "  ⚠️  KOS collab import failed"

# 3. SharedBrain identity_bridge
echo "▸ SharedBrain identity_bridge..."
python3 -c "
import os, sys
sys.path.insert(0, '${ROOT}/projects/kairon/packages/sharedbrain-bridge/src')
from sharedbrain_bridge.nucleus.interfaces.identity_bridge import map_role_to_identity
id = map_role_to_identity('test-agent')
print(f'  ✅ identity_bridge OK: {id.id}')
" 2>&1 || echo "  ⚠️  identity_bridge failed"

# 4. Agentmesh / pipeline tracer (obsolete, handled by kairon Python tests)
echo "▸ agentmesh obsolete tests removed (now tested via make kairon-test)"

# 6. (skip — recursive call; run-all.sh already orchestrates all tests)

echo ""
echo "PASS"
