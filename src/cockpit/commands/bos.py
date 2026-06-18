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
        print("(output truncated) — 完整输出请使用 'mof workflow' ...'")


def cmd_bos_list(args):
    """列出所有 BOS URI 路由。"""
    try:
        import sys

        sys.path.insert(0, str(Path.home() / "Workspace" / "projects" / "agora" / "src"))
        from agora.mcp.resolver.services import POC_SERVICES

        by_domain: dict[str, list[str]] = {}
        for s in POC_SERVICES:
            by_domain.setdefault(s.domain, []).append(s.uri)

        print(f"\n  BOS URI 路由表 ({len(POC_SERVICES)} 条)")
        print(f"  {'=' * 40}")
        for domain in sorted(by_domain):
            services = by_domain[domain]
            print(f"\n  {domain} ({len(services)}):")
            for uri in sorted(services):
                print(f"    {uri}")
    except Exception as e:
        print(f"  BOS 服务不可用: {e}")


def cmd_bos_discover(args):
    """扫描 workspace 项目，发现可注册的 MCP 服务。"""
    workspace = Path.home() / "Workspace" / "projects"
    discovered = []
    for proj_dir in sorted(workspace.iterdir()):
        pyproject = proj_dir / "pyproject.toml"
        if not pyproject.exists():
            continue
        try:
            import tomllib

            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
        except Exception:  # noqa: S112
            continue

        scripts = data.get("project", {}).get("scripts", {})
        for name, entry in scripts.items():
            if "mcp" in name.lower() or entry.startswith(name.split("-")[0]):
                discovered.append({
                    "project": proj_dir.name,
                    "script": name,
                    "entry": entry,
                })

    print(f"\n  🔍 自动发现: {len(discovered)} 个 MCP 入口")
    for d in discovered:
        print(f"    {d['project']:20s} → {d['script']:25s} ({d['entry']})")

    print()
    print("  💡 将发现的服务注册到: projects/agora/etc/bos-services.yaml")
