#!/usr/bin/env python3
"""
entropy — 反熵系统统一模块

合并 entropy-sunrise/sunset/converge 三个 shell 脚本为可测试 Python 代码。

用法:
  python3 src/entropy.py sunrise [--list|--dry-run]
  python3 src/entropy.py sunset  [--list|--dry-run]
  python3 src/entropy.py converge [--dry-run]
"""

import json
import subprocess
import sys
from datetime import UTC, datetime

from forge.forge_config import CANDIDATE_DAYS, FORGE_ROOT, REGISTRY, STALE_DAYS


def _load() -> dict:
    if REGISTRY.stat().st_size > 100 * 1024 * 1024:
        print("❌ registry 过大 (>100MB)")
        return {"tools": []}
    return json.loads(REGISTRY.read_text())


def _atomic_save(reg: dict) -> None:
    tmp = REGISTRY.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    tmp.rename(REGISTRY)


def _days_since(date_str: str) -> int:
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=UTC)
        return (datetime.now(UTC) - d).days
    except (ValueError, TypeError):
        return 0


def _now_ts() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Sunrise: 候选池管理 ──


def sunrise_list() -> None:
    """列出所有 candidate 工具及等待天数"""
    reg = _load()
    candidates = [t for t in reg.get("tools", []) if t.get("status") == "candidate"]
    print("=== 候选池 ===")
    print(f"待确认: {len(candidates)} 个\n")
    if not candidates:
        print("（空）")
        return
    print(f"{'等待天数':>8} | {'ID':<25} | {'来源':<10} | {'首次发现'}")
    print(f"{'-' * 8}-|-{'-' * 25}-|-{'-' * 10}-|-{'----------'}")
    for t in candidates:
        first_seen = t.get("_discovery", {}).get("first_seen", "1970-01-01")
        days = _days_since(first_seen)
        src = t.get("_discovery", {}).get("source", "?")
        print(f"  {days:>3} 天 | {t['id']:<25} | {src:<10} | {first_seen}")


def sunrise_cleanup(dry_run: bool = False, *, quiet: bool = False) -> int:
    """清理超过 30 天的 candidate"""
    reg = _load()
    candidates = [t for t in reg.get("tools", []) if t.get("status") == "candidate"]
    expired: list[dict] = []
    keep: list[dict] = []
    for t in candidates:
        first_seen = t.get("_discovery", {}).get("first_seen", "")
        days = _days_since(first_seen)
        if days >= CANDIDATE_DAYS:
            expired.append(t)
        else:
            keep.append(t)

    if not quiet:
        print("=== 清理过期候选 ===")
    expired_count = 0
    for t in expired:
        if not quiet:
            print(
                f"  🗑️  过期 candidate: {t['id']}（已等待 {_days_since(t.get('_discovery', {}).get('first_seen', ''))} 天）"
            )
        if not dry_run:
            reg["tools"] = [x for x in reg["tools"] if x.get("id") != t["id"] or x.get("status") != "candidate"]
            reg.setdefault("event_log", []).append(
                {
                    "type": "entropy:sunrise_expired",
                    "tool_id": t["id"],
                    "summary": f"Candidate expired and removed: {t['id']}",
                    "timestamp": _now_ts(),
                }
            )
            expired_count += 1
            if not quiet:
                print("    ✅ 已移除并记录 event_log")
        else:
            if not quiet:
                print("    🔶 --dry-run 模式，未实际移除")

    if not expired:
        if not quiet:
            print("  无过期 candidate")
    if not quiet:
        print(f"\n总计: {len(expired)} 个已过期")

    if not dry_run and expired:
        _atomic_save(reg)
        subprocess.run(
            ["bash", str(FORGE_ROOT / "scripts" / "sync-registry.sh")], capture_output=True, timeout=30, cwd=FORGE_ROOT
        )

    return len(expired)


def cmd_sunrise(args: list[str]) -> int:
    if "--help" in args or "-h" in args:
        print("用法: forge entropy sunrise [--list|--dry-run]")
        return 0
    if "--list" in args or "-l" in args:
        sunrise_list()
        return 0
    dry_run = "--dry-run" in args
    print("=== 候选池检查 ===")
    sunrise_list()
    print()
    sunrise_cleanup(dry_run)
    return 0


# ── Sunset: 日落条款 ──


def sunset_list() -> None:
    """列出所有 stale 工具"""
    reg = _load()
    stale = [t for t in reg.get("tools", []) if t.get("status") == "stale"]
    print("=== 日落扫描 ===")
    print(f"stale 工具: {len(stale)} 个\n")
    if not stale:
        print("（无 stale 工具）")
        return
    for t in stale:
        updated = t.get("updated", "?")
        days = _days_since(updated) if updated != "?" else 9999
        print(f"  ⏳ {t['id']} (stale {days} 天) — {t.get('name', '')}")


