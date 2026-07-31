#!/usr/bin/env python3
"""
eCOS v6 L3 — Runtime MCP Server 最小实现
==========================================
Phase 8.2 / DEBT-L3-001 (🔴)
通过 MCP stdio 协议暴露 7 个入口工具。

用法:
    # 直接运行 (stdio 模式，供 MCP 客户端调用)
    python3 runtime-mcp-server.py

    # 测试模式 (无 MCP 客户端时查看输出)
    python3 runtime-mcp-server.py --test health

依赖:
    - fastmcp 库 (uv add fastmcp)
"""

import json
import argparse
from datetime import datetime
from pathlib import Path


def _get_cockpit_dir() -> Path:
    """Resolve standard @驾驶舱 or 驾驶舱 folder in Documents."""
    d = Path.home() / "Documents" / "@驾驶舱"
    if d.exists():
        return d
    return Path.home() / "Documents" / "驾驶舱"


def handle_health() -> dict:
    """runtime_health: 全系统健康"""
    import subprocess

    script = _get_cockpit_dir() / "scripts" / "ecos-health-check.py"
    if not script.exists():
        return {"status": "error", "detail": "health-check 脚本不存在"}
    r = subprocess.run(
        ["python3", str(script), "--json"], capture_output=True, text=True, timeout=30, check=False)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"status": "error", "detail": r.stdout[:200]}


def handle_matrix_list() -> dict:
    """runtime_matrix_list: 服务注册表"""
    import subprocess

    reg = Path.home() / ".ecos" / "runtime" / "registry.json"
    if reg.exists():
        return json.loads(reg.read_text())
    script = Path.home() / ".ecos" / "scripts" / "ecos-register.py"
    if script.exists():
        r = subprocess.run(
            ["python3", str(script), "--status"],
            capture_output=True,
            text=True,
            timeout=10, check=False)
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:  # noqa: S110, S112
            pass  # noqa: S110, BLE001, S112  # defensive fallback
    return {"services": [], "note": "Runtime Registry 不可用"}


def handle_protocol_list() -> dict:
    """runtime_protocol_list: L0 协议注册表"""
    import yaml

    constraint_file = (
        Path.home()
        / "Documents"
        / "学习进化"
        / "2-knowledge"
        / "基建架构"
        / "L0-constraints.yaml"
    )
    if constraint_file.exists():
        data = yaml.safe_load(constraint_file.read_text())
        return {
            "protocols": data.get("protocol_registry", []),
            "last_updated": data.get("generated", ""),
        }
    return {"protocols": [], "note": "L0 constraints 文件不可读"}


def handle_protocol_get(protocol_id: str) -> dict:
    """runtime_protocol_get: 单个协议详情"""
    import yaml

    constraint_file = (
        Path.home()
        / "Documents"
        / "学习进化"
        / "2-knowledge"
        / "基建架构"
        / "L0-constraints.yaml"
    )
    if not constraint_file.exists():
        return {"error": "constraints 文件不存在"}

    data = yaml.safe_load(constraint_file.read_text())
    for p in data.get("protocol_registry", []):
        if p["id"].lower() == protocol_id.lower():
            now = datetime.now()
            intro = datetime.strptime(p["introduced"], "%Y-%m-%d")
            age_days = (now - intro).days
            decay = (
                min(1.0, age_days / p["half_life_days"])
                if p["half_life_days"] > 0
                else 1.0
            )
            return {
                "protocol": p,
                "age_days": age_days,
                "decay": round(decay, 2),
                "remaining_value": max(0, (1 - decay) * 100),
                "status": "fresh"
                if decay < 0.5
                else ("aging" if decay < 1.0 else "expired"),
            }
    return {"error": f"协议 {protocol_id} 未找到"}


def handle_ontology() -> dict:
    """runtime_ontology_get: 元模型本体"""
    meta_file = _get_cockpit_dir() / "meta-model-ecos.yaml"
    if meta_file.exists():
        import yaml

        return yaml.safe_load(meta_file.read_text())
    return {"error": "元模型文件不可用"}


def handle_brief() -> dict:
    """runtime_brief: 会话简报"""
    import subprocess

    script = _get_cockpit_dir() / "scripts" / "ecos-brief.py"
    if not script.exists():
        return {"error": "ecos-brief.py 不存在"}
    r = subprocess.run(
        ["python3", str(script), "--json"], capture_output=True, text=True, timeout=45, check=False)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"error": "brief 生成失败"}


