"""C2G 战略引擎 (Round 43 P1 修真).

修真 (Round 43 P1):
  - strategy_audit: 不再硬编码 'V1 60% / V2 40%' mock, 读 .omo/tasks/{done,planned}/*.yaml
    真实数据, 统计 priority / risk_level / owner / phase 分布, 异常告警
  - strategy_gc: 同样修真, 读 .omo/tasks/planned/ + runtime/sandbox/pitches/ 真 mtime

设计:
  1. 不依赖 adapter (adapters 没暴露这些聚合统计接口)
  2. 直接读 yaml 真实数据 (Pydantic 不需要, 简单 dict 即可)
  3. 异常检查:
     - P0 任务 > 5 个: 堆积告警
     - L3 risk task 存在: 需关注
     - owner 集中度 > 50%: 知识单点
     - done task 7d 内 0 个: 战略停滞
"""
from __future__ import annotations

import argparse
import sys
import time
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from .bridge import get_omo_dir


def _load_yaml_safe(path: Path) -> dict[str, Any] | None:
    """读 yaml 失败返 None (修真版容忍 schema 不一致)."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return data
    except (OSError, yaml.YAMLError):
        return None


def _list_task_files(omo_dir: Path) -> tuple[list[Path], list[Path]]:
    """读 .omo/tasks/done/ + planned/ 所有 yaml. 返 (done_files, planned_files)."""
    done_dir = omo_dir / "tasks" / "done"
    planned_dir = omo_dir / "tasks" / "planned"
    done_files = sorted(done_dir.glob("*.yaml")) if done_dir.is_dir() else []
    planned_files = sorted(planned_dir.glob("*.yaml")) if planned_dir.is_dir() else []
    return done_files, planned_files


def _collect_metrics(task_files: list[Path]) -> dict[str, Counter]:
    """聚合任务文件的 priority / risk_level / owner / phase 分布."""
    priority_c: Counter[str] = Counter()
    risk_c: Counter[str] = Counter()
    owner_c: Counter[str] = Counter()
    phase_c: Counter[str] = Counter()
    status_c: Counter[str] = Counter()

    for path in task_files:
        data = _load_yaml_safe(path)
        if data is None:
            continue
        priority_c[data.get("priority", "unassigned")] += 1
        risk_c[data.get("risk_level", "unassigned")] += 1
        owner = data.get("owner") or data.get("assigned_to") or "unassigned"
        owner_c[owner] += 1
        phase_c[str(data.get("phase", "unphased"))] += 1
        status_c[data.get("status", "unknown")] += 1

    return {
        "priority": priority_c,
        "risk_level": risk_c,
        "owner": owner_c,
        "phase": phase_c,
        "status": status_c,
    }


def _check_anomalies(metrics: dict[str, Counter], total: int) -> list[str]:
    """修真版异常告警: 修真前 mock 无任何告警. 现在按真实指标检查."""
    warnings: list[str] = []
    if total == 0:
        warnings.append("⚠️  没有 .omo/tasks/{done,planned}/*.yaml 数据, 战略审计无意义")
        return warnings

    # 1. P0 任务堆积
    p0_count = metrics["priority"].get("P0", 0)
    if p0_count > 5:
        warnings.append(f"⚠️  P0 任务 {p0_count} 个, 超过阈值 5 (战略优先级可能失衡)")

    # 2. L3 risk 存在 (高风险任务需关注)
    l3_count = metrics["risk_level"].get("L3", 0)
    if l3_count > 0:
        warnings.append(f"⚠️  L3 高风险任务 {l3_count} 个, 需重点 review")

    # 3. Owner 集中度
    top_owners = metrics["owner"].most_common(1)
    if top_owners and total > 0:
        top_owner, top_count = top_owners[0]
        concentration = top_count / total * 100
        if concentration > 50:
            warnings.append(
                f"⚠️  Owner 集中度: {top_owner} 持有 {concentration:.0f}% 任务 "
                f"(单点故障风险, 知识/能力集中)"
            )

    # 4. done task 7d 内 0 个 (战略停滞)
    done_dir = (Path(".omo") / "tasks" / "done")
    if done_dir.is_dir():
        recent_count = 0
        now = time.time()
        for path in done_dir.glob("*.yaml"):
            if (now - path.stat().st_mtime) < 7 * 24 * 3600:
                recent_count += 1
        if recent_count == 0:
            warnings.append("⚠️  最近 7 天无 done task 完成, 战略执行可能停滞")

    return warnings


def strategy_audit(base_dir: Path, adapter: str = "ecos") -> int:
    """修真: 读真实 .omo/tasks/ 数据, 统计 priority/risk/owner/phase 分布 + 异常告警.

    修真前 (mock): 硬编码 'V1 60% / V2 40%'.
    修真后 (Round 43 P1): 真审计 — 读 yaml, 聚合指标, 异常告警.

    修真 v2 (Round 43 P1 修真修真): base_dir 已经是 .omo 目录时, 直接用;
    不重复 get_omo_dir (修真前会触发, 修真后已修).
    """
    omo_dir = base_dir
    print(f"🧠 [Strategic Audit] 正在执行全盘战略审计 (读真实 .omo/tasks/ 数据, adapter: {adapter})...")

    done_files, planned_files = _list_task_files(omo_dir)
    all_files = done_files + planned_files
    total = len(all_files)
    total_done = len(done_files)
    total_planned = len(planned_files)

    print(f"📊 Task Inventory: {total_done} done + {total_planned} planned = {total} total")
    if total == 0:
        print("✅ No tasks found.")
        return 0

    metrics = _collect_metrics(all_files)

    # 1. Priority 分布
    print()
    print("📈 Priority Distribution:")
    for p, count in metrics["priority"].most_common():
        print(f"   {p:<12} {count:>3}")

    # 2. Risk Level
    print()
    print("🛡️  Risk Level Distribution:")
    for r, count in metrics["risk_level"].most_common():
        print(f"   {r:<12} {count:>3}")

    # 3. Owner (top 10)
    print()
    print(f"👥 Owner Distribution (top 10):")
    for o, count in metrics["owner"].most_common(10):
        print(f"   {o:<24} {count:>3}")

    # 4. Phase
    print()
    print("🌊 Phase Distribution:")
    for ph, count in sorted(metrics["phase"].items(), key=lambda x: (x[0] == "unphased", x[0])):
        print(f"   {ph:<12} {count:>3}")

    # 5. Status
    print()
    print("🏷️  Status Distribution:")
    for s, count in metrics["status"].most_common():
        print(f"   {s:<12} {count:>3}")

    # 6. 异常告警 (修真版新功能)
    print()
    print("🚨 Anomaly Detection:")
    warnings = _check_anomalies(metrics, total)
    if not warnings:
        print("   ✅ 无异常")
    else:
        for w in warnings:
            print(f"   {w}")

    print()
    print(f"✅ Strategic audit complete. {total} tasks analyzed.")
    return 0


def strategy_gc(base_dir: Path, adapter: str = "ecos") -> int:
    """修真: 真 GC, 读 runtime/sandbox/pitches/ 真 mtime (修真前是 mock, 全返 0)."""
    workspace_root = base_dir if adapter == "local" else get_omo_dir(base_dir).parent
    if workspace_root.name == ".omo":
        workspace_root = workspace_root.parent
    if workspace_root.name == "omo":
        workspace_root = workspace_root.parent.parent

    sandbox_dir = workspace_root / "runtime" / "sandbox" / "pitches"
    decayed_dir = workspace_root / "runtime" / "sandbox" / "decayed"
    decay_threshold_days = 28
    decay_threshold_seconds = decay_threshold_days * 24 * 3600

    print(f"♻️ [Entropy GC] 正在扫描 Sandbox (Threshold: {decay_threshold_days} days)...")

    if not sandbox_dir.is_dir():
        print(f"   (Sandbox 目录 {sandbox_dir} 不存在, 跳过)")
        return 0

    decayed_dir.mkdir(parents=True, exist_ok=True)
    current_time = time.time()
    decayed_count = 0
    total_scanned = 0

    for md_file in sandbox_dir.glob("*.md"):
        total_scanned += 1
        mtime = md_file.stat().st_mtime
        if (current_time - mtime) > decay_threshold_seconds:
            days_old = int((current_time - mtime) / 86400)
            print(f"   -> 归档 {md_file.name} (mtime {days_old} 天前)")
            shutil.move(str(md_file), str(decayed_dir / md_file.name))
            decayed_count += 1

    print(f"✅ GC 完成。扫描 {total_scanned} 个, 清理 {decayed_count} 个滞留 Pitch。")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="C2G Strategy Engine (Round 43 P1 修真)")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("audit", help="真审计: 读 .omo/tasks/ 真实数据, 修真前 mock 已废弃")
    subparsers.add_parser("gc", help="真 GC: 读 sandbox/pitches/ 真 mtime, 修真前 mock 已废弃")

    args = parser.parse_args(argv)
    omo_dir = get_omo_dir(Path.cwd())

    if args.command == "audit":
        return strategy_audit(omo_dir)
    if args.command == "gc":
        return strategy_gc(omo_dir)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
