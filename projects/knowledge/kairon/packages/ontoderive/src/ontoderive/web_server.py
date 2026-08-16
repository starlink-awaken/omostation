"""OntoDerive Web Server — FastAPI 仪表盘 + MCP/SSE 传输层"""

from __future__ import annotations

import threading
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ontoderive.core.derive import OntoDerive
from ontoderive.mcp_server import TOOL_DEFS, handle_mcp_request

app = FastAPI(title="OntoDerive", version="3.6.4")

# 项目缓存
_project: OntoDerive | None = None
_project_path: str = "."


def _get_od(project: str | None = None) -> OntoDerive:
    global _project, _project_path
    p = project or _project_path
    if _project is None or _project_path != p:
        _project = OntoDerive(p)
        _project_path = p
    return _project


# ── API 路由 ──


@app.get("/api/status")
async def api_status(project: str = "") -> Any:
    od = _get_od(project or None)
    try:
        r = od.derive()
        check = od.check()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return {
        "project": project or _project_path,
        "facts": len(r.get("facts", {})),
        "inferences": len(r.get("inferences", {})),
        "conclusions": len(r.get("derived_conclusions", [])),
        "checks_passed": sum(1 for c in check if c.get("passed")),
        "checks_total": len(check),
    }


@app.get("/api/derive")
async def api_derive(project: str = "") -> Any:
    od = _get_od(project or None)
    return od.derive()


@app.get("/api/check")
async def api_check(project: str = "") -> Any:
    od = _get_od(project or None)
    return od.check()


@app.get("/api/export")
async def api_export(project: str = "", fmt: str = "json") -> Any:
    od = _get_od(project or None)
    r = od.derive()
    from ontoderive.core.export import to_html, to_json

    if fmt == "html":
        return HTMLResponse(to_html(r, project or _project_path))
    if fmt == "json":
        return to_json(r)
    return {"error": f"unknown format: {fmt}"}


# ── MCP over HTTP/SSE (AgentMesh 集成) ──


@app.post("/mcp")
async def mcp_call(request: Request) -> Any:
    """JSON-RPC compatibility bridge backed by the FastMCP tool surface."""
    body = await request.json()
    body["jsonrpc"] = "2.0"
    return JSONResponse(handle_mcp_request(body))


@app.get("/mcp/tools")
async def mcp_tools() -> dict[str, Any]:
    """返回 FastMCP-native 工具列表 — 供 AgentMesh 注册"""
    return {"tools": TOOL_DEFS}


# ── 仪表盘页面 ──


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OntoDerive Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, sans-serif;
         background: #0f172a; color: #e2e8f0; padding: 2rem; }
  h1 { font-size: 1.5rem; margin-bottom: 1rem; color: #38bdf8; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 1rem; margin-bottom: 2rem; }
  .card { background: #1e293b; border-radius: 8px; padding: 1.25rem; }
  .card h3 { font-size: 0.75rem; text-transform: uppercase; color: #64748b; margin-bottom: 0.5rem; }
  .card .value { font-size: 2rem; font-weight: 700; color: #38bdf8; }
  .card .value.pass { color: #4ade80; }
  .card .value.fail { color: #f87171; }
  button { background: #2563eb; color: white; border: none; padding: 0.5rem 1rem;
           border-radius: 6px; cursor: pointer; font-size: 0.875rem; }
  button:hover { background: #1d4ed8; }
  pre { background: #1e293b; border-radius: 8px; padding: 1rem; overflow: auto;
        max-height: 400px; font-size: 0.8rem; margin-top: 1rem; }
  .tools-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                gap: 0.5rem; margin-top: 1rem; }
  .tool-card { background: #1e293b; border-radius: 6px; padding: 0.75rem; font-size: 0.8rem; }
  .tool-card .name { color: #38bdf8; font-weight: 600; }
  .tool-card .desc { color: #94a3b8; margin-top: 0.25rem; }
</style>
</head>
<body>
  <h1>OntoDerive v3.6.4 <span style="font-size:0.8rem;color:#64748b;font-weight:400">Dashboard</span></h1>
  <div class="grid" id="status">
    <div class="card"><h3>项目</h3><div class="value" id="project">-</div></div>
    <div class="card"><h3>事实</h3><div class="value" id="facts">-</div></div>
    <div class="card"><h3>推论</h3><div class="value" id="inferences">-</div></div>
    <div class="card"><h3>结论</h3><div class="value" id="conclusions">-</div></div>
    <div class="card"><h3>检查通过</h3><div class="value pass" id="checks_passed">-</div></div>
  </div>

  <div style="margin-bottom:1rem;display:flex;gap:0.5rem;align-items:center">
    <input id="projectInput" value="."
           style="background:#1e293b;color:#e2e8f0;border:1px solid #334155;border-radius:6px">
    <button onclick="refresh()">刷新</button>
    <button onclick="derive()">推导</button>
    <button onclick="exportHTML()">导出 HTML</button>
  </div>

  <h2 style="font-size:1rem;margin-bottom:0.5rem;color:#94a3b8">MCP 工具</h2>
  <div class="tools-grid" id="tools"></div>

  <h2 style="font-size:1rem;margin:1rem 0 0.5rem;color:#94a3b8">输出</h2>
  <pre id="output">点击按钮查看结果</pre>

<script>
async function api(path) {
  const project = document.getElementById('projectInput').value;
  const resp = await fetch(`${path}?project=${encodeURIComponent(project)}`);
  return resp.json();
}

async function refresh() {
  const data = await api('/api/status');
  document.getElementById('project').textContent = data.project || '-';
  document.getElementById('facts').textContent = data.facts ?? '-';
  document.getElementById('inferences').textContent = data.inferences ?? '-';
  document.getElementById('conclusions').textContent = data.conclusions ?? '-';
  document.getElementById('checks_passed').textContent =
    `${data.checks_passed ?? '-'}/${data.checks_total ?? '-'}`;
  document.getElementById('output').textContent = JSON.stringify(data, null, 2);
}

async function derive() {
  const data = await api('/api/derive');
  document.getElementById('output').textContent = JSON.stringify(data, null, 2);
}

async function exportHTML() {
  const project = document.getElementById('projectInput').value;
  window.open(`/api/export?project=${encodeURIComponent(project)}&fmt=html`, '_blank');
}

async function loadTools() {
  const resp = await fetch('/mcp/tools');
  const data = await resp.json();
  const container = document.getElementById('tools');
  container.innerHTML = (data.tools || []).map(t =>
    `<div class="tool-card"><div class="name">${t.name}</div><div class="desc">${t.description}</div></div>`
  ).join('');
}

refresh();
loadTools();
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> Any:
    return DASHBOARD_HTML


def serve(project: str = ".", host: str = "127.0.0.1", port: int = 8080, watch: bool = True) -> None:
    """启动 Web 服务"""
    global _project_path
    _project_path = project

    if watch:
        from ontoderive.watcher import FileWatcher

        t = threading.Thread(target=FileWatcher(project).watch, daemon=True)
        t.start()

    import uvicorn

    print(f"[serve] OntoDerive Dashboard → http://{host}:{port}")
    print(f"[serve] MCP HTTP         → http://{host}:{port}/mcp")
    uvicorn.run(app, host=host, port=port, log_level="info")