def handle_kv_get(key: str) -> dict:
    """runtime_kv_get: daemon-state 查询"""
    import sqlite3

    state_db = Path.home() / ".ecos" / "daemon-state.db"
    if not state_db.exists():
        return {"key": key, "value": None, "note": "daemon-state 不存在"}

    conn = sqlite3.connect(str(state_db))
    conn.row_factory = sqlite3.Row

    if key == "daemon":
        cursor = conn.execute(
            "SELECT COUNT(*) as total, COALESCE(SUM(CASE WHEN exit_code=0 THEN 1 ELSE 0 END),0) as passed, MAX(started_at) as last FROM cycles"
        )
        row = cursor.fetchone()
        result = dict(row) if row else {}
    elif key == "sla":
        cursor = conn.execute(
            "SELECT COUNT(*) as total, COALESCE(SUM(CASE WHEN exit_code=0 THEN 1 ELSE 0 END),0) as passes FROM cycles"
        )
        row = cursor.fetchone()
        result = dict(row) if row else {}
        if result.get("total", 0) > 0:
            result["uptime"] = round(result["passes"] / result["total"] * 100, 1)
    elif key == "health":
        cursor = conn.execute(
            "SELECT alert_type, message, created_at FROM alerts ORDER BY created_at DESC LIMIT 10"
        )
        result = {"alerts": [dict(r) for r in cursor.fetchall()]}
    elif key == "protocols":
        result = handle_protocol_list()
    else:
        result = {"key": key, "note": f"未知键: {key}"}

    conn.close()
    result["_key"] = key
    return result


# ── Agent handlers (整合 agent-runtime 7 action, 调 executor 核心) ──────────
# agent-runtime BOS 声明统一指向 runtime.mcp_server, 消除 cockpit 壳层间接.
# 核心 API 已存在 (AgentRuntime/Tools/TaskScheduler/AgentHub), 这里只做 MCP 暴露.


def handle_agent_list_tools() -> dict:
    """列出 AgentRuntime 可用工具 (Tools.build_tool_registry)."""
    from runtime.executor.tools import Tools

    try:
        registry = Tools().build_tool_registry()
        return {"tools": list(registry.keys()), "count": len(registry)}
    except Exception as e:  # noqa: BLE001  # defensive fallback
        return {"error": f"{type(e).__name__}: {e}"}


def handle_agent_list() -> dict:
    """列出已注册 agent (AgentHub.list_all)."""
    from runtime.executor.agent_hub import AgentHub

    try:
        agents = AgentHub().list_all()
        return {
            "agents": [
                {"id": a.id, "name": a.name, "endpoint": a.endpoint, "status": a.status}
                for a in agents
            ],
            "count": len(agents),
        }
    except Exception as e:  # noqa: BLE001  # defensive fallback
        return {"error": f"{type(e).__name__}: {e}"}


def handle_agent_status() -> dict:
    """AgentRuntime 状态 (model + 工具数)."""
    from runtime.executor.engine import AgentRuntime

    try:
        rt = AgentRuntime()
        return {
            "model": rt.model,
            "tool_count": len(rt._tool_registry),
            "status": "ready",
        }
    except Exception as e:  # noqa: BLE001  # defensive fallback
        return {"error": f"{type(e).__name__}: {e}"}


def handle_agent_task_status(task_id: str) -> dict:
    """查询任务状态 (TaskScheduler.get_status)."""
    from runtime.executor.task_scheduler import TaskScheduler

    try:
        sched = TaskScheduler()
        status = sched.get_status(task_id)
        return {"task_id": task_id, "status": str(status)}
    except KeyError:
        return {"error": f"Task not found: {task_id}"}
    except Exception as e:  # noqa: BLE001  # defensive fallback
        return {"error": f"{type(e).__name__}: {e}"}


def handle_agent_run_task(prompt: str, tools: str = "") -> dict:
    """执行任务 (AgentRuntime.run_task). 注意: 需要 LLM provider 才能真跑."""
    from runtime.executor.engine import AgentRuntime

    try:
        rt = AgentRuntime()
        tools_enabled = [t.strip() for t in tools.split(",") if t.strip()] or None
        return rt.run_task(prompt, tools_enabled=tools_enabled)
    except Exception as e:  # noqa: BLE001  # defensive fallback
        return {"error": f"{type(e).__name__}: {e}"}


