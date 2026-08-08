"""cockpit CLI 子命令分发器 — 自 cli.py main() 拆出的执行逻辑 (god-module 拆分)。

cli.py 的 main() 保留 argparse parser 构建 + handlers 分发表;
本模块持有每个子命令分支的 dispatch/执行函数。

关于符号解析方式:
- dispatch_* 中引用的 cmd_* 若为 cli.py 模块级 re-export (如 cmd_research_*、
  cmd_data_*、cmd_bus 等), 一律通过 _get_cli() 延迟读取 `cockpit.cli` 模块属性。
  原因: 测试用 `monkeypatch.setattr(cli, "cmd_xxx", mock)` 验证路由分发,
  必须在调用时刻解析模块属性才能让 patch 生效 (与 commands/base.py 的
  _get_console() 惰性引用模式一致)。
- dispatch_* 内部 import 的模块 (如 cockpit.commands.code 等) 保持函数内
  延迟 import, 与原 cli.py 行为一致。
"""

from __future__ import annotations

import argparse

from .commands.base import _SCRIPT_DIR


def _get_cli():
    """延迟获取 cockpit.cli 模块 (调用时解析, 避免模块级循环 import)."""
    from cockpit import cli as _mod

    return _mod


def dispatch_research(a):
    _cli = _get_cli()
    if getattr(a, "batch", False) and getattr(a, "topic", []):
        if len(a.topic) >= 2:
            return _cli._cmd_research_batch(a)
    if getattr(a, "search", False):
        return _cli.cmd_research_search(a)
    if getattr(a, "compare", False):
        return _cli.cmd_research_compare(a)
    if getattr(a, "merge", False):
        return _cli.cmd_research_merge(a)
    if getattr(a, "digest", False):
        return _cli.cmd_research_digest(a)
    if getattr(a, "audit", False):
        return _cli.cmd_research_audit(a)
    if getattr(a, "quarantine", False):
        return _cli.cmd_research_quarantine(a)
    if getattr(a, "restore", False):
        return _cli.cmd_research_restore(a)
    if getattr(a, "heatmap", False):
        return _cli.cmd_research_heatmap(a)
    if getattr(a, "follow_up", False):
        return _cli.cmd_research_follow_up(a)
    if getattr(a, "health", False):
        return _cli.cmd_research_health(a)
    if getattr(a, "backup", None) is not None:
        a.output = a.backup or None
        return _cli.cmd_research_backup(a)
    if getattr(a, "backup_restore", False):
        return _cli.cmd_research_backup_restore(a)
    if getattr(a, "agent", False):
        return _cli.cmd_research_agent(a)
    if getattr(a, "list", False):
        return _cli.cmd_research_list(a)
    if getattr(a, "dossier", False):
        return _cli.cmd_research_dossier(a)
    if getattr(a, "timeline", False):
        return _cli.cmd_research_timeline(a)
    if getattr(a, "tag", False):
        return _cli.cmd_research_tag(a)
    if getattr(a, "rename", False):
        return _cli.cmd_research_rename(a)
    if getattr(a, "archive", False) or getattr(a, "all_active", False):
        return _cli.cmd_research_archive(a)
    if getattr(a, "unarchive", False):
        return _cli.cmd_research_unarchive(a)
    if getattr(a, "publish", False):
        return _cli.cmd_research_publish(a)
    if getattr(a, "export", False):
        return _cli.cmd_research_export(a)
    if getattr(a, "open", False):
        return _cli.cmd_research_open(a)
    if getattr(a, "ask", False):
        return _cli.cmd_research_ask(a)
    return _cli.cmd_research(a)


def dispatch_code(a, code_parser=None):
    if getattr(a, "code_command", "") == "workflow":
        from cockpit.commands.code import cmd_code_workflow

        return cmd_code_workflow(a)
    elif getattr(a, "code_command", ""):
        from cockpit.commands.code import cmd_code_base

        return cmd_code_base(a)
    # 裸 `cockpit code` / 未知子命令: 由 main() 传入对应 parser 打印用法
    if code_parser is not None:
        code_parser.print_help()
    return 1


def dispatch_cards(a):
    if getattr(a, "cards_command", None):
        from cockpit.commands.cards import cmd_cards as _cmd

        return _cmd(a)
    from cockpit.commands.l4bridge import cmd_cards as _cmd

    return _cmd(a)


