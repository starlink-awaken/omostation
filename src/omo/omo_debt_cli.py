#!/usr/bin/env python3
"""OMO debt CLI — list/close governed debts (治本 debt 标记滞后, OPT-12).

debt resolved 真源: resolved_debt_items 列表 (system.yaml) + debt_weight_items[id].resolved 派生.
旧 debt_weight_items 手动维护 → 漂移 (debt_summary/compute_debt_weight 无调用者, 声明≠实现, 同 OPT-7 计数漂移同病).
此命令补齐标记入口, 守防虚标 (--confirm 必填).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from .omo_debt_lifecycle import append_history
from .omo_io import write_yaml_atomic
from .omo_paths import find_omo_dir
from .omo_shared import load_yaml


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _find_omo_dir() -> Path:
    return find_omo_dir()


def _debt_item_path(omo_dir: Path, debt_id: str) -> Path:
    return omo_dir / "debt" / "items" / f"{debt_id}.yaml"


def cmd_debt_list(omo_dir: Path) -> int:
    """列 system.yaml debt_weight_items + resolved 状态."""
    state_file = omo_dir / "state" / "system.yaml"
    if not state_file.exists():
        print("⚠️  state/system.yaml not found")
        return 0
    data = load_yaml(state_file)
    items = data.get("debt_weight_items") or {}
    open_items = [(k, v) for k, v in items.items() if not v.get("resolved")]
    done_items = [(k, v) for k, v in items.items() if v.get("resolved")]
    print(f"=== Debt ({len(items)} total: {len(open_items)} open / {len(done_items)} resolved) ===")
    print(f"debt_weight: {data.get('debt_weight')}")
    if open_items:
        print("\n--- open ---")
        for k, v in open_items:
            print(f"  🔴 {k}: {(v.get('desc') or '')[:60]}")
    if done_items:
        print("\n--- resolved ---")
        for k, v in done_items:
            print(f"  ✅ {k}: {(v.get('desc') or '')[:60]}")
    return 0


def cmd_debt_close(omo_dir: Path, debt_id: str, dry_run: bool, confirm: bool) -> int:
    """关闭 canonical debt item.

    debt lifecycle 的真源是 `.omo/debt/items/*.yaml`，不再写 `state/system.yaml`
    里的派生字段，避免继续制造 drift。
    """
    item_path = _debt_item_path(omo_dir, debt_id)
    if not item_path.exists():
        print(f"❌ 未知 debt_id: {debt_id} (不在 .omo/debt/items)")
        return 1

    payload = load_yaml(item_path)
    if not isinstance(payload, dict):
        print(f"⚠️  debt item 非 dict: {debt_id}")
        return 1
    if str(payload.get("lifecycle_state") or "") == "closed":
        print(f"⚠️  {debt_id} 已是 closed (无需重复标记)")
        return 0

    desc = str(payload.get("description") or payload.get("title") or "")
    if dry_run:
        print(f"=== dry-run: close {debt_id} ===")
        print(f"  desc: {desc}")
        print("  lifecycle_state: identified/open -> closed")
        return 0
    if not confirm:
        print(f"⚠️  关闭 {debt_id} 需 --confirm")
        print(f"    先确认: omo debt close {debt_id} --dry-run")
        return 1

    timestamp = _utc_now()
    payload["lifecycle_state"] = "closed"
    payload["gate_level"] = "none"
    payload["last_reviewed_at"] = timestamp
    payload["closed_at"] = timestamp
    append_history(
        payload,
        "close",
        "Closed debt item via legacy debt CLI compatibility path.",
        timestamp=timestamp,
    )
    write_yaml_atomic(item_path, payload)
    print(f"✅ {debt_id} 已关闭")
    print(f"   lifecycle_state: {payload['lifecycle_state']}")
    return 0


def cmd_debt_desc(omo_dir: Path, debt_id: str, new_desc: str, dry_run: bool) -> int:
    """更新 canonical debt item description."""
    item_path = _debt_item_path(omo_dir, debt_id)
    if not item_path.exists():
        print(f"❌ 未知 debt_id: {debt_id} (不在 .omo/debt/items)")
        return 1
    payload = load_yaml(item_path)
    if not isinstance(payload, dict):
        print(f"⚠️  debt item 非 dict: {debt_id}")
        return 1
    old_desc = str(payload.get("description") or "")
    if dry_run:
        print(f"=== dry-run: desc {debt_id} ===")
        print(f"  old: {old_desc}")
        print(f"  new: {new_desc}")
        return 0

    payload["description"] = new_desc
    append_history(
        payload,
        "update_description",
        f"Updated description from {old_desc!r} to {new_desc!r}.",
        timestamp=_utc_now(),
    )
    write_yaml_atomic(item_path, payload)
    print(f"✅ {debt_id} description 已更新")
    print(f"  old: {old_desc}")
    print(f"  new: {new_desc}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo debt", description="OMO debt 标记管理 (治本标记滞后/漂移)")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="列 debt_weight_items + resolved 状态")
    cp = sub.add_parser("close", help="标 debt resolved (治本标记滞后, --confirm 防虚标)")
    cp.add_argument("debt_id", help="Debt ID (如 DEBT-FUTURE-ANNOTATIONS)")
    cp.add_argument("--dry-run", action="store_true", help="预览不写")
    cp.add_argument("--confirm", action="store_true", help="确认标记 (防虚标必填)")
    dp = sub.add_parser("desc", help="改 debt desc (治本 desc 漂移/虚标)")
    dp.add_argument("debt_id", help="Debt ID")
    dp.add_argument("desc", help="新 desc (真相, 勿虚标)")
    dp.add_argument("--dry-run", action="store_true", help="预览不写")
    args = parser.parse_args(argv)
    omo_dir = _find_omo_dir()
    if args.command == "list":
        return cmd_debt_list(omo_dir)
    elif args.command == "close":
        return cmd_debt_close(omo_dir, args.debt_id, args.dry_run, args.confirm)
    elif args.command == "desc":
        return cmd_debt_desc(omo_dir, args.debt_id, args.desc, args.dry_run)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
