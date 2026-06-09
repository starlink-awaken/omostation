"""Cockpit BOS Commands — L3 入口层 BOS URI 集成"""

import subprocess
from pathlib import Path

ECOS_TOOLS = Path(__file__).parent.parent.parent.parent / "ecos" / "src" / "ecos" / "ssot" / "tools"
MOF_WORKFLOW = str(ECOS_TOOLS / "mof-workflow.py")


def cmd_bos_status(args):
    """显示 BOS URI 系统和蜂群实时状态"""
    print("═══ BOS URI System Status ═══")
    print()

    # BOS metrics from core modules
    try:
        import sys

        sys.path.insert(0, str(Path.home() / "Workspace" / "projects" / "agora" / "src"))
        from agora.mcp.bos_metrics import bos_metrics
        from agora.mcp.bos_middleware import bos_cache

        summary = bos_metrics.summary()
        cache = bos_cache.status()

        print("🔗 BOS Metrics:")
        print(f"   Calls: {summary['total_calls']}")
        print(f"   Success rate: {summary['success_rate'] * 100:.1f}%")
        print(f"   Avg latency: {summary['avg_latency_ms']:.1f}ms")
        print(f"   Cache: {cache['active_entries']} active / {cache['total']} total")
    except Exception as e:
        print(f"   BOS Metrics unavailable: {e}")

    # Swarm status
    try:
        import sys

        sys.path.insert(0, str(Path.home() / "Workspace" / "projects" / "agora" / "src"))
        from agora.mcp.swarm import get_swarm

        swarm = get_swarm()
        status = swarm.status()

        print()
        print("🐝 Agora Swarm:")
        print(f"   Role: {status['role']}")
        print(f"   Total nodes: {status['total_nodes']}")
        print(f"   Online nodes: {status['online_nodes']}")
    except Exception:
        print()
        print("🐝 Agora Swarm: standalone mode")

    print()
    print("💡 Commands: cockpit workflow list | cockpit workflow show <name>")


def cmd_bos_workflow(args):
    """委托给 mof workflow CLI (L0 层)"""
    cmd_name = args.subcommand if hasattr(args, "subcommand") else "list"
    extra = getattr(args, "extra", [])
    result = subprocess.run(
        ["python3", MOF_WORKFLOW, cmd_name] + extra,
        capture_output=True,
        text=True,
    )
    print(result.stdout[:2000])
    if result.returncode != 0:
        print("(output truncated) — 完整输出请使用 'mof workflow ...'")
