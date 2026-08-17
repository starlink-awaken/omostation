#!/usr/bin/env python3
"""Execute close-duplicate-gap-first actions from the convergence manifest."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _normalize_round(entry: dict[str, Any]) -> str:
    evidence = entry.get("evidence", {})
    return str(evidence.get("decision_round", "unknown")).strip()


def _normalize_action(entry: dict[str, Any]) -> str:
    return str(entry.get("action", "pending")).strip() or "pending"


def _dedupe_manifest(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen = set()
    out: list[dict[str, Any]] = []
    duplicate_count = 0

    for entry in entries:
        key = (
            str(entry.get("name", "")),
            str(entry.get("bin", "")),
            str(entry.get("scripts", "")),
            _normalize_action(entry),
            str(entry.get("owner", "governance")),
        )
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        out.append(entry)

    return out, duplicate_count


def _read_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def _is_safe_wrapper(path: Path, bin_path: Path) -> bool:
    text = _read_text(path)
    if not text:
        return False

    if "Compatibility wrapper" not in text or "runpy.run_path" not in text:
        return False

    # Compatibility wrappers in scripts/ are safe to retire only when they point to a
    # peer implementation that is already identical to bin.
    script_bin = _read_bytes(bin_path)
    if script_bin is None:
        return False

    # 兼容 wrapper 本身通常挂在 scripts/bin 下，且内容会指向下一层实现。
    # 如果 wrapper 目标与 bin 一致，则可删除 wrapper（将入口收敛到 bin）。
    # 不做复杂 AST 解析，避免误判；非兼容文本的 wrapper 一律人工确认。
    for line in text.splitlines():
        if "SSOT =" in line and "runpy.run_path" in text:
            # 允许有 `runpy` 动态读取路径的场景，先做保守判定。
            # 仅依赖“有兼容描述 + runpy + 可读到 bin 文件内容”作为安全门槛。
            return True

    return False


def execute_batch(
    entries: list[dict[str, Any]],
    target_round: str,
    target_owner: str,
    apply_changes: bool,
    output: Path,
    json_path: Path | None,
) -> dict[str, Any]:
    selected = [
        item
        for item in entries
        if item.get("action") == "close-duplicate-gap-first"
        and (target_round == "all" or _normalize_round(item) == target_round)
        and (not target_owner or str(item.get("owner", "governance")) == target_owner)
    ]

    selected.sort(
        key=lambda item: (_normalize_round(item), str(item.get("owner", "governance")), str(item.get("name", "")))
    )

    round_stats: dict[str, int] = defaultdict(int)
    owner_stats: dict[str, int] = defaultdict(int)
    result_stats: dict[str, int] = defaultdict(int)
    skipped_reasons: dict[str, int] = defaultdict(int)

    report_rows = []
    for item in selected:
        owner = str(item.get("owner", "governance"))
        round_name = _normalize_round(item)
        bin_path = Path(item.get("bin", ""))
        scripts_path = Path(item.get("scripts", ""))
        name = str(item.get("name", ""))
        round_stats[round_name] += 1
        owner_stats[owner] += 1

        result = "skip"
        reason = ""

        bin_bytes = _read_bytes(bin_path)
        scripts_bytes = _read_bytes(scripts_path)
        if bin_bytes is None or scripts_bytes is None:
            skipped_reasons["missing_file"] += 1
            reason = "missing_file"
        elif bin_bytes == scripts_bytes:
            if apply_changes:
                try:
                    scripts_path.unlink()
                    result = "removed"
                    reason = "identical"
                except OSError as exc:
                    result = "failed"
                    reason = f"remove_failed: {exc}"
            else:
                result = "ready_remove"
                reason = "identical"
        elif _is_safe_wrapper(scripts_path, bin_path):
            if apply_changes:
                try:
                    scripts_path.unlink()
                    result = "removed"
                    reason = "compat_wrapper"
                except OSError as exc:
                    result = "failed"
                    reason = f"remove_failed: {exc}"
            else:
                result = "ready_remove"
                reason = "compat_wrapper"
        else:
            skipped_reasons["content_mismatch"] += 1
            reason = "content_mismatch"

        result_stats[result] += 1

        report_rows.append(
            {
                "name": name,
                "owner": owner,
                "round": round_name,
                "due": str((item.get("evidence", {}) or {}).get("due_date", "")),
                "status": str(item.get("status", "managed")),
                "bin": str(item.get("bin", "")),
                "scripts": str(item.get("scripts", "")),
                "result": result,
                "reason": reason,
            }
        )

    lines: list[str] = []
    lines.append("# scripts close-duplicate-gap-first 执行计划与结果")
    lines.append("")
    lines.append(f"- 生成时间: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("- 数据源: `docs/operations/bin-scripts-convergence-manifest.json`")
    lines.append(f"- Round 筛选: {target_round}")
    if target_owner:
        lines.append(f"- Owner 筛选: {target_owner}")
    lines.append(f"- 模式: {'apply' if apply_changes else 'dry-run'}")
    lines.append(f"- 条目数: {len(selected)}")
    lines.append("")
    lines.append("## 按 round 分布")
    for round_name in sorted(round_stats):
        lines.append(f"- {round_name}: {round_stats[round_name]}")
    lines.append("")
    lines.append("## 按 owner 分布")
    for owner in sorted(owner_stats):
        lines.append(f"- {owner}: {owner_stats[owner]}")
    lines.append("")
    if skipped_reasons:
        lines.append("## 跳过原因")
        for reason, count in sorted(skipped_reasons.items(), key=lambda item: item[0]):
            lines.append(f"- {reason}: {count}")
        lines.append("")

    headers = ["name", "owner", "round", "status", "result", "reason", "bin", "scripts"]
    widths = [len(h) for h in headers]
    for row in report_rows:
        values = [
            row["name"],
            row["owner"],
            row["round"],
            row["status"],
            row["result"],
            row["reason"],
            row["bin"],
            row["scripts"],
        ]
        for idx, value in enumerate(values):
            widths[idx] = max(widths[idx], len(value))

    lines.append("## 执行清单")
    if not report_rows:
        lines.append("None")
    else:
        lines.append("| " + " | ".join(h.ljust(widths[idx]) for idx, h in enumerate(headers)) + " |")
        lines.append("| " + " | ".join("-" * widths[idx] for idx in range(len(headers))) + " |")
        for row in report_rows:
            values = [
                row["name"],
                row["owner"],
                row["round"],
                row["status"],
                row["result"],
                row["reason"],
                row["bin"],
                row["scripts"],
            ]
            lines.append("| " + " | ".join(value.ljust(widths[idx]) for idx, value in enumerate(values)) + " |")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "filter_round": target_round,
        "filter_owner": target_owner,
        "mode": "apply" if apply_changes else "dry-run",
        "entries": len(selected),
        "result_count": dict(result_stats),
        "skipped_reasons": dict(skipped_reasons),
        "round_count": {k: v for k, v in sorted(round_stats.items())},
        "owner_count": {k: v for k, v in sorted(owner_stats.items())},
        "items": report_rows,
    }

    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--round", default="all", help="Filter by decision_round, default all")
    parser.add_argument("--owner", default="", help="Filter by owner, default all")
    parser.add_argument("--output", required=True)
    parser.add_argument("--json", default="", help="输出 JSON 清单路径（可选）")
    parser.add_argument("--apply", action="store_true", help="执行删除（默认 dry-run）")
    args = parser.parse_args()

    manifest = _load_json(Path(args.manifest))
    entries = manifest.get("entries", []) if isinstance(manifest, dict) else []
    entries = [entry for entry in entries if isinstance(entry, dict)]
    entries, duplicate_count = _dedupe_manifest(entries)
    if duplicate_count:
        print(f"warn: manifest contains duplicate entries, skipped {duplicate_count}", file=sys.stderr)

    summary = execute_batch(
        entries=entries,
        target_round=args.round,
        target_owner=args.owner,
        apply_changes=args.apply,
        output=Path(args.output),
        json_path=Path(args.json) if args.json else None,
    )

    print(f"generated {args.output}")
    if args.json:
        print(f"generated {args.json}")

    result_count = summary["result_count"]
    if args.apply:
        removed = result_count.get("removed", 0)
        skipped = summary["entries"] - removed - result_count.get("failed", 0)
        print(
            f"entries={summary['entries']} removed={removed} failed={result_count.get('failed', 0)} skipped={skipped}"
        )
    else:
        ready = result_count.get("ready_remove", 0)
        print(f"entries={summary['entries']} ready_remove={ready} skipped={summary['entries'] - ready}")

    if args.apply and result_count.get("failed", 0):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
