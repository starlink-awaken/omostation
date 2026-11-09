#!/bin/bash
# tailscale-heartbeat.sh — tailscale 产出断言心跳 (2026-09-01, 8/25 病理双案教训)
#
# 真相 (9/1 复盘): daemon 一直活着, 但 CLI 默认连 /var/run/tailscaled.socket
# 而 brew daemon 监听 /var/run/tailscale.brew.sock → "CLI 连错后端" 假死误诊。
# 本心跳钉死 socket 做产出断言: status --json 成功才算 ok; 连接失败 + utun
# 挂 100.x 时标注 zombie/错socket 嫌疑。
#
# 2026-11-09 修: 上面「brew daemon 监听 brew socket」的前提**已不成立** ——
# /Library/LaunchDaemons/com.tailscale.brew.plist 只传 `--state=...`, **不传
# `--socket=`** ⇒ daemon 用默认 /var/run/tailscaled.socket, brew socket 根本不存在。
# 于是 `$TS_SOCKET status` 每次连不上 → 心跳一直 FAIL(zombie_interface=true),
# 而 `tailscale status` 实际是好的。改为**逐个探测候选 socket**, 第一个能用的胜出。
#
# 产物: .omo/state/tailscale-heartbeat.json (运行时区, 不入库)
# 挂载: launchd 每 10 分钟 (或手动) — bin/health/ 首个健康巡检脚本

set -u

# TAILSCALE_BIN 供测试注入假二进制 (避免测试去写 /opt/homebrew/bin)
TS_BIN="${TAILSCALE_BIN:-/opt/homebrew/bin/tailscale}"
# 候选 socket: 显式 socket 优先 (brew 旧配置), 否则不传 --socket 走 CLI 默认
# (当前 plist 的实际行为)。逐个探测, 第一个 status 能跑通的胜出。
TS_SOCKET_CANDIDATES=(
  "--socket=/var/run/tailscale.brew.sock"
  "--socket=/var/run/tailscaled.socket"
  ""
)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# 写面跟随 profile (AGENTS.md「写路径要在调用时刻解析」): launchd plist 设了
# OMOSTATION_STATE_ROOT, 产物就该落在 state 根 —— 旧版用 SCRIPT_DIR 反推, 落在安装位上。
DEFAULT_WS_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
WS_ROOT="${OMOSTATION_STATE_ROOT:-$DEFAULT_WS_ROOT}"
STATE_FILE="$WS_ROOT/.omo/state/tailscale-heartbeat.json"
MACMINI_IP="100.64.110.118"

mkdir -p "$(dirname "$STATE_FILE")"

now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

TS_SOCKET=""
for candidate in "${TS_SOCKET_CANDIDATES[@]}"; do
  if "$TS_BIN" $candidate status --json >/dev/null 2>&1; then
    TS_SOCKET="$candidate"
    break
  fi
done

status_json=$("$TS_BIN" $TS_SOCKET status --json 2>/dev/null)
rc=$?

zombie=false
if [ $rc -ne 0 ]; then
  # 僵尸接口检测: daemon 失败但 utun 挂着 100.x 地址 → 残留假象
  if ifconfig 2>/dev/null | grep -A 1 "^utun" | grep -q "inet 100\."; then
    zombie=true
  fi
  python3 - "$STATE_FILE" "$now" "$zombie" <<'PYEOF'
import json, sys
state, ts, zombie = sys.argv[1], sys.argv[2], sys.argv[3] == "true"
json.dump({
    "schema": "omostation.tailscale-heartbeat.v1",
    "ok": False,
    "zombie_interface": zombie,
    "checked_at": ts,
    "action": "sudo launchctl load -w /Library/LaunchDaemons/com.tailscale.brew.plist && tailscale up" if zombie else "tailscale up",
}, open(state, "w"), ensure_ascii=False, indent=1)
PYEOF
  echo "tailscale-heartbeat: FAIL (zombie_interface=$zombie) → $STATE_FILE"
  exit 1
fi

# 成功路径: peers 统计 + Mac mini 在线
python3 - "$STATE_FILE" "$now" "$status_json" "$MACMINI_IP" <<'PYEOF'
import json, sys
state, ts, raw, mac_ip = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
d = json.loads(raw)
peers = d.get("Peer") or {}
macmini_online = any(
    p.get("TailscaleIPs") and mac_ip in p["TailscaleIPs"] and p.get("Online")
    for p in peers.values()
)
json.dump({
    "schema": "omostation.tailscale-heartbeat.v1",
    "ok": True,
    "zombie_interface": False,
    "checked_at": ts,
    "peers_total": len(peers),
    "peers_online": sum(1 for p in peers.values() if p.get("Online")),
    "macmini_online": macmini_online,
}, open(state, "w"), ensure_ascii=False, indent=1)
PYEOF
echo "tailscale-heartbeat: OK → $STATE_FILE"
exit 0
