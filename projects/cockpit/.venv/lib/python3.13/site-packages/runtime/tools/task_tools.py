from .shared import PROJECT_HOME, _STATS
import json

def _runtime_stats() -> str:
    import yaml
    reg_file = PROJECT_HOME / "protocols" / "kei-extensions.yaml"
    ext_count = len(yaml.safe_load(reg_file.read_text()).get("extensions", [])) if reg_file.exists() else 0
    plane_file = PROJECT_HOME / "protocols" / "tri-plane-registry.yaml"
    plane_count = len(yaml.safe_load(plane_file.read_text()).get("planes", [])) if plane_file.exists() else 0
    proto_file = PROJECT_HOME / "protocols" / "L0-registry.yaml"
    proto_count = len(yaml.safe_load(proto_file.read_text()).get("protocols", [])) if proto_file.exists() else 0
    
    from runtime.tools import TOOLS
    tool_count = len(TOOLS)
    lines = [
        "╔════════════════════════════════════════╗",
        "║     eCOS Runtime Usage Statistics      ║",
        "╠════════════════════════════════════════╣",
        f"║  MCP Tools:              {tool_count:3d}           ║",
        f"║  Registered Extensions:  {ext_count:3d}           ║",
        f"║  Kernel Planes:          {plane_count:3d}           ║",
        f"║  L0 Protocols:           {proto_count:3d}           ║",
        "╠════════════════════════════════════════╣",
        "║          Tool Call Costing             ║",
        "╠════════════════════════════════════════╣",
    ]
    if not _STATS:
        lines.append("║  (no tool calls yet)                   ║")
    else:
        for tname, cnt in _STATS.items():
            lines.append(f"║  {tname:24s} {cnt:4d}         ║")
    lines.append("╚════════════════════════════════════════╝")
    return "\n".join(lines)

def _taskobject_submit(payload: dict) -> str:
    from runtime.taskobject_adapter import _validate_taskobject, _utc_now
    from runtime.tools import TOOL_MAP
    
    error = _validate_taskobject(payload)
    if error:
        return json.dumps({"status": "error", "error": error, "task_id": payload.get("id", "")})
    
    tool_name = payload["target"]["tool"]
    params = payload["target"].get("params", {})
    
    tool = TOOL_MAP.get(tool_name)
    if not tool:
        return json.dumps({"status": "error", "error": f"Tool not found: {tool_name}", "task_id": payload.get("id", "")})
        
    try:
        _STATS[tool_name] = _STATS.get(tool_name, 0) + 1
        result = tool["handler"](params)
        out = {
            "status": "ok",
            "result": result,
            "task_id": payload.get("id", ""),
            "dispatched_at": _utc_now(),
            "source": payload.get("context", {}).get("source", "unknown")
        }
        return json.dumps(out)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e), "task_id": payload.get("id", "")})

TOOLS = [
    {
        "name": "runtime_stats",
        "description": "Show runtime usage statistics.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: _runtime_stats(),
    },
    {
        "name": "taskobject_submit",
        "description": "Submit a TaskObject v1 envelope for execution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "payload": {"type": "object", "description": "The TaskObject payload"}
            },
            "required": ["payload"],
        },
        "handler": lambda args: _taskobject_submit(args["payload"]),
    }
]
