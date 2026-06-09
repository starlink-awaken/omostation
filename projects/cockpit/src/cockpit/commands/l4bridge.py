"""cockpit.commands.l4bridge — L4 bridge CLI commands (context, cards, vault)."""

from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path

from .base import _get_console, _get_err, _panel

try:
    from cockpit.scripts.cockpit_mcp import (
        workspace_context,
        cards_status,
        cards_check,
        vault_search,
    )

    _HAS_L4 = True
except ImportError:
    _HAS_L4 = False


def cmd_context(_args: Namespace) -> int:
    """显示 workspace 完整上下文 (Phase / CARDS / 约束 / 引导)。"""
    console = _get_console()

    if not _HAS_L4:
        _get_err().print("[red]❌ L4 bridge 不可用[/]")
        return 1

    try:
        ctx = json.loads(workspace_context())
    except Exception as e:
        _get_err().print(f"[red]❌ workspace_context 调用失败: {e}[/]")
        return 1

    # Phase
    console.print(
        _panel(
            f"[bold cyan]🛸 Workspace Context[/bold cyan]\n"
            f"Phase [bold]{ctx['phase']}[/bold] · {ctx['theme']}\n"
            f"状态: [bold green]{ctx.get('phase_status', '?')}[/]",
            "cyan",
        )
    )

    # P0 Cards
    cards = ctx.get("cards_summary", {})
    if cards.get("p0_open", 0) > 0:
        console.print(f"\n[bold red]⚡ P0 活跃 ({cards['p0_open']}):[/]")
        for title in cards.get("p0_titles", []):
            console.print(f"  [red]▪[/] {title}")
    else:
        console.print("\n[green]✅ 无 P0 待处理[/]")

    # Constraints
    constraints = ctx.get("constraints", [])
    console.print(f"\n[bold yellow]🔒 约束 ({len(constraints)}):[/]")
    for c in constraints[:5]:
        console.print(f"  [dim]◦[/] {c}")

    # Guidance
    guidance = ctx.get("next_guidance", "")
    if guidance:
        console.print(f"\n[bold blue]🧭 下一步:[/]")
        for line in guidance.split("."):
            if line.strip():
                console.print(f"  [blue]→[/] {line.strip()}.")

    console.print()
    return 0


def cmd_domains(_args: Namespace) -> int:
    """列出 L4 所有域及其状态。"""
    console = _get_console()

    if not _HAS_L4:
        _get_err().print("[red]❌ L4 bridge 不可用[/]")
        return 1

    try:
        from cockpit.scripts.cockpit_mcp import domains_list

        result = json.loads(domains_list())
    except Exception as e:
        _get_err().print(f"[red]❌ domains_list 失败: {e}[/]")
        return 1

    console.print(f"\n[bold cyan]🌐 L4 域状态 ({result['total']} 域)[/]\n")
    for d in result.get("domains", []):
        icon = "[green]✓[/]" if d["exists"] else "[red]✗[/]"
        console.print(f"  {icon} [bold]{d['name']}[/] [dim]{d['path']}[/]")

    return 0


def cmd_skill(args: Namespace) -> int:
    """运行 L4 定时技能 (由 cron_service 触发)。"""
    console = _get_console()

    skill_name = getattr(args, "skill_name", "") or ""
    if not skill_name:
        _get_err().print("[yellow]用法: cockpit workspace skill run <skill_name>[/]")
        return 1

    console.print(f"[cyan]⏳ 执行技能: {skill_name}...[/]")

    skill_file = (
        Path(__file__).resolve().parents[4] / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof"
        / "m1" / "skill" / f"SKILL-SCHEDULED-{skill_name}.yaml"
    )

    if not skill_file.exists():
        _get_err().print(f"[red]❌ 技能未找到: SKILL-SCHEDULED-{skill_name}.yaml[/]")
        return 1

    try:
        import yaml

        skill_def = yaml.safe_load(skill_file.read_text(encoding="utf-8"))
        desc = skill_def.get("description", skill_def.get("name", skill_name))
        console.print(f"  [dim]描述: {desc}[/]")
        console.print(f"  [green]✓ 技能已调度 (由 cron_service 执行)[/]")
        return 0
    except Exception as e:
        _get_err().print(f"[red]❌ 技能执行失败: {e}[/]")
        return 1