def dispatch_bos(a):
    _cli = _get_cli()
    sub = getattr(a, "bos_cmd", "")
    if sub == "list":
        return _cli.cmd_bos_list(a)
    elif sub == "discover":
        return _cli.cmd_bos_discover(a)
    elif sub == "resolve":
        return _cli.cmd_bos_resolve(a)
    elif sub == "read":
        return _cli.cmd_bos_read(a)
    elif sub == "capability":
        return _cli.cmd_bos_capability(a)
    elif sub == "inbox":
        from cockpit.commands.bos_inbox import cmd_bos_inbox

        return cmd_bos_inbox(a)
    elif sub == "health":
        return _cli.cmd_bos_health(a)
    elif sub == "backends":
        return _cli.cmd_bos_backends(a)
    elif sub == "reload":
        return _cli.cmd_bos_reload(a)
    elif sub == "register":
        return _cli.cmd_bos_register(a)
    elif sub == "workflow":
        return _cli.cmd_bos_workflow(a)
    elif sub == "mutate":
        return _cli.cmd_bos_mutate(a)
    else:
        return _cli.cmd_bos_status(a)


def dispatch_bus(a):
    _cli = _get_cli()
    return _cli.cmd_bus(a)


def dispatch_observe(a):
    _cli = _get_cli()
    return _cli.cmd_observe(a)


def dispatch_family_hub(a):
    _cli = _get_cli()
    return _cli.cmd_family_hub(a)


def dispatch_mesh(a):
    _cli = _get_cli()
    return _cli.cmd_mesh(a)


def dispatch_scenario(a):
    from cockpit.commands.scenario import cmd_scenario

    return cmd_scenario(a)


def dispatch_iterate(a):
    from cockpit.commands.iterate import cmd_iterate

    return cmd_iterate(a)


def _dispatch_debt(a):
    """cockpit debt 子命令路由: score → 评分算法, 其他 → omo debt 委派."""
    sub = getattr(a, "debt_subcommand", None)
    if sub == "score" or sub is None:
        from cockpit.commands.debt_scoring import cmd_debt_score

        return cmd_debt_score(a)
    # 其他子命令 (list/summary/predict 等) 委派给 omo debt
    # 子命令名作为 omo debt 首参 (cockpit debt list → omo debt list)
    from cockpit.commands.omo import cmd_omo_debt

    a.omo_debt_args = [sub] + list(getattr(a, "omo_debt_args", []))

    return cmd_omo_debt(a)


def dispatch_agent_runtime(a):
    from cockpit import agent_runtime_cli

    argv: list[str] = []
    if getattr(a, "prompt", None):
        argv.extend(["--prompt", a.prompt])
    if getattr(a, "task", None):
        argv.extend(["--task", a.task])
    if getattr(a, "model", None):
        argv.extend(["--model", a.model])
    if getattr(a, "tools", None):
        argv.extend(["--tools", *a.tools])
    if getattr(a, "server", None):
        argv.append("--server")
    if getattr(a, "port", None) is not None:
        argv.extend(["--port", str(a.port)])
    return agent_runtime_cli.run_agent_runtime(argv)


def dispatch_compass(a):
    import os
    import subprocess

    c2g_project = str((_SCRIPT_DIR.parent.parent.parent.parent / "c2g").resolve())
    cmd = ["uv", "run", "--project", c2g_project, "c2g"] + getattr(a, "compass_args", [])
    # 清 VIRTUAL_ENV 避免 uv venv 冲突 (cockpit → c2g subprocess 继承父环境)
    env = {k: v for k, v in os.environ.items() if not k.startswith("VIRTUAL_ENV") and k != "PYTHONHOME"}
    return subprocess.call(cmd, env=env)


def dispatch_bdsk(a):
    from cockpit.commands.bdsk_engine import DynamicBDSKAdjudicator

    topic = getattr(a, "topic", "架构决策与技术选型")
    res = DynamicBDSKAdjudicator.adjudicate(topic)

    source_tag = "⚡️ AetherForge + omlxc (Local LLM Active)" if res.get("engine_source") == "aetherforge_local_llm" else "ℹ️ [AetherForge] 网关未在线 ➔ 平滑降级至领域推理引擎"

    print("=========================================================================")
    print(f" 🧠 B.D.S.K. 虚拟董事会 (4 角动态对抗模式) ➔ {source_tag}")
    print(f" 🔬 领域分类: {res['domain_label']} | 🎯 议题: {res['topic']}")
    print("=========================================================================")
    print("🧑‍💻 Builder (建造者/技术合伙人):")
    print(f"  • {res['builder']}")
    print("⚡️ Devil (批判者/风控官):")
    print(f"  • {res['devil']}")
    print("🧠 Sage (贤者/战略家):")
    print(f"  • {res['sage']}")
    print("👁️ Keeper (守夜人/观察者):")
    print(f"  • {res['keeper']}")
    print("=========================================================================")
    print(f"💡 4 角共识裁决结论: {res['conclusion']}")
    print("=========================================================================")
    return 0


