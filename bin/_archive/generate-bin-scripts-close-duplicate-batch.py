#!/usr/bin/env python3
"""Emit close-duplicate-gap-first execution batches from convergence manifest."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _normalize_action(entry: dict[str, Any]) -> str:
    return str(entry.get("action", "pending")).strip() or "pending"


def _normalize_round(entry: dict[str, Any]) -> str:
    evidence = entry.get("evidence", {})
    return str(evidence.get("decision_round", "unknown")).strip()


def _normalize_due(entry: dict[str, Any]) -> str:
    evidence = entry.get("evidence", {})
    return str(evidence.get("due_date", "")).strip()


def _normalize_risk(entry: dict[str, Any]) -> int:
    evidence = entry.get("evidence", {})
    try:
        return int(evidence.get("risk_score", 0))
    except (TypeError, ValueError):
        return 0


def _normalize_status(entry: dict[str, Any]) -> str:
    return str(entry.get("status", "managed") or "managed").strip() or "managed"


def _parse_due(due: str) -> datetime:
    if due:
        try:
            return datetime.fromisoformat(due)
        except ValueError:
            pass
    return datetime.max


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


def _as_table(rows: list[tuple[str, ...]]) -> str:
    if not rows:
        return "None\n"

    headers = ["name", "owner", "round", "due", "risk", "status", "bin", "scripts"]
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(str(value)))

    lines = []
    lines.append("| " + " | ".join(h.ljust(widths[idx]) for idx, h in enumerate(headers)) + " |")
    lines.append("| " + " | ".join("-" * widths[idx] for idx in range(len(headers))) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(value).ljust(widths[idx]) for idx, value in enumerate(row)) + " |")
    return "\n".join(lines) + "\n"


def emit_batch(
    entries: list[dict[str, Any]], target_round: str, target_owner: str, output: Path, json_path: Path | None
) -> dict[str, Any]:
    selected = [
        item
        for item in entries
        if item.get("action") == "close-duplicate-gap-first"
        and (target_round == "all" or _normalize_round(item) == target_round)
        and (not target_owner or str(item.get("owner", "governance")) == target_owner)
    ]

    selected.sort(
        key=lambda item: (
            _normalize_round(item),
            _parse_due(_normalize_due(item)),
            -_normalize_risk(item),
            str(item.get("name", "")),
        )
    )

    round_stats: dict[str, int] = defaultdict(int)
    owner_stats: dict[str, int] = defaultdict(int)
    for item in selected:
        round_stats[_normalize_round(item)] += 1
        owner_stats[str(item.get("owner", "governance"))] += 1

    lines: list[str] = []
    lines.append("# scripts close-duplicate-gap-first 执行清单")
    lines.append("")
    lines.append(f"- 生成时间: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("- 数据源: `docs/operations/bin-scripts-convergence-manifest.json`")
    lines.append(f"- Round 筛选: {target_round}")
    if target_owner:
        lines.append(f"- Owner 筛选: {target_owner}")
    lines.append(f"- 条目数: {len(selected)}")
    lines.append("")

    lines.append("## 按 round 分布")
    if round_stats:
        for round_name in sorted(round_stats):
            lines.append(f"- {round_name}: {round_stats[round_name]}")
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## 按 owner 分布")
    if owner_stats:
        for owner in sorted(owner_stats):
            lines.append(f"- {owner}: {owner_stats[owner]}")
    else:
        lines.append("- none")
    lines.append("")

    rows = []
    for item in selected:
        rows.append(
            (
                str(item.get("name", "")),
                str(item.get("owner", "governance")),
                _normalize_round(item),
                _normalize_due(item),
                str(_normalize_risk(item)),
                _normalize_status(item),
                str(item.get("bin", "")),
                str(item.get("scripts", "")),
            )
        )
    lines.append("## 任务清单（按 round -> due -> risk desc）")
    lines.append(_as_table(rows))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "filter_round": target_round,
        "filter_owner": target_owner,
        "entries": len(selected),
        "round_count": {k: v for k, v in sorted(round_stats.items())},
        "owner_count": {k: v for k, v in sorted(owner_stats.items())},
        "items": [
            {
                "name": item.get("name"),
                "owner": item.get("owner", "governance"),
                "round": _normalize_round(item),
                "due": _normalize_due(item),
                "risk": _normalize_risk(item),
                "status": _normalize_status(item),
                "bin": item.get("bin"),
                "scripts": item.get("scripts"),
            }
            for item in selected
        ],
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
    parser.add_argument("--output", required=True, help="输出 markdown 报告路径")
    parser.add_argument("--json", default="", help="输出 JSON 清单路径（可选）")
    args = parser.parse_args()

    manifest = _load_json(Path(args.manifest))
    entries = manifest.get("entries", []) if isinstance(manifest, dict) else []
    entries = [entry for entry in entries if isinstance(entry, dict)]

    entries, duplicate_count = _dedupe_manifest(entries)
    if duplicate_count:
        print(f"warn: manifest contains duplicate entries, skipped {duplicate_count}", file=sys.stderr)

    summary = emit_batch(
        entries=entries,
        target_round=args.round,
        target_owner=args.owner,
        output=Path(args.output),
        json_path=Path(args.json) if args.json else None,
    )

    print(f"generated {args.output}")
    if args.json:
        print(f"generated {args.json}")
    print(f"entries={summary['entries']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
