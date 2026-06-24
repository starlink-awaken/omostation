#!/usr/bin/env python3
"""OMO state CLI — show system state from state/."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from .omo_ingress import write_system_projection_fields
from .omo_paths import find_omo_dir
from .omo_shared import load_yaml, load_yaml_required


def _find_omo_dir() -> Path:
    return find_omo_dir()


def cmd_state_show(omo_dir: Path, fmt: str) -> int:
    state_file = omo_dir / "state" / "system.yaml"
    if not state_file.exists():
        print("⚠️  state/system.yaml not found")
        return 0
    data = load_yaml_required(state_file)
    if fmt == "json":
        print(json.dumps(data, indent=2, default=str))
        return 0
    governance = data.get("governance", {}) if isinstance(data, dict) else {}
    code_freeze = (
        governance.get("code_freeze")
        if isinstance(governance, dict) and "code_freeze" in governance
        else data.get("code_freeze", False)
    )
    # Tabular format
    print(f"Phase:          {data.get('current_phase', '?')}")
    print(f"Health:         {data.get('health_score', '?')}")
    print(f"Active agents:  {data.get('active_agents', 0)}")
    print(f"Idle agents:    {data.get('idle_agents', 0)}")
    print(f"Blocked tasks:  {data.get('blocked_tasks', 0)}")
    print(f"Code freeze:    {code_freeze}")
    print(f"Next milestone: {data.get('next_milestone', '?')}")
    return 0


def cmd_state_health(omo_dir: Path) -> int:
    health_file = omo_dir / "state" / "system_health.yaml"
    if not health_file.exists():
        print("⚠️  state/system_health.yaml not found")
        return 0
    data = load_yaml_required(health_file)
    svc_dict = data.get("services", {}) if isinstance(data, dict) else {}
    running = 0
    failed = 0
    for name, svc in svc_dict.items():
        if isinstance(svc, dict):
            st = (
                svc.get("health_check")
                or svc.get("runtime", {}).get("status", "")
                or ""
            )
            if st == "healthy":
                running += 1
            elif st in ("failed", "stopped"):
                failed += 1
    total = len(svc_dict)
    print(f"Services: {total} total ({running} healthy, {failed} degraded)")
    print()
    for name, svc in svc_dict.items():
        if not isinstance(svc, dict):
            continue
        st = svc.get("health_check") or svc.get("runtime", {}).get("status", "") or "?"
        icon = (
            "🟢"
            if st == "healthy"
            else "🟡"
            if st in ("idle", "unmanaged")
            else "🔴"
            if st in ("failed", "stopped")
            else "⚪"
        )
        detail = svc.get("name", name)
        print(f"  {icon} {detail}: {st}")
    return 0


def cmd_state_refresh(omo_dir: Path, dry_run: bool) -> int:
    """Scan runtime Matrix and refresh system_health.yaml.

    Queries:
    1. Runtime CLI: `runtime matrix list` — service registry
    2. KEI audit: `~/.runtime/data/kei_audit.jsonl` — recent audit records
    3. Agora health: `:7430/health` — Agora status
    """
    import subprocess
    import time

    health_file = omo_dir / "state" / "system_health.yaml"
    current_data = load_yaml(health_file) if health_file.exists() else {"services": {}}
    services = (
        current_data.get("services", {}) if isinstance(current_data, dict) else {}
    )
    now = time.time()

    updates = 0
    # 1. Query runtime Matrix for service list
    runtime_root = Path.home() / "Workspace" / "projects" / "runtime"
    try:
        result = subprocess.run(
            [
                "uv",
                "run",
                "--directory",
                str(runtime_root),
                "runtime",
                "matrix",
                "list",
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            import json as _json

            matrix_data = _json.loads(result.stdout)
            for svc in matrix_data if isinstance(matrix_data, list) else []:
                name = svc.get("name", "?")
                svc_status = svc.get("status", "unknown")
                port = svc.get("port")
                if name not in services:
                    services[name] = {"name": name, "health_check": "unknown"}
                services[name]["runtime"] = {
                    "status": svc_status,
                    "port": port,
                    "timestamp": now,
                    "freshness_seconds": 0,
                }
                updates += 1
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("⚠️  Runtime Matrix query failed (runtime CLI not available)")

    # 2. Update health_check based on runtime status
    #    running/idle/active  → healthy
    #    configured           → scheduled
    #    failed/stopped       → failed
    #    (missing/unknown)    → unmanaged
    for name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        rt = svc.get("runtime", {})
        if isinstance(rt, dict):
            rst = rt.get("status", "")
            if rst in ("running", "idle", "active"):
                svc["health_check"] = "healthy"
                svc["port_listening"] = bool(rt.get("port"))
            elif rst == "configured":
                svc["health_check"] = "scheduled"
            elif rst in ("failed", "stopped"):
                svc["health_check"] = "failed"

    # 3. Write back
    output = {"last_scan": now, "services": services}
    if dry_run:
        print(json.dumps(output, indent=2, default=str))
        print(f"\n(dry-run: {updates} services would be updated)")
    else:
        health_file.write_text(
            yaml.dump(output, default_flow_style=False, allow_unicode=True)
        )
        print(f"✅ system_health.yaml refreshed: {updates} services updated")
    return 0


def _read_task_title(task_file: Path) -> str:
    """读 task yaml 的 title 字段 (DRY: 复用 cmd_task_list 的前几行解析口径).

    不用完整 yaml.load — task 文件较大时省 IO, 只取头部 title 行即可.
    """
    try:
        for line in task_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("title:"):
                return line.split(":", 1)[1].strip().strip("\"'")[:48]
            if line.startswith("status:") or line.startswith("description:"):
                break
    except OSError:
        pass
    return "(no title)"


def cmd_state_sync_tasks(omo_dir: Path, dry_run: bool) -> int:
    """从 tasks/ 真实文件数重算 system.yaml 计数 (治本: 真源=目录, 计数是派生缓存).

    系统思维 OPT-7: system.yaml 的 completed/planned/active/total_tasks 和
    next_planned_tasks/next_active_tasks 手动维护 → 归档任务后漂移
    (上轮归档 2 任务后 completed 88 vs 实际 90, next_planned_tasks 残留已归档的
    TASK-KAIRON-MYPY-STRICT 僵尸数据). 此命令从 tasks/{active,planned,done}
    真实文件重算, 根治"手动维护→漂移".

    SSOT 铁律不违背: task 目录是真源 (state plane), system.yaml 计数是派生缓存,
    sync 让两者对齐 (非凭空写数). drafts/ 不算正式 task (同 cmd_task_list 口径).
    """
    import datetime as _dt

    state_file = omo_dir / "state" / "system.yaml"
    if not state_file.exists():
        print("⚠️  state/system.yaml not found")
        return 1
    data = load_yaml_required(state_file)
    if not isinstance(data, dict):
        print("⚠️  state/system.yaml 顶层非 dict, 跳过")
        return 1

    # 真源: tasks/{active,planned,done} 真实文件 (drafts 不算正式 task)
    counts: dict[str, int] = {}
    by_id: dict[str, list[str]] = {}
    for sub in ("active", "planned", "done"):
        d = omo_dir / "tasks" / sub
        files = sorted(d.glob("*.yaml")) if d.exists() else []
        counts[sub] = len(files)
        if sub in ("active", "planned"):
            by_id[sub] = [f"{f.stem} ({_read_task_title(f)})" for f in files]

    active_n, planned_n, done_n = counts["active"], counts["planned"], counts["done"]
    total_n = active_n + planned_n + done_n
    new_active_list = by_id.get("active", [])
    new_planned_list = by_id.get("planned", [])

    old = {
        "completed_tasks": data.get("completed_tasks"),
        "planned_tasks": data.get("planned_tasks"),
        "active_tasks": data.get("active_tasks"),
        "total_tasks": data.get("total_tasks"),
    }
    updated_at = (
        _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    updates = {
        "completed_tasks": done_n,
        "planned_tasks": planned_n,
        "active_tasks": active_n,
        "total_tasks": total_n,
        "next_active_tasks": new_active_list or ["(No active tasks)"],
        "next_planned_tasks": new_planned_list,
        "updated_at": updated_at,
    }
    data.update(updates)

    if dry_run:
        print("=== sync-tasks (dry-run) ===")
        for k in ("completed_tasks", "planned_tasks", "active_tasks", "total_tasks"):
            print(f"  {k}: {old[k]} → {data[k]}")
        print(f"  next_planned_tasks: {len(new_planned_list)} 项 (从 planned/ 重建)")
        print(f"  next_active_tasks:  {len(new_active_list)} 项 (从 active/ 重建)")
        return 0

    write_system_projection_fields(
        omo_dir,
        updates=updates,
        actor="omo state sync-tasks",
        source_ref="omo-state:sync-tasks",
        now=updated_at,
        allowed_fields={
            "completed_tasks",
            "planned_tasks",
            "active_tasks",
            "total_tasks",
            "next_active_tasks",
            "next_planned_tasks",
            "updated_at",
        },
    )
    print("✅ system.yaml task 计数已同步 (真源=tasks/ 目录)")
    for k in ("completed_tasks", "planned_tasks", "active_tasks", "total_tasks"):
        print(f"  {k}: {old[k]} → {data[k]}")
    print(
        f"  next_planned_tasks: {len(new_planned_list)} 项 (从 planned/ 重建, 僵尸已清)"
    )
    print(f"  next_active_tasks:  {len(new_active_list)} 项 (从 active/ 重建)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omo state", description="OMO system state viewer"
    )
    sub = parser.add_subparsers(dest="command")
    sp = sub.add_parser("show", help="Show system state")
    sp.add_argument("--format", "-f", choices=["text", "json"], default="text")
    sub.add_parser("health", help="Show service health")
    rp = sub.add_parser(
        "refresh", help="Scan runtime Matrix and refresh system_health.yaml"
    )
    rp.add_argument(
        "--dry-run", action="store_true", help="Preview changes without writing"
    )
    stp = sub.add_parser(
        "sync-tasks",
        help="从 tasks/ 真实文件数重算 system.yaml 计数 (治本手动维护漂移)",
    )
    stp.add_argument(
        "--dry-run", action="store_true", help="Preview changes without writing"
    )
    args = parser.parse_args(argv)
    omo_dir = _find_omo_dir()
    if args.command == "show":
        return cmd_state_show(omo_dir, args.format)
    elif args.command == "health":
        return cmd_state_health(omo_dir)
    elif args.command == "refresh":
        return cmd_state_refresh(omo_dir, dry_run=args.dry_run)
    elif args.command == "sync-tasks":
        return cmd_state_sync_tasks(omo_dir, dry_run=args.dry_run)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
