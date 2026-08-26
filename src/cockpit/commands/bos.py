"""Cockpit BOS Commands — L3 入口层 BOS URI 集成"""

import json
import subprocess
import sys
from pathlib import Path

# commands/ → cockpit/ → src/ → cockpit package root → projects/cockpit → projects → workspace
_WORKSPACE = Path(__file__).resolve().parents[5]
# resolve/read 依赖 agora resolver + ecos 工具链, 需注入 src (与 agora.py 委派同理)
for _src in (
    _WORKSPACE / "projects" / "agora" / "src",
    _WORKSPACE / "projects" / "ecos" / "src",
):
    if str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

ECOS_TOOLS = Path(__file__).parent.parent.parent.parent / "ecos" / "src" / "ecos" / "ssot" / "tools"
MOF_WORKFLOW = str(ECOS_TOOLS / "mof-workflow.py")
_CAPABILITY_RECEIPT_FIELDS = frozenset(
    {
        "schema",
        "operation",
        "status",
        "capability_id",
        "registry_digest",
        "record_digest",
        "selector_digest",
        "admission_status",
        "admission_decision_digest",
        "health_status",
        "health_evidence_digest",
        "adapter_kind",
        "adapter_target_digest",
        "invocation_attempted",
        "input_digest",
        "result_digest",
        "exit_code",
        "error_code",
        "error_detail_digest",
        "binding_digest",
    }
)


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


def _load_bos_yaml_services() -> list[dict]:
    """Load raw bos-services.yaml entries (includes non-routable statuses)."""
    import yaml

    # projects/cockpit → projects → workspace
    root = Path(__file__).resolve().parents[4]
    path = root / "agora" / "etc" / "bos-services.yaml"
    if not path.is_file():
        # fallback: workspace-relative via parents[5] if layout differs
        alt = Path(__file__).resolve().parents[5] / "projects" / "agora" / "etc" / "bos-services.yaml"
        path = alt if alt.is_file() else path
    docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    for d in docs:
        if isinstance(d, dict) and "services" in d:
            return [s for s in (d["services"] or []) if isinstance(s, dict)]
    return []


def cmd_bos_list(args):
    """列出 BOS URI 路由。默认仅 routable；--all 含 unimplemented/deprecated。"""
    show_all = bool(getattr(args, "all", False) or getattr(args, "include_all", False))
    try:
        if show_all:
            raw = _load_bos_yaml_services()
            from collections import Counter

            status_c = Counter((s.get("status") or "active") for s in raw)
            by_domain: dict[str, list[tuple[str, str]]] = {}
            for s in raw:
                uri = s.get("uri") or ""
                st = s.get("status") or "active"
                domain = s.get("domain") or "unknown"
                by_domain.setdefault(domain, []).append((uri, st))

            print(f"\n  BOS URI 全量表 (yaml, {len(raw)} 条) — 含 non-routable")
            print(f"  status: {dict(status_c)}")
            print(f"  {'=' * 40}")
            for domain in sorted(by_domain):
                services = sorted(by_domain[domain], key=lambda x: x[0])
                print(f"\n  {domain} ({len(services)}):")
                for uri, st in services:
                    mark = "" if st == "active" else f"  [{st}]"
                    print(f"    {uri}{mark}")
            print("\n  💡 默认路由表不含 unimplemented/deprecated。 去掉 --all 仅看 routable。")
            return 0

        from cockpit.adapters.agora import POC_SERVICES

        by_domain: dict[str, list[str]] = {}
        for s in POC_SERVICES:
            by_domain.setdefault(s.domain, []).append(s.uri)

        print(f"\n  BOS URI 路由表 ({len(POC_SERVICES)} 条 routable)")
        print(f"  {'=' * 40}")
        for domain in sorted(by_domain):
            services = by_domain[domain]
            print(f"\n  {domain} ({len(services)}):")
            for uri in sorted(services):
                print(f"    {uri}")
        print("\n  💡 查看 yaml 中 unimplemented/deprecated: cockpit bos list --all")
        return 0
    except Exception as e:  # defensive fallback
        print(f"  BOS 服务不可用: {e}")
        return 1


def cmd_bos_resolve(args):
    """通过 BOS 网关解析指定 URI 的路由与执行元数据。"""
    try:
        from agora.mcp.resolver.api import get_service

        uri = getattr(args, "uri", "")
        service = get_service(uri)
        if not service:
            print(f"❌ 无法解析 BOS URI: {uri} (未在 bos-services.yaml 中注册)")
            return 1

        print("═══ BOS URI Route Resolution ═══")
        print(f"🔗 URI:         {service.uri}")
        print(f"📦 Domain:      {service.domain}")
        print(f"⚡️ Action:      {service.action}")
        print(f"🚀 Transport:   {service.transport}")
        print(f"🛠️ Package:     {service.package or '(builtin/gateway)'}")
        print(f"💻 Command:     {' '.join(service.command)}")
        print(f"📖 Description: {service.description}")
        return 0
    except Exception as e:
        print(f"❌ 解析异常: {e}")
        return 1


