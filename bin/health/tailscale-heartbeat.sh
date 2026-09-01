#!/bin/bash
# tailscale-heartbeat.sh — tailscale 产出断言心跳 (2026-09-01, 8/25 病理双案教训)
#
# 真相 (9/1 复盘): daemon 一直活着, 但 CLI 默认连 /var/run/tailscaled.socket
# 而 brew daemon 监听 /var/run/tailscale.brew.sock → "CLI 连错后端" 假死误诊。
# 本心跳钉死 socket 做产出断言: status --json 成功才算 ok; 连接失败 + utun
# 挂 100.x 时标注 zombie/错socket 嫌疑。
#
# 产物: .omo/state/tailscale-heartbeat.json (运行时区, 不入库)
# 挂载: launchd 每 10 分钟 (或手动) — bin/health/ 首个健康巡检脚本

set -u

TS_BIN="/opt/homebrew/bin/tailscale"
TS_SOCKET="--socket=/var/run/tailscale.brew.sock"  # 8/25+9/1 双案教训: CLI 必须钉死 socket
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WS_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"  # bin/health/ → workspace root
STATE_FILE="$WS_ROOT/.omo/state/tailscale-heartbeat.json"
MACMINI_IP="100.99.210.78"

mkdir -p "$(dirname "$STATE_FILE")"

now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
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
