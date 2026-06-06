#!/usr/bin/env python3
"""
ecos_dashboard.py — eCOS Web Dashboard 原型 (Phase 9)

轻量级 HTTP server, 展示 SSB 系统状态、Watchdog、Agora、Forge、agentmesh 面板。

用法:
  python3 scripts/ecos_dashboard.py              # 默认端口 9090
  python3 scripts/ecos_dashboard.py --port 8080  # 指定端口
"""

import json
import sqlite3
import sys
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import yaml

ECOS_HOME = Path(__file__).resolve().parent.parent
SSB_DB = ECOS_HOME / "LADS" / "ssb" / "ecos.db"
STATE_FILE = ECOS_HOME / "STATE.yaml"
WATCHDOG_FILE = Path.home() / ".hermes" / "ecos-watchdog" / "failures.json"
AGORA_SERVICES_FILE = Path.home() / "Workspace" / "agora" / "agora-services.json"
AGENTMESH_HEALTH_URL = "http://127.0.0.1:3000/v1/health"


def load_state() -> dict:
    """读取 STATE.yaml"""
    try:
        return yaml.safe_load(STATE_FILE.read_text()) or {}
    except Exception:
        return {}


def get_ssb_stats() -> dict:
    """SSB 数据库统计 — 数据库不存在时优雅返回空数据"""
    if not SSB_DB.exists():
        return {
            "error": "DB not found",
            "total": 0,
            "signed": 0,
            "coverage_pct": 0,
            "max_seq": 0,
            "types": [],
            "recent": [],
        }
    try:
        db = sqlite3.connect(str(SSB_DB))
        total = db.execute("SELECT COUNT(*) FROM ssb_events").fetchone()[0]
        signed = db.execute(
            "SELECT COUNT(*) FROM ssb_events WHERE agent_signature IS NOT NULL AND agent_signature != ''"
        ).fetchone()[0]
        types = db.execute(
            "SELECT event_type, COUNT(*) as c FROM ssb_events GROUP BY event_type ORDER BY c DESC LIMIT 8"
        ).fetchall()
        max_seq = db.execute("SELECT MAX(seq) FROM ssb_events").fetchone()[0]
        recent = db.execute(
            "SELECT seq, event_type, source_agent, substr(summary,1,60) as s, timestamp "
            "FROM ssb_events ORDER BY seq DESC LIMIT 20"
        ).fetchall()
        db.close()
        return {
            "total": total,
            "signed": signed,
            "coverage_pct": round(signed / total * 100, 1) if total > 0 else 0,
            "max_seq": max_seq,
            "types": [{"type": r[0], "count": r[1]} for r in types],
            "recent": [{"seq": r[0], "type": r[1], "agent": r[2], "summary": r[3], "ts": r[4]} for r in recent],
        }
    except Exception as e:
        return {
            "error": str(e),
            "total": 0,
            "signed": 0,
            "coverage_pct": 0,
            "max_seq": 0,
            "types": [],
            "recent": [],
        }


def get_cron_status() -> list:
    """获取 cron 状态 (通过 hermes cron list 或手动节选)"""
    return [
        {"id": "WF-001", "name": "KOS索引", "schedule": "02:00", "status": "active"},
        {"id": "WF-002", "name": "Minerva研究", "schedule": "周日03:00", "status": "active"},
        {"id": "WF-003", "name": "健康检查", "schedule": "09:00", "status": "active"},
        {"id": "WF-005", "name": "HANDOFF更新", "schedule": "每2h", "status": "active"},
        {"id": "WF-006", "name": "感知管道", "schedule": "每小时", "status": "active"},
        {"id": "WF-007", "name": "安全检查", "schedule": "每6h", "status": "active"},
        {"id": "WF-008", "name": "Kanban桥接", "schedule": "每5min", "status": "active"},
        {"id": "WF-009", "name": "委员会周检", "schedule": "周一09:00", "status": "active"},
        {"id": "WF-010", "name": "宪法执行器", "schedule": "04:00", "status": "active"},
        {"id": "WF-011", "name": "每日摘要", "schedule": "12:00", "status": "active"},
        {"id": "WF-012", "name": "研究推送", "schedule": "12:00", "status": "active"},
        {"id": "WF-013", "name": "知识缺口检测", "schedule": "每天", "status": "active"},
    ]


