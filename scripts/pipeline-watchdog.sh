#!/bin/bash
# 织星算力池链路守护：定期探测各后端，自动拉起挂掉的 oMLX App。
# 由 launchd (com.omlxc.watchdog) 周期调度，也可手动运行做一次性检查。
set -uo pipefail

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
OMLXC="$HOME/.local/bin/omlxc"

LOG_DIR="$HOME/.config/omlxc"
LOG="$LOG_DIR/watchdog.log"
mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "$(ts) $1" >> "$LOG"; }

check_http() {
  curl -sf -m 3 "$1" >/dev/null 2>&1
}

# --- oMLX App (自愈：进程活着但端口不通是已知故障模式) ---
if ! check_http "http://127.0.0.1:8000/v1/models"; then
  log "[WARN] oMLX App 端口 8000 无响应，尝试重启"
  pkill -x oMLX 2>/dev/null
  sleep 2
  open -a oMLX 2>/dev/null
  for i in 1 2 3 4 5 6; do
    sleep 5
    check_http "http://127.0.0.1:8000/v1/models" && break
  done
  if check_http "http://127.0.0.1:8000/v1/models"; then
    log "[OK] oMLX App 已恢复"
  else
    log "[ERROR] oMLX App 重启后仍无响应，需要人工检查"
  fi
fi

# --- brew tailscaled (临时进程守护: 死了报警; 持久化方案待用户批准) ---
if ! pgrep -f "tailscale.brew.sock" > /dev/null; then
  log "[ERROR] brew tailscaled 不在运行 — 远程节点链路已断"
fi

# --- LM Studio：只监控记录，不自动重启 ---
# LM Studio 有已知的 JIT 加载失控上下文问题(见 docs/operations/2026-08-22-*),
# 自动重启解决不了根因，反而可能在同一个坑里循环重启，宁可如实报警。
check_http "http://127.0.0.1:1234/v1/models" || log "[ERROR] LM Studio (MBP) 端口 1234 无响应"

# --- Ollama (自愈：2026-08-22 单次会话内观察到两次崩溃，均干净重启即恢复，
#     无 LM Studio 那类失控加载风险) ---
if ! check_http "http://127.0.0.1:11434/api/tags"; then
  log "[WARN] Ollama 端口 11434 无响应，尝试重启"
  open -a Ollama 2>/dev/null
  for i in 1 2 3 4 5 6; do
    sleep 5
    check_http "http://127.0.0.1:11434/api/tags" && break
  done
  if check_http "http://127.0.0.1:11434/api/tags"; then
    log "[OK] Ollama 已恢复"
  else
    log "[ERROR] Ollama 重启后仍无响应，需要人工检查"
  fi
fi

# --- omlxc daemon ---
if ! "$OMLXC" daemon status --json 2>/dev/null | grep -q '"running"'; then
  log "[WARN] omlxc daemon 未运行，尝试重启"
  "$OMLXC" daemon restart --yes --confirm-impact >>"$LOG" 2>&1
fi

# --- remote_resident 常驻策略维护 (2026-08-22: 此前是纯声明性死配置,
#     全代码库无任何执行逻辑读取, mac-mini/y7000p 的常驻全靠人工 SSH
#     维持, TTL 到期不会自动恢复。本脚本让它真正生效) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/remote-resident-maintain.py" >>"$LOG" 2>&1

# --- 模型级可用性(读探测缓存，不发真实生成请求，代价很低) ---
# 只能测出"探测都连不上"这一类(如 oMLX App 整体下线导致 placement 全灭)；
# 输出乱码这类要真实生成才测得到的问题不在这一层，见 deep-registration-audit.sh。
zero_avail=$("$OMLXC" models list --json 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    items=d['data']['items']
    bad=[m['id'] for m in items if m.get('placement_states') and not any(p.get('available') for p in m['placement_states'])]
    print(','.join(bad))
except Exception:
    pass
" 2>/dev/null)
if [ -n "$zero_avail" ]; then
  log "[WARN] 以下模型所有 placement 均不可用: $zero_avail"
fi

# 日志裁剪，避免无限增长
if [ -f "$LOG" ]; then
  tail -n 2000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
exit 0
