#!/usr/bin/env python3
"""
auto-backfill-omotask-fields v2 — ruamel.yaml 增量回填
========================================================
P7 推进: v1 用 PyYAML 重写整个 properties 段丢失原引号风格.
v2 用 ruamel.yaml 增量改写, 保留原始引号/缩进风格.

回填策略 (保守, 不虚报):
- prerequisites: 从 .omo/tasks/ 源读透传
- sub_gates/red_lines/phase_*_condition/final_close_condition/forbidden_claims/assessment: 留空
- evidence: 从 .omo/tasks/ 源读透传
- signals: RoadmapPhase 留空 (业务信号); Task 从 description 推断
- m3_parent: 必填 (auto-fill "ManagementElement.OMOTask" if missing)

Usage:
    cd projects/ecos
    uv run --with ruamel.yaml python3 src/ecos/ssot/tools/auto-backfill-omotask-fields-v2.py
    uv run --with ruamel.yaml python3 src/ecos/ssot/tools/auto-backfill-omotask-fields-v2.py --sync
    uv run --with ruamel.yaml python3 src/ecos/ssot/tools/auto-backfill-omotask-fields-v2.py --strict
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    from ruamel.yaml import YAML

    _YAML = YAML()
    _YAML.preserve_quotes = True
    _YAML.indent(mapping=2, sequence=2, offset=0)
except ImportError:
    print("FATAL: ruamel.yaml not installed. Run: uv add ruamel.yaml", file=sys.stderr)
    sys.exit(2)

TOOL_PATH = Path(__file__).resolve()
REPO_ROOT = TOOL_PATH.parent.parent.parent.parent.parent
WORKSPACE_ROOT = TOOL_PATH.parent.parent.parent.parent.parent.parent.parent

M1_OMO_LAYER = REPO_ROOT / "src" / "ecos" / "ssot" / "mof" / "m1" / "omo_layer"
OMO_TASKS_ACTIVE = WORKSPACE_ROOT / ".omo" / "tasks" / "active"
OMO_TASKS_PLANNED = WORKSPACE_ROOT / ".omo" / "tasks" / "planned"
OMO_TASKS_DONE = WORKSPACE_ROOT / ".omo" / "tasks" / "done"

BACKFILL_FIELDS = [
    "prerequisites",
    "sub_gates",
    "red_lines",
    "phase_open_condition",
    "phase_blocked_condition",
    "final_close_condition",
    "forbidden_claims",
    "evidence",
    "assessment",
]
INFO_FIELDS = ["m3_parent", "signals"]


def load_omotask_m1() -> list[Path]:
    if not M1_OMO_LAYER.exists():
        return []
    return sorted(M1_OMO_LAYER.glob("OMOTASK-*.yaml"))


def load_yaml_ruamel(path: Path) -> dict:
    return _YAML.load(path.read_text(encoding="utf-8"))


def save_yaml_ruamel(path: Path, data: dict) -> None:
    from io import StringIO

    buf = StringIO()
    _YAML.dump(data, buf)
    path.write_text(buf.getvalue(), encoding="utf-8")


def load_omo_tasks() -> dict:
    out = {}
    for d in (OMO_TASKS_ACTIVE, OMO_TASKS_PLANNED, OMO_TASKS_DONE):
        if not d.exists():
            continue
        for f in d.glob("*.yaml"):
            try:
                data = _YAML.load(f.read_text(encoding="utf-8"))
            except Exception:  # defensive fallback
                continue
            if isinstance(data, dict) and "id" in data:
                out[data["id"]] = data
    return out


def backfill_node(file_path: Path, omo_tasks: dict) -> dict:
    """dry-run: 读 + backfill in-memory (不改磁盘), 返回 result dict."""
    data = load_yaml_ruamel(file_path)
    return backfill_data(data, file_path, omo_tasks)


def backfill_data(data: dict, file_path: Path, omo_tasks: dict) -> dict:
    if not isinstance(data, dict) or "id" not in data:
        return {
            "id": "?",
            "file": str(file_path),
            "changed": False,
            "added": [],
            "status": "skip",
        }

    nid = data["id"]
    omo_id = nid.replace("OMOTASK-", "")
    omo_data = omo_tasks.get(omo_id, {})
    properties = data.get("properties")
    if properties is None:
        properties = {}
        data["properties"] = properties
    if not isinstance(properties, dict):
        properties = {}
        data["properties"] = properties

    added = []
    subtype = data.get("subtype", "Task")

    if subtype == "RoadmapPhase":
        for f in BACKFILL_FIELDS:
            if f in properties and properties[f]:
                continue
            if f in ("prerequisites", "evidence") and f in omo_data:
                val = omo_data[f]
                if isinstance(val, list) and val:
                    properties[f] = val
                    added.append(f"{f}<-omo")
                    continue

    for f in INFO_FIELDS:
        if f in properties and properties[f]:
            continue
        if f == "m3_parent":
            properties["m3_parent"] = "ManagementElement.OMOTask"
            added.append("m3_parent<-default")
        elif f == "signals" and subtype == "Task":
            # 不管 description 是否存在都给 signals (task 默认运行信号)
            properties["signals"] = [f"task-{omo_id}-running"]
            added.append("signals<-default")

    return {
        "id": nid,
        "file": str(file_path),
        "changed": len(added) > 0,
        "added": added,
        "status": "ok",
    }


def format_report(results: list[dict]) -> str:
    lines = []
    lines.append("=" * 72)
    lines.append(
        "  auto-backfill-omotask-fields v2 — OMOTask 字段批量回填 (ruamel.yaml)"
    )
    lines.append("=" * 72)
    lines.append(f"  时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    total = len(results)
    changed = [r for r in results if r["changed"]]
    field_added = Counter()
    for r in changed:
        for a in r["added"]:
            field = a.split("<-")[0]
            field_added[field] += 1
    lines.append("  ── 统计 ──")
    lines.append(f"  节点总数: {total}")
    lines.append(f"  待回填 (changed): {len(changed)}")
    lines.append(f"  已有 (unchanged): {total - len(changed)}")
    lines.append("")
    if field_added:
        lines.append("  ── 待回填字段 ──")
        for f, c in field_added.most_common(10):
            lines.append(f"    {f:30} {c}x")
        lines.append("")
    lines.append("=" * 72)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="OMOTask 字段批量回填 (v2 ruamel.yaml)"
    )
    parser.add_argument("--sync", action="store_true", help="实际写盘")
    parser.add_argument(
        "--json", dest="json_output", action="store_true", help="JSON 输出"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="写盘后跑 omo-fields-completeness-check --strict",
    )
    args = parser.parse_args()

    files = load_omotask_m1()
    omo_tasks = load_omo_tasks()
    results = []

    for f in files:
        if args.sync:
            # 重新读 + backfill + 写盘, 保证内存和磁盘一致
            data = load_yaml_ruamel(f)
            result = backfill_data(data, f, omo_tasks)
            if result["changed"]:
                save_yaml_ruamel(f, data)
        else:
            result = backfill_node(f, omo_tasks)
        results.append(result)

    if args.sync:
        n = sum(1 for r in results if r["changed"])
        print(f"✅ 写盘 {n} 个节点", file=sys.stderr)

    if args.strict:
        result = subprocess.run(
            [
                "python3",
                "src/ecos/ssot/tools/omo-fields-completeness-check.py",
                "--strict",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.returncode != 0:
            print("❌ omo-fields-completeness-check --strict 失败", file=sys.stderr)
            sys.exit(1)

    if args.json_output:
        print(
            json.dumps(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "total": len(results),
                    "changed": sum(1 for r in results if r["changed"]),
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
    else:
        print(format_report(results))


if __name__ == "__main__":
    main()
