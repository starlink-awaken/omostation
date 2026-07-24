"""Workflow runs CLI — 工作流运行历史查询与管理

用法:
    ecos workflow runs               # 列出所有运行记录
    ecos workflow runs --status failed  # 只列出失败
    ecos workflow runs <workflow_id>  # 查看单条运行详情
    ecos workflow runs --recent 5     # 最近 N 条

M0 snapshots 存储在 ~/.omo/state/workflow-runs/
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

SNAPSHOT_DIR = Path.home() / ".omo" / "state" / "workflow-runs"


def _load_all_runs() -> list[dict[str, Any]]:
    """从 M0 snapshot 目录加载所有运行记录"""
    if not SNAPSHOT_DIR.exists():
        return []
    runs: list[dict[str, Any]] = []
    for f in sorted(SNAPSHOT_DIR.glob("*.yaml"), reverse=True):
        try:
            import yaml

            with open(f) as fh:
                data = yaml.safe_load(fh)
            if data and data.get("schema") == "M0-v1":
                runs.append(data)
        except Exception:  # defensive fallback
            continue
    return runs


def _format_run(run: dict[str, Any], verbose: bool = False) -> str:
    """格式化单条运行记录"""
    wf_id = run.get("workflow_id", "?")
    name = run.get("name", wf_id)
    status = run.get("status", "?")
    passed = run.get("result", {}).get("passed", 0)
    failed = run.get("result", {}).get("failed", 0)
    ts = run.get("generated_at", "")[:19].replace("T", " ")

    status_icon = "✅" if status == "ok" else "❌" if status == "failed" else "➖"
    backend = run.get("execution", {}).get("backend", "?")
    mode = run.get("execution", {}).get("mode", "?")

    line = f"{status_icon} {ts}  {name:35s}  backend={backend:10s} mode={mode:15s}  {passed}✅ {failed}❌"
    if verbose:
        violations = run.get("result", {}).get("violations", [])
        if violations:
            for v in violations:
                line += f"\n    ⚠️  {v.get('message', '')}"
        steps = run.get("result", {}).get("steps", [])
        for s in steps:
            icon = "✅" if s.get("status") == "ok" else "❌"
            line += f"\n    {icon}  {s.get('name', '?')}  ({s.get('status', '?')})"
    return line


def cmd_runs(args: list[str]) -> None:
    """workflow runs 子命令"""
    print("⚠️ ECOS Workflow Runs 独立 CLI 已弃用，请使用 cockpit 替代", file=sys.stderr)
    # 解析参数
    status_filter = None
    wf_id_filter = None
    recent = None
    verbose = False
    detailed_wf = None

    i = 0
    while i < len(args):
        if args[i] == "--status" and i + 1 < len(args):
            status_filter = args[i + 1]
            i += 2
        elif args[i] == "--recent" and i + 1 < len(args):
            recent = int(args[i + 1])
            i += 2
        elif args[i] in ("-v", "--verbose"):
            verbose = True
            i += 1
        elif args[i] == "--help":
            _print_help()
            return
        else:
            # 第一个非 option 参数当作 workflow_id 详情查询
            if detailed_wf is None and not args[i].startswith("--"):
                detailed_wf = args[i]
            i += 1

    if detailed_wf:
        _show_detail(detailed_wf)
        return

    runs = _load_all_runs()

    if not runs:
        print("没有工作流运行记录。")
        return

    # 过滤
    if status_filter:
        runs = [r for r in runs if r.get("status") == status_filter]
    if wf_id_filter:
        runs = [r for r in runs if r.get("workflow_id") == wf_id_filter]
    if recent:
        runs = runs[:recent]

    if not runs:
        print("没有匹配的工作流运行记录。")
        return

    # 统计
    total = len(runs)
    ok_count = sum(1 for r in runs if r.get("status") == "ok")
    failed_count = sum(1 for r in runs if r.get("status") == "failed")
    total_passed = sum(r.get("result", {}).get("passed", 0) for r in runs)
    total_failed = sum(r.get("result", {}).get("failed", 0) for r in runs)

    print(f"📋 工作流运行历史 ({total} 条)")
    print(f"{'=' * 100}")
    for run in runs:
        print(_format_run(run, verbose))
    print(f"{'=' * 100}")
    print(
        f"总计: {total} runs | {ok_count} 成功 {failed_count} 失败 | {total_passed}✅ {total_failed}❌"
    )


def _show_detail(workflow_id: str) -> None:
    """显示单条工作流的所有运行记录"""
    runs = _load_all_runs()
    matched = [r for r in runs if r.get("workflow_id") == workflow_id]

    if not matched:
        print(f"工作流 '{workflow_id}' 无运行记录。")
        return

    print(f"📋 工作流: {workflow_id}")
    print(f"  运行次数: {len(matched)}")
    print()

    for i, run in enumerate(matched, 1):
        print(f"  [{i}] {_format_run(run, verbose=True)}")
        print()


def _print_help() -> None:
    print("用法: ecos workflow runs [选项] [workflow_id]")
    print()
    print("选项:")
    print("  --status ok|failed    按状态过滤")
    print("  --recent N            最近 N 条")
    print("  -v, --verbose         显示详细步骤和违规")
    print("  workflow_id           查看指定工作流的所有运行记录")


if __name__ == "__main__":
    cmd_runs(sys.argv[1:])
