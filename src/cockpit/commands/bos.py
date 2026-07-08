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
        from cockpit.adapters.agora import bos_cache, bos_metrics

        summary = bos_metrics.summary()
        cache = bos_cache.status()

        print("🔗 BOS Metrics:")
        print(f"   Calls: {summary['total_calls']}")
        print(f"   Success rate: {summary['success_rate'] * 100:.1f}%")
        print(f"   Avg latency: {summary['avg_latency_ms']:.1f}ms")
        print(f"   Cache: {cache['active_entries']} active / {cache['total']} total")
    except Exception as e:  # defensive fallback
        print(f"   BOS Metrics unavailable: {e}")

    # Swarm status
    try:
        from cockpit.adapters.agora import get_swarm

        swarm = get_swarm()
        status = swarm.status()

        print()
        print("🐝 Agora Swarm:")
        print(f"   Role: {status['role']}")
        print(f"   Total nodes: {status['total_nodes']}")
        print(f"   Online nodes: {status['online_nodes']}")
    except Exception:  # defensive fallback
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
        from cockpit.adapters.agora import POC_SERVICES

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
    except Exception as e:  # defensive fallback
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
        except Exception:  # noqa: S112  # defensive fallback
            continue

        scripts = data.get("project", {}).get("scripts", {})
        for name, entry in scripts.items():
            if "mcp" in name.lower() or entry.startswith(name.split("-")[0]):
                discovered.append(
                    {
                        "project": proj_dir.name,
                        "script": name,
                        "entry": entry,
                    }
                )

    print(f"\n  🔍 自动发现: {len(discovered)} 个 MCP 入口")
    for d in discovered:
        print(f"    {d['project']:20s} → {d['script']:25s} ({d['entry']})")

    print()
    print("  💡 将发现的服务注册到: projects/agora/etc/bos-services.yaml")


# ── BOS Backend Management ───────────────────────────────────


def _agora_workspace() -> str:
    """Return the agora project directory path for uv commands."""
    from pathlib import Path

    return str(Path(__file__).parent.parent.parent.parent.parent / "agora")


