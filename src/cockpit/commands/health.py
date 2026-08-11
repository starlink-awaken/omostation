from __future__ import annotations

import json
import os
from argparse import Namespace
from pathlib import Path

from rich.console import Console

from cockpit.adapters import governance_context

console = Console()


def _get_l4_registry():
    """获取正式 ManifestRegistry 的只读 legacy 投影。"""
    try:
        from l4_kernel.manifest_registry import ManifestRegistry  # type: ignore[import-not-found]

        documents_root = Path(os.environ.get("L4_DOCUMENTS_ROOT", str(Path.home() / "Documents"))).expanduser()
        registry_path = Path(
            os.environ.get(
                "L4_DOMAIN_REGISTRY",
                str(documents_root / "@公共" / "_control" / "L4-DOMAIN-REGISTRY.yaml"),
            )
        )
        return ManifestRegistry.load(registry_path).as_legacy_registry()
    except Exception:
        return None


def _cmd_health(args: Namespace) -> int:
    """一键系统健康检查 — 聚合 Context + Status + 可选全栈检查。"""
    return_code = 0

    # JSON 模式：直接输出 workspace_context() 并退出，不混入人类可读面板。
    if bool(getattr(args, "json", False)):
        ctx = governance_context.workspace_context()
        print(json.dumps(ctx, ensure_ascii=False))
        return 0 if ctx["status"] == "ok" else 1

    # ── L4 Context ──────────────────────────────────────────────
    console.print("\n[bold cyan]═══ L4 上下文 ═══[/]\n")
    try:
        from .l4bridge import cmd_context

        return_code = max(return_code, cmd_context(args))
    except Exception:  # defensive fallback
        console.print("[yellow]⚠ L4 bridge 不可用[/]")
        return_code = 1

    # ── L3 Cockpit Status ───────────────────────────────────────
    console.print("\n[bold cyan]═══ L3 Cockpit ═══[/]\n")
    try:
        # 产品走查 v5 #V5-02: health 不重复完整 status 工作台 (避免与 cockpit status
        # 输出冗余); 聚焦健康摘要, 完整工作台引导用户用 cockpit status
        ctx = governance_context.workspace_context()
        console.print(f"  Phase {ctx.get('phase', '?')} · {str(ctx.get('theme', ''))[:40]}")
        cs = ctx.get("cards_summary", {}) or {}
        console.print(f"  活跃卡片: {cs.get('active', 0)} (P0: {cs.get('p0_open', 0)})")
        console.print(f"  状态: {ctx['status']}")
        console.print("  [dim]完整工作台 → [cyan]cockpit status[/][/]")
        if ctx["status"] != "ok":
            return_code = 1
    except Exception as e:  # defensive fallback
        console.print(f"[red]Cockpit status error: {e}[/]")
        return_code = 1

    # ── Full: I0 Agora + L1 Runtime + L2 OMO ────────────────────
    if getattr(args, "full", False):
        console.print("\n[bold cyan]═══ I0 服务网格 ═══[/]\n")
        try:
            # Try l4-kernel for domain health first
            reg = _get_l4_registry()
            if reg is not None:
                h = reg.aggregate_health()
                if not args.json:
                    console.print(
                        f"  [dim]域总数: {h['total']}  |  存在: {h['existing']}  |  健康率: {h['health_rate']}[/]"
                    )
            else:
                console.print("[yellow]⚠ l4-kernel 域配置未找到，跳过域健康聚合[/]")

            # Agora stats via subprocess as fallback
            import subprocess as _sp

            ws = Path(os.environ.get("WORKSPACE_ROOT", str(Path(__file__).resolve().parents[5])))
            agora_bin = ws / "projects" / "agora" / ".venv" / "bin" / "agora"
            if agora_bin.exists():
                result = _sp.run([str(agora_bin), "stats"], capture_output=True, text=True, timeout=15)
                if not args.json:
                    for line in result.stdout.split("\n"):
                        if "总计" in line or "健康" in line or "异常" in line or "健康率" in line:
                            console.print(f"  [dim]{line.strip()}[/]")
            else:
                console.print("[yellow]⚠ agora CLI 未安装[/]")
        except Exception as e:  # defensive fallback
            console.print(f"[yellow]⚠ I0 检查跳过: {e}[/]")

        # ── L4 Domain Health ──────────────────────────────────────
        console.print("\n[bold cyan]═══ L4 域健康 ═══[/]\n")
        try:
            from cockpit.adapters.l4_kernel import DomainHealth  # type: ignore[import-not-found]

            reg = _get_l4_registry()
            if reg is not None:
                dh = DomainHealth(reg)
                dashboard = dh.generate_dashboard()
                if not args.json:
                    for line in dashboard.split("\n"):
                        if line.startswith("- **"):
                            console.print(f"  [dim]{line.strip()}[/]")
            else:
                console.print("[yellow]⚠ l4-kernel 域配置未找到，跳过 L4 域健康[/]")
        except ImportError:
            console.print("[yellow]⚠ l4-kernel 未安装[/]")

        # ── Full: Runtime Matrix ────────────────────────────────
        console.print("\n[bold cyan]═══ L1 运行时 ═══[/]\n")
        matrix_path = Path.home() / "runtime" / "matrix_state.json"
        if not args.json and matrix_path.exists():
            try:
                import json as _j

                state = _j.loads(matrix_path.read_text())
                svcs = state.get("services", {})
                console.print(f"  [dim]服务注册: {len(svcs)} 项[/]")

                # matrix_state.json schema (runtime scheduler):
                #   health_check: 'healthy'|'scheduled'|'unreachable'|...
                #   runtime.status: 'running'|'idle'|'scheduled'|'failed'|'unmanaged'
                # 旧代码读顶层 'healthy' 键 (不存在) → 恒 0/N 假红灯。
                def _svc_healthy(s: dict) -> bool:
                    if s.get("health_check") == "healthy":
                        return True
                    return (s.get("runtime") or {}).get("status") in ("running", "scheduled")

                managed = {n: s for n, s in svcs.items() if (s.get("runtime") or {}).get("status") != "unmanaged"}
                h = sum(1 for s in managed.values() if _svc_healthy(s))
                t = max(len(managed), 1)
                unmanaged = len(svcs) - len(managed)
                suffix = f"  (unmanaged: {unmanaged})" if unmanaged else ""
                console.print(f"  [{'green' if h == t else 'yellow'}]健康: {h}/{t}{suffix}[/]")
                bad = [n for n, s in managed.items() if not _svc_healthy(s)]
                if bad:
                    console.print(f"  [yellow]异常: {', '.join(sorted(bad))}[/]")
            except Exception:  # defensive fallback
                console.print("[yellow]⚠ Matrix state 解析失败[/]")
        elif not args.json:
            console.print("[yellow]⚠ Matrix state 未生成 (runtime scheduler 未运行)[/]")

        # ── Full: OMO Debt ───────────────────────────────────────
        console.print("\n[bold cyan]═══ L2 治理 ═══[/]\n")
        ws = Path(os.environ.get("WORKSPACE_ROOT", str(Path(__file__).resolve().parents[5])))
        debt_path = ws / ".omo" / "state" / "system.yaml"
        if debt_path.exists():
            try:
                import yaml

                sys_data = yaml.safe_load(debt_path.read_text())
                if not args.json:
                    phase = sys_data.get("current_phase", "?")
                    health = sys_data.get("health_score", 0)
                    debt = sys_data.get("debt_weight", 0)
                    console.print(f"  [dim]Phase: {phase}  |  健康分: {health}  |  债务权重: {debt}[/]")
            except Exception:  # defensive fallback
                console.print("[yellow]⚠ OMO state 解析失败[/]")
        elif not args.json:
            console.print("[yellow]⚠ OMO state 未生成[/]")

        # ── Full: L4 文档域健康 ─────────────────────────────────
        console.print("\n[bold cyan]═══ L4 文档域 ═══[/]\n")
        kems = governance_context.kems_status()
        audit = kems["content_audit"]
        console.print(
            f"  [dim]域注册: {kems['domains']['status']} ({kems['domains']['total']})  |  "
            f"内容审计: {audit['status']} ({len(audit.get('violations', []))} violations)[/]"
        )
        if kems["status"] != "ok":
            return_code = 1

        if return_code == 0:
            console.print("\n[bold green]✅ 全栈健康检查完成[/]\n")
        else:
            console.print("\n[bold yellow]⚠ 全栈健康检查完成，但存在异常[/]\n")

    return return_code
