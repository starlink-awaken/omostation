#!/bin/bash
# omlxc 集群健康检查
set -euo pipefail

echo "=== omlxc 集群健康检查 $(date '+%Y-%m-%d %H:%M') ==="
echo ""

echo "--- 守护进程 ---"
if omlxc daemon status >/dev/null 2>&1; then
    echo "  ✅ daemon: running"
else
    echo "  ❌ daemon: NOT RUNNING"
fi
echo ""

echo "--- 模型状态 ---"
omlxc models list --json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
items = d['data']['items']
total = len(items)
total_p = sum(len(m.get('placement_states',[])) for m in items)
avail_p = sum(1 for m in items for p in m.get('placement_states',[]) if p.get('available'))
pct = avail_p * 100 // total_p if total_p else 0
print(f'  模型: {total}')
print(f'  Placement: {avail_p}/{total_p} available ({pct}%)')
for m in items:
    states = m.get('placement_states',[])
    if states:
        a = sum(1 for p in states if p.get('available'))
        if a == 0:
            print(f'  ⚠️  {m[\"id\"]}: 0/{len(states)} available')
"
echo ""

echo "--- 后端健康 ---"
omlxc doctor --direct --json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
for c in d.get('data',{}).get('checks',[]):
    ok = '✅' if c.get('ok') else '❌'
    detail = c.get('detail','')
    print(f'  {ok} {c[\"name\"]}: {detail}')
" 2>/dev/null || echo "  (doctor unavailable)"
echo ""

echo "--- 路由统计 ---"
sqlite3 "$HOME/.config/omlxc/state.db" "SELECT
  '  总请求: ' || COUNT(*) || ' | 成功: ' || SUM(success) || ' (' || ROUND(AVG(success)*100,1) || '%)'
FROM request_metrics;" 2>/dev/null
