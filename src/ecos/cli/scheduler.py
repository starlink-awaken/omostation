#!/usr/bin/env python3
"""
eCOS Schedule Engine — 轻量调度器

把平台无关的调度描述（schedule/*.yaml）翻译成具体执行：
  kanban driver  → hermes kanban create/link/dispatch
  manual driver  → 输出人类可操作手册

Usage:
  python3 ecos_scheduler.py WF-004 --driver kanban
  python3 ecos_scheduler.py WF-004 --driver manual
  python3 ecos_scheduler.py WF-004 --driver kanban --validate-only
  python3 ecos_scheduler.py WF-004 --status
"""

import json
import os
import subprocess
import sys
import textwrap
from datetime import datetime

import yaml

from ecos.common.common import ECOS_HOME as ECOS_ROOT  # type: ignore[import-not-found]

SCHEDULE_DIR = ECOS_ROOT / "schedule"
BOARD = "ecos"

HERMES_BIN = os.environ.get("HERMES_BIN", "hermes")

# ─── Helpers ───────────────────────────────────


def _run(*args, capture=True):
    """Run hermes CLI command, return stdout."""
    cmd = [HERMES_BIN] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(
            f"⚠️  `{' '.join(cmd)}` failed:\n{r.stderr.strip()[:200]}", file=sys.stderr
        )
        return None
    return r.stdout.strip()


def _kanban(*args):
    """Run hermes kanban --board <BOARD> <subcommand> ..."""
    return _run("kanban", "--board", BOARD, *args)


def _step_tag(schedule_id: str, step: str) -> str:
    """Unique Kanban task title tag for traceability."""
    return f"[{schedule_id}/{step}]"


def _resolve_dep_order(chain):
    """Topological sort with cycle detection."""
    by_id = {s["step"]: s for s in chain}
    depths = {}
    visiting = set()  # cycle detection

    def _depth(step_id):
        if step_id in depths:
            return depths[step_id]
        if step_id in visiting:
            raise ValueError(f"Circular dependency detected: {step_id}")
        visiting.add(step_id)
        deps = by_id[step_id].get("depends_on", [])
        if not deps:
            depths[step_id] = 0
        else:
            depths[step_id] = 1 + max(_depth(d) for d in deps)
        visiting.discard(step_id)
        return depths[step_id]

    for s in chain:
        _depth(s["step"])
    return sorted(chain, key=lambda s: depths[s["step"]])


# ─── Validator ─────────────────────────────────


def validate(schedule: dict) -> list:
    """Validate schedule descriptor structure. Return list of issues."""
    issues = []
    if "id" not in schedule:
        issues.append("Missing 'id'")
    if "chain" not in schedule or not isinstance(schedule["chain"], list):
        issues.append("Missing or invalid 'chain'")
    if not issues:
        step_ids = {s["step"] for s in schedule["chain"]}
        for s in schedule["chain"]:
            for dep in s.get("depends_on", []):
                if dep not in step_ids:
                    issues.append(f"Step {s['step']} depends on missing step '{dep}'")
    return issues


# ─── Drivers ──────────────────────────────────


def run_kanban_driver(schedule: dict, validate_only: bool = False):
    """Create tasks + dependencies on Kanban board."""
    sid = schedule["id"]
    roles = schedule.get("roles", {})
    chain = _resolve_dep_order(schedule["chain"])

    print(f"═══ Kanban Driver: {sid} ═══")
    print(f"Board: {BOARD}  |  Steps: {len(chain)}")
    print()

    task_ids = {}  # step -> kanban task id

    for step in chain:
        step_id = step["step"]
        role_name = step["role"]
        role_info = roles.get(role_name, {})
        assignee = role_info.get("assignee", role_name)
        action = step.get("name", step_id)
        detail = step.get("action", "")
        step.get("parallelism", 1)

        title = f"{_step_tag(sid, step_id)} {action}"

        if validate_only:
            print(f"  [DRY-RUN] Would create: {title}")
            print(f"            assignee: {assignee}")
            if step.get("depends_on"):
                print(f"            depends: {step['depends_on']}")
            print()
            continue

        # Create the task
        result = _kanban(
            "create",
            title,
            "--body",
            detail,
            "--assignee",
            assignee,
            "--tenant",
            sid.lower(),
            "--json",
        )
        if result is None:
            print(f"  ❌ Failed to create task for {step_id}")
            continue

        try:
            data = json.loads(result)
            task_id = data.get("id") or data.get("kanban_id", "")
            task_ids[step_id] = task_id
            print(f"  ✅ {step_id} → task {task_id} ({assignee})")
        except (json.JSONDecodeError, KeyError):
            task_id = ""
            print(f"  ⚠️  Created {step_id} but couldn't parse ID: {result[:80]}")

        # Link dependencies
        for dep in step.get("depends_on", []):
            parent_id = task_ids.get(dep)
            if parent_id:
                _kanban("link", parent_id, task_id)
                print(f"     linked ← {dep} ({parent_id})")

    if validate_only:
        print("  ✅ Dry-run complete. No tasks created.")
    else:
        print(f"\nTasks ready. Run `hermes kanban list --board {BOARD}` to see them.")

    return task_ids


