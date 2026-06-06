"""OMO Plane MCP Server — expose governance capabilities as MCP tools.

No external dependencies (no FastMCP, no pydantic).
Raw JSON-RPC over stdio, same pattern as Runtime MCP Server.
Launch via: python3 omo_mcp_server.py
"""
import json
import subprocess
import sys
from pathlib import Path

OMO_HOME = Path(__file__).parent.parent
CLI_CMD = ["uv", "run", "python3", "-m", "omo.cli"]


def _run_omo(subcommand: list[str], timeout: int = 30) -> str:
    """Run omo cli subcommand and return output."""
    try:
        r = subprocess.run(
            [*CLI_CMD, *subcommand],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(OMO_HOME),
        )
        if r.returncode == 0:
            return r.stdout.strip()
        return f"❌ Error (exit={r.returncode}): {r.stderr.strip() or r.stdout.strip()[:500]}"
    except subprocess.TimeoutExpired:
        return "❌ Timeout (30s)"
    except FileNotFoundError:
        return "❌ Command not found: uv — is it installed?"
    except Exception as e:
        return f"❌ Exception: {e}"


# ── Tool Definitions ────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "omo_phase_list",
        "description": "List all OMO phases and their current status.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: _run_omo(["phase14", "triage"]),
    },
    {
        "name": "omo_debt_registry",
        "description": "Query the OMO debt registry by keyword.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Search keyword for debt items"}
            },
            "required": ["keyword"],
        },
        "handler": lambda args: _run_omo(["capability", "registry", "debt", args.get("keyword", "")]),
    },
    {
        "name": "omo_worker_status",
        "description": "Check OMO worker dispatch status.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: _run_omo(["worker", "gc"]),
    },
    {
        "name": "omo_metacognition",
        "description": "Run OMO metacognition audit — system health check.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Metacognition command: baseline, proposals, collaboration, or rehearse",
                    "enum": ["baseline", "proposals", "collaboration", "rehearse"],
                }
            },
            "required": ["command"],
        },
        "handler": lambda args: _run_omo(["metacognition", args.get("command", "baseline")]),
    },
    {
        "name": "omo_garbage_collect",
        "description": "Run OMO garbage collection on stale drafts.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: _run_omo(["worker", "gc"]),
    },
    {
        "name": "omo_ledger",
        "description": "Query OMO ledger entries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "subcommand": {
                    "type": "string",
                    "description": "Ledger subcommand: list or show",
                }
            },
            "required": ["subcommand"],
        },
        "handler": lambda args: _run_omo(["ledger", "--message", f"ledger-{args.get('subcommand', 'list')}"]),
    },
]

TOOL_MAP = {t["name"]: t for t in TOOLS}


# ── JSON-RPC Handler ─────────────────────────────────────────────────────

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
                     "inputSchema": t["inputSchema"]}
                    for t in TOOLS
                ]
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})

        tool = TOOL_MAP.get(tool_name)
        if not tool:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}
            }

        result = tool["handler"](args)
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {"content": [{"type": "text", "text": str(result)}]}
        }

    elif method == "resources/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": []}}

    return None


# ── Main Loop ────────────────────────────────────────────────────────────

def main() -> None:
    """JSON-RPC stdio server loop."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
            if resp:
                send_response(resp)
        except json.JSONDecodeError:
            send_response({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            })
        except Exception as e:
            req_id = req.get("id") if 'req' in dir() else None  # noqa: SIM118
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": f"Internal error: {e}"},
            })


if __name__ == "__main__":
    main()
