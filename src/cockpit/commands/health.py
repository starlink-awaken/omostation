from __future__ import annotations

import os
import sys
from argparse import Namespace
from pathlib import Path

from rich.console import Console

console = Console()


def _get_l4_registry():
    """获取 l4-kernel DomainRegistry；配置缺失时返回 None 而不是崩溃。"""
    try:
        from cockpit.adapters.l4_kernel import DomainRegistry, load_overrides_from_config

        l4_config_path = Path(
            os.environ.get("L4_DOMAIN_CONFIG", str(Path.home() / ".config" / "l4-kernel" / "domains.toml"))
        )
        return DomainRegistry(path_overrides=load_overrides_from_config(l4_config_path))
    except Exception:
        return None


def _cmd_health(args: Namespace) -> int:
    """一键系统健康检查 — 聚合 Context + Status + 可选全栈检查。"""
    return_code = 0

    # JSON 模式：直接输出 workspace_context() 并退出，不混入人类可读面板。
    if bool(getattr(args, "json", False)):
        try:
            from cockpit.scripts.cockpit_mcp import workspace_context

            print(workspace_context())
            return 0
        except Exception as e:  # defensive fallback
            import json as _json

            print(_json.dumps({"error": str(e)}, ensure_ascii=False))
            return 1

    # ── L4 Context ──────────────────────────────────────────────
    console.print("\n[bold cyan]═══ L4 上下文 ═══[/]\n")
    try:
        from .l4bridge import cmd_context

        cmd_context(args)
    except Exception:  # defensive fallback
        console.print("[yellow]⚠ L4 bridge 不可用[/]")
        return_code = 1

    # ── L3 Cockpit Status ───────────────────────────────────────
    console.print("\n[bold cyan]═══ L3 Cockpit ═══[/]\n")
    try:
        # 产品走查 v5 #V5-02: health 不重复完整 status 工作台 (避免与 cockpit status
        # 输出冗余); 聚焦健康摘要, 完整工作台引导用户用 cockpit status
        import json as _json

        from cockpit.scripts.cockpit_mcp import workspace_context

        ctx = _json.loads(workspace_context())
        console.print(f"  Phase {ctx.get('phase', '?')} · {str(ctx.get('theme', ''))[:40]}")
        cs = ctx.get("cards_summary", {}) or {}
        console.print(f"  活跃卡片: {cs.get('active', 0)} (P0: {cs.get('p0_open', 0)})")
        console.print("  [dim]完整工作台 → [cyan]cockpit status[/][/]")
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
            from cockpit.adapters.l4_kernel import DomainHealth

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
                console.print(f"  [dim]服务注册: {len(state.get('services', {}))} 项[/]")
                h = sum(1 for s in state.get("services", {}).values() if s.get("healthy"))
                t = max(len(state.get("services", {})), 1)
                console.print(f"  [{'green' if h == t else 'yellow'}]健康: {h}/{t}[/]")
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
        l4_health = Path.home() / "Documents" / "@驾驶舱" / "_runtime" / "ecos-health-check.py"
        if l4_health.exists():
            try:
                import subprocess as _l4sp

                result = _l4sp.run(
                    [sys.executable, str(l4_health)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if not args.json:
                    for line in result.stdout.split("\n"):
                        stripped = line.strip()
                        if stripped and not stripped.startswith("L4"):
                            console.print(f"  [dim]{stripped}[/]")
            except Exception as e:  # defensive fallback
                console.print(f"[yellow]⚠ L4 文档域检查跳过: {e}[/]")
        elif not args.json:
            console.print("[yellow]⚠ L4 健康脚本未找到 (创建 _runtime/ecos-health-check.py)[/]")

        console.print("\n[bold green]✅ 全栈健康检查完成[/]\n")

    return return_code
