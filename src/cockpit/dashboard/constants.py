"""Paths, config, HTML templates for the Cockpit Dashboard."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # cockpit/src/cockpit/
WORKSPACE_ROOT = Path.home() / "Workspace"
OMO_ROOT = Path.home() / "Workspace/projects/omo"
RUNTIME_HOME = Path(os.environ.get("RUNTIME_HOME", str(Path.home() / "runtime")))
M0_SNAPSHOT_PATH = Path.home() / "Workspace/projects/ecos/src/ecos/ssot/mof/m0/snapshot.yaml"
COCKPIT_UI_DIST = Path.home() / "Workspace/projects/cockpit-ui/dist"
PROVIDER_PLANE_PATH = WORKSPACE_ROOT / ".omo" / "state" / "provider-plane.yaml"
LLM_QUOTA_SUMMARY_PATH = RUNTIME_HOME / "data" / "llm_quota_summary.json"
LLM_COST_LOG_PATH = RUNTIME_HOME / "data" / "llm_cost.jsonl"
BOS_METRICS_PATH = WORKSPACE_ROOT / ".omo" / "_knowledge" / "bos-metrics.jsonl"

# ─── Layer sources (I0, L2, L1, L0) ────────────────────────
LAYER_SOURCES: list[dict] = [
    {"layer": "I0", "name": "agora", "url": "http://localhost:7431/v1/health", "port": 7431},
    {"layer": "L2", "name": "omo", "url": "http://localhost:9190/api/v1/status", "port": 9190},
    {"layer": "L1", "name": "runtime", "url": "http://localhost:9876/api/v1/status", "port": 9876},
    {"layer": "L0", "name": "ecos", "url": "file://m0_snapshot", "port": None, "source": "m0_snapshot"},
]

DEFAULT_COMPUTE_TOPOLOGY = [
    {"id": "local-mac", "label": "Local-Mac", "kind": "local", "role": "Cockpit / Agent host"},
    {"id": "macmini-ollama", "label": "MacMini (Ollama)", "kind": "local", "role": "Local inference"},
    {"id": "y7000p-lmstudio", "label": "Y7000P (LMStudio)", "kind": "local", "role": "GPU workstation"},
    {"id": "cloud-cc-switch", "label": "Cloud (cc-switch)", "kind": "cloud", "role": "Remote provider relay"},
]

PORT = int(os.environ.get("COCKPIT_DASHBOARD_PORT", "8090"))
DASHBOARD_TOKEN = os.environ.get("COCKPIT_DASHBOARD_TOKEN", "")
DASHBOARD_CORS_ORIGIN = os.environ.get("COCKPIT_DASHBOARD_CORS_ORIGIN", "http://localhost:8090")
DASHBOARD_RATE_LIMIT = int(os.environ.get("COCKPIT_DASHBOARD_RATE_LIMIT", "60"))


# ─── HTML Templates ──────────────────────────────────────────
OVERVIEW_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cockpit — 统一状态概览</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',monospace;background:#0d1117;color:#c9d1d9;padding:24px}
h1{color:#58a6ff;font-size:20px;margin-bottom:4px}
.sub{color:#8b949e;font-size:12px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.layer-card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px}
.layer-card h2{font-size:14px;margin-bottom:8px;display:flex;align-items:center;gap:8px}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600}
.badge-ok{background:#052e16;color:#4ade80}.badge-degraded{background:#271c00;color:#fbbf24}.badge-down{background:#3b0d0d;color:#f87171}
.status-dot{width:10px;height:10px;border-radius:50%;display:inline-block;flex-shrink:0}
.dot-ok{background:#4ade80}.dot-degraded{background:#fbbf24}.dot-down{background:#f87171}
.stat{display:flex;justify-content:space-between;padding:4px 0;font-size:12px;border-bottom:1px solid #21262d}
.stat:last-child{border:none}.label{color:#8b949e}.val{color:#58a6ff;font-weight:600}
a{color:#58a6ff;text-decoration:none}a:hover{text-decoration:underline}
.nav{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap}
.nav a{padding:6px 14px;background:#161b22;border:1px solid #30363d;border-radius:6px;font-size:12px}
.nav a:hover{background:#1c2333;border-color:#58a6ff}
.legacy-link{font-size:12px;color:#8b949e;margin-top:16px;text-align:center}
</style>
</head>
<body>
<h1>&#x25C8; Cockpit — 统一状态概览</h1>
<div class="sub">L3 聚合入口 · 自动检测各层状态</div>
<div class="nav">
  <a href="/overview">&#x1F4CA; 债务驾驶舱 (原有)</a>
  <a href="/bos">&#x1F4E6; BOS 可观测</a>
  <a href="/arch">&#x1F527; 架构健康</a>
  <a href="/">&#x2728; Hermes Console</a>
  <a href="/api/v1/status">&#x1F4CB; API JSON</a>
  <a href="/api/v1/m0">&#x1F4CA; M0 快照</a>
  <a href="http://localhost:7430">&#x2197; Agora (I0)</a>
  <a href="http://localhost:9090">&#x2197; OMO (L2)</a>
  <a href="http://localhost:9876">&#x2197; Runtime (L1)</a>
</div>
<div class="grid" id="layer-grid">
  <div style="color:#8b949e;grid-column:1/-1;text-align:center;padding:40px">Loading...</div>
</div>
<div class="legacy-link">
  <span id="refresh-time"></span>
</div>
<script>
async function refresh(){try{
const r=await fetch('/api/v1/status');const d=await r.json();
let html='';
d.layers.forEach(l=>{
  const badgeCls=l.status==='ok'?'badge-ok':l.status==='degraded'?'badge-degraded':'badge-down';
  const dotCls='dot-'+l.status;
  let body='';
  if(l.data){
    if(l.data.router)body+='<div class="stat"><span class="label">路由</span><span class="val">'+l.data.router.total_routes+'</span></div>';
    if(l.data.domains)body+='<div class="stat"><span class="label">域</span><span class="val">'+Object.keys(l.data.domains).length+'</span></div>';
    if(l.data.metrics)body+='<div class="stat"><span class="label">调用</span><span class="val">'+l.data.metrics.total_calls+'</span></div>';
    if(l.data.poc_services)body+='<div class="stat"><span class="label">POC</span><span class="val">'+l.data.poc_services.total+'</span></div>';
    if(l.data.summary){
      const s=l.data.summary;
      body+='<div class="stat"><span class="label">健康</span><span class="val">'+s.healthy+'/'+s.total_layers+'</span></div>';
    }
    if(l.data.snapshot){
      const snap=l.data.snapshot;
      body+='<div class="stat"><span class="label">Daemon</span><span class="val">'+(snap.daemon.healthy?'\u2705 \u5065\u5eb7':'\u274c \u5f02\u5e38')+'</span></div>';
      body+='<div class="stat"><span class="label">M1 \u8282\u70b9</span><span class="val">'+snap.m1_node_count+'</span></div>';
      body+='<div class="stat"><span class="label">\u5feb\u7167\u7248\u672c</span><span class="val">'+(snap.version||'N/A')+'</span></div>';
      body+='<div style="margin-top:8px;font-size:11px;color:#8b949e">\u534f\u8bae\u8870\u51cf</div>';
      for(const [pname, p] of Object.entries(snap.protocols||{})){
        const pct=p.remaining_pct;
        const decay=p.decay;
        const age=p.age_days;
        const status=p.status;
        const barColor=pct>80?'#4ade80':pct>50?'#fbbf24':'#f87171';
        const statusBadgeCls=status==='fresh'?'badge-ok':status==='aging'?'badge-degraded':'badge-down';
        body+='<div style="margin:6px 0;padding:6px 8px;background:#0d1117;border:1px solid #21262d;border-radius:4px">'+
          '<div style="display:flex;justify-content:space-between;margin-bottom:4px">'+
          '<span style="font-weight:600;font-size:11px">'+pname+'</span>'+
          '<span class="badge '+statusBadgeCls+'"">'+status+'</span>'+
          '</div>'+
          '<div style="display:flex;justify-content:space-between;font-size:10px;color:#8b949e;margin-bottom:3px">'+
          '<span>\u8870\u51cf: '+(decay*100).toFixed(0)+'%</span>'+
          '<span>\u5269\u4f59: '+pct+'%</span>'+
          '<span>\u5df2\u8fc7: '+age+'\u5929</span>'+
          '</div>'+
          '<div style="background:#21262d;border-radius:4px;height:8px;overflow:hidden">'+
          '<div style="height:100%;width:'+pct+'%;background:'+barColor+';border-radius:4px;transition:width 0.5s"></div>'+
          '</div>'+
          '</div>';
      }
    }
  }
  if(l.error)body+='<div class="stat"><span class="label">错误</span><span style="color:#f87171;font-size:11px">'+l.error.slice(0,60)+'</span></div>';
  if(!body)body='<div class="stat"><span class="label">无数据</span></div>';
  html+='<div class="layer-card"><h2><span class="status-dot '+dotCls+'"></span> '+l.layer+' '+l.name+' <span class="badge '+badgeCls+'">'+l.status+'</span></h2>'+body+'</div>';
});
document.getElementById('layer-grid').innerHTML=html;
document.getElementById('refresh-time').textContent='Updated '+new Date().toLocaleTimeString();
}catch(e){console.error(e);}}
refresh();setInterval(refresh,15000);
</script>
</body></html>"""

