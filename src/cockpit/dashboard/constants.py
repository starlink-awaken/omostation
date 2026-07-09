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
    {"layer": "I0", "name": "agora", "url": f"http://localhost:{os.environ.get('AGORA_MCP_SSE_PORT', '7431')}/v1/health", "port": int(os.environ.get("AGORA_MCP_SSE_PORT", "7431"))},
    {"layer": "L2", "name": "omo", "url": f"http://localhost:{os.environ.get('OMO_DASHBOARD_PORT', '9190')}/api/v1/status", "port": int(os.environ.get("OMO_DASHBOARD_PORT", "9190"))},
    {"layer": "L1", "name": "runtime", "url": f"http://localhost:{os.environ.get('RUNTIME_L1_PORT', '9876')}/api/v1/status", "port": int(os.environ.get("RUNTIME_L1_PORT", "9876"))},
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
<title>Cockpit — Today &amp; Overview</title>
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
.quick-actions{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap}
.quick-actions a{padding:10px 20px;background:#161b22;border:1px solid #58a6ff;border-radius:8px;font-size:13px;color:#58a6ff;text-decoration:none;font-weight:600}
.quick-actions a:hover{background:#1c2333;border-color:#4ade80}
</style>
</head>
<body>
<h1>&#x25C8; Cockpit — Today &amp; Overview</h1>
<div class="sub">L3 &#x805a;&#x5408;&#x5165;&#x53e3; &middot; &#x4eca;&#x65e5;&#x6982;&#x89c8; &middot; &#x5c42;&#x72b6;&#x6001; &middot; &#x6536;&#x655b;&#x8fdb;&#x5ea6;</div>

<!-- &#x5feb;&#x901f;&#x6267;&#x884c; -->
<div class="quick-actions">
  <a href="/bos">&#x1F4E6; BOS Dashboard</a>
  <a href="/arch">&#x1F527; &#x67b6;&#x6784;&#x5065;&#x5eb7;</a>
  <a href="/">&#x2728; Hermes Console</a>
  <a href="/api/v1/status">&#x1F4CB; API JSON</a>
  <a href="http://localhost:8090/overview">&#x1F4CA; &#x503a;&#x52a1;&#x9a7e;&#x9a76;&#x8231;</a>
</div>

<!-- Today at a Glance cards -->
<div class="grid" id="today-cards"></div>

<!-- Layer status grid -->
<div class="grid" id="layer-grid">
  <div style="color:#8b949e;grid-column:1/-1;text-align:center;padding:40px">Loading...</div>
</div>

<!-- Convergence status -->
<div class="grid" id="convergence-section" style="margin-top:16px"></div>

<div class="legacy-link">
  <span id="refresh-time"></span>
</div>
<script>
async function loadOverview() {
  try {
    // Fetch all data in parallel
    const [statusR, convR] = await Promise.all([
      fetch('/api/v1/status').then(r => r.ok ? r.json() : null),
      fetch('/api/convergence/status').then(r => r.ok ? r.json() : null),
    ]);
    const d = statusR || {layers:[],summary:{}};
    const conv = convR || {};

    // Today's cards
    const totalOk = d.summary ? d.summary.healthy : 0;
    const totalLayers = d.summary ? d.summary.total_layers : 0;
    const healthPct = totalLayers ? Math.round(totalOk/totalLayers*100) : 0;
    const convPct = conv.convergence_pct || 0;
    document.getElementById('today-cards').innerHTML = [
      {label:'&#x5c42;&#x5065;&#x5eb7;', val:totalOk+'/'+totalLayers, pct:healthPct, color:healthPct>=80?'#4ade80':'#fbbf24'},
      {label:'&#x6536;&#x655b;&#x8fdb;&#x5ea6;', val:convPct+'%', pct:convPct, color:convPct>=80?'#4ade80':'#fbbf24'},
      {label:'&#x5269;&#x4f59;&#x5165;&#x53e3;', val:(conv.remaining||[]).length+'/'+(conv.total_entry_points||0), pct:0},
      {label:'&#x6700;&#x65b0;&#x5237;&#x65b0;', val:new Date().toLocaleTimeString(), pct:0},
    ].map(c => '<div class="layer-card" style="text-align:center"><div style="font-size:12px;color:#8b949e;margin-bottom:4px">'+c.label+'</div><div style="font-size:28px;font-weight:700;color:'+(c.color||'#58a6ff')+'">'+c.val+'</div>'+(c.pct>0?'<div style="background:#21262d;border-radius:4px;height:6px;margin-top:6px;overflow:hidden"><div style="height:100%;width:'+c.pct+'%;background:'+c.color+';border-radius:4px"></div></div>':'')+'</div>').join('');

    // Layer status
    let html = '';
    d.layers.forEach(l => {
      const badgeCls=l.status==='ok'?'badge-ok':l.status==='degraded'?'badge-degraded':'badge-down';
      const dotCls='dot-'+l.status;
      let body='';
      if(l.data){
        if(l.data.router)body+='<div class="stat"><span class="label">&#x8def;&#x7531;</span><span class="val">'+l.data.router.total_routes+'</span></div>';
        if(l.data.domains)body+='<div class="stat"><span class="label">&#x57df;</span><span class="val">'+Object.keys(l.data.domains).length+'</span></div>';
        if(l.data.metrics)body+='<div class="stat"><span class="label">&#x8c03;&#x7528;</span><span class="val">'+l.data.metrics.total_calls+'</span></div>';
        if(l.data.poc_services)body+='<div class="stat"><span class="label">POC</span><span class="val">'+l.data.poc_services.total+'</span></div>';
        if(l.data.summary){
          const s=l.data.summary;
          body+='<div class="stat"><span class="label">&#x5065;&#x5eb7;</span><span class="val">'+s.healthy+'/'+s.total_layers+'</span></div>';
        }
        if(l.data.snapshot){
          const snap=l.data.snapshot;
          body+='<div class="stat"><span class="label">Daemon</span><span class="val">'+(snap.daemon.healthy?'&#x2705; &#x5065;&#x5eb7;':'&#x274c; &#x5f02;&#x5e38;')+'</span></div>';
          body+='<div class="stat"><span class="label">&#x8282;&#x70b9;</span><span class="val">'+snap.m1_node_count+'</span></div>';
          body+='<div style="margin-top:8px;font-size:11px;color:#8b949e">&#x534f;&#x8bae;&#x8870;&#x51cf;</div>';
          for(const [pname, p] of Object.entries(snap.protocols||{})){
            const pct=p.remaining_pct;
            const barColor=pct>80?'#4ade80':pct>50?'#fbbf24':'#f87171';
            body+='<div style="margin:3px 0;padding:4px 6px;background:#0d1117;border:1px solid #21262d;border-radius:4px;font-size:10px">'+
              '<div style="display:flex;justify-content:space-between">'+
              '<span>'+pname+' <span class="badge '+(status==='fresh'?'badge-ok':status==='aging'?'badge-degraded':'badge-down')+'">'+p.status+'</span></span>'+
              '<span>'+pct+'%</span></div>'+
              '<div style="background:#21262d;border-radius:4px;height:5px;overflow:hidden;margin-top:2px">'+
              '<div style="height:100%;width:'+pct+'%;background:'+barColor+';border-radius:4px"></div></div></div>';
          }
        }
      }
      if(l.error)body+='<div class="stat"><span class="label">&#x9519;&#x8bef;</span><span style="color:#f87171;font-size:11px">'+l.error.slice(0,60)+'</span></div>';
      if(!body)body='<div class="stat"><span class="label">&#x65e0;&#x6570;&#x636e;</span></div>';
      html+='<div class="layer-card"><h2><span class="status-dot '+dotCls+'"></span> '+l.layer+' '+l.name+' <span class="badge '+badgeCls+'">'+l.status+'</span></h2>'+body+'</div>';
    });
    document.getElementById('layer-grid').innerHTML=html;

    // Convergence section
    let convHtml = '';
    if (conv.entries) {
      convHtml += '<div class="layer-card" style="grid-column:1/-1"><h2>&#x1F500; &#x6536;&#x655b;&#x8fdb;&#x5ea6;: '+(conv.converged_to_cockpit||0)+'/'+(conv.total_entry_points||0)+' &#x5411; cockpit</h2><table style="width:100%;border-collapse:collapse;font-size:12px"><tr><th>CLI</th><th>&#x89d2;&#x8272;</th><th>&#x5df2;&#x6536;&#x655b;</th><th>&#x91cd;&#x5b9a;&#x5411;</th></tr>';
      conv.entries.forEach(function(e) {
        const cls = e.converged ? 'badge-ok' : 'badge-down';
        convHtml += '<tr><td>'+e.cli+'</td><td style="color:#8b949e">'+e.role+'</td><td><span class="badge '+cls+'">'+(e.converged?'&#x2705; &#x5df2;&#x6536;&#x655b;':'&#x274c; &#x5c1a;&#x672a;')+'</span></td><td style="font-size:10px;color:#8b949e">'+(e.redirect||'-')+'</td></tr>';
      });
      convHtml += '</table></div>';
    }
    document.getElementById('convergence-section').innerHTML = convHtml;
    document.getElementById('refresh-time').textContent = 'Updated '+new Date().toLocaleTimeString();
  } catch(e) {
    document.getElementById('layer-grid').innerHTML = '<div class="layer-card" style="grid-column:1/-1"><p style="color:#f87171">&#x52a0;&#x8f7d;&#x5931;&#x8d25;: '+e.message+'</p></div>';
    console.error(e);
  }
}
loadOverview();setInterval(loadOverview,15000);
</script>
</body></html>"""

BOS_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cockpit — 产品控制台</title>
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
<h1>&#x25C8; Cockpit — 产品控制台</h1>
<div class="sub">BOS &#x53ef;&#x89c2;&#x6d4b; &middot; Cron &#x6d41;&#x6c34;&#x7ebf; &middot; &#x6cbb;&#x7406;&#x5ba1;&#x8ba1; &middot; &#x4ea7;&#x54c1;&#x8fdb;&#x5ea6;</div>
<div class="nav">
  <a href="/overview">&#x1F30D; &#x72b6;&#x6001;&#x6982;&#x89c8;</a>
  <a href="/arch">&#x1F527; &#x67b6;&#x6784;&#x5065;&#x5eb7;</a>
  <a href="/">&#x2728; Hermes Console</a>
  <a href="/api/bos/metrics">&#x1F4CB; BOS JSON</a>
  <a href="/api/cron/summary">&#x1F4CB; Cron JSON</a>
  <a href="/api/governance/summary">&#x1F4CB; &#x6cbb;&#x7406;JSON</a>
</div>
<!-- Today at a Glance -->
<div id="today-glance" class="grid"></div>
<!-- BOS Summary -->
<div id="summary" class="grid"></div>
<!-- BOS Domains -->
<div id="domains"></div>
<!-- Cron Pipeline -->
<div id="cron-section"></div>
<!-- Governance Audit -->
<div id="governance-section"></div>
<!-- BOS Recent Calls -->
<div class="grid" id="details"></div>
<script>
async function loadAll() {
  try {
    // Fetch all APIs in parallel
    const [metricsR, cronR, govR, convR] = await Promise.all([
      fetch('/api/bos/metrics').then(r => r.ok ? r.json() : null),
      fetch('/api/cron/summary').then(r => r.ok ? r.json() : null),
      fetch('/api/governance/summary').then(r => r.ok ? r.json() : null),
      fetch('/api/convergence/status').then(r => r.ok ? r.json() : null),
    ]);
    const d = metricsR || {summary:{},domains:[],recent:[]};
    const cron = cronR || {total_tasks:0,today_tasks:[],all_tasks:[]};
    const gov = govR || {health_score:0};
    const conv = convR || {};

    // Today at a Glance cards
    const healthScore = gov.health_score || 0;
    const bosCalls = d.summary ? d.summary.total_calls : 0;
    const cronToday = cron.today_count || 0;
    const convPct = conv.convergence_pct || 0;
    document.getElementById('today-glance').innerHTML = [
      {label:'&#x5065;&#x5eb7;&#x5206;', val:healthScore+'/100', color:healthScore>=80?'#4ade80':healthScore>=60?'#fbbf24':'#f87171', pct:healthScore},
      {label:'BOS &#x8c03;&#x7528;', val:bosCalls, color:'#58a6ff'},
      {label:'Cron &#x4eca;&#x65e5;', val:cronToday+' &#x4efb;&#x52a1;', color:cron.error_count>0?'#f87171':'#4ade80'},
      {label:'&#x6536;&#x655b;&#x7387;', val:convPct+'%', color:convPct>=80?'#4ade80':convPct>=60?'#fbbf24':'#f87171', pct:convPct},
    ].map(c => '<div class="card" style="text-align:center"><div style="font-size:12px;color:#8b949e;margin-bottom:4px">'+c.label+'</div><div style="font-size:32px;font-weight:700;color:'+(c.color||'#58a6ff')+'">'+c.val+'</div>'+(c.pct!==undefined?'<div style="background:#21262d;border-radius:4px;height:6px;margin-top:6px;overflow:hidden"><div style="height:100%;width:'+c.pct+'%;background:'+c.color+';border-radius:4px"></div></div>':'')+'</div>').join('');

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

    // Cron Pipeline section
    let chtml = '<div class="card" style="grid-column:1/-1"><h2>&#x23F0; Cron &#x6d41;&#x6c34;&#x7ebf; <span style="font-size:11px;color:#8b949e;font-weight:400">&#x4eca;&#x65e5;'+(cron.today_count||0)+' &#x4efb;&#x52a1; &middot; &#x5171; '+cron.total_tasks+' &#x4efb;&#x52a1;</span></h2>';
    if (cron.today_tasks && cron.today_tasks.length > 0) {
      chtml += '<table><tr><th>&#x4efb;&#x52a1;</th><th>&#x72b6;&#x6001;</th><th>&#x6267;&#x884c;</th><th>&#x6458;&#x8981;</th></tr>';
      cron.today_tasks.slice(0,12).forEach(function(t) {
        const cls = t.status === 'ok' ? 'badge-resolved' : t.status === 'silent' ? '' : 'badge-error';
        const label = t.status === 'silent' ? '&#x5b89;&#x9759;' : t.status;
        chtml += '<tr><td style="font-size:10px;max-width:140px;overflow:hidden;text-overflow:ellipsis">'+(t.name||t.task_id).slice(0,40)+'</td><td><span class="badge '+cls+'">'+label+'</span></td><td style="font-size:10px;color:#8b949e">'+(t.latest_run||'').slice(0,16)+'</td><td style="font-size:10px;color:#8b949e;max-width:200px;overflow:hidden;text-overflow:ellipsis">'+((t.summary||'')).slice(0,60)+'</td></tr>';
      });
      chtml += '</table>';
    } else {
      chtml += '<div class="stat"><span class="label">&#x4eca;&#x65e5;&#x6682;&#x65e0; cron &#x4efb;&#x52a1;&#x6267;&#x884c;</span></div>';
    }
    chtml += '</div>';
    document.getElementById('cron-section').innerHTML = '<div class="grid">'+chtml+'</div>';

    // Governance Audit section
    let ghtml = '<div class="card" style="grid-column:1/-1"><h2>&#x1F4DD; &#x6cbb;&#x7406;&#x5ba1;&#x8ba1; <span style="font-size:11px;color:#8b949e;font-weight:400">&#x6700;&#x65b0;: '+(gov.latest_audit||'N/A')+'</span></h2>';
    ghtml += '<div class="stat"><span class="label">&#x5065;&#x5eb7;&#x5206;</span><span class="val">'+(gov.health_score||0)+'/100</span></div>';
    ghtml += '<div class="stat"><span class="label">&#x503a;&#x52a1;&#x603b;&#x6570;</span><span class="val">'+((gov.total_debt||0))+' ('+((gov.resolved||0))+' &#x5df2;&#x89e3;&#x51b3;, '+((gov.unresolved||0))+' &#x672a;&#x89e3;&#x51b3;)</span></div>';
    ghtml += '<div class="stat"><span class="label">&#x89e3;&#x51b3;&#x7387;</span><span class="val">'+(gov.resolution_rate||0)+'%</span></div>';
    ghtml += '<div class="stat"><span class="label">&#x9879;&#x76ee;&#x6570;</span><span class="val">'+(gov.project_count||0)+'</span></div>';
    if (gov.findings && gov.findings.length > 0) {
      ghtml += '<div style="margin-top:8px;font-size:11px;color:#58a6ff">&#x6700;&#x8fd1;&#x53d1;&#x73b0;</div>';
      gov.findings.slice(-5).forEach(function(f) {
        ghtml += '<div class="stat"><span class="label" style="font-size:10px">'+f.date+'</span><span style="font-size:10px;color:#8b949e">'+(f.note||'').slice(0,80)+'</span></div>';
      });
    }
    ghtml += '</div>';
    document.getElementById('governance-section').innerHTML = '<div class="grid">'+ghtml+'</div>';

  } catch(e) { document.getElementById('summary').innerHTML = '<div class="card"><p style="color:#f87171">&#x52a0;&#x8f7d;&#x5931;&#x8d25;: '+e.message+'</p></div>'; }
}
loadAll();setInterval(loadAll,30000);
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
    const [archR, govR] = await Promise.all([
      fetch('/api/v1/arch-health').then(r => r.ok ? r.json() : null),
      fetch('/api/governance/summary').then(r => r.ok ? r.json() : null),
    ]);
    const d = archR || {};
    const gov = govR || {health_score:0};
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

    // Audit trail (from arch health)
    const aud = d.audits || {};
    gridHtml += '<div class="card"><h2>&#x1F4DD; &#x5ba1;&#x8ba1;&#x5b58;&#x6863;</h2>'+
      '<div class="stat"><span class="label">&#x603b;&#x6570;</span><span class="val">'+aud.total+' &#x4efd;</span></div>'+
      '<div class="stat"><span class="label">&#x6700;&#x65b0;</span><span class="val" style="font-size:10px">'+(aud.latest?aud.latest.slice(0,40):'N/A')+'</span></div>'+
      '</div>';

    // Governance data from Wave 3 API
    gridHtml += '<div class="card"><h2>&#x1F4E1; &#x6cbb;&#x7406;&#x6570;&#x636e;</h2>'+
      '<div class="stat"><span class="label">&#x5065;&#x5eb7;&#x5206;</span><span class="val">'+(gov.health_score||0)+'/100</span></div>'+
      '<div class="stat"><span class="label">&#x503a;&#x52a1;</span><span class="val">'+((gov.total_debt||0))+' ('+((gov.resolved||0))+'/'+((gov.unresolved||0))+')</span></div>'+
      '<div class="stat"><span class="label">&#x89e3;&#x51b3;&#x7387;</span><span class="val">'+(gov.resolution_rate||0)+'%</span></div>'+
      '<div class="stat"><span class="label">&#x9879;&#x76ee;</span><span class="val">'+(gov.project_count||0)+'</span></div>'+
      '<div class="stat"><span class="label" style="font-size:10px">&#x8d8b;&#x52bf;&#x8bb0;&#x5f55;</span><span class="val" style="font-size:10px">'+(gov.trend_entries||0)+'</span></div>'+
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