def cmd_bos_read(args):
    """通过 BOS 网关读取并执行目标 URI 的结果，支持参数传参。"""
    try:
        import json

        from agora.mcp.resolver.api import _run_maybe_async
        from agora.server.tools_bos import _resolve_with_router

        uri = getattr(args, "uri", "")
        raw_args = getattr(args, "args", "{}")
        try:
            params = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except Exception:
            print(f"❌ 无法解析 JSON 参数: {raw_args}")
            return 1

        res, source = _run_maybe_async(_resolve_with_router(uri, **params))
        print("═══ BOS URI Read Result ═══")
        print(f"🔗 Target: {uri} (source={source})")
        print(f"📤 Output:\n{json.dumps(res, indent=2, ensure_ascii=False)}")
        return 0
    except Exception as e:
        print(f"❌ 读取异常: {e}")
        return 1


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
        except Exception:  # defensive fallback  # noqa: S112
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


def _load_capability_services() -> list:
    """Load capability-domain services from BOS YAML (preferred) or POC_SERVICES."""
    services: list = []
    try:
        from cockpit.adapters.agora import load_from_yaml

        services = list(load_from_yaml() or [])
    except Exception:
        try:
            from agora.mcp.resolver.services import POC_SERVICES

            services = list(POC_SERVICES)
        except Exception:
            services = []
    return [
        s
        for s in services
        if getattr(s, "domain", "") == "capability" or str(getattr(s, "uri", "")).startswith("bos://capability/")
    ]


def _match_capability_service(services: list, key: str):
    """Match only a full BOS URI or its canonical capability ID."""
    key = (key or "").strip()
    if not key:
        return None
    if key.startswith("bos-service:"):
        key = key.removeprefix("bos-service:")
    if not key.startswith("bos://"):
        return None
    for s in services:
        uri = str(getattr(s, "uri", "") or "")
        if key == uri:
            return s
    return None


def _sanitize_capability_receipt(receipt: object, canonical_id: str) -> dict:
    """Project an untrusted child result into the fixed public receipt schema."""
    if not isinstance(receipt, dict) or receipt.get("schema") != "capability-invocation-receipt/v1":
        raise ValueError("invalid receipt schema")
    if receipt.get("operation") not in {None, "invoke"}:
        raise ValueError("invalid receipt operation")
    if receipt.get("capability_id") not in {None, canonical_id}:
        raise ValueError("receipt capability mismatch")
    return {key: receipt[key] for key in _CAPABILITY_RECEIPT_FIELDS if key in receipt}


def run_bos_capability_invoke(
    *,
    capability_id: str,
    input_json,
    binding_json=None,
    inspection_receipt_json=None,
    admission_receipt_json=None,
    operation_id=None,
    effect_classification=None,
) -> int:
    """Forward one governed BOS invoke with its full binding bundle to capability-sync."""
    command = [
        sys.executable,
        str(_WORKSPACE / "bin" / "capability-sync.py"),
        "invoke",
        "--id",
        capability_id,
        "--input-json",
        str(input_json),
    ]
    if binding_json is not None:
        command.extend(["--binding-json", str(binding_json)])
    if inspection_receipt_json is not None:
        command.extend(["--inspection-receipt-json", str(inspection_receipt_json)])
    if admission_receipt_json is not None:
        command.extend(["--admission-receipt-json", str(admission_receipt_json)])
    if operation_id is not None:
        command.extend(["--operation-id", operation_id])
    if effect_classification is not None:
        command.extend(["--effect-classification", effect_classification])
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    try:
        receipt = _sanitize_capability_receipt(json.loads(result.stdout), capability_id)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps({"schema": "capability-invocation-receipt/v1", "status": "invalid_receipt"}, sort_keys=True))
    else:
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return int(result.returncode)


