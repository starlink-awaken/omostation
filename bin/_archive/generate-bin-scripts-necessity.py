#!/usr/bin/env python3
"""Generate a long-term scripts necessity report from the bin/scripts manifest."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime, timezone
from pathlib import Path


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _normalize_action(entry: dict) -> str:
    return str(entry.get("action", "pending")).strip() or "pending"


def _is_managed(entry: dict) -> bool:
    status = str(entry.get("status", "")).strip().lower()
    return status in {"", "managed", "active", "accepted", "approved", "stable"}


def _dedupe_manifest(entries: list[dict]) -> tuple[list[dict], int]:
    seen: set[tuple[str, str, str, str, str]] = set()
    deduped: list[dict] = []
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
        deduped.append(entry)

    return deduped, duplicate_count


def _as_md_table(rows: list[tuple[str, ...]], headers: list[str]) -> str:
    if not rows:
        return "None\n"
    width = [len(h) for h in headers]
    for row in rows:
        for idx, col in enumerate(row):
            width[idx] = max(width[idx], len(str(col)))
    header_row = "| " + " | ".join(h.ljust(width[i]) for i, h in enumerate(headers)) + " |"
    sep_row = "| " + " | ".join("-" * width[i] for i in range(len(headers))) + " |"
    lines = [header_row, sep_row]
    for row in rows:
        lines.append("| " + " | ".join(str(col).ljust(width[idx]) for idx, col in enumerate(row)) + " |")
    return "\n".join(lines) + "\n"


def build_report(manifest_entries: list[dict], audit_payload: dict | None) -> str:
    total_entries = len(manifest_entries)
    action_counter: Counter[str] = Counter()
    owner_counter: Counter[str] = Counter()
    managed_counter: Counter[str] = Counter()

    close_rows: list[tuple[str, ...]] = []
    shim_rows: list[tuple[str, ...]] = []
    ssot_rows: list[tuple[str, ...]] = []

    for entry in manifest_entries:
        action = _normalize_action(entry)
        owner = str(entry.get("owner", "governance")).strip()
        action_counter[action] += 1
        owner_counter[owner] += 1
        managed_counter[action + (":managed" if _is_managed(entry) else ":unmanaged")] += 1

        evidence = entry.get("evidence", {}) if isinstance(entry.get("evidence"), dict) else {}
        row = (
            str(entry.get("name", "")),
            owner,
            str(entry.get("status", "")) or "managed",
            action,
            str(evidence.get("decision_round", "-")),
            str(evidence.get("due_date", "-")),
            str(evidence.get("risk_score", "-")),
            str(entry.get("bin", "")),
            str(entry.get("scripts", "")),
        )
        if action == "close-duplicate-gap-first":
            close_rows.append(row)
        elif action == "bin-master, scripts-compat-shim":
            shim_rows.append(row)
        elif action == "bin-ssot-master, root-wrapper, scripts-compat-shim":
            ssot_rows.append(row)

    close_rows.sort(key=lambda r: (r[1], r[0]))
    shim_rows.sort(key=lambda r: (r[1], r[0]))
    ssot_rows.sort(key=lambda r: (r[1], r[0]))

    lines = []
    lines.append("# scripts 兼容层与并行能力收敛清单（快照）")
    lines.append("")

    generated_at = datetime.now(tz=UTC).isoformat()
    lines.append(f"- 生成时间: {generated_at}")
    lines.append("- 清单入口: `docs/operations/bin-scripts-convergence-manifest.json`")
    lines.append(f"- 清单总条目: **{total_entries}**")

    if audit_payload:
        stats = audit_payload.get("stats", {})
        lines.append(f"- 当前扫描总脚本: {stats.get('total_scripts', '-')}")
        lines.append(f"- 并行候选（bin/scripts 重名）: {stats.get('parallel_candidates', '-')}")
        lines.append(f"- 并行缺口: {stats.get('parallel_manifest_gaps', '-')}")
        lines.append(
            "- 管控并行（managed/high-confidence）: "
            f"{stats.get('managed_parallel_duplicates', '-')}, 未控高风险并行: "
            f"{stats.get('unmanaged_parallel_duplicates', '-')}",
        )
    else:
        lines.append("- 当前扫描总脚本: -")
        lines.append("- 并行候选（bin/scripts 重名）: -")
        lines.append("- 并行缺口: -")

    lines.append("")
    lines.append("## 说明")
    lines.append("- 依据 `(name, bin, scripts, action, owner)` 去重后统计和汇总")
    lines.append("")
    lines.append("## 一、全量分层")
    lines.append("- 按 action 统计:")
    for action, count in sorted(action_counter.items()):
        managed_key = action + ":managed"
        unmanaged_key = action + ":unmanaged"
        lines.append(
            f"  - `{action}`: {count}（managed={managed_counter.get(managed_key, 0)} "
            f"/ unmanaged={managed_counter.get(unmanaged_key, 0)}）"
        )
    lines.append("- 按 owner 统计:")
    for owner, count in sorted(owner_counter.items()):
        lines.append(f"  - {owner}: {count}")

    lines.append("")
    lines.append("## 二、`close-duplicate-gap-first`（优先消化）")
    lines.append(
        _as_md_table(
            [
                (name, owner, status, action, round_name, due_date, risk, bin_path, scripts_path)
                for name, owner, status, action, round_name, due_date, risk, bin_path, scripts_path in close_rows
            ],
            ["name", "owner", "status", "action", "round", "due", "risk", "bin", "scripts"],
        )
    )

    lines.append("\n## 三、`bin-master, scripts-compat-shim`（兼容入口保留）\n")
    lines.append(f"共 {len(shim_rows)} 条")
    lines.append(
        _as_md_table(
            [
                (name, owner, status, action, due, bin_path, scripts_path)
                for name, owner, status, action, _round_name, due, risk, bin_path, scripts_path in shim_rows
            ],
            ["name", "owner", "status", "action", "due", "bin", "scripts"],
        )
    )

    lines.append("## 四、`bin-ssot-master, root-wrapper, scripts-compat-shim`（SSOT wrapper）\n")
    lines.append(f"共 {len(ssot_rows)} 条")
    if ssot_rows:
        lines.append(
            _as_md_table(
                [
                    (name, owner, status, action, due, bin_path, scripts_path)
                    for name, owner, status, action, _round_name, due, risk, bin_path, scripts_path in ssot_rows
                ],
                ["name", "owner", "status", "action", "due", "bin", "scripts"],
            )
        )

    lines.append("")
    lines.append("## 五、实施建议")
    lines.append("")
    lines.append("- **阶段策略**：")
    lines.append("  - 第一优先：保持 `close-duplicate-gap-first` 组 manifest 约定不变，按 owner 落地到对应项目或子域。")
    lines.append(
        "  - 第二优先：每周执行一次 `make bin-tool-registry-scripts-necessity`，复核新增并行缺口并回填 manifest。"
    )
    lines.append("  - 第三优先：对高频调用脚本，确保根 `bin` 与 `scripts/bin` 的 shim 行为一致，并保留兼容入口。")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="docs/operations/bin-scripts-convergence-manifest.json")
    parser.add_argument("--snapshot", default="")
    parser.add_argument("--output", default="docs/operations/bin-scripts-necessity-report.md")
    parser.add_argument("--json", default="")
    args = parser.parse_args()

    manifest = _load_json(Path(args.manifest))
    entries = manifest.get("entries", []) if isinstance(manifest, dict) else []
    entries = [entry for entry in entries if isinstance(entry, dict)]
    entries, duplicate_count = _dedupe_manifest(entries)
    if duplicate_count:
        print(f"warn: manifest contains duplicate entries, skipped {duplicate_count}", file=sys.stderr)

    snapshot = _load_json(Path(args.snapshot)) if args.snapshot else {}
    report = build_report(entries, snapshot if snapshot else None)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    if args.json:
        summary = {
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "entries": len(entries),
            "close_duplicate": len([e for e in entries if _normalize_action(e) == "close-duplicate-gap-first"]),
            "compat_shim": len([e for e in entries if _normalize_action(e) == "bin-master, scripts-compat-shim"]),
            "ssot_wrapper": len(
                [e for e in entries if _normalize_action(e) == "bin-ssot-master, root-wrapper, scripts-compat-shim"]
            ),
        }
        json_path = Path(args.json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"generated {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
