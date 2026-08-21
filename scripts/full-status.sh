#!/bin/bash
# 一键全貌：daemon/模型可用性/后端进程/内存/Tailscale/看门狗日志/磁盘，全部只读。
# 设计目标：agent(含未来的我) 一条命令拿到完整状态，不用再像 2026-08-22 那样
# 分散跑十几条命令做排查。
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

echo "=== omlxc 全链路状态 $(date '+%Y-%m-%d %H:%M:%S') ==="
echo ""

echo "--- daemon ---"
omlxc daemon status 2>&1 | grep -o "running\|stopped\|error" | head -1 | sed 's/^/  状态: /'

echo ""
echo "--- 后端进程存活 (不代表模型可用，只代表进程/端口通不通) ---"
for name_url in "LM Studio|http://127.0.0.1:1234/v1/models" "oMLX App|http://127.0.0.1:8000/v1/models" "Ollama|http://127.0.0.1:11434/api/tags"; do
  name="${name_url%%|*}"; url="${name_url##*|}"
  if curl -sf -m 3 "$url" >/dev/null 2>&1; then
    printf "  ✅ %-12s %s\n" "$name" "$url"
  else
    printf "  ❌ %-12s %s\n" "$name" "$url"
  fi
done

echo ""
echo "--- 模型可用性 (探测缓存，非实时生成验证) ---"
omlxc models list --json 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    items=d['data']['items']
    total=len(items)
    total_p=sum(len(m.get('placement_states',[])) for m in items)
    avail_p=sum(1 for m in items for p in m.get('placement_states',[]) if p.get('available'))
    print(f'  模型: {total} 个 | Placement: {avail_p}/{total_p} 可用')
    zero=[m['id'] for m in items if m.get('placement_states') and not any(p.get('available') for p in m['placement_states'])]
    if zero:
        print(f'  ⚠️  全灭: {\", \".join(zero)}')
except Exception as e:
    print(f'  (读取失败: {e})')
"

echo ""
echo "--- 内存 ---"
free_pages=$(vm_stat | awk '/Pages free/ {gsub(/\./,"",$3); print $3}')
free_gb=$(( free_pages * 16384 / 1024 / 1024 / 1024 ))
echo "  可用: ~${free_gb}GB"
lms ps 2>/dev/null | tail -n +2 | grep -v "^$" | while read -r line; do
  [ -n "$line" ] && echo "  LM Studio 驻留: $line"
done

echo ""
echo "--- Tailscale (mac-mini / y7000p 依赖这个) ---"
ts_line=$(tailscale status 2>&1 | head -1)
echo "  $ts_line"

echo ""
echo "--- AetherForge 网关 ---"
# 网关需要鉴权，未带 key 的探测会拿到 401——这代表"活着"不是"挂了"，
# 只有连接层面的失败(exit!=0，端口都连不上)才算真的下线。
if curl -s -o /dev/null -m 3 http://127.0.0.1:4000/v1/models 2>&1; then
  echo "  ✅ 端口 4000 响应正常 (有响应即视为活着，未校验鉴权)"
else
  echo "  ❌ 端口 4000 连接失败，真的下线了"
fi

echo ""
echo "--- 看门狗最近事件 (最近5条，全绿=无输出) ---"
tail -5 ~/.config/omlxc/watchdog.log 2>/dev/null || echo "  (无日志)"

echo ""
echo "--- 磁盘 (模型卷) ---"
df -h /Volumes/Model 2>/dev/null | tail -1 || echo "  (无法读取)"
