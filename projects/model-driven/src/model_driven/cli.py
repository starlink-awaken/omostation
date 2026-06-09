"""
model_driven.cli — CLI 入口

提供 model-driven 的命令行接口：
- model-driven lifecycle <command>
- model-driven spec <command>
- model-driven adr <command>
- model-driven okr <command>
- model-driven tool <command>
- model-driven mcp
"""

from __future__ import annotations

import sys
from pathlib import Path


def cmd_lifecycle(args: list[str]) -> None:
    """生命周期管理命令"""
    from model_driven.lifecycle.tracking import LifecycleManager
    from model_driven.lifecycle.transitions import TransitionEngine
    from model_driven.mof.m3_extended import LifecycleStage

    manager = LifecycleManager()
    engine = TransitionEngine()

    if not args:
        print("用法: model-driven lifecycle <create|advance|status|dashboard|blockers>")
        return

    subcmd = args[0]

    if subcmd == "create":
        entity_id = args[1] if len(args) > 1 else "default"
        entity_type = args[2] if len(args) > 2 else ""
        manager.create_tracker(entity_id, entity_type)
        print(f"✅ 已创建生命周期追踪器: {entity_id}")

    elif subcmd == "advance":
        if len(args) < 3:
            print("用法: model-driven lifecycle advance <entity_id> <stage>")
            return
        entity_id = args[1]
        stage_str = args[2]
        tracker = manager.get_tracker(entity_id)
        if not tracker:
            print(f"❌ 实体不存在: {entity_id}")
            return
        try:
            target = LifecycleStage.from_str(stage_str)
        except ValueError:
            print(f"❌ 无效阶段: {stage_str}")
            return
        success, msg, _ = engine.try_transition(tracker, target)
        print(f"{'✅' if success else '❌'} {msg}")

    elif subcmd == "status":
        entity_id = args[1] if len(args) > 1 else None
        if entity_id:
            summary = manager.get_stage_summary(entity_id)
            if summary:
                print(f"实体: {summary['entity_id']}")
                print(f"当前阶段: {summary['current_stage']}")
                print(f"进度: {summary['progress_pct']}%")
        else:
            dashboard = manager.generate_dashboard()
            print(f"实体总数: {dashboard.total_entities}")
            print(f"平均进度: {dashboard.avg_progress}%")
            for stage, count in dashboard.entities_by_stage.items():
                if count > 0:
                    print(f"  {stage}: {count}")

    elif subcmd == "dashboard":
        dashboard = manager.generate_dashboard()
        print("=== 全生命周期仪表板 ===")
        print(f"实体总数: {dashboard.total_entities}")
        print(f"平均进度: {dashboard.avg_progress}%")
        print(f"阻塞项: {len(dashboard.blockers)}")
        for blocker in dashboard.blockers:
            print(f"  - [{blocker['entity_id']}] {blocker['stage']}: {blocker['issue']}")

    elif subcmd == "blockers":
        blockers = manager.get_all_blockers()
        if blockers:
            print(f"阻塞项: {len(blockers)}")
            for b in blockers:
                print(f"  - [{b['entity_id']}] {b['stage']}: {b['issue']}")
        else:
            print("✅ 无阻塞项")


def cmd_spec(args: list[str]) -> None:
    """Spec 管理命令"""
    from model_driven.management.spec import SpecManager

    manager = SpecManager()
    if not args:
        print("用法: model-driven spec <create|list>")
        return

    subcmd = args[0]
    if subcmd == "create":
        spec_id = args[1] if len(args) > 1 else f"SPEC-{len(manager.list_all()) + 1}"
        title = args[2] if len(args) > 2 else "未命名"
        spec = manager.create(spec_id, title)
        print(f"✅ 已创建 Spec: {spec.id} - {spec.title}")

    elif subcmd == "list":
        specs = manager.list_all()
        if specs:
            for s in specs:
                print(f"  [{s.status.value}] {s.id}: {s.title}")
        else:
            print("无 Spec")


