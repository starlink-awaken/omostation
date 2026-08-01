#!/usr/bin/env python3
"""OMO state CLI — show system state from state/."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from .omo_ingress import write_system_projection_fields
from .omo_ingress_state import sync_state_projection
from .omo_io import write_text_atomic
from .omo_paths import find_omo_dir
from .omo_shared import load_yaml, load_yaml_required


def _find_omo_dir() -> Path:
    return find_omo_dir()


def _emit(msg: str, *, quiet: bool = False) -> None:
    """Human diagnostics: stdout by default; stderr when quiet (JSON parent).

    Keeps machine-readable JSON on stdout free of warning/progress noise.
    """
    print(msg, file=sys.stderr if quiet else sys.stdout)


def cmd_state_show(omo_dir: Path, fmt: str) -> int:
    state_file = omo_dir / "state" / "system.yaml"
    if not state_file.exists():
        # warnings never pollute JSON stdout
        print(
            "⚠️  state/system.yaml not found",
            file=sys.stderr if fmt == "json" else sys.stdout,
        )
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
    canonical_health_file = omo_dir / "state" / "runtime" / "system_health.yaml"
    legacy_health_file = omo_dir / "state" / "system_health.yaml"
    health_file = (
        canonical_health_file if canonical_health_file.exists() else legacy_health_file
    )
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

    canonical_health_file = omo_dir / "state" / "runtime" / "system_health.yaml"
    legacy_health_file = omo_dir / "state" / "system_health.yaml"
    health_file = (
        canonical_health_file if canonical_health_file.exists() else legacy_health_file
    )
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
        payload = yaml.dump(output, default_flow_style=False, allow_unicode=True)
        write_text_atomic(canonical_health_file, payload)
        write_text_atomic(
            legacy_health_file,
            payload,
        )
        health_file = canonical_health_file
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
            if line.startswith(("status:", "description:")):
                break
    except OSError:
        pass
    return "(no title)"


def _rebuild_tasks_registry_index(
    omo_dir: Path,
    planned_list: list[str],
    done_n: int,
    updated_at: str,
) -> bool:
    """重建 tasks/registry/INDEX.md 动态段 (Planned 表 + 标题计数 + Updated 行).

    治本: sync-tasks 之前只刷 system.yaml, INDEX.md 手维护 → planned_tasks_ref
    指针长期指向过期文档 (2026-06-29 发现 INDEX 写 planned=1/done=114 的 06-24
    旧值, 实际 14/91). INDEX.md 自述"由验证流程生成, 与实际目录保持同步", 同
    system.yaml 计数一样从 tasks/ 真源派生, sync 时一并刷, 根治指针漂移.

    保留段 (手维护不动): Active 正文 / Completed 里程碑列表 / Archived / Blocked.
    刷新段 (派生): Planned Tasks 表格 + Planned/Completed 标题计数 + Updated 行.

    Returns False 当 INDEX 缺失或结构不符预期 (不报错, 保留手维护兜底).
    """
    import re

    index_file = omo_dir / "tasks" / "registry" / "INDEX.md"
    if not index_file.exists():
        return False
    text = index_file.read_text(encoding="utf-8")
    planned_n = len(planned_list)

    # Planned 表格 (ID | Title | candidate) — title 清洗 | 与换行避免破坏表格
    rows: list[str] = []
    for item in planned_list:
        tid, _, rest = item.partition(" (")
        title = rest.rstrip(")").replace("|", "/").replace("\n", " ").strip()[:80]
        rows.append(f"| {tid} | {title} | candidate |")
    table = (
        "| ID | Title | Status |\n|----|-------|--------|\n" + "\n".join(rows) + "\n\n"
    )

    # 1. Planned Tasks 段 (## 标题 → 补充规划注释前, 表格整段重建)
    text, n1 = re.subn(
        r"(## Planned Tasks \()\d+( 个\)\n).*?(> \*\*补充规划\*\*)",
        lambda m: f"{m.group(1)}{planned_n}{m.group(2)}{table}{m.group(3)}",
        text,
        count=1,
        flags=re.DOTALL,
    )
    # 2. Completed Tasks 标题计数 (匹配 \d+ 替换, 非 f-string 插值)
    text, _ = re.subn(
        r"(## Completed Tasks \()\d+( 个\))",
        lambda m: f"{m.group(1)}{done_n}{m.group(2)}",
        text,
    )

    # 3. Updated 行 (整行替换, capture 原 archived 数保留)
    def _repl_updated(m: re.Match[str]) -> str:
        archived = m.group(1)
        return (
            f"*Updated: {updated_at[:10]} (依据 `omo state sync-tasks` 与真实目录重算: "
            f"done={done_n}, planned={planned_n}, active=0, archived={archived} 顶层)*"
        )

    text, n3 = re.subn(
        r"\*Updated: \d{4}-\d{2}-\d{2}.*?archived=(\d+)[^\n]*\*",
        _repl_updated,
        text,
    )
    # 4. Completed 段正文 "tasks/done/ — N 个顶层 YAML 文件" (与标题计数同源, 防正文残留)
    text, _ = re.subn(
        r"(`tasks/done/`\s+—\s+)\d+( 个顶层)",
        lambda m: f"{m.group(1)}{done_n}{m.group(2)}",
        text,
    )
    if not (n1 and n3):
        return False  # INDEX 结构不符预期, 跳过 (n2/n4 可能为 0 若已是正确数, 不卡)
    write_text_atomic(
        index_file, text
    )  # sensitive-governed-writes: atomic helper 豁免 (P1 CI 修复)
    return True


def cmd_state_sync_tasks(omo_dir: Path, dry_run: bool, *, quiet: bool = False) -> int:
    """从 tasks/ 真实文件数重算 system.yaml 计数 (治本: 真源=目录, 计数是派生缓存).

    系统思维 OPT-7: system.yaml 的 completed/planned/active/total_tasks 和
    next_planned_tasks/next_active_tasks 手动维护 → 归档任务后漂移
    (上轮归档 2 任务后 completed 88 vs 实际 90, next_planned_tasks 残留已归档的
    TASK-KAIRON-MYPY-STRICT 僵尸数据). 此命令从 tasks/{active,planned,done}
    真实文件重算, 根治"手动维护→漂移".

    SSOT 铁律不违背: task 目录是真源 (state plane), system.yaml 计数是派生缓存,
    sync 让两者对齐 (非凭空写数). drafts/ 不算正式 task (同 cmd_task_list 口径).

    quiet=True: 诊断输出到 stderr (供 state sync --json 嵌套调用, 避免污染 stdout).
    """
    import datetime as _dt

    state_file = omo_dir / "state" / "system.yaml"
    if not state_file.exists():
        _emit("⚠️  state/system.yaml not found", quiet=quiet)
        return 1
    data = load_yaml_required(state_file)
    if not isinstance(data, dict):
        _emit("⚠️  state/system.yaml 顶层非 dict, 跳过", quiet=quiet)
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
        _dt.datetime.now(_dt.UTC)
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
        _emit("=== sync-tasks (dry-run) ===", quiet=quiet)
        for k in ("completed_tasks", "planned_tasks", "active_tasks", "total_tasks"):
            _emit(f"  {k}: {old[k]} → {data[k]}", quiet=quiet)
        _emit(
            f"  next_planned_tasks: {len(new_planned_list)} 项 (从 planned/ 重建)",
            quiet=quiet,
        )
        _emit(
            f"  next_active_tasks:  {len(new_active_list)} 项 (从 active/ 重建)",
            quiet=quiet,
        )
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
    # 治本: 同步重建 tasks/registry/INDEX.md (之前只刷 system.yaml, INDEX 手维护→指针漂移)
    index_ok = _rebuild_tasks_registry_index(
        omo_dir,
        planned_list=new_planned_list,
        done_n=done_n,
        updated_at=updated_at,
    )
    _emit("✅ system.yaml task 计数已同步 (真源=tasks/ 目录)", quiet=quiet)
    for k in ("completed_tasks", "planned_tasks", "active_tasks", "total_tasks"):
        _emit(f"  {k}: {old[k]} → {data[k]}", quiet=quiet)
    _emit(
        f"  next_planned_tasks: {len(new_planned_list)} 项 (从 planned/ 重建, 僵尸已清)",
        quiet=quiet,
    )
    _emit(
        f"  next_active_tasks:  {len(new_active_list)} 项 (从 active/ 重建)",
        quiet=quiet,
    )
    if index_ok:
        _emit(
            f"  tasks/registry/INDEX.md: Planned 表+计数+Updated 已重建 "
            f"(planned={planned_n}, done={done_n})",
            quiet=quiet,
        )
    else:
        _emit(
            "  ⚠️ tasks/registry/INDEX.md 未重建 (缺失或结构不符, 保留手维护)",
            quiet=quiet,
        )
    return 0


def cmd_state_sync(omo_dir: Path, dry_run: bool, fmt: str) -> int:
    """Sync high-churn runtime projections through the state broker."""
    quiet = fmt == "json"
    try:
        report = sync_state_projection(omo_dir.parent, dry_run=dry_run)
    except Exception as exc:
        print(
            f"⚠️  state projection sync failed: {exc}",
            file=sys.stderr if quiet else sys.stdout,
        )
        return 1

    # ADR-0231 §D2: main sync 也应重算 task 计数, 否则 system.yaml 的
    # completed_tasks/total_tasks/planned_tasks/active_tasks 与物理 SSOT 漂移
    # (sync-tasks 子命令用户很少单独跑, 计数成为手维护隐性债).
    sync_tasks_rc = cmd_state_sync_tasks(omo_dir, dry_run=dry_run, quiet=quiet)
    if sync_tasks_rc != 0 and not dry_run:
        print(
            f"⚠️  sync-tasks 重算失败 (rc={sync_tasks_rc}), 不阻塞主 sync",
            file=sys.stderr if quiet else sys.stdout,
        )

    if fmt == "json":
        # Pure JSON on stdout only — nested diagnostics already redirected to stderr.
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    mode = "dry-run" if dry_run else "apply"
    print(f"state-sync ({mode}): changed={report['changed_count']}")
    for item in report["writes"]:
        marker = "changed" if item["changed"] else "same"
        print(f"  - {marker}: {item['path']}")
    if report.get("artifact_ref"):
        print(f"  artifact: {report['artifact_ref']}")
    return 0


def cmd_state_set(omo_dir: Path, key: str, value: str, fmt: str) -> int:
    """Set a state field via OMO broker — validates write-owners and writes atomically."""
    state_file = omo_dir / "state" / "system.yaml"
    if not state_file.exists():
        print("❌ state/system.yaml not found")
        return 1

    # Validate key exists in write-owners registry
    write_owners = omo_dir / "_truth" / "registry" / "write-owners.yaml"
    state_owners: dict[str, str] = {}
    if write_owners.exists():
        wo_data = load_yaml_required(write_owners)
        fields = wo_data.get("fields", {})
        state_owners = fields.get(".omo/state/system.yaml", {})

    if state_owners and key not in state_owners:
        allowed = ", ".join(sorted(state_owners.keys()))
        print(f"❌ '{key}' is not a registered write field")
        print(f"   Allowed fields in system.yaml: {allowed}")
        return 1

    # Parse value (try int/float first, then keep string)
    parsed: int | float | str = value
    try:
        parsed = int(value)
    except ValueError:
        try:
            parsed = float(value)
        except ValueError:
            parsed = value

    # Load, update, write atomically
    data = load_yaml_required(state_file)
    data[key] = parsed
    raw = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    write_text_atomic(state_file, raw)

    print(f"✅ {key} = {parsed}")
    if state_owners:
        print(f"   (write owner: {state_owners.get(key, 'unregistered')})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omo state", description="OMO system state viewer"
    )
    sub = parser.add_subparsers(dest="command")
    sp = sub.add_parser("show", help="Show system state")
    sp.add_argument("--format", "-f", choices=["text", "json"], default="text")
    sub.add_parser("health", help="Show service health")
    setp = sub.add_parser("set", help="Set a state field via OMO broker")
    setp.add_argument("key", help="Field name (e.g. current_phase)")
    setp.add_argument("value", help="Field value (auto-parsed as int/float/str)")
    setp.add_argument("--format", "-f", choices=["text", "json"], default="text")
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
    syncp = sub.add_parser(
        "sync",
        help="Sync runtime projections through the OMO state broker",
    )
    syncp.add_argument(
        "--dry-run", action="store_true", help="Preview changes without writing"
    )
    syncp.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args(argv)
    omo_dir = _find_omo_dir()
    if args.command == "show":
        return cmd_state_show(omo_dir, args.format)
    elif args.command == "health":
        return cmd_state_health(omo_dir)
    elif args.command == "set":
        return cmd_state_set(omo_dir, args.key, args.value, args.format)
    elif args.command == "refresh":
        return cmd_state_refresh(omo_dir, dry_run=args.dry_run)
    elif args.command == "sync-tasks":
        return cmd_state_sync_tasks(omo_dir, dry_run=args.dry_run)
    elif args.command == "sync":
        return cmd_state_sync(
            omo_dir,
            dry_run=args.dry_run,
            fmt="json" if args.json else "text",
        )
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