def cmd_cards(args: Namespace) -> int:
    """显示 CARDS 状态。"""
    console = _get_console()

    if not _HAS_L4:
        _get_err().print("[red]❌ L4 bridge 不可用[/]")
        return 1

    if getattr(args, "check", False):
        card_id = getattr(args, "card_id", "") or ""
        try:
            result = json.loads(cards_check(card_id=card_id))
        except Exception as e:
            _get_err().print(f"[red]❌ cards_check 失败: {e}[/]")
            return 1

        if result["compliant"]:
            console.print("[bold green]✅ 合规[/]")
        else:
            console.print("[bold red]❌ 违规:[/]")
            for v in result.get("violations", []):
                console.print(f"  [red]▪[/] {v}")
        console.print(f"\n[dim]已检查 {result['constraints_checked']} 项约束[/]")
        return 0

    try:
        items = json.loads(cards_status())
    except Exception as e:
        _get_err().print(f"[red]❌ cards_status 失败: {e}[/]")
        return 1

    console.print(_panel(f"[bold cyan]🃏 CARDS ({len(items)} active)[/]", "cyan"))

    for card in items:
        color = {"P0": "red", "P1": "yellow", "P2": "blue", "P3": "dim"}.get(card["priority"], "dim")
        status_color = "green" if card["status"] != "closed" else "dim"
        console.print(
            f"  [[{color}]{card['priority']}[/]] "
            f"[{status_color}]{card['title']}[/] "
            f"[dim]({card['type']} · {card['domain']})[/]"
        )

    console.print()
    return 0


def cmd_vault(args: Namespace) -> int:
    """搜索 L4 Vault。"""
    console = _get_console()

    if not _HAS_L4:
        _get_err().print("[red]❌ L4 bridge 不可用[/]")
        return 1

    keyword = getattr(args, "keyword", "") or ""
    if not keyword:
        _get_err().print("[yellow]用法: workspace vault search <keyword>[/]")
        return 1

    try:
        result = json.loads(vault_search(keyword=keyword))
    except Exception as e:
        _get_err().print(f"[red]❌ vault_search 失败: {e}[/]")
        return 1

    console.print(f"[bold cyan]🔍 Vault 搜索: \"{keyword}\" ({result['total']} 结果)[/]\n")

    for r in result.get("results", []):
        console.print(f"  [bold]{r['title']}[/]")
        console.print(f"  [dim]{r['path']}[/]")
        if r.get("snippet"):
            snippet = r["snippet"].replace(keyword, f"[bold yellow]{keyword}[/]")
            console.print(f"  {snippet}\n")

    return 0


# ── model-driven 桥接命令 ────────────────────────────────────────────


def cmd_model_driven_lifecycle(args: Namespace) -> int:
    """model-driven lifecycle 子命令 (通过 cockpit CLI 入口)。"""
    console = _get_console()
    try:
        from model_driven.lifecycle.tracking import LifecycleManager
        from model_driven.lifecycle.transitions import TransitionEngine
        from model_driven.mof.m3_extended import LifecycleStage

        mgr = LifecycleManager()
        engine = TransitionEngine()

        subcmd = getattr(args, "md_subcmd", "status")
        entity_id = getattr(args, "md_entity", "cockpit")

        if subcmd == "create":
            mgr.create_tracker(entity_id, getattr(args, "md_type", ""))
            console.print(f"[green]✅ 已创建生命周期追踪: {entity_id}[/]")

        elif subcmd == "advance":
            target = LifecycleStage.from_str(getattr(args, "md_stage", "planning"))
            tracker = mgr.get_tracker(entity_id)
            if not tracker:
                tracker = mgr.create_tracker(entity_id)
            success, msg, _ = engine.try_transition(tracker, target)
            icon = "✅" if success else "❌"
            console.print(f"[{'green' if success else 'red'}]{icon} {msg}[/]")

        elif subcmd == "dashboard":
            dashboard = mgr.generate_dashboard()
            console.print(f"[bold cyan]全生命周期仪表板[/]")
            console.print(f"实体: {dashboard.total_entities} | 进度: {dashboard.avg_progress}%")
            for blocker in dashboard.blockers:
                console.print(f"  [red]🔴 [{blocker['entity_id']}] {blocker['stage']}: {blocker['issue']}[/]")

        else:  # status
            summary = mgr.get_stage_summary(entity_id)
            if summary:
                console.print(f"[bold]实体: {summary['entity_id']}[/]")
                console.print(f"阶段: {summary['current_stage']} | 进度: {summary['progress_pct']}%")
            else:
                console.print(f"[yellow]⚠️ 未找到实体: {entity_id}[/]")

        return 0
    except ImportError:
        _get_err().print("[red]❌ model-driven 不可用[/]")
        return 1