def cmd_bos_capability(args) -> int:
    """BOS capability / toolbox 外部能力入口。"""
    subcmd = getattr(args, "capability_command", "list")
    output_format = getattr(args, "global_output", "tty") or "tty"

    if subcmd == "list":
        try:
            services = _load_capability_services()
            data = []
            for s in services:
                data.append(
                    {
                        "uri": getattr(s, "uri", "?"),
                        "description": getattr(s, "description", "") or "",
                        "transport": getattr(s, "transport", "") or "",
                    }
                )
            from cockpit.commands.base import render_command_result

            render_command_result(
                title="BOS Capability 服务注册表大盘",
                data=data,
                output_format=output_format,
                columns=["uri", "description", "transport"],
            )
            return 0
        except Exception as e:  # defensive fallback
            print(f"  Capability 服务不可用: {e}")
            return 1

    if subcmd == "invoke":
        svc_id = getattr(args, "capability_service", None)
        if not svc_id:
            print("用法: cockpit bos capability invoke <bos-uri> --input-json <file>")
            return 1
        try:
            services = _load_capability_services()
        except Exception as e:
            print(f"  加载 BOS 注册表失败: {e}")
            return 1
        svc = _match_capability_service(services, svc_id)
        if svc is None:
            print("  未找到精确 capability URI；短名和子串调用已禁用")
            print("  用 `cockpit bos capability list` 查看完整 URI")
            return 1
        input_json = getattr(args, "capability_input_json", None)
        if input_json is None:
            print("  缺少 --input-json；仅接受结构化输入文件")
            return 1
        uri = str(getattr(svc, "uri", "") or "")
        canonical_id = "bos-service:" + uri
        command = [
            sys.executable,
            str(_WORKSPACE / "bin" / "capability-sync.py"),
            "invoke",
            "--id",
            canonical_id,
            "--input-json",
            str(input_json),
        ]
        binding_json = getattr(args, "capability_binding_json", None)
        if binding_json is not None:
            command.extend(["--binding-json", str(binding_json)])
        inspection_receipt_json = getattr(args, "capability_inspection_receipt_json", None)
        if inspection_receipt_json is not None:
            command.extend(["--inspection-receipt-json", str(inspection_receipt_json)])
        admission_receipt_json = getattr(args, "capability_admission_receipt_json", None)
        if admission_receipt_json is not None:
            command.extend(["--admission-receipt-json", str(admission_receipt_json)])
        operation_id = getattr(args, "capability_operation_id", None)
        if operation_id is not None:
            command.extend(["--operation-id", operation_id])
        effect_classification = getattr(args, "capability_effect_classification", None)
        if effect_classification is not None:
            command.extend(["--effect-classification", effect_classification])
        try:
            result = subprocess.run(command, check=False, capture_output=True, text=True)
        except OSError:
            print(
                json.dumps(
                    {
                        "schema": "capability-invocation-receipt/v1",
                        "status": "rejected",
                        "error_code": "CAPABILITY_GATEWAY_UNAVAILABLE",
                        "invocation_attempted": False,
                    },
                    sort_keys=True,
                )
            )
            return 5
        try:
            receipt = _sanitize_capability_receipt(json.loads(result.stdout), canonical_id)
        except (json.JSONDecodeError, ValueError):
            receipt = {
                "schema": "capability-invocation-receipt/v1",
                "status": "rejected",
                "error_code": "CAPABILITY_GATEWAY_INVALID_RECEIPT",
                "invocation_attempted": False,
            }
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
        return int(result.returncode)

    print("用法: cockpit bos capability {list|invoke <service_id>}")
    return 1


def _agora_mcp_port() -> int:
    """从主仓 protocols/port-registry.yaml (SSOT) 读取 agora-mcp-sse 端口 (默认 7431).

    避免硬编码端口漂移 (与 swarm 面板同一数据源)。
    """
    try:
        import yaml

        reg = _WORKSPACE / "protocols" / "port-registry.yaml"
        data = yaml.safe_load(reg.read_text(encoding="utf-8"))
        ports = data.get("ports", data) if isinstance(data, dict) else {}
        if isinstance(ports, dict):
            for p, meta in ports.items():
                if isinstance(meta, dict) and meta.get("name") == "agora-mcp-sse":
                    return int(p)
    except (OSError, ValueError, TypeError):
        pass
    return 7431


def cmd_bos_mutate(args):
    """通过 agora MCP (SSE :7431, P0 后共用 /v1/tools/call) 统一 BOS URI 写协议 (mutate_resource) 修改资源."""
    uri = getattr(args, "uri", "")
    payload = getattr(args, "payload", "{}")
    action = getattr(args, "action", "update")
    import json
    import os
    import urllib.request

    body = json.dumps(
        {
            "name": "mutate_resource",
            "arguments": {"uri": uri, "payload": payload, "action": action},
        }
    ).encode()
    # /v1/tools/call 现于 SSE (7431) 与 HTTP 双模式注册 (P0 共用路由)。
    # 端口从 port-registry SSOT 读取 (agora-mcp-sse=7431)。
    # 需 Authorization: Bearer AGORA_API_KEY (agora AuthMiddleware fail-closed)。
    api_key = os.environ.get("AGORA_API_KEY", "")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    mcp_port = _agora_mcp_port()
    req = urllib.request.Request(
        f"http://127.0.0.1:{mcp_port}/v1/tools/call",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            data = json.loads(resp.read())
    except Exception as exc:
        print(f"❌ 无法连接 agora MCP :{mcp_port} (需 agora-mcp --sse 或 --http 运行): {exc}")
        print("  启动: uv run --directory projects/agora agora-mcp --sse")
        return 1

    print("═══ BOS Mutate ═══")
    content = data.get("result", {}).get("content") or [data]
    for item in content:
        if isinstance(item, dict):
            text = item.get("text", json.dumps(item, ensure_ascii=False))
            print(f"  {text}")
        else:
            print(f"  {item}")
    return 0