def cmd_adr(args: list[str]) -> None:
    """ADR 管理命令"""
    from model_driven.management.adr import ADRManager

    manager = ADRManager()
    if not args:
        print("用法: model-driven adr <create|list>")
        return

    subcmd = args[0]
    if subcmd == "create":
        adr_id = args[1] if len(args) > 1 else f"ADR-{len(manager.list_all()) + 1}"
        title = args[2] if len(args) > 2 else "未命名"
        adr = manager.create(adr_id, title)
        print(f"✅ 已创建 ADR: {adr.id} - {adr.title}")

    elif subcmd == "list":
        adrs = manager.list_all()
        if adrs:
            for a in adrs:
                print(f"  [{a.status.value}] {a.id}: {a.title}")
        else:
            print("无 ADR")


def cmd_okr(args: list[str]) -> None:
    """OKR 管理命令"""
    from model_driven.management.okr import OKRManager

    manager = OKRManager()
    if not args:
        print("用法: model-driven okr <create|list|progress>")
        return

    subcmd = args[0]
    if subcmd == "create":
        okr_id = args[1] if len(args) > 1 else f"OKR-{len(manager.list_all()) + 1}"
        objective = args[2] if len(args) > 2 else "未定义目标"
        okr = manager.create(okr_id, objective)
        print(f"✅ 已创建 OKR: {okr.id} - {okr.objective}")

    elif subcmd == "list":
        okrs = manager.list_all()
        if okrs:
            for o in okrs:
                print(f"  [{o.status.value}] {o.id}: {o.objective} (进度: {o.progress:.0%})")
        else:
            print("无 OKR")

    elif subcmd == "progress":
        stats = manager.get_stats()
        print(f"OKR 总数: {stats['total']}")
        print(f"平均进度: {stats['avg_progress']}%")


def cmd_tool(args: list[str]) -> None:
    """工具链命令"""
    from model_driven.toolchain import create_default_bus

    bus = create_default_bus()
    if not args:
        print("用法: model-driven tool <list|execute>")
        return

    subcmd = args[0]
    if subcmd == "list":
        for tool_def in bus.list_tools():
            print(f"  [{tool_def.category}] {tool_def.name}: {tool_def.description}")

    elif subcmd == "execute":
        if len(args) < 2:
            print("用法: model-driven tool execute <tool_name>")
            return
        tool_name = args[1]
        result = bus.execute(tool_name)
        print(f"{'✅' if result.success else '❌'} {result.message}")


def cmd_mcp(args: list[str]) -> None:
    """MCP Server 命令"""
    from model_driven.mcp_server import MCPServer

    server = MCPServer()
    if not args:
        print("用法: model-driven mcp <list|execute>")
        return

    subcmd = args[0]
    if subcmd == "list":
        for tool in server.list_tools():
            print(f"  [{tool['category']}] {tool['name']}: {tool['description']}")

    elif subcmd == "execute":
        if len(args) < 2:
            print("用法: model-driven mcp execute <tool_name>")
            return
        tool_name = args[1]
        result = server.execute(tool_name)
        print(f"{'✅' if result.get('success') else '❌'} {result.get('message', '')}")


def main():
    """主入口"""
    args = sys.argv[1:]

    if not args:
        print("model-driven — 全生命周期模型驱动平台")
        print()
        print("用法: model-driven <command> [args]")
        print()
        print("命令:")
        print("  lifecycle   生命周期管理")
        print("  spec        Spec 管理")
        print("  adr         ADR 管理")
        print("  okr         OKR 管理")
        print("  tool        工具链")
        print("  mcp         MCP Server")
        return

    cmd = args[0]
    rest = args[1:]

    commands = {
        "lifecycle": cmd_lifecycle,
        "spec": cmd_spec,
        "adr": cmd_adr,
        "okr": cmd_okr,
        "tool": cmd_tool,
        "mcp": cmd_mcp,
    }

    if cmd in commands:
        commands[cmd](rest)
    else:
        print(f"未知命令: {cmd}")
        print(f"可用命令: {', '.join(commands.keys())}")


if __name__ == "__main__":
    main()