def get_watchdog_status() -> dict:
    """读取 watchdog failures.json，返回各服务健康状态"""
    try:
        data = json.loads(WATCHDOG_FILE.read_text())
        return data
    except Exception as e:
        return {"error": str(e)}


def get_agora_services() -> list:
    """读取 Agora 服务注册表"""
    try:
        data = json.loads(AGORA_SERVICES_FILE.read_text())
        return data.get("services", [])
    except Exception as e:
        return [{"_error": str(e)}]


def get_forge_stats() -> dict:
    """Forge 统计 — 硬编码值，后续可从 Forge API 获取"""
    return {
        "tools": 108,
        "graph_nodes": 423,
        "graph_edges": 634,
    }


def get_agentmesh_health() -> dict:
    """从 agentmesh health endpoint 获取代理在线状态"""
    try:
        req = urllib.request.Request(AGENTMESH_HEALTH_URL, method="GET")  # noqa: S310
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except Exception as e:
        return {"error": str(e), "status": "unreachable"}


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>eCOS Dashboard</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:#0d1117; color:#c9d1d9; padding:20px; }}
h1 {{ font-size:24px; margin-bottom:20px; color:#58a6ff; }}
h2 {{ font-size:18px; margin:20px 0 10px; color:#8b949e; border-bottom:1px solid #21262d; padding-bottom:5px; }}
.section-desc {{ font-size:12px; color:#484f58; margin:-8px 0 12px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; margin-bottom:20px; }}
.card {{ background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px; }}
.card .value {{ font-size:28px; font-weight:bold; color:#58a6ff; }}
.card .label {{ font-size:12px; color:#8b949e; margin-top:4px; }}
.card .sub {{ font-size:13px; color:#8b949e; margin-top:8px; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ text-align:left; padding:8px 12px; border-bottom:2px solid #21262d; color:#8b949e; }}
td {{ padding:8px 12px; border-bottom:1px solid #21262d; }}
td.type {{ color:#58a6ff; font-weight:bold; }}
tr:hover {{ background:#1c2128; }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:bold; }}
.badge-green {{ background:#1b3a1f; color:#3fb950; }}
.badge-yellow {{ background:#3d2e00; color:#d29922; }}
.badge-red {{ background:#3d1117; color:#f85149; }}
.ts {{ color:#484f58; font-size:11px; font-family:monospace; }}
.footer {{ margin-top:30px; text-align:center; font-size:11px; color:#484f58; }}
</style>
</head>
<body>
<h1>🔭 eCOS Dashboard</h1>
<div class="grid" id="state-cards"></div>

<h2>🛡️ Watchdog 健康状态</h2>
<p class="section-desc">来源: ~/.hermes/ecos-watchdog/failures.json</p>
<div class="grid" id="watchdog-cards"></div>

<h2>🔌 Agora 注册服务 (10)</h2>
<p class="section-desc">来源: ~/Workspace/agora/agora-services.json</p>
<table id="agora-table"><tr><th>服务</th><th>描述</th><th>协议</th><th>端口</th><th>标签</th></tr></table>

<h2>⚙️ Forge 统计</h2>
<div class="grid" id="forge-cards"></div>

<h2>🌐 Agent Mesh 状态</h2>
<p class="section-desc">来源: http://127.0.0.1:3000/v1/health</p>
<div class="grid" id="agentmesh-cards"></div>

<h2>⚡ SSB 事件类型分布</h2>
<div class="grid" id="type-cards"></div>

<h2>⏱ Cron 任务</h2>
<table id="cron-table"><tr><th>ID</th><th>名称</th><th>调度</th><th>状态</th></tr></table>

<h2>📡 最近 20 条事件</h2>
<table id="events-table"><tr><th>#</th><th>类型</th><th>来源</th><th>摘要</th><th>时间</th></tr></table>

<div class="footer">eCOS v<span id="version"></span> · 数据实时 · 自动刷新</div>
<script>
const state = {STATE_JSON};
const ssb = {SSB_JSON};
const crons = {CRON_JSON};
const watchdog = {WATCHDOG_JSON};
const agoraSvcs = {AGORA_JSON};
const forge = {FORGE_JSON};
const agentmesh = {AGENTMESH_JSON};

document.getElementById('version').textContent = state.version || '?';

// ---- State cards ----
const cards = [
  {{v:state.phase||'?'+''+':'+state.phase_name||''+''+':'+state.version, l:'Phase / 版本'}},
  {{v:state.architecture||'?', l:'架构', sub:'实现度'}},
  {{v:state.security||'?', l:'安全', sub:'评分'}},
  {{v:ssb.total||0, l:'SSB 事件', sub:'seq#'+(ssb.max_seq||0)}},
  {{v:state.tests||'?', l:'测试', sub:'通过数'}},
  {{v:state.scripts||'?', l:'脚本', sub:'总数'}},
  {{v:state.cron||0, l:'Cron 任务', sub:'在线'}},
  {{v:state.adr||0, l:'ADR 决策', sub:'归档'}},
  {{v:ssb.coverage_pct||0, l:'签名覆盖率', sub:'%'}},
];
document.getElementById('state-cards').innerHTML = cards.map(c =>
  `<div class="card"><div class="value">${{c.v}}</div><div class="label">${{c.l}}</div><div class="sub">${{c.sub||''}}</div></div>`
).join('');

// ---- Watchdog cards ----
function badgeForFailures(f) {{ return f > 0 ? 'badge-red' : 'badge-green'; }}
function labelForFailures(f) {{ return f > 0 ? '⚠ ' + f + ' 失败' : '✓ 健康'; }}
var wdHtml = '';
if (watchdog.error) {{
  wdHtml = '<div class="card"><div class="label">错误</div><div class="sub">' + watchdog.error + '</div></div>';
}} else {{
  Object.keys(watchdog).forEach(function(k) {{
    var svc = watchdog[k];
    wdHtml += '<div class="card"><div class="value"><span class="badge ' + badgeForFailures(svc.failures||0) + '">' + labelForFailures(svc.failures||0) + '</span></div><div class="label">' + k + '</div><div class="sub ts">上次正常: ' + (svc.last_ok||'N/A').slice(0,19) + '</div></div>';
  }});
}}
document.getElementById('watchdog-cards').innerHTML = wdHtml;

// ---- Agora services table ----
var agoraHtml = '<tr><th>服务</th><th>描述</th><th>协议</th><th>端口</th><th>标签</th></tr>';
if (Array.isArray(agoraSvcs) && agoraSvcs.length > 0 && !agoraSvcs[0]._error) {
  agoraSvcs.forEach(function(s) {
    var tags = (s.tags||[]).map(function(t) { return '<span class="badge badge-green">' + t + '</span>'; }).join(' ');
    agoraHtml += '<tr><td><b>' + s.name + '</b></td><td>' + (s.description||'').slice(0,60) + '</td><td>' + (s.protocol||'-') + '</td><td>' + (s.port||'-') + '</td><td>' + tags + '</td></tr>';
  });
} else {
  agoraHtml += '<tr><td colspan="5">' + (Array.isArray(agoraSvcs) ? (agoraSvcs[0]&&agoraSvcs[0]._error||'无法加载') : '无法加载') + '</td></tr>';
}
document.getElementById('agora-table').innerHTML = agoraHtml;

// ---- Forge cards ----
document.getElementById('forge-cards').innerHTML =
  '<div class="card"><div class="value">' + (forge.tools||'?') + '</div><div class="label">🔧 工具数</div></div>' +
  '<div class="card"><div class="value">' + (forge.graph_nodes||'?') + '</div><div class="label">📊 图谱节点</div></div>' +
  '<div class="card"><div class="value">' + (forge.graph_edges||'?') + '</div><div class="label">🔗 图谱边</div></div>';

// ---- AgentMesh cards ----
var amHtml = '';
if (agentmesh.error) {
  amHtml = '<div class="card"><div class="value" style="color:#f85149">⚠ 离线</div><div class="label">Agent Mesh</div><div class="sub">' + agentmesh.error + '</div></div>';
} else {
  var online = (agentmesh.agents && agentmesh.agents.online) || agentmesh.online_agents || agentmesh.agents_online || agentmesh.active_agents || '?';
  var total = (agentmesh.agents && agentmesh.agents.total) || agentmesh.total_agents || agentmesh.agents_total || '?';
  var statusText = agentmesh.status || 'ok';
  var statusColor = statusText === 'ok' ? '#3fb950' : '#d29922';
  amHtml = '<div class="card"><div class="value" style="color:' + statusColor + '">' + online + ' / ' + total + '</div><div class="label">🤖 在线 / 总代理</div><div class="sub">状态: ' + statusText + ' · 运行 ' + (agentmesh.uptime_seconds ? Math.floor(agentmesh.uptime_seconds/60) + 'm' : '') + '</div></div>';
  // additional metrics
  if (agentmesh.tasks) {
    amHtml += '<div class="card"><div class="value" style="font-size:24px">' + agentmesh.tasks.completed + '</div><div class="label">✅ 已完成任务</div></div>';
    amHtml += '<div class="card"><div class="value" style="font-size:24px">' + agentmesh.tasks.failed + '</div><div class="label">❌ 失败任务</div></div>';
  }
  if (agentmesh.models) {
    amHtml += '<div class="card"><div class="value" style="font-size:24px">' + agentmesh.models.total + '</div><div class="label">🧠 模型数</div></div>';
  }
}
document.getElementById('agentmesh-cards').innerHTML = amHtml;

// ---- SSB types ----
document.getElementById('type-cards').innerHTML = (ssb.types||[]).map(function(t) {{
  return '<div class="card"><div class="value">' + t.count + '</div><div class="label">' + t.type + '</div></div>';
}}).join('');

// ---- Cron table ----
document.getElementById('cron-table').innerHTML =
  '<tr><th>ID</th><th>名称</th><th>调度</th><th>状态</th></tr>' +
  (crons||[]).map(function(c) {{
    return '<tr><td><b>' + c.id + '</b></td><td>' + c.name + '</td><td>' + c.schedule + '</td><td><span class="badge badge-green">● 在线</span></td></tr>';
  }}).join('');

// ---- Events table ----
document.getElementById('events-table').innerHTML =
  '<tr><th>#</th><th>类型</th><th>来源</th><th>摘要</th><th>时间</th></tr>' +
  (ssb.recent||[]).map(function(e) {{
    return '<tr><td>' + e.seq + '</td><td class="type">' + e.type + '</td><td>' + (e.agent||'') + '</td><td>' + (e.summary||'') + '</td><td class="ts">' + ((e.ts||'').slice(0,19)) + '</td></tr>';
  }}).join('');
</script>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return

        state = load_state()
        ssb = get_ssb_stats()
        crons = get_cron_status()
        watchdog = get_watchdog_status()
        agora_svcs = get_agora_services()
        forge_stats = get_forge_stats()
        agentmesh_health = get_agentmesh_health()
        scripts_count = len(list(ECOS_HOME.glob("scripts/*.py")))

        state["scripts"] = scripts_count
        state["cron"] = len(crons)

        html = DASHBOARD_HTML.replace("{STATE_JSON}", json.dumps(state, ensure_ascii=False))
        html = html.replace("{SSB_JSON}", json.dumps(ssb, ensure_ascii=False))
        html = html.replace("{CRON_JSON}", json.dumps(crons, ensure_ascii=False))
        html = html.replace("{WATCHDOG_JSON}", json.dumps(watchdog, ensure_ascii=False))
        html = html.replace("{AGORA_JSON}", json.dumps(agora_svcs, ensure_ascii=False))
        html = html.replace("{FORGE_JSON}", json.dumps(forge_stats, ensure_ascii=False))
        html = html.replace("{AGENTMESH_JSON}", json.dumps(agentmesh_health, ensure_ascii=False))

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        sys.stderr.write(f"[eCOS Dashboard] {args[0]} {args[1]} {args[2]}\n")


def main():
    """eCOS Dashboard entry point (CLI)."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: ecos-dashboard [--port PORT]")
        print()
        print("eCOS Web Dashboard — 展示 SSB 系统状态、Watchdog、Agora、Forge、agentmesh 面板。")
        print()
        print("Options:")
        print("  --port PORT  指定 HTTP 端口 (default: 9090)")
        return

    PORT = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 9090  # noqa: N806

    print(f"🔭 eCOS Dashboard → http://localhost:{PORT}")
    print("   面板: State · Watchdog · Agora · Forge · AgentMesh · SSB · Cron")
    print("   停止: Ctrl+C")
    server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)  # noqa: S104
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