def cmd_model_driven_spec(args: Namespace) -> int:
    """model-driven spec 子命令。"""
    console = _get_console()
    try:
        from model_driven.management.spec import SpecManager, SpecStatus

        mgr = SpecManager()
        subcmd = getattr(args, "md_subcmd", "list")

        if subcmd == "create":
            spec_id = getattr(args, "md_id", f"SPEC-{len(mgr.list_all()) + 1}")
            title = getattr(args, "md_title", "未命名")
            spec = mgr.create(spec_id, title)
            console.print(f"[green]✅ 已创建 Spec: {spec.id} - {spec.title}[/]")
        else:
            specs = mgr.list_all()
            if specs:
                for s in specs:
                    console.print(f"  [{s.status.value}] {s.id}: {s.title}")
            else:
                console.print("[dim]无 Spec[/]")

        return 0
    except ImportError:
        _get_err().print("[red]❌ model-driven 不可用[/]")
        return 1


def cmd_model_driven_okr(args: Namespace) -> int:
    """model-driven okr 子命令。"""
    console = _get_console()
    try:
        from model_driven.management.okr import OKRManager

        mgr = OKRManager()
        subcmd = getattr(args, "md_subcmd", "list")

        if subcmd == "create":
            okr_id = getattr(args, "md_id", f"OKR-{len(mgr.list_all()) + 1}")
            objective = getattr(args, "md_objective", "未定义目标")
            okr = mgr.create(okr_id, objective)
            console.print(f"[green]✅ 已创建 OKR: {okr.id} - {okr.objective}[/]")
        else:
            okrs = mgr.list_all()
            if okrs:
                for o in okrs:
                    console.print(f"  [{o.status.value}] {o.id}: {o.objective} ({o.progress:.0%})")
            else:
                console.print("[dim]无 OKR[/]")

        return 0
    except ImportError:
        _get_err().print("[red]❌ model-driven 不可用[/]")
        _get_err().print("[dim]  请确保 model-driven 已安装: cd ~/Workspace/projects/model-driven && uv sync[/]")
        return 1


# ── 统一 model-driven 入口 ────────────────────────────────────────


def _md_not_available() -> int:
    _get_err().print("[red]❌ model-driven 不可用[/]")
    _get_err().print("[dim]  请确保 model-driven 已安装:[/]")
    _get_err().print("[dim]    cd ~/Workspace/projects/model-driven && uv sync[/]")
    return 1


def cmd_model_driven(args: Namespace) -> int:
    """统一 model-driven 入口 — 合并 lifecycle/spec/okr/derive/pipeline 为一个子命令。

    用法: cockpit model-driven <lifecycle|spec|okr|derive|pipeline> [action] [args]
    """
    console = _get_console()
    subcmd = getattr(args, "md_subcmd", "lifecycle")
    try:
        if subcmd == "lifecycle":
            return _md_lifecycle(args, console)
        elif subcmd == "spec":
            return _md_spec(args, console)
        elif subcmd == "okr":
            return _md_okr(args, console)
        elif subcmd == "derive":
            return _md_derive(args, console)
        elif subcmd == "pipeline":
            return _md_pipeline(args, console)
        else:
            console.print(f"[yellow]未知 model-driven 子命令: {subcmd}[/]")
            console.print("可用: lifecycle, spec, okr, derive, pipeline")
            return 1
    except ImportError:
        return _md_not_available()


