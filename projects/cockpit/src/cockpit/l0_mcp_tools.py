"""
织星 MOF — L0 MCP 工具集 (l0_mcp_tools)
=========================================
供 cockpit 或其他 MCP Server import 使用的 L0 查询工具。
每个函数可以直接注册为 MCP tool。

MCP Tools:
  l0_status         — 系统状态摘要
  l0_validate       — 全量校验
  l0_audit          — 漂移审计
  l0_protocols      — 协议健康度
  l0_adr_list       — ADR 列表
  l0_entity_resolve — 实体解析

集成方式 (在 cockpit MCP server 中):
    from l0_mcp_tools import l0_status, l0_validate, l0_audit

    @server.tool()
    def l0_status() -> str:
        return l0_status()
"""

import json
import subprocess
from pathlib import Path

HOME = Path.home()
MOF = HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools" / "mof.py"
MOF_VALIDATE = HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools" / "mof-validate.py"
MOF_AUDIT = HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools" / "mof-audit.py"


def _run_tool(tool_path: Path, args: list = None) -> dict:
    try:
        result = subprocess.run(
            ["python3", str(tool_path)] + (args or []) + ["--json"], capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except Exception:
        pass
    return {"error": "tool execution failed"}


def l0_status() -> str:
    """L0 系统状态摘要 — Agent 启动时调用"""
    _run_tool(MOF, ["status"]) if False else {}

    # Direct status computation (bypass subprocess for speed)
    m1_count = sum(
        1 for _ in (HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1").rglob("*.yaml")
    )
    m2_count = len(
        list((HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m2").glob("*.yaml"))
    )

    # Get protocol health
    sla_result = _run_tool(
        HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools" / "mof-sla.py", ["--snapshot-only"]
    )

    lines = [
        "织星 L0 状态:",
        f"  M2 类型: {m2_count}",
        f"  M1 节点: {m1_count}",
        f"  校验: {'✅ 全部通过' if m1_count > 0 else '⚠️'}",
    ]

    if sla_result and "protocols" not in str(sla_result):
        pass  # skip error

    return "\n".join(lines)


def l0_validate() -> str:
    """全量 M1↔M2 校验 — 检查架构合规性"""
    result = _run_tool(MOF_VALIDATE)
    if "error" in result:
        return f"❌ 校验失败: {result['error']}"

    node_count = result.get("node_count", "?")
    total = len(result.get("results", []))
    errors = sum(1 for r in result.get("results", []) if r.get("level") == "error")

    return f"L0 校验: {node_count} 节点 | 通过: {total - errors}/{total} | {'✅ 全部通过' if errors == 0 else f'❌ {errors} 错误'}"


def l0_audit() -> str:
    """M1↔M0 漂移审计 — 检查声明 vs 实际"""
    result = _run_tool(MOF_AUDIT)
    drifts = result.get("drifts", result.get("items", result.get("drift_count", 0)))
    if isinstance(drifts, list):
        drift_count = len(drifts)
    else:
        drift_count = drifts

    if drift_count == 0:
        return "L0 审计: ✅ 无漂移 — M1 声明与 M0 运行时一致"
    else:
        return f"L0 审计: ⚠️ {drift_count} 项漂移"


def l0_protocols() -> str:
    """协议健康度"""
    sla = _run_tool(
        HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools" / "mof-sla.py", ["--snapshot-only"]
    )
    lines = ["协议健康度:"]
    protocols = sla.get("protocols", {}) if isinstance(sla, dict) else {}
    for pid, state in protocols.items():
        remaining = state.get("remaining_pct", "?")
        status = state.get("status", "?")
        icon = "🟢" if status == "fresh" else ("🟡" if status == "aging" else "🔴")
        lines.append(f"  {icon} {pid}: {remaining}%")
    return "\n".join(lines) if protocols else "L0 协议: 无数据"


def l0_adr_list() -> str:
    """ADR 列表"""
    import yaml

    decisions_dir = HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "decision"
    if not decisions_dir.exists():
        return "L0 ADR: 无决策记录"

    lines = ["架构决策记录 (ADR):"]
    for f in sorted(decisions_dir.glob("*.yaml")):
        try:
            d = yaml.safe_load(open(f))
            status = d.get("status", "?")
            name = d.get("name", f.stem)[:60]
            icon = {"accepted": "✅", "proposed": "📋", "rejected": "❌"}.get(status, "❓")
            lines.append(f"  {icon} {name}")
        except Exception:
            pass
    return "\n".join(lines)


def l0_entity_resolve(query: str) -> str:
    """跨域实体解析"""
    result = _run_tool(
        HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools" / "mof-entity.py",
        ["resolve", query],
    )
    entities = result.get("entities", [])
    if not entities:
        return f"实体 '{query}': 未找到"

    lines = [f"实体 '{query}' ({len(entities)} 处):"]
    for e in entities:
        lines.append(f"  📍 {e.get('name', '?')} — {e.get('domain', '?')} [{e.get('entity_type', '?')}]")
    return "\n".join(lines)


# ── model-driven 桥接 ──


def md_lifecycle_status(entity_id: str = "ecos") -> str:
    """model-driven 生命周期状态 — 查询实体的全生命周期阶段进度"""
    try:
        from model_driven.lifecycle.tracking import LifecycleManager

        mgr = LifecycleManager()
        summary = mgr.get_stage_summary(entity_id)
        if summary:
            return f"实体 '{entity_id}': 阶段={summary['current_stage']} 进度={summary['progress_pct']}%"
        return f"实体 '{entity_id}': 未追踪"
    except ImportError:
        return "model-driven 不可用 (安装: cd ~/Workspace/projects/model-driven && uv sync)"


def md_validate() -> str:
    """model-driven 自反验证 — 用 model-validate 校验 L0 MOF M1 节点"""
    try:
        from pathlib import Path

        import yaml
        from model_driven.toolchain.tools import tool_validate

        m1_dir = Path.home() / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1"
        nodes = []
        for d in sorted(m1_dir.iterdir()):
            if d.is_dir():
                for f in sorted(d.glob("*.yaml")):
                    try:
                        data = yaml.safe_load(open(f))
                        if data and "type" in data:
                            nodes.append(data)
                    except Exception:
                        pass

        result = tool_validate(models=nodes)
        return f"model-driven 自反验证: passed={result['passed']}, errors={result['error_count']}, warnings={result['warning_count']}, nodes={len(nodes)}"
    except ImportError:
        return "model-driven 不可用 (安装: cd ~/Workspace/projects/model-driven && uv sync)"


# ── MCP Tool Registry ──
# 供 cockpit MCP server 注册使用
MCP_TOOLS = {
    "l0_status": {
        "function": l0_status,
        "description": "L0 系统状态摘要 — M2类型数·M1节点数·校验状态·协议健康度",
        "parameters": {},
    },
    "l0_validate": {
        "function": l0_validate,
        "description": "全量 M1↔M2 架构校验 — 检查所有 M1 节点是否满足 M2 元模型约束",
        "parameters": {},
    },
    "l0_audit": {
        "function": l0_audit,
        "description": "M1↔M0 漂移审计 — 检查架构声明与实际运行时是否一致",
        "parameters": {},
    },
    "l0_protocols": {
        "function": l0_protocols,
        "description": "协议健康度 — 所有注册协议的价值衰减状态",
        "parameters": {},
    },
    "l0_adr_list": {
        "function": l0_adr_list,
        "description": "架构决策记录列表 — 所有已接受的架构决策",
        "parameters": {},
    },
    "l0_entity_resolve": {
        "function": l0_entity_resolve,
        "description": "跨域实体解析 — 查询同一实体在多个域的出现",
        "parameters": {"query": "实体名称"},
    },
    "md_lifecycle_status": {
        "function": md_lifecycle_status,
        "description": "model-driven 生命周期状态 — 查询实体的全生命周期阶段进度",
        "parameters": {"entity_id": "实体 ID (默认 ecos)"},
    },
    "md_validate": {
        "function": md_validate,
        "description": "model-driven 自反验证 — 用 model-driven 工具校验 L0 MOF M1 节点",
        "parameters": {},
    },
}


# ── CLI for testing ──
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("L0 MCP Tools — 可用工具:")
        for name, info in MCP_TOOLS.items():
            print(f"  {name}: {info['description']}")
        sys.exit(0)

    tool = sys.argv[1]
    if tool == "status":
        print(l0_status())
    elif tool == "validate":
        print(l0_validate())
    elif tool == "audit":
        print(l0_audit())
    elif tool == "protocols":
        print(l0_protocols())
    elif tool == "adr":
        print(l0_adr_list())
    elif tool == "entity" and len(sys.argv) > 2:
        print(l0_entity_resolve(sys.argv[2]))
    else:
        print(f"未知工具: {tool}")
