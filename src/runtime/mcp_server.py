"""Runtime MCP Server — expose L1 operations as MCP tools.

Connects via stdio transport (launched by MCP client).
No port management needed. No daemon.
"""
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

RUNTIME_HOME = Path(os.environ.get("RUNTIME_HOME", Path.home() / "runtime"))
PROJECT_HOME = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_HOME / "scripts"


def _run_script(script_name: str, *args: str) -> str:
    script = SCRIPTS_DIR / script_name
    env = os.environ.copy()
    env["RUNTIME_HOME"] = str(RUNTIME_HOME)
    try:
        r = subprocess.run(
            [str(script), *args],
            capture_output=True, text=True, timeout=30, env=env,
        )
        return r.stdout.strip() if r.returncode == 0 else (
            f"❌ Error (exit={r.returncode}): {r.stderr.strip() or r.stdout.strip()}")
    except subprocess.TimeoutExpired:
        return "❌ Timeout (30s)"
    except FileNotFoundError:
        return f"❌ Script not found: {script}"

def _matrix_list() -> str:
    from runtime.matrix import list_services
    services = list_services()
    parts = [f"{'NAME':20s} {'TYPE':12s} {'PORT':6s} {'STATUS':12s}", "-" * 60]
    for s in services:
        port = str(s.port) if s.port else "—"
        parts.append(f"{s.name:20s} {s.type:12s} {port:6s} {s.status:12s}")
    return "\n".join(parts)

def _matrix_get(name: str) -> str:
    from runtime.matrix import get_service, resolve_path
    svc = get_service(name)
    if not svc: return f"❌ Service not found: {name}"
    lines = [f"Name:     {svc.name}", f"Type:     {svc.type}", f"Status:   {svc.status}"]
    if svc.port: lines.append(f"Port:     {svc.port}")
    if svc.launchd_label: lines.append(f"Launchd:  {svc.launchd_label}")
    if svc.health_url: lines.append(f"Health:   {svc.health_url}")
    if svc.docker_container: lines.append(f"Docker:   {svc.docker_container}")
    dp = resolve_path(svc.deploy_path)
    if dp: lines.append(f"Deploy:   {dp}")
    lp = resolve_path(svc.log_path)
    if lp: lines.append(f"Logs:     {lp}")
    return "\n".join(lines)

def _protocol_list() -> str:
    from runtime.protocol import L0_PROTOCOLS
    icons = {"active": "✅", "draft": "📝", "planned": "🔲", "deprecated": "🗄️"}
    parts = [f"{'PROTOCOL':25s} {'VERSION':12s} {'CATEGORY':22s} {'STATUS':10s}", "-" * 75]
    for p in L0_PROTOCOLS:
        icon = icons.get(p.status, "❓")
        parts.append(f"{icon} {p.name:22s} {p.version:12s} {p.category:22s} {p.status:10s}")
    parts.append(f"\nTotal: {len(L0_PROTOCOLS)} protocols")
    return "\n".join(parts)

def _protocol_get(name: str) -> str:
    from runtime.protocol import get_protocol
    p = get_protocol(name)
    if not p: return f"❌ Protocol not found: {name}"
    lines = [f"Protocol:  {p.name} v{p.version}", f"Category:  {p.category}", f"Status:    {p.status}", f"Desc:      {p.description}"]
    if p.spec_url: lines.append(f"Spec:      {p.spec_url}")
    if p.port_range: lines.append(f"Ports:     {p.port_range}")
    lines.append(f"Transport: {', '.join(p.transport)}")
    return "\n".join(lines)


# ─── Tool definitions ────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "runtime_health",
        "description": "Run a full health scan of all services. Returns JSON.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: _run_script("health-scan.sh", "--json"),
    },
    {
        "name": "runtime_matrix_list",
        "description": "List all services in the runtime matrix.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: _matrix_list(),
    },
    {
        "name": "runtime_matrix_get",
        "description": "Get detailed info about a specific service.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Service name"}},
            "required": ["name"],
        },
        "handler": lambda args: _matrix_get(args["name"]),
    },
    {
        "name": "runtime_service_ctl",
        "description": "Start, stop, restart, or check status of a service.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Service name"},
                "action": {"type": "string", "enum": ["status", "start", "stop", "restart"]},
            },
            "required": ["name", "action"],
        },
        "handler": lambda args: _run_script("service-ctl.sh", args["name"], args["action"]),
    },
    {
        "name": "runtime_protocol_list",
        "description": "List all L0 protocols in the registry.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: _protocol_list(),
    },
    {
        "name": "runtime_protocol_get",
        "description": "Get detailed info about a specific protocol.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Protocol name"}},
            "required": ["name"],
        },
        "handler": lambda args: _protocol_get(args["name"]),
    },
]

TOOL_MAP = {t["name"]: t for t in TOOLS}


# ─── MCP Server (raw JSON-RPC over stdio) ────────────────────────────────

def send_response(msg: dict) -> None:
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()

def handle_request(req: dict) -> dict:
    method = req.get("method", "")
    req_id = req.get("id")
    params = req.get("params", {})

    if method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "tools": [
                    {"name": t["name"], "description": t["description"],
                     "inputSchema": t["inputSchema"]}
                    for t in TOOLS
                ]
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        tool = TOOL_MAP.get(tool_name)
        if not tool:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}
            }
        try:
            result = tool["handler"](arguments)
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": result}]}
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32000, "message": str(e)}
            }

    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    elif method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "eCOS Runtime", "version": "0.1.0"}
            }
        }

    elif method == "notifications/initialized":
        return None  # no response for notifications

    else:
        return {
            "jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }


import json

def main():
    """Main loop: read JSON-RPC from stdin, write to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
            if resp is not None:
                send_response(resp)
        except json.JSONDecodeError:
            send_response({
                "jsonrpc": "2.0", "id": None,
                "error": {"code": -32700, "message": "Parse error"}
            })
        except Exception as e:
            send_response({
                "jsonrpc": "2.0", "id": None,
                "error": {"code": -32000, "message": str(e)}
            })

if __name__ == "__main__":
    main()
