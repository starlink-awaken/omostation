"""cockpit.commands.l4bridge — L4 bridge CLI commands (context, cards, vault)."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from cockpit.adapters import governance_context

from .base import _get_console, _get_err, _panel


def cmd_context(_args: Namespace) -> int:
    """显示 workspace 完整上下文 (Phase / CARDS / 约束 / 引导)。"""
    console = _get_console()

    try:
        ctx = governance_context.workspace_context()
    except Exception as e:  # defensive fallback
        _get_err().print(f"[red]❌ workspace_context 调用失败: {e}[/]")
        return 1

    # Phase
    console.print(
        _panel(
            f"[bold cyan]🛸 Workspace Context[/bold cyan]\n"
            f"Phase [bold]{ctx.get('phase') or '?'}[/bold] · {ctx.get('theme') or ''}\n"
            f"状态: [bold]{ctx.get('status', 'unavailable')}[/]",
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

    domain_summary = ctx.get("domain_summary", {})
    console.print(
        f"\n[bold cyan]🌐 Documents 域:[/] {domain_summary.get('existing', 0)}/{domain_summary.get('total', 0)}"
    )

    console.print()
    return 0 if ctx.get("status") == "ok" else 1


def cmd_domains(_args: Namespace) -> int:
    """列出 L4 所有域及其状态。"""
    console = _get_console()

    try:
        result = governance_context.domains_list()
    except Exception as e:  # defensive fallback
        _get_err().print(f"[red]❌ domains_list 失败: {e}[/]")
        return 1

    if not result["available"]:
        _get_err().print(f"[red]❌ domains_list 不可用: {result.get('error', 'unknown error')}[/]")
        return 1
    console.print(f"\n[bold cyan]🌐 Documents 域状态 ({result['total']} 域)[/]\n")
    for d in result.get("domains", []):
        icon = "[green]✓[/]" if d["exists"] else "[red]✗[/]"
        console.print(f"  {icon} [bold]{d['name']}[/] [dim]{d['path']}[/]")

    return 0 if result["status"] == "ok" else 1


def cmd_domain_status(args: Namespace) -> int:
    """显示 Documents 域项目的只读 binding 和引导文件状态。"""

    console = _get_console()
    domain_id = getattr(args, "domain_id", "") or ""
    try:
        result = governance_context.domain_project_status(domain_id)
    except Exception as exc:  # defensive boundary: never report an unknown error as success
        result = {"status": "unavailable", "error": str(exc), "domains": [], "summary": {}}

    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False, default=str))
    else:
        summary = result.get("summary", {})
        console.print(
            f"[bold cyan]Documents 域项目状态[/] {result.get('status', 'unavailable')} "
            f"· ok={summary.get('ok', 0)} degraded={summary.get('degraded', 0)}"
        )
        for domain in result.get("domains", []):
            console.print(f"  [bold]{domain.get('id', '?')}[/] · {domain.get('status', 'unavailable')}")
            for gateway in domain.get("gateways", []):
                console.print(f"    {gateway.get('client', '?')}: {gateway.get('status', 'unknown')}")
            facts = domain.get("facts", {})
            console.print(f"    facts: {facts.get('status', 'unknown')}")
        if result.get("error"):
            _get_err().print(f"[red]❌ {result['error']}[/]")

    return {"ok": 0, "degraded": 1, "unavailable": 2}.get(result.get("status"), 2)


def cmd_facts_audit(args: Namespace) -> int:
    """审计 Documents 域声明的 facts 文件。"""

    console = _get_console()
    domain_id = getattr(args, "domain_id", "") or ""
    try:
        result = governance_context.domain_facts_audit(domain_id)
    except Exception as exc:  # defensive boundary: preserve the contract exit code
        result = {"status": "unavailable", "error": str(exc), "domains": [], "summary": {}}

    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False, default=str))
    else:
        summary = result.get("summary", {})
        summary_text = " ".join(
            f"{name}={summary.get(name, 0)}" for name in ("present", "missing", "unreadable", "invalid")
        )
        console.print(f"[bold cyan]Documents facts 审计[/] {result.get('status', 'unavailable')} · {summary_text}")
        for domain in result.get("domains", []):
            facts = domain.get("facts", {})
            modified_on = facts.get("modified_on")
            date = f" · {modified_on}" if modified_on else ""
            console.print(
                f"  [bold]{domain.get('id', '?')}[/] · {domain.get('name', '?')} · "
                f"facts: {facts.get('status', 'unknown')}{date}"
            )
        if result.get("error"):
            _get_err().print(f"[red]❌ {result['error']}[/]")

    return {"ok": 0, "violations": 1, "unavailable": 2}.get(result.get("status"), 2)


def cmd_facts_validation(args: Namespace) -> int:
    """Read the bounded Runtime facts validation receipt for one domain."""

    console = _get_console()
    domain_id = getattr(args, "domain_id", "") or ""
    try:
        result = governance_context.domain_facts_validation_status(domain_id)
    except Exception as exc:  # defensive boundary: preserve the contract exit code
        result = {"status": "unavailable", "error": str(exc), "validation": None}

    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False, default=str))
    else:
        validation = result.get("validation") or {}
        console.print(
            "[bold cyan]Documents Facts Runtime 校验[/] "
            f"{result.get('status', 'unavailable')} · facts_total={validation.get('facts_total', 0)} "
            f"· errors={validation.get('error_count', 0)} · warnings={validation.get('warning_count', 0)}"
        )
        if result.get("error"):
            _get_err().print(f"[red]❌ {result['error']}[/]")

    return {"ok": 0, "violations": 1, "unavailable": 2}.get(result.get("status"), 2)


def cmd_controller_shadow(args: Namespace) -> int:
    """Read the incomplete legacy controller shadow receipt for one domain."""

    console = _get_console()
    domain_id = getattr(args, "domain_id", "") or ""
    try:
        result = governance_context.domain_controller_shadow_status(domain_id)
    except Exception as exc:  # defensive boundary: preserve the contract exit code
        result = {"status": "unavailable", "error": str(exc), "shadow": None}

    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False, default=str))
    else:
        shadow = result.get("shadow") or {}
        console.print(
            "[bold yellow]Documents 控制器影子迁移[/] "
            f"{result.get('status', 'unavailable')} · "
            f"observed_rules={len(shadow.get('observed_rule_ids', []))}/"
            f"{len(shadow.get('legacy_rule_ids', []))} · "
            f"unobserved_rules={len(shadow.get('unobserved_rule_ids', []))} · "
            f"cutover_ready={shadow.get('cutover_ready', False)}"
        )
        if result.get("error"):
            _get_err().print(f"[red]❌ {result['error']}[/]")

    return {"shadow_observed": 1, "unavailable": 2}.get(result.get("status"), 2)


def cmd_skill(args: Namespace) -> int:
    """运行 L4 定时技能 (由 cron_service 触发)。"""
    console = _get_console()

    skill_name = getattr(args, "skill_name", "") or ""
    if not skill_name:
        _get_err().print("[yellow]用法: cockpit cockpit skill run <skill_name>[/]")
        return 1

    console.print(f"[cyan]⏳ 执行技能: {skill_name}...[/]")

    skill_file = (
        Path(__file__).resolve().parents[5]
        / "projects"
        / "ecos"
        / "src"
        / "ecos"
        / "ssot"
        / "mof"
        / "m1"
        / "skill"
        / f"SKILL-SCHEDULED-{skill_name}.yaml"
    )

    if not skill_file.exists():
        _get_err().print(f"[red]❌ 技能未找到: SKILL-SCHEDULED-{skill_name}.yaml[/]")
        return 1

    try:
        import yaml

        skill_def = yaml.safe_load(skill_file.read_text(encoding="utf-8"))
        desc = skill_def.get("description", skill_def.get("name", skill_name))
        console.print(f"  [dim]描述: {desc}[/]")
        console.print("  [green]✓ 技能已调度 (由 cron_service 执行)[/]")
        return 0
    except Exception as e:  # defensive fallback
        _get_err().print(f"[red]❌ 技能执行失败: {e}[/]")
        return 1


def cmd_cards(args: Namespace) -> int:
    """显示 CARDS 状态。"""
    console = _get_console()

    if getattr(args, "check", False):
        card_id = getattr(args, "card_id", "") or ""
        try:
            result = governance_context.cards_check(card_id=card_id)
        except Exception as e:  # defensive fallback
            _get_err().print(f"[red]❌ cards_check 失败: {e}[/]")
            return 1

        if result["compliant"]:
            console.print("[bold green]✅ 合规[/]")
        else:
            console.print("[bold red]❌ 违规:[/]")
            for v in result.get("violations", []):
                console.print(f"  [red]▪[/] {v}")
        console.print(f"\n[dim]OMO exit={result['returncode']} · scope={result['scope']}[/]")
        return int(result["returncode"])

    try:
        result = governance_context.cards_status()
    except Exception as e:  # defensive fallback
        _get_err().print(f"[red]❌ cards_status 失败: {e}[/]")
        return 1

    if not result["available"]:
        _get_err().print(f"[red]❌ cards_status 不可用: {result.get('error', 'unknown error')}[/]")
        return 1
    items = result["items"]
    # 产品走查 v5 #V5-14: 同 title 重复卡去重合并
    seen: dict[str, dict] = {}
    for card in items:
        key = str(card.get("title", "")).strip()
        if key in seen:
            seen[key]["count"] += 1
        else:
            entry = dict(card)
            entry["count"] = 1
            seen[key] = entry
    console.print(_panel(f"[bold cyan]🃏 CARDS ({len(items)} active, {len(seen)} 去重后)[/]", "cyan"))

    for card in seen.values():
        color = {"P0": "red", "P1": "yellow", "P2": "blue", "P3": "dim"}.get(card["priority"], "dim")
        status_color = "green" if card["status"] != "closed" else "dim"
        dup = f" [yellow](×{card['count']})[/]" if card["count"] > 1 else ""
        console.print(
            f"  [[{color}]{card['priority']}[/]] "
            f"[{status_color}]{card['title']}[/]{dup} "
            f"[dim]({card.get('type', '?')} · {card.get('domain', '?')})[/]"
        )

    console.print()
    return 0 if result["status"] == "ok" else 1


def cmd_vault(args: Namespace) -> int:
    """搜索 L4 Vault。"""
    keyword = getattr(args, "keyword", "") or ""
    if not keyword:
        _get_err().print("[yellow]用法: cockpit vault search <keyword>[/]")
        return 1

    _get_err().print("[yellow]⚠ vault search owner 尚未接入新治理适配器，请通过 Workspace/KOS 搜索[/]")
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
    from cockpit.adapters.model_driven import (
        LifecycleManager,  # pyright: ignore[reportAttributeAccessIssue]
        LifecycleStage,  # pyright: ignore[reportAttributeAccessIssue]
        TransitionEngine,  # pyright: ignore[reportAttributeAccessIssue]
    )

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
    from cockpit.adapters.model_driven import SpecManager  # pyright: ignore[reportAttributeAccessIssue]

    mgr = SpecManager()
    action = getattr(args, "md_action", "list")
    if action == "create":
        sid = getattr(args, "md_id", f"SPEC-{len(mgr.list_all()) + 1}")
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
    from cockpit.adapters.model_driven import OKRManager  # pyright: ignore[reportAttributeAccessIssue]

    mgr = OKRManager()
    action = getattr(args, "md_action", "list")
    if action == "create":
        oid = getattr(args, "md_id", f"OKR-{len(mgr.list_all()) + 1}")
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
    from cockpit.adapters.model_driven import (
        DerivationEngine,  # pyright: ignore[reportAttributeAccessIssue]
        load_m1_nodes,  # pyright: ignore[reportAttributeAccessIssue]
    )

    nodes = load_m1_nodes()
    engine = DerivationEngine()
    engine.execute_all(nodes, {"expected_progress": 0.5})
    s = engine.get_summary()
    console.print(f"[bold cyan]📊 推导报告[/] 规则:{s['total_rules']} 触发:{s['triggered']} 风险:{s['by_risk_level']}")
    if s["high_risks"]:
        for r in s["high_risks"][:5]:
            console.print(f"  [red]🔴 {r.rule_id}: {r.message[:80]}[/]")
    return 0


def _md_pipeline(args: Namespace, console) -> int:
    from cockpit.adapters.model_driven import (
        PipelinePhase,  # pyright: ignore[reportAttributeAccessIssue]
        PipelineTracker,  # pyright: ignore[reportAttributeAccessIssue]
    )

    entity_id = getattr(args, "md_entity", "ecos")
    action = getattr(args, "md_action", "status")
    tracker = PipelineTracker.load(entity_id) or PipelineTracker(entity_id=entity_id)

    if action == "start":
        phase = PipelinePhase(getattr(args, "md_phase", "cold_start"))
        if tracker.start_phase(phase):
            tracker.save()
            console.print(f"[green]✅ 启动: {phase.value}[/]")
        else:
            console.print("[red]❌ 前置 Phase 未完成[/]")
    elif action == "complete":
        phase = PipelinePhase(getattr(args, "md_phase", "cold_start"))
        if tracker.complete_phase(phase):
            tracker.save()
            console.print(f"[green]✅ 完成: {phase.value}[/]")
        else:
            console.print("[red]❌ 阶段未全部完成[/]")
    else:
        p = tracker.get_progress()
        console.print(f"[bold cyan]📊 流水线: {entity_id}[/] Phase:{p['current_phase']}")
        for pn, pi in p["phases"].items():
            icon = "✅" if pi["status"] == "completed" else ("🔄" if pi["status"] == "in_progress" else "⏳")
            console.print(f"  {icon} {pn}: {pi['progress_pct']}%")
    return 0


def cmd_model_driven_derive(args: Namespace) -> int:
    """[已废弃] 使用 cmd_model_driven(args, md_subcmd='derive') 替代"""
    return cmd_model_driven(args)


def cmd_model_driven_pipeline(args: Namespace) -> int:
    """[已废弃] 使用 cmd_model_driven(args, md_subcmd='pipeline') 替代"""
    return cmd_model_driven(args)
