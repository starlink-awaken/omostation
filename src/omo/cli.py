#!/usr/bin/env python3
from __future__ import annotations

import sys
import warnings


def main(argv: list[str] | None = None) -> int:
    warnings.warn(
        "omo CLI 为内部程序接口。人类用户请使用 cockpit。",
        DeprecationWarning,
        stacklevel=2,
    )
    args = list(argv if argv is not None else sys.argv[1:])
    # P48-W2: serve 子命令 (stdin/stdout JSON-RPC, 供 agora subprocess spawn)
    if args and args[0] == "serve":
        from omo.omo_sync_serve import serve as omo_serve

        return omo_serve()
    if args and args[0] in {"capability", "registry", "scenario", "pkg"}:
        from omo.omo_capability import main as capability_main

        return capability_main(args)
    if args and args[0] == "baseline":
        from omo.omo_baseline_write import main as baseline_main

        return baseline_main(args[1:])
    if args and args[0] == "metacognition":
        from omo.omo_metacognition import main as metacognition_main

        return metacognition_main(args[1:])
    if args and args[0] == "phase14":
        from omo.omo_phase14 import main as phase14_main

        return phase14_main(args[1:])
    if args and args[0] == "phase15":
        from omo.omo_phase15 import main as phase15_main

        return phase15_main(args[1:])
    if args and args[0] == "phase16":
        from omo.omo_phase16 import main as phase16_main

        return phase16_main(args[1:])

    if args and args[0] == "ledger":
        from omo.omo_ledger import main as ledger_main

        return ledger_main(args[1:])
    if args and args[0] == "bridge":
        print("⚠️ DEPRECATED: 'omo bridge' 已迁移，建议改用 'workspace compass bet'。")
        from omo.omo_bridge import main as bridge_main

        return bridge_main(args[1:])
    if args and args[0] == "cards":
        from omo.omo_cards import main as cards_main

        return cards_main(args[1:])
    if args and args[0] == "gc":
        from omo.omo_gc import main as gc_main

        return gc_main(args[1:])

    if args and args[0] == "goal":
        from omo.omo_goal import main as goal_main

        return goal_main(args[1:])
    if args and args[0] == "knowledge":
        from omo.omo_knowledge import main as knowledge_main

        return knowledge_main(args[1:])
    if args and args[0] == "delivery":
        from omo.omo_delivery import main as delivery_main

        return delivery_main(args[1:])
    if args and args[0] == "standard":
        from omo.omo_standard import main as standard_main

        return standard_main(args[1:])
    if args and args[0] == "state":
        from omo.omo_state import main as state_main

        return state_main(args[1:])
    if args and args[0] == "debt":
        from omo.omo_debt_cli import main as debt_main

        return debt_main(args[1:])
    if args and args[0] == "i0":
        from omo.omo_i0 import main as i0_main

        return i0_main(args[1:])

    if args and args[0] == "observability":
        from omo.omo_observability import main as obs_main

        return obs_main(args[1:])
    if args and args[0] in ("log", "metric"):
        from omo.omo_observability import main as obs_main

        return obs_main(args)

    if args and args[0] == "event":
        from omo.omo_event import main as event_main

        return event_main(args[1:])

    if args and args[0] == "alert":
        from omo.omo_alert import main as alert_main

        return alert_main(args[1:])

    if args and args[0] == "dashboard":
        from omo.omo_dashboard import main as dash_main

        return dash_main(args[1:])

    if args and args[0] == "task":
        from omo.omo_task import main as task_main

        rc = task_main(args[1:])
        # ISC-10: task 状态变更后刷新 debt dashboard (治本: 看板不再依赖手动 `omo debt refresh`).
        # 根因: refresh_outputs 原本只在 `omo debt refresh` 触发, task create/close/promote/archive
        # 改状态不刷看板 → debt-dashboard generated_at 停更. 本 post-hook 让状态变更自动触发刷新.
        if rc == 0:
            _refresh_dashboard_safely("task")
        return rc

    if args and args[0] == "evidence":
        from omo.omo_evidence import main as ev_main

        return ev_main(args[1:])

    if args and args[0] == "cost":
        from omo.omo_cost import main as cost_main

        return cost_main(args[1:])

    if args and args[0] == "governance":
        from omo.omo_audit import governance_history_main, governance_main
        from omo.omo_governance import main as governance_ops_main

        sub = args[1] if len(args) > 1 else "audit"
        # 修 P36 bug: 之前 None 触发 governance_main 用 sys.argv[1:] 重解析, 导致
        # "omo governance audit" 无 --output 时报 "unrecognized arguments: governance audit"
        rest = args[2:] if len(args) > 2 else []
        if sub == "history":
            return governance_history_main(rest)
        if sub in {
            "propose",
            "approve",
            "apply",
            "list",
            "surfaces",
            "ingress-goal",
            "ingress-task",
            "ingress-debt",
        }:
            return governance_ops_main(args[1:])
        if sub in ("audit", "--help", "-h", None):
            return governance_main(rest)
        # unknown sub: treat as audit args
        return governance_main(args[1:])

    if args and args[0] == "daemon":
        from omo.omo_daemon import main as daemon_main

        return daemon_main(args[1:])

    if args and args[0] == "sse-daemon":
        from omo.omo_sse_daemon import main as sse_daemon_main

        return sse_daemon_main()

    if args and args[0] == "bos":
        # BOS (Banyan Object Service) URI 注册/查询 — P33-W1 战役 2 起步
        from omo.omo_bos import main as bos_main

        return bos_main(args[1:])

    if args and args[0] == "health":
        from omo.omo_health import main as health_main

        return health_main(args[1:])

    if args and args[0] == "readiness":
        from omo.omo_readiness import main as readiness_main

        return readiness_main(args[1:])

    if args and args[0] == "external-resources":
        from omo.omo_external_resources import main as external_resources_main

        return external_resources_main(args[1:])

    if args and args[0] in ("x-axis", "xaxis"):
        from omo.omo_xplane import main as xplane_main

        return xplane_main(args[1:])

    if args and args[0] == "inspect":
        import argparse

        parser = argparse.ArgumentParser(prog="omo inspect", description="统一检查入口")
        parser.add_argument("--json", action="store_true", help="JSON 输出")
        parsed = parser.parse_args(args[1:])
        from omo.omo_inspect import cmd_inspect

        return cmd_inspect(json_output=parsed.json)

    if args and args[0] == "healing":
        return _cmd_healing(args[1:])

    if args and args[0] == "predict":
        return _cmd_predict(args[1:])

    if args and args[0] == "cache":
        return _cmd_cache(args[1:])

    if args and args[0] == "logs":
        # Round 10 P0: 统一管理 .omo/_knowledge/*.jsonl (list/inspect/tail/audit)
        from omo.omo_logs import main as logs_main

        return logs_main(args[1:])

    if args and args[0] == "lint":
        # Round 15 P0 (P1-2 from pattern §11.6): 静态校验 7 consumer 写时走 Pydantic schema
        from omo.omo_lint import main as lint_main

        return lint_main(args[1:])

    if args and args[0] == "acl":
        # Scheme C 5c L2 (ADR-0189): path ACL plan/apply (opt-in OMO_OS_ACL=1)
        from omo.omo_acl import main as acl_main

        return acl_main(args[1:])

    if args and args[0] == "lint-metrics":
        # Round 42 P0: omo lint schemas + §17 metrics (单命令跑两者, CI 友好)
        from omo.omo_lint import cmd_lint_schemas

        return cmd_lint_schemas(metrics=True)

    if args and args[0] == "trail":
        # Round 12 P0: omo_trail 第 7 consumer CLI (record/show)
        # Round 19 P0: 加 seed 子命令, 让 trail 业务真落地
        from omo.omo_trail import main as trail_main

        return trail_main(args[1:])

    if args and args[0] == "audit-rollout":
        # Round 27 P0: 跨仓 baseline 聚合 (§12.5.1 步骤 1)
        from omo.omo_audit_rollout import main as rollout_main

        return rollout_main(args[1:])

    # OPC-P3 D1 wiring: omo_worker module 暴露 worker/task 全套子命令
    # (validate / promote-apply / promote-eval / promote-readiness / ...),
    # 原 cli.py 没有 dispatch 此入口
    if args and args[0] in {"worker", "wt"}:
        from omo.omo_worker import main as worker_main

        # The facade parser still owns the worker/task namespace. Preserve the
        # public `omo worker <command>` shape while routing through that parser.
        return worker_main(["worker", *args[1:]])

    if args and args[0] == "workspace":
        # ISC-46: workspace status 作为 worktree dirty 计数唯一 SSOT (治本 E3)
        from omo.omo_workspace import main as workspace_main

        return workspace_main(args[1:])

    if args and args[0] == "strategy":
        print(
            "⚠️ DEPRECATED: 'omo strategy' 已迁移，建议改用 'workspace compass radar' 或 'workspace compass gc'。"
        )
        from omo.omo_strategy import main as strategy_main

        return strategy_main(args[1:])

    if args and args[0] == "manage":
        from omo.omo_manage import main as manage_main

        return manage_main(args[1:])

    if args and args[0] == "validate":
        from omo.omo_validate import main as validate_main

        return validate_main(args[1:])

    if args and args[0] == "audit":
        return _cmd_audit(args[1:])

    if args and args[0] == "doctor":
        import argparse

        parser = argparse.ArgumentParser(
            prog="omo doctor", description="统一健康检查入口"
        )
        parser.add_argument("--json", action="store_true", help="JSON 输出")
        parsed = parser.parse_args(args[1:])
        from omo.omo_doctor import cmd_doctor

        return cmd_doctor(json_output=parsed.json)

    if args and args[0] == "inspect":
        import argparse

        parser = argparse.ArgumentParser(prog="omo inspect", description="统一检查入口")
        parser.add_argument("--json", action="store_true", help="JSON 输出")
        parsed = parser.parse_args(args[1:])
        from omo.omo_inspect import cmd_inspect

        return cmd_inspect(json_output=parsed.json)

    if args and args[0] == "docs":
        import argparse

        parser = argparse.ArgumentParser(
            prog="omo docs", description="CLI 文档自动生成"
        )
        parser.add_argument("--output", "-o", type=str, help="输出文件路径")
        parsed = parser.parse_args(args[1:])
        from omo.omo_docs import cmd_docs

        return cmd_docs(output=parsed.output)

    if args and args[0] == "report":
        import argparse

        parser = argparse.ArgumentParser(prog="omo report", description="综合报告生成")
        parser.add_argument("--output", "-o", type=str, help="输出文件路径")
        parser.add_argument("--json", action="store_true", help="JSON 输出")
        parsed = parser.parse_args(args[1:])
        from omo.omo_report import cmd_report

        return cmd_report(output=parsed.output, json_output=parsed.json)

    if args and args[0] == "watch":
        import argparse

        parser = argparse.ArgumentParser(prog="omo watch", description="实时监控模式")
        parser.add_argument(
            "--interval", "-i", type=int, default=60, help="检查间隔 (秒)"
        )
        parser.add_argument(
            "--count", "-n", type=int, default=None, help="最大检查次数"
        )
        parsed = parser.parse_args(args[1:])
        from omo.omo_watch import cmd_watch

        return cmd_watch(interval=parsed.interval, max_iterations=parsed.count)

    # 兜底:有参但无匹配子命令 → 报错退出;无参 → 静默退出 0(保持原行为)
    if args:
        print(f"Unknown subcommand: {args[0]}", file=sys.stderr)
        return 1
    return 0


