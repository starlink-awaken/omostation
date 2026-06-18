import os
import re
from pathlib import Path

source_file = Path("projects/agora/src/agora/mcp_tools.py")
tools_dir = Path("projects/agora/src/agora/tools")
tools_dir.mkdir(exist_ok=True)

content = source_file.read_text()

# Extract lines
lines = content.splitlines()

# We'll put lines 1 to 223 into base.py
base_lines = lines[:223]

# Categories:
categories = {
    "core": ["tool_ping", "tool_post_result", "tool_get_task_info", "tool_broadcast_event"],
    "monitoring": ["tool_get_swarm_health", "tool_get_system_resources", "tool_get_metrics_snapshot"],
    "synapse": ["tool_synapse_hello", "tool_synapse_ping"],
    "domain": ["tool_memory_query", "tool_execution_submit_task", "tool_governance_submit_request", "tool_evolution_status", "tool_swarm_dispatch"],
    "voice": ["tool_voice_speak", "tool_voice_session_info", "tool_voice_intent_digest"],
    "dt": ["tool_mail_handler", "tool_tasks_list"],
    "registry": ["build_default_registry"]
}

func_to_cat = {}
for cat, funcs in categories.items():
    for f in funcs:
        func_to_cat[f] = cat

func_bodies = {}
current_func = None
current_body = []

for line in lines[223:]:
    m = re.match(r"^def (tool_[a-zA-Z0-9_]+|build_default_registry)\b", line)
    if m:
        if current_func:
            func_bodies[current_func] = current_body
        current_func = m.group(1)
        current_body = [line]
    else:
        if current_func:
            current_body.append(line)

if current_func:
    func_bodies[current_func] = current_body

with open(tools_dir / "base.py", "w") as f:
    f.write("\n".join(base_lines) + "\n")

imports_for_others = """from __future__ import annotations
import json
import logging
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
from typing import Any
from pathlib import Path
from agora.tools.base import (
    ToolContext, JSONDict, _require, _read_json_object, _json_object,
    _HAS_RESULT_BUS, _TaskResult, _ResultBus, _get_synapse_link,
    _synapse_hello_handler, _synapse_ping_handler, _mcp_surface_contract,
    SurfaceIngressKind, SurfaceContractError, _surface_payload,
    _HAS_PSUTIL, _psutil, MCPToolRegistry, ToolEntry, ToolHandler
)

_log = logging.getLogger(__name__)

"""

# Write category files
for cat in categories:
    with open(tools_dir / f"{cat}.py", "w") as f:
        f.write(imports_for_others)
        if cat == "registry":
            for c in categories:
                if c != "registry":
                    funcs = [func for func in categories[c] if func in func_bodies]
                    if funcs:
                        f.write(f"from agora.tools.{c} import " + ", ".join(funcs) + "\n")
            f.write("\n")
        
        for func in categories[cat]:
            if func in func_bodies:
                f.write("\n".join(func_bodies[func]) + "\n\n")

# Write __init__.py
with open(tools_dir / "__init__.py", "w") as f:
    f.write("from agora.tools.base import *\n")
    for cat in categories:
        f.write(f"from agora.tools.{cat} import *\n")

# Write new mcp_tools.py
new_mcp_tools = """from __future__ import annotations
from agora.tools import *
"""
source_file.write_text(new_mcp_tools)
print("Done splitting!")
