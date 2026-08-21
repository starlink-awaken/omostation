#!/bin/bash
# 织星算力池链路守护：定期探测各后端，自动拉起挂掉的 oMLX App。
# 由 launchd (com.omlxc.watchdog) 周期调度，也可手动运行做一次性检查。
set -uo pipefail

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
  sleep 8
  if check_http "http://127.0.0.1:8000/v1/models"; then
    log "[OK] oMLX App 已恢复"
  else
    log "[ERROR] oMLX App 重启后仍无响应，需要人工检查"
  fi
fi

# --- LM Studio / Ollama：只监控记录，不自动重启(避免打断用户正在用的GUI窗口) ---
check_http "http://127.0.0.1:1234/v1/models" || log "[ERROR] LM Studio (MBP) 端口 1234 无响应"
check_http "http://127.0.0.1:11434/api/tags" || log "[ERROR] Ollama (MBP) 端口 11434 无响应"

# --- omlxc daemon ---
if ! omlxc daemon status --json 2>/dev/null | grep -q '"running"'; then
  log "[WARN] omlxc daemon 未运行，尝试重启"
  omlxc daemon restart --yes --confirm-impact >>"$LOG" 2>&1
fi

# 日志裁剪，避免无限增长
if [ -f "$LOG" ]; then
  tail -n 2000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
exit 0
