"""cockpit.chain — 声明式链路编排命令组 (Phase C).

挂载契约 (见 _subcommands.py / cli.py 预埋):
  register_chain(sub, workspace_parser)  注册 chain 子 parser 组
  cmd_chain(args)                        按 args.chain_command 分发
"""

from __future__ import annotations

import argparse

from cockpit.chain.runner import parse_params, run_chain
from cockpit.chain.spec import (
    ChainSpecError,
    chain_source,
    init_chain,
    list_chains,
    load_chain,
    spec_to_raw,
    validate_command_catalog,
    validate_spec,
)


def register_chain(sub: argparse._SubParsersAction, workspace_parser) -> None:
    p = sub.add_parser("chain", help="🔗 声明式链路编排 — 按 YAML spec 串联 cockpit 命令 (list/show/run/validate/init)")
    p.add_argument("chain_command", nargs="?", default="list", choices=["list", "show", "run", "validate", "init"], help="chain 子命令")
    p.add_argument("chain_id", nargs="?", help="链路 ID")
    p.add_argument("--dry-run", action="store_true", help="只打印计划, 不执行")
    p.add_argument("--resume", metavar="RUN_ID", help="从指定 run 恢复 (跳过已 succeeded 步骤)")
    p.add_argument("--force-rerun", action="store_true", help="resume 时强制重跑全部步骤")
    p.add_argument("--non-interactive", action="store_true", help="HITL 点不阻塞, 取默认继续")
    p.add_argument("--param", action="append", default=[], metavar="K=V", help="链路参数 (可多次)")
    p.add_argument("--force", action="store_true", help="init 时覆盖已存在文件")


def cmd_chain(args: argparse.Namespace) -> int:
    cmd = getattr(args, "chain_command", "list") or "list"
    try:
        if cmd == "list":
            return _cmd_list()
        if cmd == "show":
            return _cmd_show(args.chain_id)
        if cmd == "run":
            return _cmd_run(args)
        if cmd == "validate":
            return _cmd_validate(args.chain_id)
        if cmd == "init":
            return _cmd_init(args.chain_id, force=args.force)
    except ChainSpecError as e:
        print(f"[chain] 错误: {e}")
        return 2
    print(f"[chain] 未知子命令: {cmd}")
    return 2


def _cmd_list() -> int:
    chains = list_chains()
    if not chains:
        print("[chain] 无可用链路 (搜索路径: <repo>/config/chains, <workspace>/config/chains, ~/.workspace/chains)")
        return 0
    print(f"{'ID':<24} {'NAME':<28} SOURCE")
    for cid in chains:
        try:
            spec = load_chain(cid)
            name = spec.name
        except Exception:
            name = "<解析失败>"
        print(f"{cid:<24} {name:<28} {chain_source(cid)}")
    return 0


def _cmd_show(chain_id: str | None) -> int:
    if not chain_id:
        print("[chain] 用法: cockpit chain show <id>")
        return 2
    spec = load_chain(chain_id)
    raw = spec_to_raw(spec)
    import json

    print(json.dumps(raw, ensure_ascii=False, indent=2))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    if not args.chain_id:
        print("[chain] 用法: cockpit chain run <id>")
        return 2
    spec = load_chain(args.chain_id)
    errors = validate_spec(spec)
    if errors:
        print("[chain] spec 校验失败:")
        for e in errors:
            print(f"  - {e}")
        return 2
    params = parse_params(args.param)
    return run_chain(
        spec,
        dry_run=args.dry_run,
        resume_run_id=args.resume,
        force_rerun=args.force_rerun,
        non_interactive=args.non_interactive,
        params=params,
    )


def _cmd_validate(chain_id: str | None) -> int:
    if not chain_id:
        print("[chain] 用法: cockpit chain validate <id>")
        return 2
    spec = load_chain(chain_id)
    errors = validate_spec(spec) + validate_command_catalog(spec)
    if errors:
        print(f"[chain] validate '{chain_id}': FAIL ({len(errors)} 个问题)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"[chain] validate '{chain_id}': OK ({len(spec.steps)} steps, source={spec.source_path})")
    return 0


def _cmd_init(chain_id: str | None, *, force: bool = False) -> int:
    if not chain_id:
        print("[chain] 用法: cockpit chain init <new-id>")
        return 2
    target = init_chain(chain_id, force=force)
    print(f"[chain] 已生成骨架: {target}")
    return 0
