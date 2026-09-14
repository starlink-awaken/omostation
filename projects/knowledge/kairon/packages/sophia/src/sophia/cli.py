"""Sophia CLI — command-line interface for paradigm engine."""

from __future__ import annotations

import argparse
import json
import sys


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sophia", description="Sophia — Symbolic Research Paradigm Engine")
    sub = p.add_subparsers(dest="command")

    # compile
    c = sub.add_parser("compile", help="Compile a paradigm for a research question")
    c.add_argument("query", help="Research question")
    c.add_argument("--json", action="store_true", help="Output as JSON")

    # ops
    sub.add_parser("ops", help="List atomic operations")

    # states
    sub.add_parser("states", help="List research states")

    # transitions
    sub.add_parser("transitions", help="List base transition rules")

    # learn
    learn_parser = sub.add_parser("learn", help="Show learning insights")
    learn_parser.add_argument("--domain", default="", help="Filter by domain (ops subcommand)")
    learn_sub = learn_parser.add_subparsers(dest="learn_cmd")
    learn_ops = learn_sub.add_parser("ops", help="Show effective operations")
    learn_ops.add_argument("--domain", default="", help="Filter by domain")
    learn_suggest = learn_sub.add_parser("suggest", help="Suggest paradigm for query")
    learn_suggest.add_argument("query", help="Research question")
    learn_suggest.add_argument("--json", action="store_true", help="Output as JSON")

    # evolve
    ev = sub.add_parser("evolve", help="Suggest paradigm improvements from learning history")
    ev.add_argument("query", help="Research question to optimize")

    # export
    e = sub.add_parser("export", help="Export paradigm program as diagram")
    e.add_argument("file", help="Paradigm JSON file")
    e.add_argument("--format", default="mermaid", choices=["mermaid", "json"], help="Output format")

    # diff
    d = sub.add_parser("diff", help="Compare two paradigm programs")
    d.add_argument("file_a", help="First paradigm JSON")
    d.add_argument("file_b", help="Second paradigm JSON")

    # validate
    v = sub.add_parser("validate", help="Validate a paradigm program JSON")
    v.add_argument("file", help="Paradigm JSON file")

    # mcp
    sub.add_parser("mcp", help="Start MCP server")

    # tui
    sub.add_parser("tui", help="Start interactive TUI")

    return p


def main() -> int:
    print("⚠️ Sophia 独立 CLI 已弃用，请使用 cockpit 替代", file=sys.stderr)
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "compile":
        from .compiler import compile_paradigm_sync

        prog = compile_paradigm_sync(args.query)
        if args.json:
            print(json.dumps(prog.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"\nParadigm: {prog.name}")
            print(f"Operations: {' → '.join(op.value for op in prog.operations)}")
            print(
                f"States: {prog.state_count} | Transitions: {len(prog.transitions)} | "
                f"Max iterations: {prog.max_iterations}"
            )
            issues = prog.validate()
            if issues:
                for i in issues:
                    print(f"  ⚠ {i}")

    elif args.command == "ops":
        from .symbols import AtomicOp

        for op in AtomicOp:
            print(f"  {op.value}")

    elif args.command == "states":
        from .symbols import ResearchState

        for s in ResearchState:
            print(f"  {s.value}")

    elif args.command == "transitions":
        from .symbols import BASE_TRANSITIONS

        for t in BASE_TRANSITIONS:
            print(
                f"  {t.from_state.value} --[{t.operation.value}]--> {t.to_state.value} "
                f"(gate: {t.gate.__name__}, fail: {t.on_fail.value})"
            )

    elif args.command == "learn":
        from .learner import ParadigmLearner

        learner = ParadigmLearner()
        if args.learn_cmd == "ops":
            scores = learner.get_effective_ops(domain_hint=args.domain)
            if args.json:
                print(json.dumps(scores, ensure_ascii=False, indent=2))
            elif scores:
                for op_name, score in sorted(scores.items(), key=lambda x: -x[1]):
                    print(f"  {op_name}: {score:.1f}")
            else:
                print("  No traces recorded yet.")
        elif args.learn_cmd == "suggest":
            suggestion = learner.suggest_paradigm(args.query)
            if args.json:
                print(json.dumps(suggestion, ensure_ascii=False, indent=2))
            elif suggestion["sample_count"] > 0:
                print(f"  样本数: {suggestion['sample_count']}")
                print(f"  置信度: {suggestion['confidence']:.0f}%")
                print(f"  推荐操作: {' → '.join(suggestion['recommended_ops'])}")
            else:
                print("  No data yet.")

    elif args.command == "evolve":
        from .compiler import compile_paradigm_sync
        from .learner import ParadigmLearner

        learner = ParadigmLearner()
        default = compile_paradigm_sync(args.query)
        suggestion = learner.suggest_paradigm(args.query)

        print(f"\n  问题: {args.query}")
        print(f"\n  默认范式: {' → '.join(op.value for op in default.operations)}")
        print(f"  状态数: {default.state_count}  转移数: {len(default.transitions)}")

        if suggestion["sample_count"] > 0:
            print(f"\n  学习数据: {suggestion['sample_count']} 条相似追踪 (置信度: {suggestion['confidence']:.0f}%)")
            print(f"  推荐操作: {' → '.join(suggestion['recommended_ops'])}")
            print("\n  参考案例:")
            for t in suggestion["top_traces"][:3]:
                print(f"    [{t['quality']}分] {t['query'][:80]}")
                print(f"           操作: {' → '.join(t['ops'])}")

            added = set(suggestion["recommended_ops"]) - {op.value for op in default.operations}
            removed = {op.value for op in default.operations} - set(suggestion["recommended_ops"])
            if added:
                print(f"\n  ✚ 建议增加: {sorted(added)}")
            if removed:
                print(f"  ✖ 建议移除: {sorted(removed)}")
            if not added and not removed:
                print("\n  默认范式已是最优 ✓")
        else:
            print("\n  无历史数据，使用默认范式。")
        print()

    elif args.command == "export":
        from pathlib import Path

        data = json.loads(Path(args.file).read_text())
        from .compiler import recompile_from_dict

        prog = recompile_from_dict(data)
        if args.format == "mermaid":
            print(prog.to_mermaid())
        else:
            print(json.dumps(prog.to_dict(), ensure_ascii=False, indent=2))

    elif args.command == "diff":
        from pathlib import Path

        data_a = json.loads(Path(args.file_a).read_text())
        data_b = json.loads(Path(args.file_b).read_text())
        from .compiler import recompile_from_dict

        delta = recompile_from_dict(data_a).diff(recompile_from_dict(data_b))
        print(json.dumps(delta, ensure_ascii=False, indent=2))

    elif args.command == "validate":
        from pathlib import Path

        data = json.loads(Path(args.file).read_text())
        from .compiler import recompile_from_dict

        prog = recompile_from_dict(data)
        issues = prog.validate()
        if issues:
            print("FAIL")
            for i in issues:
                print(f"  - {i}")
            return 1
        else:
            print("OK")
            return 0

    elif args.command == "mcp":
        from .server.mcp_server import main as mcp_main

        return mcp_main()

    elif args.command == "tui":
        from .tui.app import main as tui_main

        return tui_main()

    return 0


if __name__ == "__main__":
    sys.exit(main())