def _refresh_dashboard_safely(trigger: str = "") -> None:
    """ISC-10: 状态变更命令后安全刷新 debt dashboard.

    refresh_outputs 失败不阻塞主命令 (dashboard 是衍生视图, best-effort 容错).
    由 cli 分发层 post-hook 调用 (task / healing 等状态变更入口).
    """
    try:
        import os
        from datetime import UTC, datetime
        from pathlib import Path

        from omo.omo_debt import refresh_outputs

        ws = Path(os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace")))
        omo_dir = ws / ".omo"
        if not omo_dir.is_dir():
            return
        now = (
            datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
        refresh_outputs(omo_dir, now)
    except Exception as e:
        print(f"⚠️  [dashboard refresh skipped via {trigger}]: {e}", file=sys.stderr)


def _cmd_audit(args: list[str]) -> int:
    """omo audit <subcommand> — X 审计工具集.

    Subcommands:
        cards      — CARDS X3 value metrics (SQLite 聚合)
        vault      — Vault X1 audit (Markdown content hash + author tracking)
        freshness  — X2 freshness audit (3 条 P43 巡检规则)
    """
    if not args or args[0] in ("-h", "--help"):
        print("omo audit — X 审计工具集\n")
        print("Usage: omo audit <subcommand> [options]\n")
        print("Subcommands:")
        print("  cards      CARDS X3 value metrics (SQLite 聚合)")
        print("  vault      Vault X1 audit (Markdown content hash + author tracking)")
        print("  freshness  X2 freshness audit (3 条 P43 巡检规则)")
        print("\nUse 'omo audit <subcommand> --help' for subcommand help.")
        return 0

    sub = args[0]
    rest = args[1:]

    if sub == "cards":
        import argparse

        parser = argparse.ArgumentParser(
            prog="omo audit cards",
            description="CARDS X3 value metrics — 从 SQLite 聚合 card 指标",
        )
        parser.add_argument("--db", type=str, help="显式指定 db 路径")
        parser.add_argument("--json", action="store_true", help="JSON 输出")
        parser.add_argument("--output", type=str, help="写入文件 (相对于 workspace)")
        parsed = parser.parse_args(rest)
        from omo.omo_audit_cards import cmd_cards

        return cmd_cards(
            db_path=parsed.db, json_output=parsed.json, output=parsed.output
        )

    if sub == "vault":
        import argparse

        parser = argparse.ArgumentParser(
            prog="omo audit vault",
            description="Vault X1 audit — Markdown content hash + author tracking",
        )
        parser.add_argument("--days", type=int, default=90, help="staleness 阈值 (天)")
        parser.add_argument("--root", type=str, help="扫描根目录 (默认 workspace root)")
        parser.add_argument("--json", action="store_true", help="JSON 输出")
        parser.add_argument("--output", type=str, help="写入文件 (相对于 workspace)")
        parsed = parser.parse_args(rest)
        from omo.omo_audit_vault import cmd_vault

        return cmd_vault(
            days=parsed.days,
            root=parsed.root,
            json_output=parsed.json,
            output=parsed.output,
        )

    if sub == "freshness":
        import argparse

        parser = argparse.ArgumentParser(
            prog="omo audit freshness",
            description="X2 freshness audit — 执行 3 条 P43 巡检规则",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="仅输出，不写审计日志"
        )
        parser.add_argument("--only", type=str, help="仅运行指定规则")
        parser.add_argument("--json", action="store_true", help="JSON 输出")
        parsed = parser.parse_args(rest)
        from omo.omo_audit_freshness import cmd_freshness

        return cmd_freshness(
            dry_run=parsed.dry_run, only=parsed.only, json_output=parsed.json
        )

    print(f"Unknown audit subcommand: {sub}")
    return 1


def _cmd_healing(args: list[str]) -> int:
    """omo healing <subcommand> — 自愈引擎管理 CLI。

    Subcommands:
        status      — 显示引擎当前状态
        fix-run <n> — 手动执行修复脚本
        fix-list    — 列出所有可用修复脚本
        rules       — 列出所有规则
        config      — 导出当前规则到 YAML
        history     — 显示触发和修复历史
    """
    if not args:
        print("Usage: omo healing <status|fix-run|fix-list|rules|config|history>")
        return 1

    sub = args[0]

    if sub == "status":
        import json

        from omo.omo_self_healing import get_healing_engine

        engine = get_healing_engine()
        status = engine.get_status()
        print(json.dumps(status, indent=2, default=str, ensure_ascii=False))

    elif sub == "fix-run":
        if len(args) < 2:
            print("Usage: omo healing fix-run <name>")
            return 1
        from omo.omo_self_healing import run_fix

        result = run_fix(args[1])
        status_icon = "✅" if result["success"] else "❌"
        print(f"{status_icon} {result['fix_name']}: {result['output']}")
        return 0 if result["success"] else 1

    elif sub == "fix-list":
        from omo.omo_self_healing import list_fixes

        for fix in list_fixes():
            print(f"  - {fix}")

    elif sub == "rules":
        from omo.omo_self_healing import get_healing_engine

        engine = get_healing_engine()
        for r in engine._rules:
            fixes = f" fixes={r.fix_names}" if r.fix_names else ""
            print(f"  {r.name}: threshold={r.threshold} {r.severity}{fixes}")

    elif sub == "config":
        from omo.omo_self_healing import get_healing_engine, save_rules

        engine = get_healing_engine()
        save_rules(engine._rules)
        print("Rules saved to .omo/self_healing_rules.yaml")

    elif sub == "history":
        import json

        from omo.omo_self_healing import get_history

        data = get_history()
        print(json.dumps(data, indent=2, default=str, ensure_ascii=False))

    else:
        print(f"Unknown subcommand: {sub}")
        return 1

    return 0


def _cmd_predict(args: list[str]) -> int:
    """预测性治理 - 事前预警"""
    import argparse

    parser = argparse.ArgumentParser(
        prog="omo predict", description="预测性治理 - 事前预警"
    )
    subparsers = parser.add_subparsers(dest="predict_sub", required=True)

    parser_risks = subparsers.add_parser("risks", help="预测未来治理风险")
    parser_risks.add_argument(
        "--days", type=int, default=7, help="预测未来天数 (默认: 7)"
    )
    parser_risks.add_argument("--json", action="store_true", help="JSON 输出")

    parser_debt = subparsers.add_parser("debt", help="预测债务恶化风险")
    parser_debt.add_argument(
        "--days", type=int, default=30, help="预测未来天数 (默认: 30)"
    )
    parser_debt.add_argument("--json", action="store_true", help="JSON 输出")

    subparsers.add_parser("actions", help="推荐预防性治理动作")

    subparsers.add_parser("alerts", help="生成早期预警")

    parsed = parser.parse_args(args)

    from pathlib import Path

    from omo.predictive_governance import PredictiveGovernanceEngine

    omo_dir = Path.cwd() / ".omo"  # S4: bridge_utils死模块移除inline非补实现
    engine = PredictiveGovernanceEngine(omo_dir)

    if parsed.predict_sub == "risks":
        forecast = engine.forecast_governance_risks(parsed.days)
        if parsed.json:
            import json

            data = {
                "time_horizon_days": forecast.time_horizon_days,
                "overall_risk_level": forecast.overall_risk_level,
                "high_risks_count": len(forecast.high_risks),
                "medium_risks_count": len(forecast.medium_risks),
                "low_risks_count": len(forecast.low_risks),
                "key_trends": forecast.key_trends,
            }
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"📊 [Predictive Governance] 风险预测 (未来 {parsed.days} 天):")
            print(f"  整体风险级别: {forecast.overall_risk_level.upper()}")
            print(f"  高风险: {len(forecast.high_risks)} 项")
            print(f"  中风险: {len(forecast.medium_risks)} 项")
            print(f"  低风险: {len(forecast.low_risks)} 项")
            if forecast.key_trends:
                print("  关键趋势:")
                for trend in forecast.key_trends:
                    print(f"    • {trend}")

    elif parsed.predict_sub == "debt":
        risks = engine.predict_debt_deterioration(parsed.days)
        if parsed.json:
            import json

            data = [
                {
                    "debt_id": r.debt_id,
                    "risk_score": r.risk_score,
                    "predicted_deterioration_days": r.predicted_deterioration_days,
                    "recommended_action": r.recommended_action,
                    "contributing_factors": r.contributing_factors,
                }
                for r in risks
            ]
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"📊 [Predictive Governance] 债务恶化预测 (未来 {parsed.days} 天):")
            if not risks:
                print("  ✓ 未检测到高风险债务")
            else:
                for risk in risks:
                    icon = "🔴" if risk.risk_score > 0.8 else "🟡"
                    print(
                        f"  {icon} {risk.debt_id}: 风险分数 {risk.risk_score:.0%}, "
                        f"预计恶化: {risk.predicted_deterioration_days} 天, "
                        f"建议: {risk.recommended_action}"
                    )

    elif parsed.predict_sub == "actions":
        actions = engine.recommend_proactive_actions()
        print("💡 [Predictive Governance] 推荐预防性治理动作:")
        if not actions:
            print("  (无推荐动作)")
        else:
            for action in actions:
                print(f"  优先级 {action.priority}: {action.action}")
                print(f"    理由: {action.rationale}")
                print(
                    f"    工作量: {action.effort_estimate}, 影响: {action.estimated_impact}"
                )

    elif parsed.predict_sub == "alerts":
        alerts = engine.generate_early_warning_alerts()
        print("⚠️ [Predictive Governance] 早期预警:")
        if not alerts:
            print("  (无预警)")
        else:
            for alert in alerts:
                icon = "🔴" if alert.get("severity") == "critical" else "🟡"
                print(f"  {icon} {alert.get('message')}")

    return 0


