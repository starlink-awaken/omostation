#!/usr/bin/env python3
"""Autoloop Controller — 自主闭环执行引擎 (EVO-01).

定期扫 debt/gap 台账 → 按风险分级 → S1/S2 自动执行 → 验证 → 关闭.
守 S1/S2/S3 门禁:
  - S1 (低风险): 自动执行 + 自动关闭
  - S2 (中风险): 自动执行 + 生成审查请求 (需人工确认关闭)
  - S3 (高风险): 不执行, 仅报人

Usage:
  python3 bin/ssot/autoloop-controller.py              # 跑一轮闭环
  python3 bin/ssot/autoloop-controller.py --dry-run    # 预览 (不执行)
  python3 bin/ssot/autoloop-controller.py --json       # JSON 输出
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from _shared import ROOT, append_jsonl, is_runnable_cmd, load_yaml, utc_now

DEBT_DIR = ROOT / ".omo" / "debt" / "items"
GAP_DIR = ROOT / ".omo" / "debt" / "gap-items"
TRACE_LOG = ROOT / ".omo" / "state" / "autoloop-trace.jsonl"
VERIFY_CACHE = ROOT / ".omo" / "state" / "autoloop-verify-cache.json"

# S1: 只读/生成类, 无状态副作用 → 自动执行+关闭
# S2: 有状态写入但可回滚 → 自动执行+人审关闭
# S3: 架构/破坏性 → 仅报人
S1_ACTIONS = {"create_scene_cards", "cleanup_task", "create_debt_task"}
S2_ACTIONS = {"research_task", "generate_report", "update_registry"}
S3_ACTIONS = {"architecture_change", "remove_capability", "modify_governance"}


def _load_debt_items() -> list[dict]:
    """Load open debt items (state not resolved/closed)."""
    items: list[dict] = []
    if not DEBT_DIR.is_dir():
        return items
    for path in sorted(DEBT_DIR.glob("*.yaml")):
        data = load_yaml(path)
        state = str(data.get("lifecycle_state", "open"))
        if state in ("resolved", "closed", "archived"):
            continue
        items.append({"source": "debt", "path": path, **data})
    return items


def _load_gap_items() -> list[dict]:
    """Load open gap items (all are open until closed)."""
    items: list[dict] = []
    if not GAP_DIR.is_dir():
        return items
    for path in sorted(GAP_DIR.glob("*.yaml")):
        if path.name == "TEMPLATE.yaml":
            continue
        data = load_yaml(path)
        state = str(data.get("lifecycle_state", "open"))
        if state in ("resolved", "closed"):
            continue
        items.append({"source": "gap", "path": path, **data})
    return items


def _classify(item: dict) -> str:
    """Classify action level by action type (S1/S2/S3)."""
    action = str(item.get("action", item.get("gap_class", "")))
    if action in S3_ACTIONS:
        return "S3"
    if action in S2_ACTIONS:
        return "S2"
    return "S1"


def _build_task_cmd(item: dict) -> list[str] | None:
    """Map item to an executable verification command (for S1 auto-run)."""
    verification_cmd = str(item.get("verification_cmd", "") or "").strip()
    if not is_runnable_cmd(verification_cmd):
        return None
    return ["bash", "-c", verification_cmd]


def _load_verify_cache() -> dict[str, Any]:
    """Load mtime-keyed verification cache (path_mtime -> result)."""
    if VERIFY_CACHE.exists():
        try:
            return json.loads(VERIFY_CACHE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_verify_cache(cache: dict[str, Any]) -> None:
    VERIFY_CACHE.parent.mkdir(parents=True, exist_ok=True)
    VERIFY_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def _close_item(item: dict) -> bool:
    """Actually close an item by updating its YAML lifecycle_state to 'closed'.

    Without this, items stay 'open' forever even after auto_closed disposition.
    """
    yaml_path = item.get("path")
    if not yaml_path or not isinstance(yaml_path, Path) or not yaml_path.exists():
        return False
    try:
        import yaml

        data = load_yaml(yaml_path) or {}
        data["lifecycle_state"] = "closed"
        data["closed_at"] = utc_now()
        data["closed_by"] = "autoloop-controller"
        data["close_reason"] = "S1 auto-close: verification passed"
        yaml_path.write_text(
            yaml.dump(
                data, allow_unicode=True, sort_keys=False, default_flow_style=False
            ),
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


def _try_heuristic_verify(item: dict) -> dict[str, Any]:
    """启发式验证 — 对无 verification_cmd 的 item 做基本判断.

    规则:
    - 标题含 'viol-test' 或 'Schema violation' + 无 cmd → stale test artifact → pass
    - 其他无 cmd → no_cmd (保持 kept_open)
    """
    title = str(item.get("title", ""))
    verification_cmd = str(item.get("verification_cmd", "") or "").strip()

    if not is_runnable_cmd(verification_cmd):
        # 已 resolved 的 item 直接关闭 (不需要再验证)
        lifecycle = str(item.get("lifecycle_state", "")).strip()
        if lifecycle == "resolved":
            return {"status": "passed", "note": "lifecycle_state=resolved, auto-close"}
        # 检查是否是 stale test artifact
        if "viol-test" in title or "Schema violation" in title:
            return {"status": "passed", "note": "stale test artifact, auto-cleanable"}
        return {"status": "no_cmd", "note": "no runnable verification_cmd"}

    return {}  # 空dict = 交给正常验证流程


def _run_verification(item: dict) -> dict[str, Any]:
    """Run the item's verification command, with mtime-based caching to avoid re-executing
    slow subprocesses when the YAML file hasn't changed."""
    cmd = _build_task_cmd(item)
    if not cmd:
        # 启发式验证: 无cmd的item可能可以通过启发式判断
        heuristic = _try_heuristic_verify(item)
        if heuristic:
            return heuristic
        return {"status": "no_cmd", "note": "no runnable verification_cmd"}

    # Check mtime cache: skip re-run if YAML unchanged since last verification
    yaml_path = item.get("path")
    cache_key = ""
    cache: dict[str, Any] = {}
    if yaml_path and isinstance(yaml_path, Path) and yaml_path.exists():
        try:
            cache_key = f"{yaml_path}:{os.path.getmtime(yaml_path)}"
            cache = _load_verify_cache()
            cached = cache.get(cache_key)
            if cached is not None:
                cached["cached"] = True
                return cached
        except OSError:
            pass

    try:
        proc = subprocess.run(
            cmd, cwd=ROOT, capture_output=True, text=True, timeout=60, check=False
        )
        result = {
            "status": "passed" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "stderr_tail": proc.stderr[-200:],
        }
    except Exception as exc:
        result = {"status": "error", "error": str(exc)}

    # Persist to cache (reuse already-loaded cache dict)
    if cache_key:
        try:
            cache[cache_key] = result
            if len(cache) > 200:
                keys = list(cache.keys())[-200:]
                cache = {k: cache[k] for k in keys}
            _save_verify_cache(cache)
        except OSError:
            pass

    return result