def cmd_bos_backends(args) -> int:
    """列出所有 MCP backend + 心跳健康状态。"""
    from rich import box
    from rich.console import Console
    from rich.table import Table

    console = Console()
    try:
        import subprocess

        r = subprocess.run(
            [
                "uv",
                "run",
                "--directory",
                _agora_workspace(),
                "python",
                "-c",
                """
from agora.auth.mcp_gateway import _health_checker
from agora.auth.mcp_gateway import KNOWN_BACKENDS

# Print header
print(f"total_backends: {len(KNOWN_BACKENDS)}")

# If health checker is running, show status
if _health_checker is not None:
    status = _health_checker.get_all_status()
    for name in sorted(status):
        s = status[name]
        alive = 'yes' if s['alive'] else 'no'
        fails = s['consecutive_failures']
        print(f"backend: {name}|alive={alive}|fails={fails}")
else:
    for b in KNOWN_BACKENDS:
        print(f"backend: {b['name']}|alive=unknown|fails=0")
""",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode != 0:
            console.print(f"[red]获取 backend 状态失败:[/] {r.stderr[:200]}")
            return 1

        table = Table(title="MCP Backends — 心跳健康状态", box=box.SIMPLE)
        table.add_column("Backend")
        table.add_column("状态")
        table.add_column("连续失败")
        table.add_column("最后探测")

        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("total_backends:"):
                console.print(f"\n  [bold cyan]🧩 已注册:[/] {line.split(':')[1]} backends\n")
            elif line.startswith("backend:"):
                parts = line[8:].split("|")
                name = parts[0]
                alive = "yes" in parts[1] if len(parts) > 1 else False
                fails = parts[2].split("=")[1] if len(parts) > 2 else "0"
                status_str = "[green]🟢 在线[/]" if alive else "[red]🔴 离线[/]"
                if fails and fails != "0":
                    status_str = "[yellow]🟡 不稳定[/]"
                table.add_row(name, status_str, str(fails), "—")

        console.print(table)
        return 0
    except Exception as e:  # defensive fallback
        console.print(f"[red]错误:[/] {e}")
        return 1


def cmd_bos_register(args) -> int:
    """动态注册新的 MCP backend。"""
    from rich.console import Console

    console = Console()

    svc_name = getattr(args, "name", "")
    command = getattr(args, "command", "uv")
    args_str = getattr(args, "args", "")
    endpoint = getattr(args, "endpoint", "")

    if not svc_name:
        console.print("[red]需要指定 backend name[/]")
        console.print("[dim]用法: cockpit bos register <name> [--command ...] [--args ...][/]")
        return 1

    svc_args = args_str.split() if args_str else []

    import json
    import subprocess

    py_code = f"""
import asyncio, json
from agora.server.dependencies import get_proxy_manager, set_proxy_manager
from agora.mcp_proxy.manager import ProxyManager

async def reg():
    pm = get_proxy_manager()
    if pm is None:
        pm = ProxyManager()
        set_proxy_manager(pm)
    svc = {{"name": "{svc_name}"}}
    svc_cmd = {json.dumps(command)}
    if svc_cmd:
        svc["command"] = svc_cmd
    svc_args = {json.dumps(svc_args)}
    if svc_args:
        svc["args"] = svc_args
    ep = {json.dumps(endpoint)}
    if ep:
        svc["mcp_endpoint"] = ep
        svc["command"] = ""
    result = await pm.add_service(svc)
    print(json.dumps({{"action": result, "name": "{svc_name}"}}))

asyncio.run(reg())
"""
    r = subprocess.run(
        ["uv", "run", "--directory", _agora_workspace(), "python", "-c", py_code],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if r.returncode != 0:
        console.print(f"[red]注册失败:[/] {r.stderr[:300]}")
        return 1

    try:
        data = json.loads(r.stdout)
        console.print(f"[green]✅ backend '{data['name']}' 注册成功[/]")
        console.print(f"   结果: {data['action']}")
        console.print("\n[dim]💡 通过 'cockpit bos backends' 查看状态[/]")
    except json.JSONDecodeError:
        console.print(f"[yellow]响应:[/] {r.stdout[:300]}")
    return 0


def cmd_bos_reload(args) -> int:
    """热重载 BOS 路由表。"""
    from rich.console import Console

    console = Console()

    import subprocess

    r = subprocess.run(
        [
            "uv",
            "run",
            "--directory",
            _agora_workspace(),
            "python",
            "-c",
            """
import asyncio
from agora.server.tools_proxy import register_proxy_tools
from fastmcp import FastMCP
from agora.mcp.resolver.bos_registry import load_from_yaml, DEFAULT_REGISTRY_PATH
from agora.mcp.resolver.services import POC_SERVICES
from collections import Counter

path = str(DEFAULT_REGISTRY_PATH)
new = load_from_yaml(path)
POC_SERVICES.clear()
POC_SERVICES.extend(new)
domains = Counter(s.domain for s in POC_SERVICES)
print(f"ok: {len(POC_SERVICES)} routes ({len(domains)} domains)")
for d, c in domains.most_common():
    print(f"  {d}: {c}")
""",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if r.returncode != 0:
        console.print(f"[red]重载失败:[/] {r.stderr[:300]}")
        return 1

    console.print("[green]✅ BOS 路由重载成功[/]")
    for line in r.stdout.splitlines():
        console.print(f"  {line}")
    console.print("\n[dim]💡 通过 'cockpit bos list' 查看路由表[/]")
    return 0


def cmd_bos_health(args) -> int:
    """显示心跳健康面板。"""
    from rich import box
    from rich.console import Console
    from rich.table import Table

    console = Console()
    try:
        import json
        import subprocess

        r = subprocess.run(
            [
                "uv",
                "run",
                "--directory",
                _agora_workspace(),
                "python",
                "-c",
                """
import json
from agora.auth.mcp_gateway import _health_checker, KNOWN_BACKENDS

h = _health_checker
if h is not None:
    status = h.get_all_status()
    alive = sum(1 for s in status.values() if s['alive'])
    dead = sum(1 for s in status.values() if not s['alive'])
    print(json.dumps({
        "running": True,
        "total_known": len(KNOWN_BACKENDS),
        "tracked": len(status),
        "alive": alive,
        "dead": dead,
        "interval": 30,
        "backends": {n: {
            "alive": s["alive"],
            "last_ok": s.get("last_ok"),
            "last_fail": s.get("last_fail"),
            "fails": s["consecutive_failures"],
        } for n, s in sorted(status.items())},
    }))
else:
    print(json.dumps({
        "running": False,
        "total_known": len(KNOWN_BACKENDS),
        "note": "心跳探测器未启动 (mcp_gateway 需以 server 模式运行)"
    }))
""",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if r.returncode != 0:
            console.print(f"[red]获取失败:[/] {r.stderr[:200]}")
            return 1

        data = json.loads(r.stdout)
        running = data.get("running", False)

        console.print("\n[bold cyan]💓 BOS 心跳健康面板[/]")
        console.print(f"  已注册: {data.get('total_known', '?')} backends")

        if not running:
            console.print(f"[yellow]  ⚠️  {data.get('note', '心跳未运行')}[/]")
            console.print("\n[dim]提示: mcp_gateway 以 server 模式运行时自动激活心跳[/]")
            return 0

        console.print(f"  跟踪中: {data.get('tracked', 0)} backends")
        console.print(f"  🟢 在线: {data.get('alive', 0)}  🔴 离线: {data.get('dead', 0)}")
        console.print(f"  探测间隔: {data.get('interval', 30)}s\n")

        table = Table(box=box.SIMPLE)
        table.add_column("Backend")
        table.add_column("状态")
        table.add_column("失败次数")
        table.add_column("上次成功")

        for name, s in data.get("backends", {}).items():
            alive = s.get("alive", False)
            fails = s.get("fails", 0)
            status_str = "[green]🟢 在线[/]" if alive else "[red]🔴 离线[/]"
            if fails >= 3:
                status_str = "[red]🔴 已删除[/]"
            elif fails >= 1:
                status_str = "[yellow]🟡 不稳定[/]"
            last_ok = s.get("last_ok", "")
            if last_ok:
                import datetime

                last_ok = datetime.datetime.fromtimestamp(last_ok).strftime("%H:%M:%S")
            else:
                last_ok = "—"
            table.add_row(name, status_str, str(fails), last_ok)

        console.print(table)
        return 0

    except Exception as e:  # defensive fallback
        console.print(f"[red]错误:[/] {e}")
        return 1