def _cmd_cache(args: list[str]) -> int:
    """状态缓存管理"""
    import argparse

    parser = argparse.ArgumentParser(prog="omo cache", description="状态缓存管理")
    subparsers = parser.add_subparsers(dest="cache_sub", required=True)

    subparsers.add_parser("stats", help="显示缓存统计")
    subparsers.add_parser("clear", help="清空所有缓存")
    parser_invalidate = subparsers.add_parser("invalidate", help="失效特定缓存")
    parser_invalidate.add_argument("pattern", type=str, help="缓存键匹配模式")

    parsed = parser.parse_args(args)

    from pathlib import Path

    from omo.state_cache import GovernanceStateCache

    omo_dir = Path.cwd() / ".omo"  # S4: bridge_utils死模块移除inline非补实现
    cache = GovernanceStateCache(omo_dir / "_cache")

    if parsed.cache_sub == "stats":
        stats = cache.get_cache_stats()
        print("📊 [State Cache] 缓存统计:")
        print(f"  总条目数: {stats['total_entries']}")
        print(f"  有效条目: {stats['valid_entries']}")
        print(f"  无效条目: {stats['invalid_entries']}")

    elif parsed.cache_sub == "clear":
        cache.invalidate_all()
        print("✅ [State Cache] 已清空所有缓存")

    elif parsed.cache_sub == "invalidate":
        cache.invalidate_on_change(parsed.pattern)
        print(f"✅ [State Cache] 已失效匹配 '{parsed.pattern}' 的缓存")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