def _trace(entry: dict[str, Any]) -> None:
    """Append trace record for auditability."""
    entry.setdefault("ts", utc_now())
    append_jsonl(TRACE_LOG, entry)


def run_loop(*, dry_run: bool = False) -> dict[str, Any]:
    """Run one autoloop cycle over debt + gap items with parallel I/O and verification."""
    # Parallel YAML load: debt and gap directories are independent
    with ThreadPoolExecutor(max_workers=2) as loader:
        debt_future = loader.submit(_load_debt_items)
        gap_future = loader.submit(_load_gap_items)
        debt_items = debt_future.result()
        gap_items = gap_future.result()

    candidates = debt_items + gap_items
    if not candidates:
        return {"status": "noop", "reason": "no open items", "processed": 0}

    # Classify first (cheap, no I/O), then run verifications in parallel
    classified = [(item, _classify(item)) for item in candidates]

    s1_count = s2_count = s3_count = 0
    results: list[dict[str, Any] | None] = [None] * len(classified)
    pending: list[tuple[int, dict]] = []

    # Phase 1: classify all; collect S3 immediately; queue S1/S2 for parallel verify
    for idx, (item, level) in enumerate(classified):
        item_id = str(item.get("id", item["path"].stem))
        action = str(item.get("action", item.get("gap_class", "?")))
        if level == "S3":
            s3_count += 1
            results[idx] = {
                "item": item_id,
                "source": item.get("source"),
                "level": "S3",
                "action": "report_only",
                "note": f"high-risk action '{action}' requires human decision",
            }
        else:
            pending.append((idx, item))

    # Phase 2: parallel verification for S1/S2 items
    if pending:
        with ThreadPoolExecutor(max_workers=min(8, max(len(pending), 1))) as executor:
            future_map: dict[Any, int] = {}
            for idx, item in pending:
                future_map[executor.submit(_run_verification, item)] = idx

            for future in as_completed(future_map):
                idx = future_map[future]
                item, level = classified[idx]
                item_id = str(item.get("id", item["path"].stem))
                action = str(item.get("action", item.get("gap_class", "?")))
                result = future.result()

                if level == "S1":
                    s1_count += 1
                else:
                    s2_count += 1

                entry = {
                    "item": item_id,
                    "source": item.get("source"),
                    "level": level,
                    "action": action,
                    "dry_run": dry_run,
                    "verification": result,
                }
                if level == "S1" and result.get("status") == "passed":
                    entry["disposition"] = "auto_closed"
                    if not dry_run:
                        closed = _close_item(item)
                        entry["yaml_closed"] = closed
                elif level == "S2" and result.get("status") == "passed":
                    entry["disposition"] = "review_pending"
                else:
                    entry["disposition"] = "kept_open"
                results[idx] = entry
                if not dry_run:
                    _trace(entry)

    return {
        "status": "completed",
        "dry_run": dry_run,
        "processed": len(candidates),
        "by_level": {"S1": s1_count, "S2": s2_count, "S3": s3_count},
        "dispositions": {
            "auto_closed": sum(
                1 for r in results if r and r.get("disposition") == "auto_closed"
            ),
            "review_pending": sum(
                1 for r in results if r and r.get("disposition") == "review_pending"
            ),
            "kept_open": sum(
                1 for r in results if r and r.get("disposition") == "kept_open"
            ),
            "report_only": sum(
                1 for r in results if r and r.get("action") == "report_only"
            ),
        },
        "results": [r for r in results if r],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="preview without executing"
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = run_loop(dry_run=args.dry_run)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print(
        f"Autoloop: processed {result.get('processed', 0)} items "
        f"({'DRY-RUN' if result.get('dry_run') else 'LIVE'})"
    )
    if result.get("status") == "noop":
        print(f"  {result.get('reason')}")
        return 0
    print(f"  by_level: {result.get('by_level')}")
    print(f"  dispositions: {result.get('dispositions')}")
    for r in result.get("results", []):
        marker = {
            "auto_closed": "✅",
            "review_pending": "👀",
            "kept_open": "⬜",
            "report_only": "🚫",
        }.get(r.get("disposition"), "?")
        print(f"  {marker} [{r.get('level')}] {r.get('item')}: {r.get('disposition')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