def _md_lifecycle(args: Namespace, console) -> int:
    from model_driven.lifecycle.tracking import LifecycleManager
    from model_driven.lifecycle.transitions import TransitionEngine
    from model_driven.mof.m3_extended import LifecycleStage

    mgr = LifecycleManager()
    engine = TransitionEngine()
    action = getattr(args, "md_action", "status")
    entity_id = getattr(args, "md_entity", "cockpit")

    if action == "create":
        mgr.create_tracker(entity_id, getattr(args, "md_type", ""))
        console.print(f"[green]✅ 已创建: {entity_id}[/]")
    elif action == "advance":
        target = LifecycleStage.from_str(getattr(args, "md_stage", "planning"))
        tracker = mgr.get_tracker(entity_id) or mgr.create_tracker(entity_id)
        success, msg, _ = engine.try_transition(tracker, target)
        console.print(f"[{'green' if success else 'red'}]{'✅' if success else '❌'} {msg}[/]")
    elif action == "dashboard":
        dashboard = mgr.generate_dashboard()
        console.print(f"[bold cyan]仪表板[/] 实体:{dashboard.total_entities} 进度:{dashboard.avg_progress}%")
        for b in dashboard.blockers[:5]:
            console.print(f"  [red]🔴 [{b['entity_id']}] {b['stage']}: {b['issue']}[/]")
    else:
        summary = mgr.get_stage_summary(entity_id)
        if summary:
            console.print(f"[bold]{entity_id}[/] 阶段:{summary['current_stage']} 进度:{summary['progress_pct']}%")
        else:
            console.print(f"[yellow]⚠️ 未找到: {entity_id}[/]")
    return 0


def _md_spec(args: Namespace, console) -> int:
    from model_driven.management.spec import SpecManager
    mgr = SpecManager()
    action = getattr(args, "md_action", "list")
    if action == "create":
        sid = getattr(args, "md_id", f"SPEC-{len(mgr.list_all())+1}")
        spec = mgr.create(sid, getattr(args, "md_title", "未命名"))
        console.print(f"[green]✅ Spec: {spec.id} - {spec.title}[/]")
    else:
        specs = mgr.list_all()
        for s in specs:
            console.print(f"  [{s.status.value}] {s.id}: {s.title}")
        if not specs:
            console.print("[dim]无 Spec[/]")
    return 0


def _md_okr(args: Namespace, console) -> int:
    from model_driven.management.okr import OKRManager
    mgr = OKRManager()
    action = getattr(args, "md_action", "list")
    if action == "create":
        oid = getattr(args, "md_id", f"OKR-{len(mgr.list_all())+1}")
        okr = mgr.create(oid, getattr(args, "md_objective", "未定义"))
        console.print(f"[green]✅ OKR: {okr.id} - {okr.objective}[/]")
    else:
        okrs = mgr.list_all()
        for o in okrs:
            console.print(f"  [{o.status.value}] {o.id}: {o.objective} ({o.progress:.0%})")
        if not okrs:
            console.print("[dim]无 OKR[/]")
    return 0


def _md_derive(args: Namespace, console) -> int:
    from model_driven.toolchain.derivation_engine import DerivationEngine
    import yaml
    from pathlib import Path

    m1_dir = Path.home() / "Workspace/projects/ecos/src/ecos/ssot/mof/m1"
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

    engine = DerivationEngine()
    engine.execute_all(nodes, {"expected_progress": 0.5})
    s = engine.get_summary()
    console.print(f"[bold cyan]📊 推导报告[/] 规则:{s['total_rules']} 触发:{s['triggered']} 风险:{s['by_risk_level']}")
    if s["high_risks"]:
        for r in s["high_risks"][:5]:
            console.print(f"  [red]🔴 {r.rule_id}: {r.message[:80]}[/]")
    return 0