def dispatch_journey(a):
    import subprocess

    ws_root = (_SCRIPT_DIR.parent.parent.parent.parent.parent).resolve()
    runner = str(ws_root / "bin" / "ssot" / "journey-runner.py")
    return subprocess.call(["python3", runner, "--help"])


def dispatch_panorama(a):
    import os
    import subprocess

    omo_project = str((_SCRIPT_DIR.parent.parent.parent.parent / "omo").resolve())
    cmd = ["uv", "run", "--project", omo_project, "python", "-m", "omo.cli", "panorama"]
    if getattr(a, "json", False):
        cmd.append("--json")
    env = {k: v for k, v in os.environ.items() if not k.startswith("VIRTUAL_ENV") and k != "PYTHONHOME"}
    return subprocess.call(cmd, env=env)


def dispatch_project(a):
    import os
    import subprocess

    omo_project = str((_SCRIPT_DIR.parent.parent.parent.parent / "omo").resolve())
    subcmd = getattr(a, "project_subcmd", "inspect")
    pname = getattr(a, "project_name", "")
    cmd = ["uv", "run", "--project", omo_project, "python", "-m", "omo.cli", "project", subcmd]
    if pname:
        cmd.append(pname)
    if getattr(a, "json", False):
        cmd.append("--json")
    env = {k: v for k, v in os.environ.items() if not k.startswith("VIRTUAL_ENV") and k != "PYTHONHOME"}
    return subprocess.call(cmd, env=env)


def dispatch_wave2(a):
    from cockpit.commands.wave2 import cmd_wave2

    return cmd_wave2(a)


def dispatch_workflow(a):
    wf_args = getattr(a, "workflow_args", [])
    # workflow mesh 子命令路由到 workflow_mesh 模块
    if wf_args and wf_args[0] == "mesh":
        from cockpit.commands.workflow_mesh import cmd_workflow_mesh

        mesh_args = argparse.Namespace(mesh_command=wf_args[1] if len(wf_args) > 1 else None)
        if len(wf_args) > 2 and wf_args[1] == "events":
            try:
                mesh_args.limit = int(wf_args[2])
            except (ValueError, IndexError):
                mesh_args.limit = 20
        return cmd_workflow_mesh(mesh_args)
    from cockpit.commands.workflow import handle_workflow

    return handle_workflow(wf_args)


def dispatch_agent_workflow(a):
    from cockpit.commands.agent_workflow import cmd_agent_workflow

    return cmd_agent_workflow(a)


def dispatch_agent_onboard(a):
    from cockpit.commands.agent_onboard import cmd_agent_onboard

    return cmd_agent_onboard(a)


def dispatch_monitor(a):
    from cockpit.commands.monitor import cmd_monitor

    return cmd_monitor(a)


def dispatch_data(a):
    _cli = _get_cli()
    if getattr(a, "data_command", "") == "index":
        return _cli.cmd_data_index(a)
    if getattr(a, "data_command", "") == "types":
        return _cli.cmd_data_types(a)
    if getattr(a, "data_command", "") == "gc":
        return _cli.cmd_data_gc(a)
    _cli.console.print(
        "[yellow]试试: [cyan]cockpit data index[/] 或 [cyan]cockpit data types[/] 或 [cyan]cockpit data gc[/][/]"
    )
    return 1


def dispatch_contracts(a):
    _cli = _get_cli()
    if getattr(a, "contracts_command", "") == "validate":
        return _cli.cmd_contracts_validate(a)
    if getattr(a, "contracts_command", "") == "list":
        return _cli.cmd_contracts_list(a)
    if getattr(a, "contracts_command", "") == "export-research":
        return _cli.cmd_contracts_export_research(a)
    if getattr(a, "contracts_command", "") == "export":
        if getattr(a, "contracts_export_type", "") == "identity":
            return _cli.cmd_contracts_export_identity(a)
        elif getattr(a, "contracts_export_type", "") == "event":
            return _cli.cmd_contracts_export_event(a)
    # 裸 `cockpit contracts` / 未知子命令: 给出用法而非静默 rc=1
    print(
        "用法: cockpit contracts {validate|list|export-research <ID>|export identity|export event}\n"
        "  validate          验证 Workspace 契约\n"
        "  list              列出所有已注册 Schema\n"
        "  export-research   将研究对象导出为 WorkspaceObject JSON\n"
        "  export identity/event  导出契约封套"
    )
    return 1


def cmd_product_health(a):
    import subprocess as _sp
    import sys

    result = _sp.run([sys.executable, str(_SCRIPT_DIR / "product-health")])
    returncode = getattr(result, "returncode", 0)
    return returncode if isinstance(returncode, int) else 0


def cmd_compute(a):
    from cockpit.commands.compute import cmd_compute as _c

    return _c(a)
