"""Runtime MCP Server — expose L1 operations as MCP tools.

Connects via stdio transport (launched by MCP client).
No port management needed. No daemon.
"""
import sys
import json
from runtime.tools.shared import _STATS, _record_taskobject_envelope
from runtime.tools import TOOLS, TOOL_MAP

def send_response(msg: dict) -> None:
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()

def handle_request(req: dict) -> dict | None:
    method = req.get("method", "")
    req_id = req.get("id")
    params = req.get("params", {})

    if method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "tools": [
                    {"name": t["name"], "description": t["description"],
                     "inputSchema": t["inputSchema"],
                     "callCount": _STATS.get(t["name"], 0)}
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
            from runtime.kei_sandbox import record_audit
            record_audit("execute", "ecos.runtime.mcp", "pass", f"Tool called: {tool_name}")
            _STATS[tool_name] = _STATS.get(tool_name, 0) + 1
            result = tool["handler"](arguments)
            _record_taskobject_envelope(tool_name, arguments, "ok")
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": str(result)}]}
            }
        except Exception as e:
            from runtime.kei_sandbox import record_audit
            record_audit("execute", "ecos.runtime.mcp", "fail", f"Tool failed: {tool_name}: {e}")
            _STATS[tool_name] = _STATS.get(tool_name, 0) + 1
            _record_taskobject_envelope(tool_name, arguments, "error")
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
        return None

    else:
        return {
            "jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }

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
