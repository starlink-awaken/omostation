#!/usr/bin/env python3
"""
eCOS v5 L3 — Runtime MCP Server 最小实现
==========================================
Phase 8.2 / DEBT-L3-001 (🔴)
通过 MCP stdio 协议暴露 7 个入口工具。

用法:
    # 直接运行 (stdio 模式，供 MCP 客户端调用)
    python3 runtime-mcp-server.py

    # 测试模式 (无 MCP 客户端时查看输出)
    python3 runtime-mcp-server.py --test health

依赖:
    - mcp 库 (pip install mcp)
"""

import sys
import json
import argparse
from datetime import datetime


TOOLS = [
    {
        "name": "runtime_health",
        "description": "全系统健康扫描 — 返回所有 9 项检查的通过/失败状态",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "runtime_matrix_list",
        "description": "陈列服务注册表 — 列出所有已注册的 L1 运行时服务",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "runtime_protocol_list",
        "description": "L0 协议注册表陈列 — 列出所有已注册的协议及其 half_life",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "runtime_protocol_get",
        "description": "查询单个协议详情 — 含 half_life 衰减状态",
        "inputSchema": {
            "type": "object",
            "properties": {
                "protocol_id": {"type": "string", "description": "协议 ID (MCP/ACP/A2A/BOS_URI/L0_YAML)"}
            },
            "required": ["protocol_id"],
        },
    },
    {
        "name": "runtime_ontology_get",
        "description": "查询 L0 元模型本体 — 返回 M3-M0 实体类型和关系类型",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "runtime_brief",
        "description": "获取会话简报 — 聚合健康+SLA+卡片+风险",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "runtime_kv_get",
        "description": "查询运行时键值存储 — 从 L1 daemon-state.db 读取",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "查询键 (daemon/sla/health/protocols)"}
            },
            "required": ["key"],
        },
    },
]


def handle_health() -> dict:
    """runtime_health: 全系统健康"""
    import subprocess
    script = Path.home() / "Documents" / "驾驶舱" / "scripts" / "ecos-health-check.py"
    if not script.exists():
        return {"status": "error", "detail": "health-check 脚本不存在"}
    r = subprocess.run(["python3", str(script), "--json"],
                       capture_output=True, text=True, timeout=30)
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
    # fallback: 通过 ecos-register.py 查询
    script = Path.home() / ".ecos" / "scripts" / "ecos-register.py"
    if script.exists():
        r = subprocess.run(["python3", str(script), "--status"],
                           capture_output=True, text=True, timeout=10)
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            pass
    return {"services": [], "note": "Runtime Registry 不可用"}


def handle_protocol_list() -> dict:
    """runtime_protocol_list: L0 协议注册表"""
    import yaml
    constraint_file = Path.home() / "Documents" / "学习进化" / "2-knowledge" / \
                      "基建架构" / "L0-constraints.yaml"
    if constraint_file.exists():
        data = yaml.safe_load(constraint_file.read_text())
        return {"protocols": data.get("protocol_registry", []),
                "last_updated": data.get("generated", "")}
    return {"protocols": [], "note": "L0 constraints 文件不可读"}


def handle_protocol_get(protocol_id: str) -> dict:
    """runtime_protocol_get: 单个协议详情"""
    import yaml
    from datetime import datetime
    constraint_file = Path.home() / "Documents" / "学习进化" / "2-knowledge" / \
                      "基建架构" / "L0-constraints.yaml"
    if not constraint_file.exists():
        return {"error": "constraints 文件不存在"}

    data = yaml.safe_load(constraint_file.read_text())
    for p in data.get("protocol_registry", []):
        if p["id"].lower() == protocol_id.lower():
            now = datetime.now()
            intro = datetime.strptime(p["introduced"], "%Y-%m-%d")
            age_days = (now - intro).days
            decay = min(1.0, age_days / p["half_life_days"]) if p["half_life_days"] > 0 else 1.0
            return {
                "protocol": p,
                "age_days": age_days,
                "decay": round(decay, 2),
                "remaining_value": max(0, (1 - decay) * 100),
                "status": "fresh" if decay < 0.5 else ("aging" if decay < 1.0 else "expired"),
            }
    return {"error": f"协议 {protocol_id} 未找到"}


def handle_ontology() -> dict:
    """runtime_ontology_get: 元模型本体"""
    meta_file = Path.home() / "Documents" / "驾驶舱" / "meta-model-ecos.yaml"
    if meta_file.exists():
        import yaml
        return yaml.safe_load(meta_file.read_text())
    from pathlib import Path
    return {"error": "元模型文件不可用"}


def handle_brief() -> dict:
    """runtime_brief: 会话简报"""
    import subprocess
    script = Path.home() / "Documents" / "驾驶舱" / "scripts" / "ecos-brief.py"
    if not script.exists():
        return {"error": "ecos-brief.py 不存在"}
    r = subprocess.run(["python3", str(script), "--json"],
                       capture_output=True, text=True, timeout=45)
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
        cursor = conn.execute("SELECT COUNT(*) as total, COALESCE(SUM(CASE WHEN exit_code=0 THEN 1 ELSE 0 END),0) as passed, MAX(started_at) as last FROM cycles")
        row = cursor.fetchone()
        result = dict(row) if row else {}
    elif key == "sla":
        cursor = conn.execute("SELECT COUNT(*) as total, COALESCE(SUM(CASE WHEN exit_code=0 THEN 1 ELSE 0 END),0) as passes FROM cycles")
        row = cursor.fetchone()
        result = dict(row) if row else {}
        if result.get("total", 0) > 0:
            result["uptime"] = round(result["passes"] / result["total"] * 100, 1)
    elif key == "health":
        cursor = conn.execute("SELECT alert_type, message, created_at FROM alerts ORDER BY created_at DESC LIMIT 10")
        result = {"alerts": [dict(r) for r in cursor.fetchall()]}
    elif key == "protocols":
        result = handle_protocol_list()
    else:
        result = {"key": key, "note": f"未知键: {key}"}

    conn.close()
    result["_key"] = key
    return result


from pathlib import Path  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 Runtime MCP Server")
    parser.add_argument("--test", type=str, help="测试模式: 工具名")
    parser.add_argument("--list", action="store_true", help="列出所有工具")
    args = parser.parse_args()

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
        for t in TOOLS:
            print(f"  {t['name']:30s} — {t['description'][:50]}")
        return

    # MCP stdio 模式 (供 MCP 客户端调用)
    try:
        from mcp.server import Server, stdio_server
        server = Server("ecos-runtime")

        @server.list_tools()
        async def list_tools():
            return TOOLS

        @server.call_tool()
        async def call_tool(name: str, arguments: dict):
            handlers = {
                "runtime_health": lambda: handle_health(),
                "runtime_matrix_list": lambda: handle_matrix_list(),
                "runtime_protocol_list": lambda: handle_protocol_list(),
                "runtime_protocol_get": lambda: handle_protocol_get(arguments.get("protocol_id", "")),
                "runtime_ontology_get": lambda: handle_ontology(),
                "runtime_brief": lambda: handle_brief(),
                "runtime_kv_get": lambda: handle_kv_get(arguments.get("key", "")),
            }
            handler = handlers.get(name)
            if not handler:
                raise ValueError(f"Unknown tool: {name}")
            return handler()

        import asyncio
        asyncio.run(stdio_server(server))

    except ImportError:
        print("⚠️  mcp 库未安装。运行: pip install mcp")
        print("   测试模式可用: --test health|matrix|protocols|ontology|brief")
        print("   列出工具: --list")


if __name__ == "__main__":
    main()