def run_manual_driver(schedule: dict):
    """Output human-readable step-by-step instructions."""
    sid = schedule["id"]
    roles = schedule.get("roles", {})
    chain = _resolve_dep_order(schedule["chain"])

    print(f"═══ Manual Mode: {sid} ═══")
    print(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

    for i, step in enumerate(chain, 1):
        step_id = step["step"]
        role_name = step["role"]
        assignee = roles.get(role_name, {}).get("assignee", role_name)
        action = step.get("name", step_id)
        detail = step.get("action", "")
        parallelism = step.get("parallelism", 1)
        deps = step.get("depends_on", [])

        print(f"─── Step {i}: {step_id} — {action} ───")
        print(f"  角色: {role_name} (assignee: {assignee})")
        if parallelism > 1:
            print(f"  并行副本: {parallelism}")
        if deps:
            print(f"  等待: {', '.join(deps)}")
        print()
        print(
            textwrap.fill(
                detail, width=72, initial_indent="  任务: ", subsequent_indent="       "
            )
        )
        print()

        if step["step"] == "S05":
            # 归档步骤的特殊指引
            print("  输出验证:")
            print("    □ STATE.yaml 已更新")
            print("    □ HANDOFF/LATEST.md 已写入")
            print("    □ ADR 已创建或更新")
            print("    □ FAILURES（如有失败/偏差）已记录")
        else:
            print("  预期输出: " + step.get("output", "(无明确输出定义)"))
        print()

    print("─── 完成条件 ───")
    print(f"  □ 所有 {len(chain)} 步执行完毕")
    print("  □ 中间产物在 workspace 中可检索")
    print("  □ 决策记录写入 ADR")
    print("  □ HANDOFF 更新")


def show_status(schedule: dict):
    """Show Kanban task status for this schedule's tasks."""
    sid = schedule["id"]
    _step_tag(sid, "")

    result = _kanban("list", "--tenant", sid.lower(), "--json")
    if not result:
        print(f"No tasks for {sid} on board '{BOARD}'")
        return

    try:
        tasks = json.loads(result)
    except json.JSONDecodeError:
        print(f"Raw output:\n{result}")
        return

    if isinstance(tasks, dict):
        tasks = [tasks]

    print(f"═══ Status: {sid} ═══")
    for t in tasks:
        tid = t.get("id", "?")
        status = t.get("status", "?")
        title = t.get("title", "?")
        assignee = t.get("assignee", "?")
        print(f"  {status:12s} | {tid:10s} | {assignee:8s} | {title}")
    print()


# ─── Entry ────────────────────────────────────


def load_schedule(schedule_id: str) -> dict:
    """Load YAML schedule by ID (e.g. 'WF-004')."""
    files = list(SCHEDULE_DIR.glob(f"{schedule_id}.yaml")) or list(
        SCHEDULE_DIR.glob(f"{schedule_id}.yml")
    )
    if not files:
        print(f"❌ Schedule '{schedule_id}' not found in {SCHEDULE_DIR}")
        known = [f.stem for f in SCHEDULE_DIR.glob("*.yaml")] + [
            f.stem for f in SCHEDULE_DIR.glob("*.yml")
        ]
        if known:
            print(f"   Known schedules: {', '.join(known)}")
        sys.exit(1)
    with open(files[0]) as f:
        return yaml.safe_load(f)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h"):
        print(__doc__)
        print("Available schedules:")
        for f in sorted(SCHEDULE_DIR.glob("*.yaml")) + sorted(
            SCHEDULE_DIR.glob("*.yml")
        ):
            print(f"  {f.stem}")
        sys.exit(0)

    schedule_id = sys.argv[1]
    driver = "kanban"
    validate_only = False

    for arg in sys.argv[2:]:
        if arg.startswith("--driver="):
            driver = arg.split("=", 1)[1]
        elif arg == "--validate-only":
            validate_only = True
        elif arg == "--status":
            driver = "status"

    schedule = load_schedule(schedule_id)

    # Validate
    issues = validate(schedule)
    if issues:
        print(f"❌ Validation issues for {schedule_id}:")
        for i in issues:
            print(f"  • {i}")
        sys.exit(1)

    if driver == "kanban":
        run_kanban_driver(schedule, validate_only)
    elif driver == "manual":
        run_manual_driver(schedule)
    elif driver == "status":
        show_status(schedule)
    else:
        print(f"❌ Unknown driver: {driver}")
        print("   Available: kanban, manual, status")
        sys.exit(1)


if __name__ == "__main__":
    main()
