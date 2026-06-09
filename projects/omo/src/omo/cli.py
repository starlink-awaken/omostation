#!/usr/bin/env python3
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    # P48-W2: serve 子命令 (stdin/stdout JSON-RPC, 供 agora subprocess spawn)
    if args and args[0] == "serve":
        from omo.omo_sync_serve import serve as omo_serve

        return omo_serve()
    if args and args[0] in {"capability", "registry", "scenario", "pkg"}:
        from omo.omo_capability import main as capability_main

        return capability_main(args)
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

        return task_main(args[1:])

    if args and args[0] == "evidence":
        from omo.omo_evidence import main as ev_main

        return ev_main(args[1:])

    if args and args[0] == "cost":
        from omo.omo_cost import main as cost_main

        return cost_main(args[1:])

    if args and args[0] == "governance":
        from omo.omo_audit import governance_main, governance_history_main

        sub = args[1] if len(args) > 1 else "audit"
        # 修 P36 bug: 之前 None 触发 governance_main 用 sys.argv[1:] 重解析, 导致
        # "omo governance audit" 无 --output 时报 "unrecognized arguments: governance audit"
        rest = args[2:] if len(args) > 2 else []
        if sub == "history":
            return governance_history_main(rest)
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

    if args and args[0] in ("x-axis", "xaxis"):
        from omo.omo_xplane import main as xplane_main

        return xplane_main(args[1:])

    if args and args[0] == "inspect":
        from omo.omo_inspect import main as inspect_main

        return inspect_main()

    if args and args[0] == "healing":
        return _cmd_healing(args[1:])

    if args and args[0] == "logs":
        # Round 10 P0: 统一管理 .omo/_knowledge/*.jsonl (list/inspect/tail/audit)
        from omo.omo_logs import main as logs_main

        return logs_main(args[1:])

    # 兜底:有参但无匹配子命令 → 报错退出;无参 → 静默退出 0(保持原行为)
    if args:
        print(f"Unknown subcommand: {args[0]}", file=sys.stderr)
        return 1
    return 0


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
        from omo.omo_self_healing import get_healing_engine
        import json
        engine = get_healing_engine()
        status = engine.get_status()
        print(json.dumps(status, indent=2, default=str, ensure_ascii=False))

    elif sub == "fix-run":
        if len(args) < 2:
            print("Usage: omo healing fix-run <name>")
            return 1
        from omo.omo_self_healing_fixes import run_fix
        result = run_fix(args[1])
        status_icon = "✅" if result["success"] else "❌"
        print(f"{status_icon} {result['fix_name']}: {result['output']}")
        return 0 if result["success"] else 1

    elif sub == "fix-list":
        from omo.omo_self_healing_fixes import list_fixes
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
        from omo.omo_self_healing import get_history
        import json
        data = get_history()
        print(json.dumps(data, indent=2, default=str, ensure_ascii=False))

    else:
        print(f"Unknown subcommand: {sub}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
