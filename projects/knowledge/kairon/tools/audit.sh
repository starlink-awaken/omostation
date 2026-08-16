#!/usr/bin/env bash
# audit.sh — B-1 P0 跨仓债审计 (R47 模板)
#
# 跑 kairon 仓跨仓债审计:
#   1. 检查 kairon-utils AppendOnlyLog 入口
#   2. 检查 ContentVersionTracker async 迁移
#   3. 检查 eidos EidosToBosAdapter 迁移
#   4. 输出 §17 R0 评分

set -euo pipefail

KAIRON_DIR="${1:-$(git rev-parse --show-toplevel)}"
VENV_PYTHON="${KAIRON_DIR}/.venv/bin/python"

echo "=== kairon 跨仓债审计 (B-1 P0) ==="
echo "KAIRON_DIR: $KAIRON_DIR"
echo

# 1. kairon-utils AppendOnlyLog 入口
echo "1. kairon-utils AppendOnlyLog 入口"
"$VENV_PYTHON" -c "from kairon_utils import AppendOnlyLog, fcntl_lock; print('  ✅ AppendOnlyLog + fcntl_lock importable')"

# 2. ContentVersionTracker async 迁移
echo "2. ContentVersionTracker async 迁移"
grep -q "AppendOnlyLog\|fcntl_lock" "$KAIRON_DIR/packages/kairon-utils/src/kairon_utils/versioning.py" \
    && echo "  ✅ versioning.py 已用 AppendOnlyLog" \
    || echo "  ❌ versioning.py 未迁移"

# 3. eidos EidosToBosAdapter 迁移
echo "3. eidos EidosToBosAdapter 迁移"
grep -q "AppendOnlyLog" "$KAIRON_DIR/packages/eidos/src/eidos/adapters/eidos_to_bos.py" \
    && echo "  ✅ eidos_to_bos.py 已用 AppendOnlyLog" \
    || echo "  ❌ eidos_to_bos.py 未迁移"

# 4. §17 R0 评分
echo "4. §17 健康度评分"
"$VENV_PYTHON" - <<'PYEOF'
import os
import json
from pathlib import Path
from kairon_utils import AppendOnlyLog

# 扫所有 *_versions.jsonl (ContentVersionTracker 输出)
total = 0
drift = 0
for jsonl in Path('.').rglob('*_versions.jsonl'):
    if '.venv' in str(jsonl) or 'node_modules' in str(jsonl):
        continue
    log = AppendOnlyLog(jsonl)
    for r in log.read_all():
        total += 1
        if not isinstance(r, dict) or 'ts' not in r:
            drift += 1

density = drift / total if total > 0 else 0.0
if density <= 0.01:
    grade = "R0"
elif density <= 0.05:
    grade = "R1"
elif density <= 0.10:
    grade = "R2"
elif density <= 0.30:
    grade = "R3"
elif density <= 0.50:
    grade = "R4"
else:
    grade = "R5"

print(json.dumps({
    "generated_at": "2026-06-11T00:00:00Z",
    "drift_count": drift,
    "total_records": total,
    "debt_density": round(density, 6),
    "health_grade": grade,
}, indent=2))
PYEOF

echo
echo "=== 审计完成 ==="
