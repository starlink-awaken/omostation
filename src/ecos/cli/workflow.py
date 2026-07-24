#!/usr/bin/env python3
"""ecos workflow — 工作流 CLI 命令

用法:
    ecos workflow list                    # 列出所有可用工作流
    ecos workflow run <name> [--dry-run]  # 执行工作流
    ecos workflow describe <name>         # 查看工作流定义
    ecos workflow backends                # 查看后端注册状态
    ecos workflow logs [--recent N] [--status ok|failed] [--verbose] [<workflow_id>]
                                          # 工作流运行历史

子命令委派:
    logs/runs → cli.workflow_runs
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def main() -> None:
    """CLI 入口"""
    print("⚠️ ECOS Workflow 独立 CLI 已弃用，请使用 cockpit 替代", file=sys.stderr)
    args = sys.argv[1:] if sys.argv[1:] else ["--help"]

    subcmd = args[0] if args else "help"
    subargs = args[1:]

    dispatcher = {
        "list": _cmd_list,
        "ls": _cmd_list,
        "run": _cmd_run,
        "describe": _cmd_describe,
        "cat": _cmd_describe,
        "backends": _cmd_backends,
        "actions": _cmd_actions,
        "status": _cmd_status,
        "st": _cmd_status,
        "stats": _cmd_stats,
        "logs": _cmd_logs,
        "runs": _cmd_logs,
        "create": _cmd_create,
        "new": _cmd_create,
        "validate": _cmd_validate,
        "val": _cmd_validate,
        "test": _cmd_test,
        "edit": _cmd_edit,
        "fork": _cmd_fork,
        "export": _cmd_export,
        "import": _cmd_import,
        "cache-status": _cmd_cache_status,
        "cache-invalidate": _cmd_cache_invalidate,
        "cb-status": _cmd_circuit_status,
        "cb-reset": _cmd_circuit_reset,
        "--help": _cmd_help,
        "-h": _cmd_help,
        "help": _cmd_help,
    }

    cmd = dispatcher.get(subcmd)
    if cmd is None:
        print(f"未知子命令: {subcmd}")
        _cmd_help()
        sys.exit(1)

    cmd(subargs)


# ── 子命令实现 ──


def _cmd_list(args: list[str]) -> None:
    """ecos workflow list [--with-status|-s] — 列出所有可用工作流"""
    from pathlib import Path

    from ecos.workflow import list_workflows

    with_status = "--with-status" in args or "-s" in args

    wfs = list_workflows()
    if not wfs:
        print("没有可用工作流。")
        return

    # 加载最近一次运行状态
    latest_status: dict[str, str] = {}
    if with_status:
        runs_dir = Path.home() / ".omo" / "state" / "workflow-runs"
        if runs_dir.exists():
            import yaml

            for f in sorted(runs_dir.glob("*.yaml"), reverse=True):
                try:
                    with open(f) as fh:
                        data = yaml.safe_load(fh)
                    wf_id = data.get("workflow_id", "")
                    if wf_id and wf_id not in latest_status:
                        latest_status[wf_id] = data.get("status", "?")
                except Exception:  # defensive fallback
                    pass

    print(f"📋 可用工作流 ({len(wfs)} 个)")
    if with_status:
        print(f"{'=' * 95}")
    else:
        print(f"{'=' * 80}")
    for wf in wfs:
        src = "📄" if wf.get("source") == "definition" else "📌"
        name = wf.get("name", "?")
        display = wf.get("display", name)
        extra = ""
        if wf.get("domain"):
            extra = f"  domain={wf['domain']}"
        if wf.get("layer"):
            extra += f"  layer={wf['layer']}"

        if with_status:
            wf_key = wf.get("id", wf.get("name", ""))
            status_icon = latest_status.get(wf_key, "—")
            status_char = (
                "✅"
                if status_icon == "ok"
                else "❌"
                if status_icon == "failed"
                else "➖"
            )
            print(f"  {status_char} {src}  {display:30s}  [{name}]{extra}")
        else:
            print(f"  {src}  {display:30s}  [{name}]{extra}")

    if with_status:
        print(f"{'=' * 95}")
        print("  ✅=最近成功  ❌=最近失败  ➖=无记录  📌=M1节点  📄=definition")
    else:
        print(f"{'=' * 80}")


def _cmd_run(args: list[str]) -> None:
    """ecos workflow run <name> — 执行工作流"""
    from ecos.workflow import execute_m1_workflow

    dry_run = "--dry-run" in args or "--dry" in args
    args = [a for a in args if a not in ("--dry-run", "--dry")]

    # 解析 --param/-p key=value
    params: dict[str, str] = {}
    remaining: list[str] = []
    i = 0
    while i < len(args):
        if args[i] in ("-p", "--param") and i + 1 < len(args):
            kv = args[i + 1]
            if "=" in kv:
                k, v = kv.split("=", 1)
                params[k] = v
            else:
                params[kv] = "true"
            i += 2
        elif args[i].startswith("--param="):
            kv = args[i][8:]
            if "=" in kv:
                k, v = kv.split("=", 1)
                params[k] = v
            i += 1
        else:
            remaining.append(args[i])
            i += 1
    args = remaining

    if not args:
        print("用法: ecos workflow run <name> [--dry-run] [-p key=value ...]")
        sys.exit(1)

    name = args[0]
    print(f"🚀 执行工作流: {name}" + (" (干跑模式)" if dry_run else ""))
    if params:
        print(f"   参数: {params}")
    print()

    result = execute_m1_workflow(name, params=params, dry_run=dry_run)

    if "error" in result:
        print(f"❌ {result['error']}")
        sys.exit(1)

    _print_result(result)


def _cmd_describe(args: list[str]) -> None:
    """ecos workflow describe <name> — 查看工作流定义"""
    from ecos.workflow import load_workflow

    if not args:
        print("用法: ecos workflow describe <name>")
        sys.exit(1)

    wf = load_workflow(args[0])
    if not wf:
        print(f"工作流不存在: {args[0]}")
        sys.exit(1)

    print(f"📖 工作流: {wf.get('name', args[0])}")
    print(f"  ID: {wf.get('id', '(definition)')}")
    if wf.get("description"):
        print(f"  描述: {wf['description']}")
    if wf.get("domain"):
        print(f"  域: {wf['domain']}")
    if wf.get("layer"):
        print(f"  层: {wf['layer']}")
    if wf.get("bos_uri"):
        print(f"  BOS: {wf['bos_uri']}")
    print()

    execution = wf.get("execution", {})
    has_exec = bool(execution)
    if has_exec:
        print(f"  后端: {execution.get('backend', 'default')}")
        print(f"  模式: {execution.get('mode', 'workflow')}")
        if execution.get("on_failure"):
            print(f"  失败策略: {execution['on_failure']}")
        print()

    steps = wf.get("steps", [])
    if not steps:
        print("  (无步骤定义)")
        return

    print(f"  步骤 ({len(steps)} 步):")
    print(f"  {'─' * 60}")
    for i, step in enumerate(steps, 1):
        name = step.get("name", f"step-{i}")
        action = step.get("action", "?")
        on_fail = step.get("on_failure", "")
        fail_info = f"  [on_failure={on_fail}]" if on_fail else ""
        print(f"    {i:2d}. {name:25s}  {action}{fail_info}")
    print(f"  {'─' * 60}")


def _cmd_backends(_args: list[str]) -> None:
    """ecos workflow backends — 查看后端注册状态"""
    from ecos.workflow import list_backends

    backends = list_backends()
    if not backends:
        print("没有已注册的后端。")
        return

    print(f"🔌 后端注册表 ({len(backends)} 个)")
    print(f"{'=' * 80}")
    for b in backends:
        loaded = "✅" if b.get("loaded") else "💤"
        desc = b.get("description", "")
        print(f"  {loaded}  {b['name']:15s}  {b['module_path']:30s}  {desc}")
    print(f"{'=' * 80}")
    print("💡 workflow 通过 execution.backend 字段选择后端。")


def _cmd_actions(_args: list[str]) -> None:
    """ecos workflow actions — 列出所有已注册 action"""
    from ecos.workflow.actions import list_actions

    actions = list_actions()
    if not actions:
        print("没有已注册的 action。")
        return

    print(f"⚡ 已注册 action ({len(actions)} 个)")
    print(f"{'=' * 60}")
    for a in actions:
        desc = a.get("description", "")
        print(f"  {a['name']:30s}  {desc}")
    print(f"{'=' * 60}")
    print(
        "💡 action 在工作流定义的 step.action 字段中使用。外部模块可通过 register_action() 扩展。"
    )


def _cmd_status(_args: list[str]) -> None:
    """ecos workflow status — 工作流引擎全局状态"""
    from pathlib import Path

    from ecos.workflow import list_backends
    from ecos.workflow.actions import list_actions
    from ecos.workflow.loader import list_workflows

    backends = list_backends()
    actions = list_actions()
    wfs = list_workflows()
    runs_dir = Path.home() / ".omo" / "state" / "workflow-runs"
    run_count = len(list(runs_dir.glob("*.yaml"))) if runs_dir.exists() else 0

    print("📊 工作流引擎全局状态")
    print(f"{'=' * 60}")
    print(f"  后端注册:   {len(backends)} 个")
    counts: dict[str, int] = {"💤": 0, "✅": 0}
    for b in backends:
        counts["✅" if b.get("loaded") else "💤"] += 1
    print(f"  加载状态:   {counts['✅']} 已加载 / {counts['💤']} 惰性待加载")
    print(f"  已注册 action: {len(actions)} 个")
    print(f"  可用工作流: {len(wfs)} 个")
    print(f"  历史运行记录: {run_count} 条")
    print()

    try:
        from ecos.workflow.backend_registry import resolve

        fn = resolve({"execution": {}})
        assert callable(fn)
        print("  ✅  默认后端: 可用")
    except Exception as e:  # defensive fallback
        print(f"  ❌  默认后端: {e}")

    try:
        from ecos.workflow.actions import resolve_action

        handler = resolve_action("health_check")
        if handler:
            print("  ✅  action 解析: 功能正常")
    except Exception as e:  # defensive fallback
        print(f"  ❌  action 解析: {e}")

    m1_dir = Path(__file__).parent.parent / "ssot" / "mof" / "m1" / "workflow"
    print(f"  📂  M1 节点目录: {m1_dir}")
    m1_files = list(m1_dir.glob("WORKFLOW-*.yaml")) if m1_dir.exists() else []
    print(f"  📄  M1 工作流文件: {len(m1_files)} 个")
    print(f"{'=' * 60}")


def _cmd_logs(args: list[str]) -> None:
    """ecos workflow logs — 委派到 workflow_runs"""
    from ecos.cli.workflow_runs import cmd_runs

    cmd_runs(args)


def _cmd_create(args: list[str]) -> None:
    """ecos workflow create <name> — 创建工作流模板"""
    from pathlib import Path

    import yaml

    m1 = "--m1" in args
    out_path = None
    rest = [a for a in args if a not in ("--m1",)]

    # 检查是否指定了 --path
    i = 0
    while i < len(rest):
        if rest[i] == "--path" and i + 1 < len(rest):
            out_path = Path(rest[i + 1])
            rest = rest[:i] + rest[i + 2 :]
            break
        i += 1

    if not rest:
        print("用法: ecos workflow create <name> [--m1] [--path <file>]")
        sys.exit(1)

    name = rest[0]
    safe_name = name.upper().replace(" ", "-").replace("_", "-")
    wf_id = (
        f"WORKFLOW-{safe_name}" if not safe_name.startswith("WORKFLOW-") else safe_name
    )

    if m1:
        # M1 格式模板（含完整元数据）
        template = _m1_template(wf_id, name)
        if out_path is None:
            from ecos.workflow.loader import M1_WF_DIR

            M1_WF_DIR.mkdir(parents=True, exist_ok=True)
            out_path = M1_WF_DIR / f"{wf_id}.yaml"
    else:
        # 简化 definition 格式
        template = _def_template(name)
        if out_path is None:
            from ecos.workflow.loader import WF_DIR

            WF_DIR.mkdir(parents=True, exist_ok=True)
            out_path = WF_DIR / f"{name}.yaml"

    if out_path.exists():
        print(f"⚠️ 文件已存在: {out_path}")
        overwrite = input("  覆盖? [y/N] ").strip().lower()
        if overwrite not in ("y", "yes"):
            print("已取消。")
            return

    with open(out_path, "w") as f:
        yaml.dump(
            template, f, allow_unicode=True, default_flow_style=False, sort_keys=False
        )

    print(f"✅ 工作流模板已创建: {out_path}")
    print(f"   类型: {'M1' if m1 else 'definition'}")
    print(f"   ID: {wf_id if m1 else name}")
    print(f"   执行: ecos workflow run {(wf_id if m1 else name)!r}")


def _m1_template(wf_id: str, name: str) -> dict:
    """生成 M1 格式工作流模板"""
    return {
        "id": wf_id,
        "type": "Workflow",
        "subtype": "CustomWorkflow",
        "name": name,
        "description": f"自定义工作流: {name}",
        "status": "active",
        "version": "1.0.0",
        "domain": "meta",
        "layer": "L0",
        "created": None,  # 会被 yaml 序列化为 null
        "bos_uri": f"bos://ecos/workflow/{name.lower().replace(' ', '-')}",
        "execution": {
            "backend": "default",
            "mode": "sequential",
            "max_retries": 0,
            "on_failure": "continue",
        },
        "steps": [
            {
                "order": 1,
                "name": "Step1",
                "action": "health_check",
                "description": "步骤描述",
            },
            {
                "order": 2,
                "name": "Step2",
                "action": "domain_audit",
                "description": "步骤描述",
                "depends_on": ["Step1"],
            },
        ],
        "relations": [],
        "sla": {"max_execution_time": 300, "expected_completion_rate": 0.95},
        "tags": [name.lower(), "custom"],
        "maintained_by": "user",
        "last_reviewed": None,
    }


def _def_template(name: str) -> dict:
    """生成简化 definition 格式工作流模板"""
    return {
        "name": name,
        "description": f"自定义工作流: {name}",
        "execution": {
            "backend": "default",
            "mode": "sequential",
            "on_failure": "continue",
        },
        "steps": [
            {"name": "Step1", "action": "health_check", "description": "步骤描述"},
            {"name": "Step2", "action": "domain_audit", "description": "步骤描述"},
        ],
    }


def _cmd_validate(args: list[str]) -> None:
    """ecos workflow validate <name> — 验证工作流定义"""
    from ecos.workflow import load_workflow
    from ecos.workflow.validator import validate_workflow

    if not args:
        print("用法: ecos workflow validate <name>")
        sys.exit(1)

    name = args[0]
    wf = load_workflow(name)
    if not wf:
        print(f"❌ 工作流不存在: {name}")
        sys.exit(1)

    # 构建 M1 节点结构
    wf_id = wf.get("id", name)
    wf_name = wf.get("name", name)

    print(f"🔍 验证工作流: {wf_name} ({wf_id})")
    print(f"{'=' * 60}")

    violations = validate_workflow(wf)
    if not violations:
        print("  ✅  无违规 — 工作流定义正确。")
        return

    errors = [v for v in violations if v.get("severity") == "error"]
    warnings = [v for v in violations if v.get("severity") != "error"]

    if errors:
        print(f"  ❌  错误 ({len(errors)} 项):")
        for v in errors:
            print(f"    ❌  [{v.get('id', '?')}] {v.get('message', '')}")
    if warnings:
        print(f"  ⚠️  警告 ({len(warnings)} 项):")
        for v in warnings:
            print(f"    ⚠️  [{v.get('id', '?')}] {v.get('message', '')}")

    print(f"{'=' * 60}")
    print(f"  总计: {len(errors)} error(s), {len(warnings)} warning(s)")
    if errors:
        sys.exit(1)


def _cmd_test(args: list[str]) -> None:
    """ecos workflow test <name> — mock 模式测试工作流编排"""
    if not args:
        print("用法: ecos workflow test <name>")
        sys.exit(1)

    from ecos.workflow.executor import test_workflow

    name = args[0]
    print()
    result = test_workflow(name)

    if "error" in result:
        print(f"❌ {result['error']}")
        sys.exit(1)

    if result["failed"] > 0:
        sys.exit(1)


def _cmd_edit(args: list[str]) -> None:
    """ecos workflow edit <name> — 打开编辑器编辑工作流定义"""
    import os

    if not args:
        print("用法: ecos workflow edit <name>")
        sys.exit(1)
    name = args[0]
    from ecos.workflow import load_workflow
    from ecos.workflow.loader import M1_WF_DIR, WF_DIR

    wf = load_workflow(name)
    if not wf:
        print(f"❌ 工作流不存在: {name}")
        sys.exit(1)

    # 定位文件路径
    is_m1 = wf.get("type") == "Workflow"
    if is_m1:
        wf_id = wf.get("id", f"WORKFLOW-{name.upper()}")
        file_path = M1_WF_DIR / f"{wf_id.upper()}.yaml"
    else:
        # 匹配 definitions 目录中的文件
        matched = list(WF_DIR.glob(f"{name}.yaml")) + list(WF_DIR.glob(f"{name}.yml"))
        file_path = matched[0] if matched else WF_DIR / f"{name}.yaml"

    if not file_path.exists():
        print(f"❌ 文件不存在: {file_path}")
        # 尝试模糊搜索
        candidates = list(WF_DIR.glob("*.yaml")) + list(
            M1_WF_DIR.glob("WORKFLOW-*.yaml")
        )
        for c in candidates:
            if name.lower() in c.stem.lower():
                file_path = c
                break
        else:
            sys.exit(1)

    print(f"📝 编辑: {file_path}")
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vim"))
    try:
        import subprocess

        subprocess.run([editor, str(file_path)], check=False)
        print(f"✅ 文件已保存: {file_path}")
    except FileNotFoundError:
        print(f"❌ 找不到编辑器: {editor}，请设置 EDITOR 环境变量")
        sys.exit(1)


def _cmd_export(args: list[str]) -> None:
    """ecos workflow export <name> --path <file> — 导出工作流"""
    import shutil

    from ecos.workflow import load_workflow
    from ecos.workflow.loader import M1_WF_DIR, WF_DIR

    if not args:
        print("用法: ecos workflow export <name> [--path <file>]")
        sys.exit(1)

    name = args[0]
    out_path = None
    rest = args[1:]
    i = 0
    while i < len(rest):
        if rest[i] == "--path" and i + 1 < len(rest):
            out_path = Path(rest[i + 1])
            break
        i += 1

    wf = load_workflow(name)
    if not wf:
        print(f"❌ 工作流不存在: {name}")
        sys.exit(1)

    # 找源文件
    is_m1_type = wf.get("type") == "Workflow"
    if is_m1_type:
        wf_id = wf.get("id", f"WORKFLOW-{name.upper()}")
        src_path = M1_WF_DIR / f"{wf_id.upper()}.yaml"
    else:
        matched = list(WF_DIR.glob(f"{name}.yaml")) + list(WF_DIR.glob(f"{name}.yml"))
        src_path = matched[0] if matched else WF_DIR / f"{name}.yaml"

    if not src_path.exists():
        print(f"❌ 源文件不存在: {src_path}")
        sys.exit(1)

    out_path = out_path or Path(f"{name}.yaml")
    shutil.copy2(src_path, out_path)
    print(f"✅ 工作流已导出: {src_path} → {out_path}")
    print(f"   导入: ecos workflow import {out_path}")


def _cmd_import(args: list[str]) -> None:
    """ecos workflow import <file> [--as <name>] [--m1] — 导入工作流定义"""
    import shutil

    if not args:
        print("用法: ecos workflow import <file> [--as <name>] [--m1]")
        sys.exit(1)

    src = Path(args[0])
    if not src.exists():
        print(f"❌ 文件不存在: {src}")
        sys.exit(1)

    # 解析选项
    import_as = None
    as_m1 = "--m1" in args
    rest = [a for a in args if a not in ("--m1",)]
    i = 1
    while i < len(rest):
        if rest[i] == "--as" and i + 1 < len(rest):
            import_as = rest[i + 1]
            break
        i += 1

    # 读取并校验
    import yaml

    try:
        with open(src) as f:
            wf = yaml.safe_load(f)
    except Exception as e:  # defensive fallback
        print(f"❌ YAML 解析失败: {e}")
        sys.exit(1)

    if not isinstance(wf, dict):
        print("❌ 无效的工作流定义")
        sys.exit(1)

    # 验证内容
    if import_as:
        wf_name = import_as
    elif wf.get("name"):
        wf_name = wf["name"]
    else:
        wf_name = src.stem

    # 确定目标目录
    if as_m1 or wf.get("type") == "Workflow":
        from ecos.workflow.loader import M1_WF_DIR

        M1_WF_DIR.mkdir(parents=True, exist_ok=True)
        target_id = wf.get("id", f"WORKFLOW-{wf_name.upper().replace(' ', '-')}")
        dest = M1_WF_DIR / f"{target_id}.yaml"
        wf_type = "M1"
    else:
        from ecos.workflow.loader import WF_DIR

        WF_DIR.mkdir(parents=True, exist_ok=True)
        dest = WF_DIR / f"{wf_name}.yaml"
        wf_type = "definition"

    if dest.exists():
        print(f"⚠️ 目标文件已存在: {dest}")
        answer = input("  覆盖? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("已取消。")
            return

    shutil.copy2(src, dest)
    print(f"✅ 工作流已导入: {src} → {dest} ({wf_type})")
    print(f"   执行: ecos workflow run '{wf_name}'")
    print(f"   验证: ecos workflow validate '{wf_name}'")


def _cmd_fork(args: list[str]) -> None:
    """ecos workflow fork <name> --as <new> — 派生工作流"""
    from ecos.workflow import load_workflow
    from ecos.workflow.loader import M1_WF_DIR, WF_DIR

    if not args:
        print("用法: ecos workflow fork <name> --as <new_name>")
        sys.exit(1)

    name = args[0]
    new_name = None
    rest = args[1:]
    i = 0
    while i < len(rest):
        if rest[i] == "--as" and i + 1 < len(rest):
            new_name = rest[i + 1]
            break
        i += 1

    if not new_name:
        print("用法: ecos workflow fork <name> --as <new_name>")
        sys.exit(1)

    wf = load_workflow(name)
    if not wf:
        print(f"❌ 源工作流不存在: {name}")
        sys.exit(1)

    # 定位源文件
    is_m1 = wf.get("type") == "Workflow"
    if is_m1:
        wf_id = wf.get("id", f"WORKFLOW-{name.upper()}")
        src_path = M1_WF_DIR / f"{wf_id.upper()}.yaml"
    else:
        matched = list(WF_DIR.glob(f"{name}.yaml")) + list(WF_DIR.glob(f"{name}.yml"))
        src_path = matched[0] if matched else WF_DIR / f"{name}.yaml"

    if not src_path.exists():
        print(f"❌ 源文件不存在: {src_path}")
        sys.exit(1)

    # 读取源工作流并修改
    import yaml

    with open(src_path) as f:
        new_wf = yaml.safe_load(f)

    safe_new = new_name.upper().replace(" ", "-").replace("_", "-")
    new_wf_id = (
        f"WORKFLOW-{safe_new}"
        if is_m1 and not safe_new.startswith("WORKFLOW-")
        else safe_new
    )
    new_wf["id"] = new_wf_id
    new_wf["name"] = new_name
    new_wf["description"] = f"从 {wf.get('name', name)} 派生: {new_name}"
    if new_wf.get("bos_uri"):
        new_wf["bos_uri"] = f"bos://ecos/workflow/{new_name.lower().replace(' ', '-')}"

    # 写入
    if is_m1:
        M1_WF_DIR.mkdir(parents=True, exist_ok=True)
        dest = M1_WF_DIR / f"{new_wf_id}.yaml"
    else:
        WF_DIR.mkdir(parents=True, exist_ok=True)
        dest = WF_DIR / f"{new_name}.yaml"

    if dest.exists():
        print(f"⚠️ 目标文件已存在: {dest}")
        answer = input("  覆盖? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("已取消。")
            return

    with open(dest, "w") as f:
        yaml.dump(
            new_wf, f, allow_unicode=True, default_flow_style=False, sort_keys=False
        )

    print(f"✅ 工作流已派生: {wf.get('name', name)} → {new_name}")
    print(f"   源: {src_path}")
    print(f"   目标: {dest}")
    print(f"   执行: ecos workflow run '{new_wf_id if is_m1 else dest.stem}'")
    print(f"   验证: ecos workflow validate '{new_wf_id if is_m1 else dest.stem}'")


def _cmd_stats(_args: list[str]) -> None:
    """ecos workflow stats — 运行统计"""
    from collections import Counter

    from ecos.cli.workflow_runs import SNAPSHOT_DIR, _load_all_runs

    runs = _load_all_runs()
    if not runs:
        print("📊 工作流运行统计")
        print(f"{'=' * 50}")
        print("  无运行记录。")
        return

    total = len(runs)
    ok_count = sum(1 for r in runs if r.get("status") == "ok")
    failed_count = sum(1 for r in runs if r.get("status") == "failed")
    total_passed = sum(r.get("result", {}).get("passed", 0) for r in runs)
    total_failed = sum(r.get("result", {}).get("failed", 0) for r in runs)
    success_rate = ok_count / total * 100 if total > 0 else 0

    # 按工作流统计
    wf_counter: Counter = Counter()
    for r in runs:
        wf_id = r.get("workflow_id", "?")
        wf_counter[wf_id] += 1

    top_workflows = wf_counter.most_common(10)

    # 按状态趋势
    recent_10 = runs[:10]
    recent_ok = sum(1 for r in recent_10 if r.get("status") == "ok")
    recent_fail = sum(1 for r in recent_10 if r.get("status") == "failed")

    # 时间范围
    timestamps = [r.get("generated_at", "")[:10] for r in runs if r.get("generated_at")]
    date_range = (
        f"{timestamps[-1]} ~ {timestamps[0]}"
        if len(timestamps) >= 2
        else timestamps[0]
        if timestamps
        else "N/A"
    )

    print("📊 工作流运行统计")
    print(f"{'=' * 50}")
    print(f"  总运行次数:    {total}")
    print(f"  成功率:         {success_rate:.1f}% ({ok_count} ✅ / {failed_count} ❌)")
    print(f"  步骤总计:        {total_passed} ✅ / {total_failed} ❌")
    print(f"  时间范围:        {date_range}")
    print(f"  最近 10 次:      {recent_ok} ✅ / {recent_fail} ❌")
    print(f"  数据源:          {SNAPSHOT_DIR}")
    print()
    if top_workflows:
        print(f"  最活跃工作流 (Top {len(top_workflows)}):")
        for wf_id, count in top_workflows:
            wf_ok = sum(
                1
                for r in runs
                if r.get("workflow_id") == wf_id and r.get("status") == "ok"
            )
            wf_total = count
            pct = wf_ok / wf_total * 100
            bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
            bar = bar[:10]
            print(f"    {bar}  {wf_id:45s}  {wf_ok}/{wf_total} ({pct:.0f}%)")
    print(f"{'=' * 50}")


def _cmd_help(_args: list[str] | None = None) -> None:
    print("用法: ecos workflow <子命令> [参数]")
    print()
    print("子命令:")
    print("  list [-s]               列出所有可用工作流（-s 显示最近运行状态）")
    print("  run <name> [--dry-run]  执行工作流")
    print("    [-p key=value ...]    传递参数给工作流")
    print("  describe <name>         查看工作流定义")
    print("  backends                查看后端注册表")
    print("  actions                 查看已注册 action")
    print("  status                  查看工作流引擎全局状态")
    print("  stats                   查看工作流运行统计")
    print("  create <name>           创建工作流模板")
    print("    [--m1]                生成 M1 格式（默认是简化 definition）")
    print("    [--path <file>]       指定输出路径")
    print("  validate <name>         验证工作流定义")
    print("  test <name>             测试工作流编排（mock action，验证链路）")
    print("  edit <name>             打开编辑器编辑工作流定义")
    print("  fork <name> --as <new>  派生工作流（基于已有创建新工作流）")
    print("  export <name> [--path]  导出工作流为独立文件")
    print("  import <file> [--as]    导入工作流定义")
    print("  logs|runs [选项]        工作流运行历史（同 ecos workflow runs）")
    print()
    print("运行历史选项:")
    print("  --status ok|failed      按状态过滤")
    print("  --recent N              最近 N 条")
    print("  -v, --verbose           显示详细步骤")
    print("  <workflow_id>           查看指定工作流的所有运行")
    print()
    print("示例:")
    print("  ecos workflow list")
    print("  ecos workflow run WORKFLOW-ECOS-DAILY-HEALTH")
    print("  ecos workflow run WORKFLOW-ECOS-DAILY-HEALTH --dry-run")
    print(
        "  ecos workflow run WORKFLOW-ECOS-DAILY-HEALTH -p mode=quick -p verbose=true"
    )
    print("  ecos workflow describe WORKFLOW-ECOS-DAILY-HEALTH")
    print("  ecos workflow backends")
    print("  ecos workflow logs --recent 5")
    print("  ecos workflow logs --status failed --verbose")


# ── 内部格式化 ──


def _print_result(result: dict[str, Any]) -> None:
    """格式化执行结果"""
    steps = result.get("steps", [])
    passed = result.get("passed", 0)
    failed = result.get("failed", 0)
    total = len(steps)

    violations = result.get("violations", [])
    if violations:
        for v in violations:
            icon = "⚠️" if v.get("severity") == "warning" else "❌"
            print(f"  {icon} {v.get('message', '')}")

    print()
    for step in steps:
        status = step.get("status", "?")
        icon = (
            "✅" if status == "ok" else "❌" if status in ("failed", "error") else "➖"
        )
        name = step.get("name", "?")
        res_obj = step.get("result", {})
        if isinstance(res_obj, str):
            result_text = res_obj
            details = ""
        else:
            result_text = res_obj.get("summary", "")
            details = res_obj.get("details", "")
        error = step.get("error", "")
        extra = details or result_text or error
        print(f"  {icon}  {name:30s}  {extra}" if extra else f"  {icon}  {name}")

    print()
    print(f"  结果: {passed}✅  {failed}❌  (共{total}步)")

    m0 = result.get("m0_snapshot")
    if m0:
        print(f"  M0 快照: {m0}")
    finished = result.get("finished", "")
    if finished:
        print(f"  完成时间: {finished[:19].replace('T', ' ')}")


def _cmd_cache_status(*args: str) -> None:
    """ecos workflow cache-status — 查看工作流缓存状态"""
    from ecos.workflow.cache import status

    s = status()
    print(f"工作流缓存: {s['total_entries']} 条目")
    for e in s["entries"]:
        print(f"  {e['key']}: 剩余 {e['remaining_s']}s (TTL {e['ttl_s']}s)")


def _cmd_cache_invalidate(*args: str) -> None:
    """ecos workflow cache-invalidate — 清除全部工作流缓存"""
    from ecos.workflow.cache import invalidate_all

    cleared = invalidate_all()
    print(f"已清除 {cleared} 条缓存条目")


def _cmd_circuit_status(*args: str) -> None:
    """ecos workflow cb-status — 查看后端熔断器状态"""
    from ecos.workflow.circuit_breaker import status

    s = status()
    if s["total_tripped"] == 0:
        print("后端熔断器: 无活跃熔断 ✅")
    else:
        print(f"后端熔断器: {s['total_tripped']} 个活跃熔断")
        for c in s["circuits"]:
            print(f"  {c['key']}: 剩余 {c['remaining_s']}s")
            print(f"    (TTL {c['ttl_s']}s, 已熔断 {c['unreachable_since_s']}s)")


def _cmd_circuit_reset(*args: str) -> None:
    """ecos workflow cb-reset — 重置全部后端熔断器"""
    from ecos.workflow.circuit_breaker import reset_all

    count = reset_all()
    print(f"已重置 {count} 个熔断器")


if __name__ == "__main__":
    main()
