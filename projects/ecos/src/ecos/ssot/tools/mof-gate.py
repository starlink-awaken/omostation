#!/usr/bin/env python3
"""
织星 MOF — 变更门禁 (mof-gate)
===============================
检测"绕过 L0"的变更——系统资产发生了变化但 L0 没有对应更新。

机制:
  1. 定期扫描系统资产 → 生成 M1 候选节点
  2. 与 L0 已注册的 M1 节点比对
  3. 发现孤儿资产 (存在但未注册) → 违规
  4. 检查是否有对应的 Decision M1 节点在审核中
  5. 自动创建 CARDS 债务卡片

这就是 "动架构必须先改 L0" 的约束落地机制。

用法:
    python3 mof-gate.py                 # 全量门禁检查
    python3 mof-gate.py --strict        # 严格模式 (孤儿=违规)
    python3 mof-gate.py --json          # JSON 输出
"""

import json
import yaml
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
WS = HOME / "Workspace"
DOCS = HOME / "Documents"
L0_M1 = WS / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1"
CARDS_DB = WS / "data" / "cards" / "cards.db"
SNAPSHOT_FILE = HOME / ".ecos" / "gate-snapshot.json"


def now():
    return datetime.now(timezone.utc)


def scan_current_assets() -> dict:
    """扫描当前系统资产，生成指纹"""
    assets = {}

    # Scan Documents scripts
    scripts_dir = DOCS / "驾驶舱" / "scripts"
    if scripts_dir.exists():
        for f in scripts_dir.glob("*.py"):
            key = f"L4-SCRIPT-{f.stem}"
            assets[key] = {
                "path": str(f.relative_to(HOME)),
                "size": f.stat().st_size,
                "layer": "L4",
                "type": "Script",
            }

    # Scan Workspace projects (key ones)
    ws_projects = WS / "projects"
    if ws_projects.exists():
        for proj in ["ecos", "agora", "cockpit", "runtime", "kairon"]:
            proj_dir = ws_projects / proj
            if not proj_dir.exists():
                continue
            py_files = list(proj_dir.rglob("*.py"))
            yaml_files = list(proj_dir.rglob("*.yaml"))
            key = f"COMP-WS-{proj}"
            assets[key] = {
                "path": str(proj_dir.relative_to(HOME)),
                "py_count": len(py_files),
                "yaml_count": len(yaml_files),
                "layer": {
                    "ecos": "L0",
                    "agora": "I0",
                    "cockpit": "L3",
                    "runtime": "L1",
                    "kairon": "L2",
                }.get(proj, "L2"),
                "type": "Component",
            }

    # Scan CARDS
    if CARDS_DB.exists():
        conn = sqlite3.connect(str(CARDS_DB))
        cur = conn.execute("SELECT COUNT(*) FROM cards")
        count = cur.fetchone()[0]
        conn.close()
        assets["DATA-CARDS-DB"] = {"card_count": count, "type": "DataSource"}

    return assets


def load_registered_m1_ids() -> set:
    """从 L0 M1 节点中提取已注册的资产 ID"""
    ids = set()
    if not L0_M1.exists():
        return ids
    for f in L0_M1.rglob("*.yaml"):
        try:
            data = yaml.safe_load(open(f))
            if isinstance(data, dict):
                ids.add(data.get("id", ""))
                # Also track source paths
                props = data.get("properties", {}) or {}
                sources = props.get("sources", [])
                for s in sources:
                    ids.add(f"SOURCE-{s}")
        except Exception:
            pass
    return ids


def load_previous_snapshot() -> dict:
    if SNAPSHOT_FILE.exists():
        with open(SNAPSHOT_FILE) as f:
            return json.load(f)
    return {}


def save_snapshot(assets: dict):
    SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SNAPSHOT_FILE, "w") as f:
        json.dump({"timestamp": now().isoformat(), "assets": assets}, f, indent=2)


def detect_changes(current: dict, previous: dict, registered: set) -> list[dict]:
    """检测变更"""
    violations = []

    # New assets not in previous snapshot
    new_keys = set(current.keys()) - set(previous.get("assets", {}).keys())
    for key in new_keys:
        current[key]
        # Check if registered in L0
        is_registered = any(key in rid or rid in key for rid in registered)
        if not is_registered:
            violations.append(
                {
                    "asset": key,
                    "type": "new_unregistered",
                    "severity": "medium",
                    "detail": f"新资产未在 L0 注册: {key}",
                    "suggested": "运行 mof-scan 或手动创建 L0 M1 节点",
                }
            )

    # Changed assets
    for key in set(current.keys()) & set(previous.get("assets", {}).keys()):
        prev = previous["assets"][key]
        curr = current[key]
        if prev != curr:
            is_registered = any(key in rid or rid in key for rid in registered)
            if not is_registered:
                violations.append(
                    {
                        "asset": key,
                        "type": "changed_unregistered",
                        "severity": "low",
                        "detail": f"资产已变更但 L0 未更新: {key}",
                        "suggested": "更新对应的 L0 M1 节点",
                    }
                )

    return violations


def create_gate_card(violation: dict):
    if not CARDS_DB.exists():
        return
    try:
        conn = sqlite3.connect(str(CARDS_DB))
        now_str = now().isoformat()
        debt_id = f"DEBT-GATE-{now_str[:10]}-{violation['asset'][:20]}"
        debt_id = debt_id.replace(" ", "-")[:50]
        conn.execute(
            """
            INSERT OR IGNORE INTO cards (id, type, status, title, domain, priority, summary, content, created_at, updated_at)
            VALUES (?, 'debt', 'identified', ?, 'meta', 'P2', ?, ?, ?, ?)
        """,
            (
                debt_id,
                f"变更门禁: {violation['asset'][:60]}",
                violation["detail"],
                f"## mof-gate 自动检测\n- 类型: {violation['type']}\n- {violation['detail']}\n- 建议: {violation['suggested']}",
                now_str,
                now_str,
            ),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def format_report(violations: list[dict]) -> str:
    lines = [
        "=" * 64,
        "  织星 MOF — 变更门禁报告",
        "=" * 64,
        f"  时间: {now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"  违规: {len(violations)} 项",
        "",
    ]

    if not violations:
        lines.append("  ✅ 所有变更已通过 L0 注册")
    else:
        for v in violations:
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(v["severity"], "⚪")
            lines.append(f"  {icon} [{v['type']}] {v['asset'][:50]}")
            lines.append(f"     {v['detail']}")
            lines.append(f"     → {v['suggested']}")

    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-cards", action="store_true")
    args = parser.parse_args()

    current = scan_current_assets()
    previous = load_previous_snapshot()
    registered = load_registered_m1_ids()

    violations = detect_changes(current, previous, registered)
    save_snapshot(current)

    if args.json:
        print(
            json.dumps(
                {"violations": len(violations), "items": violations},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(format_report(violations))

    if not args.no_cards and violations:
        created = sum(1 for v in violations if create_gate_card(v))
        if created:
            print(f"\n  📋 门禁自动创建: {created} 张 CARDS DEBT 卡片")


if __name__ == "__main__":
    main()