def sunset_auto_deprecate(dry_run: bool = False) -> int:
    """自动标记过期 stale 工具为 deprecated"""
    reg = _load()
    stale = [t for t in reg.get("tools", []) if t.get("status") == "stale"]
    sunset_list()
    print()

    deprecated_count = 0
    now_ts = _now_ts()
    for t in stale:
        updated = t.get("updated", "1970-01-01")
        days = _days_since(updated) if updated != "?" else 9999
        if days >= STALE_DAYS:
            print(f"  🗑️  {t['id']} — stale {days} 天（≥90），标记 deprecated")
            if not dry_run:
                for tool in reg["tools"]:
                    if tool.get("id") == t["id"] and tool.get("status") == "stale":
                        tool["status"] = "deprecated"
                        break
                reg.setdefault("event_log", []).append(
                    {
                        "type": "entropy:auto_deprecated",
                        "tool_id": t["id"],
                        "summary": f"Auto deprecated: {t['id']} (stale {days} days)",
                        "timestamp": now_ts,
                    }
                )
                deprecated_count += 1
                print("    ✅ 已标记 deprecated")

    print(f"\n已废弃: {deprecated_count} 个工具")
    if dry_run:
        print("🔶 --dry-run 模式，未实际变更")
    if not dry_run and deprecated_count:
        _atomic_save(reg)
    return deprecated_count


def cmd_sunset(args: list[str]) -> int:
    if "--help" in args or "-h" in args:
        print("用法: forge entropy sunset [--list|--dry-run]")
        return 0
    if "--list" in args or "-l" in args:
        sunset_list()
        return 0
    dry_run = "--dry-run" in args
    sunset_auto_deprecate(dry_run)
    return 0


# ── Converge: 收敛检查 ──


def converge_similar() -> None:
    """相似工具检测"""
    print("1. 相似工具检测")
    print()
    graph_utils_path = FORGE_ROOT / "src" / "graph_utils.py"
    if not graph_utils_path.exists():
        print("  ⚠️  graph_utils 未找到，跳过相似检测")
        print()
        return
    try:
        sys.path.insert(0, str(FORGE_ROOT / "src"))
        from graph_utils import compute_capability_overlap  # type: ignore

        reg = _load()
        tools = [t for t in reg.get("tools", []) if t.get("status") != "candidate"]
        if len(tools) < 2:
            print("  ⚠️  工具数量不足")
            return
        pairs = compute_capability_overlap(tools, min_similarity=0.7)
        if pairs:
            for id1, id2, sim in pairs:
                print(f"  🔗 {id1} ↔ {id2} （相似度 {sim * 100:.0f}%）")
        else:
            print("  ✅ 无高相似工具对")
    except ImportError:
        print("  ⚠️  graph_utils 未加载，跳过相似检测")
    print()


def converge_categories() -> None:
    """列出当前分类"""
    reg = _load()
    cats: set[str] = set()
    for t in reg.get("tools", []):
        for c in t.get("category", []):
            cats.add(c)
    sorted_cats = sorted(cats)
    print("2. 标签归一化\n")
    print(f"  当前分类标签（{len(sorted_cats)} 个）:")
    for c in sorted_cats:
        print(f"    - {c}")
    print()


def converge_pressure() -> None:
    """结构压力检查"""
    reg = _load()
    tools = reg.get("tools", [])
    skills = [t for t in tools if t.get("type") == "skill"]
    events = reg.get("event_log", [])

    def check(val: int, limit: int, name: str) -> str:
        ratio = val / limit
        if ratio > 0.9:
            return f"⚠️ 接近上限（{val}/{limit}）"
        return f"✅正常（{val}/{limit}）"

    print("3. 结构压力检查\n")
    print(f"  工具数: {check(len(tools), 200, '工具')}")
    print(f"  技能数: {check(len(skills), 300, '技能')}")
    print(f"  事件日志: {check(len(events), 500, '事件')}")


def cmd_converge(args: list[str]) -> int:
    dry_run = "--dry-run" in args
    print("=== 收敛检查报告 ===")
    print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    converge_similar()
    converge_categories()
    converge_pressure()

    if not dry_run:
        reg = _load()
        reg.setdefault("event_log", []).append(
            {
                "type": "entropy:converged",
                "tool_ids": [],
                "summary": "Convergence check completed",
                "timestamp": _now_ts(),
            }
        )
        _atomic_save(reg)

    return 0


# ── CLI Entry ──


def run(args: list[str]) -> int:
    if not args or args[0] in ("-h", "--help", "help"):
        print("""Forge Entropy — 反熵系统

用法: forge entropy <action> [选项]

操作:
  sunrise [--list|--dry-run]   候选池管理
  sunset  [--list|--dry-run]   日落条款
  converge [--dry-run]          收敛检查
""")
        return 0

    action = args[0]
    action_args = args[1:]
    actions = {
        "sunrise": cmd_sunrise,
        "sunset": cmd_sunset,
        "converge": cmd_converge,
    }
    if action not in actions:
        print(f"未知操作: {action}，可选: sunrise, sunset, converge")
        return 1
    return actions[action](action_args)


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