def handle_agent_chat(message: str, history: str = "[]") -> dict:
    """对话交互 (AgentRuntime chat). 需要 LLM provider."""
    import json as _json

    from runtime.executor.engine import AgentRuntime

    try:
        rt = AgentRuntime()
        messages = [{"role": "system", "content": "You are a helpful assistant."}]
        messages.extend(_json.loads(history) if history and history != "[]" else [])
        messages.append({"role": "user", "content": message})
        result = rt._call_llm(messages)
        return {"response": result.get("content", ""), "model": rt.model}
    except Exception as e:  # noqa: BLE001  # defensive fallback
        return {"error": f"{type(e).__name__}: {e}"}


def handle_agent_execute(prompt: str) -> dict:
    """执行任务 (execute = run_task 语义, 别名)."""
    return handle_agent_run_task(prompt)


# ── FastMCP server ──────────────────────────────────────────────────────────

try:
    from fastmcp import FastMCP

    mcp = FastMCP("ecos-runtime")

    @mcp.tool()
    def runtime_health() -> dict:
        return handle_health()

    @mcp.tool()
    def runtime_matrix_list() -> dict:
        return handle_matrix_list()

    @mcp.tool()
    def runtime_protocol_list() -> dict:
        return handle_protocol_list()

    @mcp.tool()
    def runtime_protocol_get(protocol_id: str) -> dict:
        return handle_protocol_get(protocol_id)

    @mcp.tool()
    def runtime_ontology_get() -> dict:
        return handle_ontology()

    @mcp.tool()
    def runtime_brief() -> dict:
        return handle_brief()

    @mcp.tool()
    def runtime_kv_get(key: str) -> dict:
        return handle_kv_get(key)

    # agent-runtime 整合工具 (调 executor 核心 API, 消除 cockpit 壳层)
    @mcp.tool()
    def runtime_agent_list_tools() -> dict:
        return handle_agent_list_tools()

    @mcp.tool()
    def runtime_agent_list() -> dict:
        return handle_agent_list()

    @mcp.tool()
    def runtime_agent_status() -> dict:
        return handle_agent_status()

    @mcp.tool()
    def runtime_agent_task_status(task_id: str) -> dict:
        return handle_agent_task_status(task_id)

    @mcp.tool()
    def runtime_agent_run_task(prompt: str, tools: str = "") -> dict:
        return handle_agent_run_task(prompt, tools)

    @mcp.tool()
    def runtime_agent_chat(message: str, history: str = "[]") -> dict:
        return handle_agent_chat(message, history)

    @mcp.tool()
    def runtime_agent_execute(prompt: str) -> dict:
        return handle_agent_execute(prompt)

except ImportError as _e:
    mcp = None
    _import_error = _e


def main():
    parser = argparse.ArgumentParser(description="eCOS v6 Runtime MCP Server")
    parser.add_argument("--test", type=str, help="测试模式: 工具名")
    parser.add_argument("--list", action="store_true", help="列出所有工具")
    args = parser.parse_args()

    # Enable KEI Sandbox
    try:
        from runtime.kei_sandbox import enable_sandbox

        kei_config = str(Path(__file__).resolve().parent.parent.parent / "kei.yaml")
        enable_sandbox(config_path=kei_config)
    except ImportError:  # noqa: S110, S112
        pass  # noqa: S110, BLE001, S112  # defensive fallback

    # 测试模式: 直接调用并打印
    if args.test:
        handlers = {
            "health": handle_health,
            "matrix": handle_matrix_list,
            "protocols": handle_protocol_list,
            "ontology": handle_ontology,
            "brief": handle_brief,
        }
        handler = handlers.get(args.test)
        if handler:
            print(json.dumps(handler(), ensure_ascii=False, indent=2))
        else:
            print(f"未知测试: {args.test}")
        return

    if args.list:
        tools = [
            "runtime_health",
            "runtime_matrix_list",
            "runtime_protocol_list",
            "runtime_protocol_get",
            "runtime_ontology_get",
            "runtime_brief",
            "runtime_kv_get",
            "runtime_agent_list_tools",
            "runtime_agent_list",
            "runtime_agent_status",
            "runtime_agent_task_status",
            "runtime_agent_run_task",
            "runtime_agent_chat",
            "runtime_agent_execute",
        ]
        for t in tools:
            print(f"  {t}")
        return

    # MCP stdio 模式
    if mcp is None:
        print(f"⚠️  fastmcp 库未安装: {_import_error}")
        print("   测试模式可用: --test health|matrix|protocols|ontology|brief")
        print("   列出工具: --list")
        return

    mcp.run()


if __name__ == "__main__":
    main()