BOS_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cockpit — BOS 调用可观测</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',monospace;background:#0d1117;color:#c9d1d9;padding:24px}
h1{color:#58a6ff;font-size:20px;margin-bottom:4px}
.sub{color:#8b949e;font-size:12px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:16px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px}
.card h2{font-size:14px;margin-bottom:8px;color:#58a6ff}
.stat{display:flex;justify-content:space-between;padding:4px 0;font-size:12px;border-bottom:1px solid #21262d}
.stat:last-child{border:none}
.label{color:#8b949e}
.val{color:#e6edf3;font-weight:600}
.badge{display:inline-block;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:600;margin-left:6px}
.badge-resolved{background:#052e16;color:#4ade80}
.badge-error{background:#3b0d0d;color:#f87171}
.bar-bg{background:#21262d;border-radius:4px;height:8px;overflow:hidden;margin:4px 0}
.bar-fill{height:100%;border-radius:4px;transition:width .5s}
table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:left;color:#8b949e;padding:6px 4px;border-bottom:1px solid #30363d}
td{padding:6px 4px;border-bottom:1px solid #21262d}
.nav{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap}
.nav a{padding:6px 14px;background:#161b22;border:1px solid #30363d;border-radius:6px;font-size:12px;color:#58a6ff;text-decoration:none}
.nav a:hover{background:#1c2333;border-color:#58a6ff}
</style>
</head>
<body>
<h1>&#x25C8; BOS 调用可观测</h1>
<div class="sub">BOS URI 路由指标 · 实时聚合</div>
<div class="nav">
  <a href="/">&#x1F4CA; 债务驾驶舱</a>
  <a href="/overview">&#x1F30D; 统一状态</a>
  <a href="/api/bos/metrics">&#x1F4CB; API JSON</a>
</div>
<div id="summary" class="grid"></div>
<div id="domains"></div>
<div class="grid" id="details"></div>
<script>
async function load() {
  try {
    const r = await fetch('/api/bos/metrics');
    const d = await r.json();

    // Summary cards
    document.getElementById('summary').innerHTML = [
      {label:'总调用', val:d.summary.total_calls},
      {label:'成功', val:d.summary.success_count, cls:'badge-resolved'},
      {label:'失败', val:d.summary.error_count, cls:d.summary.error_count>0?'badge-error':''},
      {label:'平均延迟', val:(d.summary.avg_latency||0).toFixed(1)+'ms'},
    ].map(c => '<div class="card"><div class="stat"><span class="label">'+c.label+'</span><span class="val">'+c.val+'</span></div></div>').join('');

    // Domain breakdown
    let html = '<div class="card" style="grid-column:1/-1"><h2>&#x1F4E6; 按域</h2>';
    html += '<table><tr><th>域</th><th>调用</th><th>成功率</th><th>平均延迟</th><th></th></tr>';
    d.domains.forEach(dom => {
      const pct = dom.total ? ((dom.success/dom.total)*100).toFixed(1) : 0;
      const barColor = pct > 90 ? '#4ade80' : pct > 70 ? '#fbbf24' : '#f87171';
      html += '<tr><td><strong>'+dom.domain+'</strong></td><td>'+dom.total+'</td><td>'+pct+'%</td><td>'+(dom.avg_latency||0).toFixed(1)+'ms</td>'+
        '<td><div class="bar-bg"><div class="bar-fill" style="width:'+pct+'%;background:'+barColor+'\"></div></div></td></tr>';
    });
    html += '</table></div>';
    document.getElementById('domains').innerHTML = '<div class="grid">'+html+'</div>';

    // Recent calls
    let rhtml = '<div class="card" style="grid-column:1/-1"><h2>&#x1F4C4; 最近调用</h2><table><tr><th>URI</th><th>状态</th><th>延迟</th><th>传输</th><th>时间</th></tr>';
    d.recent.slice(0,20).forEach(call => {
      const cls = call.status === 'resolved' ? 'badge-resolved' : 'badge-error';
      rhtml += '<tr><td style="font-size:11px">'+call.uri+'</td><td><span class="badge '+cls+'">'+call.status+'</span></td><td>'+(call.elapsed_ms||0).toFixed(0)+'ms</td><td>'+call.transport+'</td><td>'+(call.recorded_at||'').slice(0,19)+'</td></tr>';
    });
    rhtml += '</table></div>';
    document.getElementById('details').innerHTML = rhtml;
  } catch(e) { document.getElementById('summary').innerHTML = '<div class="card"><p style="color:#f87171">加载失败: '+e.message+'</p></div>'; }
}
load();
</script>
</body></html>"""

LIVE_DATA_JS = r"""<script>
const STATIC_DEBTS = typeof DEBTS !== 'undefined' ? DEBTS : [];
const STATIC_TIERS = typeof TIERS !== 'undefined' ? TIERS : [];
const STATIC_POLICIES = typeof POLICIES !== 'undefined' ? POLICIES : [];
const STATIC_RULES = typeof RULES !== 'undefined' ? RULES : [];
const STATIC_TIER_COUNTS = typeof TIER_COUNTS !== 'undefined' ? TIER_COUNTS : {};
const STATIC_POLICY_COUNTS = typeof POLICY_COUNTS !== 'undefined' ? POLICY_COUNTS : {};
const STATIC_RULE_COUNTS = typeof RULE_COUNTS !== 'undefined' ? RULE_COUNTS : {};
const STATIC_SEV_COLORS = typeof SEV_COLORS !== 'undefined' ? SEV_COLORS : {};

async function loadLiveDebt() {
  try {
    const resp = await fetch('/api/debt');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const ledger = await resp.json();
    if (ledger.error) { console.warn('Debt API error:', ledger.error); return; }
    const items = ledger.items || [];
    const tierCounts = {}; const policyCounts = {}; const ruleCounts = {};
    STATIC_TIERS.forEach(t => { tierCounts[t.id] = { count: 0, color: t.color }; });
    STATIC_POLICIES.forEach(p => { policyCounts[p.id] = { ...p, count: 0 }; });
    STATIC_RULES.forEach(r => { ruleCounts[r.id] = { ...r, count: 0 }; });
    items.forEach(d => {
      const tier = d.x3 || d.x3_tier;
      if (tier && tierCounts[tier]) tierCounts[tier].count++;
      const refs = Array.isArray(d.x1) ? d.x1 : (d.x1_policy_refs || []);
      refs.forEach(p => { if (policyCounts[p]) policyCounts[p].count++; });
      (d.x2 || []).forEach(r => { if (ruleCounts[r]) ruleCounts[r].count++; });
    });
    window.DEBTS = items;
    window.TIER_COUNTS = tierCounts;
    window.POLICY_COUNTS = policyCounts;
    window.RULE_COUNTS = ruleCounts;
    renderTierChart(); renderPolicyGrid(); renderX2Grid(); populateFilters(); renderTable(items);
  } catch(e) { console.warn('Live debt unavailable:', e); }
}

async function loadLiveStatus() {
  try {
    const [status, services] = await Promise.all([
      fetch('/api/status').then(r => r.ok ? r.json() : null),
      fetch('/api/services').then(r => r.ok ? r.json() : null)
    ]);
    if (status) {
      const meta = document.querySelector('.header .meta');
      if (meta) {
        const el = document.querySelector('.header .meta span:first-child');
        if (el) el.textContent = '\uD83D\uDCE6 ' + (status.total_services || '?') + ' services';
      }
    }
    const card = document.querySelector('.card-stat:first-child .value');
    if (card && services) {
      const online = services.filter(s => s.port_listening).length;
      card.textContent = online + '/' + services.length;
      card.style.color = online === services.length ? '#4ade80' : '#fbbf24';
    }
  } catch(e) { console.log('Status unavailable:', e); }
}
loadLiveDebt(); loadLiveStatus();
setInterval(loadLiveStatus, 30000);
setInterval(loadLiveDebt, 60000);
</script>"""

ARCH_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cockpit — 架构健康</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',monospace;background:#0d1117;color:#c9d1d9;padding:24px}
h1{color:#58a6ff;font-size:20px;margin-bottom:4px}
.sub{color:#8b949e;font-size:12px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:16px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px}
.card h2{font-size:14px;margin-bottom:8px;color:#58a6ff;display:flex;align-items:center;gap:8px}
.stat{display:flex;justify-content:space-between;padding:4px 0;font-size:12px;border-bottom:1px solid #21262d}
.stat:last-child{border:none}
.label{color:#8b949e}
.val{color:#e6edf3;font-weight:600}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600}
.badge-pass{background:#052e16;color:#4ade80}.badge-warn{background:#271c00;color:#fbbf24}.badge-fail{background:#3b0d0d;color:#f87171}
.bar-bg{background:#21262d;border-radius:4px;height:8px;overflow:hidden;margin:4px 0}
.bar-fill{height:100%;border-radius:4px;transition:width .5s}
.status-dot{width:10px;height:10px;border-radius:50%;display:inline-block;flex-shrink:0}
.dot-ok{background:#4ade80}.dot-warn{background:#fbbf24}.dot-fail{background:#f87171}
table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:left;color:#8b949e;padding:6px 4px;border-bottom:1px solid #30363d}
td{padding:6px 4px;border-bottom:1px solid #21262d}
.nav{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap}
.nav a{padding:6px 14px;background:#161b22;border:1px solid #30363d;border-radius:6px;font-size:12px;color:#58a6ff;text-decoration:none}
.nav a:hover{background:#1c2333;border-color:#58a6ff}
.legacy-link{font-size:12px;color:#8b949e;margin-top:16px;text-align:center}
.pipeline-node{display:flex;align-items:center;gap:8px;padding:8px;margin:4px 0;background:#0d1117;border:1px solid #21262d;border-radius:6px}
.pipeline-node .step-label{font-size:11px;font-weight:600;min-width:60px}
.pipeline-arrow{color:#30363d;text-align:center;font-size:10px}
</style>
</head>
<body>
<h1>&#x25C8; Cockpit — 架构健康</h1>
<div class="sub">治理管道 · 系统健康 · Git 状态 · Ruff Lint · 审计存档</div>
<div class="nav">
  <a href="/overview">&#x1F30D; 统一状态</a>
  <a href="/overview">&#x1F4CA; 债务驾驶舱</a>
  <a href="/bos">&#x1F4E6; BOS 可观测</a>
  <a href="/api/v1/arch-health">&#x1F4CB; API JSON</a>
  <a href="/">&#x2728; Hermes Console</a>
</div>
<div id="arch-grid" class="grid"></div>
<div id="pipeline-detail" class="grid" style="margin-top:16px"></div>
<div id="audit-section" class="grid" style="margin-top:16px"></div>
<div class="legacy-link">
  <span id="refresh-time"></span>
</div>
<script>
async function refresh() {
  try {
    const r = await fetch('/api/v1/arch-health');
    const d = await r.json();
    let gridHtml = '';

    // Governance pipeline card
    const gov = d.governance || {};
    const govDot = gov.health === 'fresh' ? 'dot-ok' : gov.health === 'aging' ? 'dot-warn' : 'dot-fail';
    const govBadge = gov.health === 'fresh' ? 'badge-pass' : gov.health === 'aging' ? 'badge-warn' : 'badge-fail';
    const govLabel = gov.health === 'fresh' ? '新鲜' : gov.health === 'aging' ? '老化' : '停滞';
    gridHtml += '<div class="card"><h2><span class="status-dot '+govDot+'"></span> 治理管道</h2>'+
      '<div class="stat"><span class="label">状态</span><span class="badge '+govBadge+'">'+govLabel+'</span></div>'+
      '<div class="stat"><span class="label">最后心跳</span><span class="val">'+(gov.days_since!=null?gov.days_since+'天前':'未知')+'</span></div>'+
      '<div class="stat"><span class="label">历史条目</span><span class="val">'+(gov.total_entries||0)+'</span></div>'+
      '</div>';

    // System health
    const sys = d.system || {};
    const score = sys.health_score;
    if (score !== undefined) {
      const barColor = score >= 80 ? '#4ade80' : score >= 60 ? '#fbbf24' : '#f87171';
      gridHtml += '<div class="card"><h2><span class="status-dot '+(score>=80?'dot-ok':score>=60?'dot-warn':'dot-fail')+'"></span> 系统健康分</h2>'+
        '<div style="font-size:36px;font-weight:700;text-align:center;color:'+barColor+'">'+score+'</div>'+
        '<div style="text-align:center;font-size:11px;color:#8b949e">/ 100</div>'+
        '<div class="bar-bg"><div class="bar-fill" style="width:'+score+'%;background:'+barColor+'"></div></div>'+
        '<div class="stat"><span class="label">更新</span><span class="val">'+(sys.last_updated||'N/A')+'</span></div>'+
        '</div>';
    }

    // Git status
    const git = d.git || {};
    const gitDot = git.status === 'clean' ? 'dot-ok' : 'dot-warn';
    gridHtml += '<div class="card"><h2><span class="status-dot '+gitDot+'"></span> Git (ecos)</h2>'+
      '<div class="stat"><span class="label">状态</span><span class="val">'+(git.status||'?')+'</span></div>'+
      '<div class="stat"><span class="label">未提交</span><span class="val">'+(git.uncommitted||0)+' 文件</span></div>'+
      '</div>';

    // Ruff lint
    const rf = d.ruff || {};
    const rfDot = rf.check === 'passed' ? 'dot-ok' : 'dot-fail';
    gridHtml += '<div class="card"><h2><span class="status-dot '+rfDot+'"></span> Ruff Lint</h2>'+
      '<div class="stat"><span class="label">检查</span><span class="val">'+(rf.check||'?')+'</span></div>'+
      '<div class="stat"><span class="label">错误</span><span class="val">'+(rf.errors||0)+'</span></div>'+
      '</div>';

    // Cron job health
    const cron = d.cron || {};
    const cronPct = cron.total ? Math.round(cron.ok / cron.total * 100) : 0;
    const cronBarColor = cronPct >= 80 ? '#4ade80' : cronPct >= 60 ? '#fbbf24' : '#f87171';
    gridHtml += '<div class="card"><h2><span class="status-dot '+(cron.error>0?'dot-warn':'dot-ok')+'"></span> Cron 任务</h2>'+
      '<div class="stat"><span class="label">总/OK/ERR</span><span class="val">'+cron.total+'/'+cron.ok+'/'+cron.error+'</span></div>'+
      '<div class="stat"><span class="label">成功率</span><span class="val">'+cronPct+'%</span></div>'+
      '<div class="bar-bg"><div class="bar-fill" style="width:'+cronPct+'%;background:'+cronBarColor+'"></div></div>'+
      '</div>';

    // MCP backends
    const mcp = d.mcp || {};
    gridHtml += '<div class="card"><h2><span class="status-dot dot-ok"></span> MCP Backends</h2>'+
      '<div class="stat"><span class="label">已注册</span><span class="val">'+mcp.total+'</span></div>'+
      '<div style="margin-top:6px;font-size:10px;color:#8b949e;max-height:120px;overflow-y:auto">'+
      (mcp.backends||[]).map(function(b){ return '<div style="padding:1px 0">'+b+'</div>'; }).join('')+
      '</div></div>';

    // Audit trail
    const aud = d.audits || {};
    gridHtml += '<div class="card"><h2>&#x1F4DD; 审计存档</h2>'+
      '<div class="stat"><span class="label">总数</span><span class="val">'+aud.total+' 份</span></div>'+
      '<div class="stat"><span class="label">最新</span><span class="val" style="font-size:10px">'+(aud.latest?aud.latest.slice(0,40):'N/A')+'</span></div>'+
      '</div>';

    // Convergence score
    const conv = d.convergence || {};
    if (conv.score !== undefined) {
      const convColor = conv.score >= 80 ? '#4ade80' : conv.score >= 60 ? '#fbbf24' : '#f87171';
      const convDot = conv.score >= 80 ? 'dot-ok' : conv.score >= 60 ? 'dot-warn' : 'dot-fail';
      let convBody = '<div class="stat"><span class="label">等级</span><span class="val">'+conv.grade+'</span></div>';
      Object.entries(conv.dimensions||{}).forEach(function([k, v]) {
        const barColor = v.score >= 80 ? '#4ade80' : v.score >= 60 ? '#fbbf24' : '#f87171';
        convBody += '<div class="stat"><span class="label" style="font-size:10px">'+k+' ('+v.weight+'%)</span><span class="val">'+v.score+'</span></div>'+
          '<div class="bar-bg" style="margin:2px 0 6px 0"><div class="bar-fill" style="width:'+v.score+'%;background:'+barColor+';height:4px"></div></div>';
      });
      gridHtml += '<div class="card"><h2><span class="status-dot '+convDot+'"></span> 收敛评分</h2>'+
        '<div style="font-size:36px;font-weight:700;text-align:center;color:'+convColor+'">'+conv.score+'</div>'+
        '<div style="text-align:center;font-size:11px;color:#8b949e">/ 100</div>'+
        '<div class="bar-bg"><div class="bar-fill" style="width:'+conv.score+'%;background:'+convColor+'"></div></div>'+
        convBody+'</div>';
    }

    if (!gridHtml) gridHtml = '<div class="card" style="grid-column:1/-1"><div class="stat"><span class="label">无架构健康数据</span></div></div>';
    document.getElementById('arch-grid').innerHTML = gridHtml;

    // Detail section
    let detailHtml = '<div class="grid" style="grid-column:1/-1">';

    // Governance detail
    detailHtml += '<div class="card" style="grid-column:1/-1"><h2>&#x1F4E1; 治理管道详情</h2>'+
      '<div class="stat"><span class="label">最后心跳时间</span><span class="val">'+(gov.last_entry||'N/A')+'</span></div>'+
      '<div class="stat"><span class="label">健康判断</span><span class="val">'+(gov.days_since!=null?(gov.days_since+'天无新记录'):'未知')+'</span></div>'+
      '</div>';

    // Cron jobs table
    if (cron.jobs && cron.jobs.length > 0) {
      detailHtml += '<div class="card" style="grid-column:1/-1"><h2>&#x23F0; Cron 任务列表</h2><table><tr><th>任务</th><th>状态</th><th>调度</th></tr>';
      cron.jobs.forEach(function(j) {
        const cls = j.status === 'ok' ? 'badge-pass' : j.status === 'error' ? 'badge-fail' : 'badge-warn';
        const label = j.status || 'never';
        detailHtml += '<tr><td style="font-size:11px">'+(j.name||'?')+'</td><td><span class="badge '+cls+'">'+label+'</span></td><td style="font-size:10px;color:#8b949e">'+(j.schedule||'')+'</td></tr>';
      });
      detailHtml += '</table></div>';
    }

    // Recent audits
    if (aud.recent && aud.recent.length > 0) {
      detailHtml += '<div class="card" style="grid-column:1/-1"><h2>&#x1F4CB; 最近审计</h2><table><tr><th>审计项</th></tr>';
      aud.recent.forEach(function(a) {
        detailHtml += '<tr><td style="font-size:10px">'+a.slice(0,60)+'</td></tr>';
      });
      detailHtml += '</table></div>';
    }

    detailHtml += '</div>';
    document.getElementById('pipeline-detail').innerHTML = detailHtml;
    document.getElementById('audit-section').innerHTML = '';

    document.getElementById('refresh-time').textContent = 'Updated '+new Date().toLocaleTimeString();
  } catch(e) {
    document.getElementById('arch-grid').innerHTML = '<div class="card" style="grid-column:1/-1"><p style="color:#f87171">加载失败: '+e.message+'</p></div>';
    console.error(e);
  }
}
refresh();setInterval(refresh,15000);
</script>
</body></html>"""