def _md_pipeline(args: Namespace, console) -> int:
    from model_driven.lifecycle.pipeline import PipelineTracker, PipelinePhase

    entity_id = getattr(args, "md_entity", "ecos")
    action = getattr(args, "md_action", "status")
    tracker = PipelineTracker.load(entity_id) or PipelineTracker(entity_id=entity_id)

    if action == "start":
        phase = PipelinePhase(getattr(args, "md_phase", "cold_start"))
        if tracker.start_phase(phase):
            tracker.save()
            console.print(f"[green]✅ 启动: {phase.value}[/]")
        else:
            console.print(f"[red]❌ 前置 Phase 未完成[/]")
    elif action == "complete":
        phase = PipelinePhase(getattr(args, "md_phase", "cold_start"))
        if tracker.complete_phase(phase):
            tracker.save()
            console.print(f"[green]✅ 完成: {phase.value}[/]")
        else:
            console.print(f"[red]❌ 阶段未全部完成[/]")
    else:
        p = tracker.get_progress()
        console.print(f"[bold cyan]📊 流水线: {entity_id}[/] Phase:{p['current_phase']}")
        for pn, pi in p["phases"].items():
            icon = "✅" if pi["status"] == "completed" else ("🔄" if pi["status"] == "in_progress" else "⏳")
            console.print(f"  {icon} {pn}: {pi['progress_pct']}%")
    return 0


def cmd_model_driven_derive(args: Namespace) -> int:
    """model-driven derive 子命令 — 运行推导规则引擎。"""
    console = _get_console()
    try:
        from model_driven.toolchain.derivation_engine import DerivationEngine
        import yaml
        from pathlib import Path

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

        engine = DerivationEngine()
        engine.execute_all(nodes, {"expected_progress": 0.5})
        summary = engine.get_summary()

        console.print(f"[bold cyan]📊 推导规则执行报告[/]")
        console.print(f"总规则: {summary['total_rules']} | 触发: {summary['triggered']} | 未触发: {summary['not_triggered']}")
        console.print(f"风险分布: {summary['by_risk_level']}")
        if summary["high_risks"]:
            console.print(f"\n[bold red]🔴 高风险 ({len(summary['high_risks'])}):[/]")
            for r in summary["high_risks"][:5]:
                console.print(f"  [{r.risk_level}] {r.rule_id}: {r.message[:80]}")

        return 0
    except ImportError:
        _get_err().print("[red]❌ model-driven 不可用[/]")
        return 1


def cmd_model_driven_pipeline(args: Namespace) -> int:
    """model-driven pipeline 子命令 — 三阶段宏观流水线。"""
    console = _get_console()
    try:
        from model_driven.lifecycle.pipeline import PipelineTracker, PipelinePhase

        entity_id = getattr(args, "md_entity", "ecos")
        subcmd = getattr(args, "md_subcmd", "status")
        tracker = PipelineTracker(entity_id=entity_id)

        if subcmd == "start":
            phase = PipelinePhase(getattr(args, "md_phase", "cold_start"))
            if tracker.start_phase(phase):
                console.print(f"[green]✅ 已启动 Phase: {phase.value}[/]")
            else:
                console.print(f"[red]❌ 无法启动 Phase: {phase.value} (前置 Phase 未完成)[/]")
        elif subcmd == "complete":
            phase = PipelinePhase(getattr(args, "md_phase", "cold_start"))
            if tracker.complete_phase(phase):
                console.print(f"[green]✅ 已完成 Phase: {phase.value}[/]")
            else:
                console.print(f"[red]❌ 无法完成 Phase (Phase 内阶段未全部完成)[/]")
        else:
            progress = tracker.get_progress()
            console.print(f"[bold cyan]📊 三阶段流水线: {entity_id}[/]")
            console.print(f"当前 Phase: {progress['current_phase']}")
            for pn, pi in progress["phases"].items():
                icon = "✅" if pi["status"] == "completed" else ("🔄" if pi["status"] == "in_progress" else "⏳")
                console.print(f"  {icon} {pn}: {pi['progress_pct']}% ({pi['stages_completed']}/{pi['stages_total']})")

        return 0
    except ImportError:
        _get_err().print("[red]❌ model-driven 不可用[/]")
        return 1
