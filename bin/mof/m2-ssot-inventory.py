#!/usr/bin/env python3
"""MOF D3 / ADR-0240 P1-1 — M2 YAML SSOT 清单 (批迁移前置).

扫描 ecos mof/m2/*.yaml, 输出:
  - schema 清单 (m2_type / file / has_fields)
  - 建议批次 (每批 ≤8, ADR-0240)
  - 可选: 与 model-driven 侧 Python 符号对照 (若子模块已 checkout)

Usage:
  python3 bin/mof/m2-ssot-inventory.py
  python3 bin/mof/m2-ssot-inventory.py --json
  python3 bin/mof/m2-ssot-inventory.py --batch-size 8
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
DEFAULT_M2 = REPO / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m2"
DEFAULT_MD = REPO / "projects" / "model-driven"


def _load_schema(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"file": path.name, "error": str(e)}
    if not isinstance(data, dict):
        return {"file": path.name, "error": "not a mapping"}
    keys = list(data.keys())
    return {
        "file": path.name,
        "m2_type": data.get("m2_type") or data.get("type") or path.stem,
        "has_fields": "fields" in data or "properties" in data,
        "has_state_machine": "state_machine" in data or "lifecycle" in data,
        "top_keys": keys[:12],
        "key_count": len(keys),
    }


def inventory(m2_dir: Path, batch_size: int, model_driven: Path | None) -> dict:
    files = sorted(m2_dir.glob("*.yaml")) if m2_dir.is_dir() else []
    schemas = [_load_schema(p) for p in files]
    ok = [s for s in schemas if "error" not in s]
    err = [s for s in schemas if "error" in s]

    batches: list[list[str]] = []
    cur: list[str] = []
    for s in ok:
        cur.append(s["file"])
        if len(cur) >= batch_size:
            batches.append(cur)
            cur = []
    if cur:
        batches.append(cur)

    md_py: list[str] = []
    if model_driven and model_driven.is_dir():
        for p in sorted(model_driven.rglob("*.py")):
            name = p.name
            if name.startswith("m2") or "schema" in name.lower() or "lifecycle" in name.lower():
                try:
                    rel = str(p.relative_to(model_driven))
                except ValueError:
                    rel = str(p)
                md_py.append(rel)

    return {
        "ssot": str(m2_dir.relative_to(REPO)) if m2_dir.is_relative_to(REPO) else str(m2_dir),
        "adr": "ADR-0240 P1-1 (M2 YAML SSOT + 分批 ≤8)",
        "schema_total": len(schemas),
        "schema_ok": len(ok),
        "schema_error": len(err),
        "with_fields": sum(1 for s in ok if s.get("has_fields")),
        "with_state_machine": sum(1 for s in ok if s.get("has_state_machine")),
        "batch_size": batch_size,
        "batch_count": len(batches),
        "batches": [
            {"batch_index": i + 1, "files": b, "count": len(b)}
            for i, b in enumerate(batches)
        ],
        "schemas": ok + err,
        "model_driven_candidates": md_py[:80],
        "model_driven_candidate_count": len(md_py),
        "next_action": (
            "Pick batch_index=1 for first PR; keep generation path DO-NOT-EDIT + 溯源指针"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MOF D3 M2 YAML SSOT inventory (P1-1 prep)")
    ap.add_argument("--m2-dir", type=Path, default=DEFAULT_M2)
    ap.add_argument("--model-driven", type=Path, default=DEFAULT_MD)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--emit-batch",
        type=int,
        default=0,
        help="写出第 N 批迁移计划 YAML 到 --emit-path (默认 .omo/state/m2-ssot-batch-N.yaml)",
    )
    ap.add_argument("--emit-path", type=Path, default=None)
    args = ap.parse_args(argv)

    if not args.m2_dir.is_dir():
        print(f"ERROR: m2 dir missing: {args.m2_dir}", file=sys.stderr)
        return 2

    md = args.model_driven if args.model_driven.is_dir() else None
    rep = inventory(args.m2_dir, max(1, args.batch_size), md)

    if args.emit_batch:
        batches = rep.get("batches") or []
        idx = args.emit_batch
        if idx < 1 or idx > len(batches):
            print(
                f"ERROR: --emit-batch {idx} out of range 1..{len(batches)}",
                file=sys.stderr,
            )
            return 2
        chosen = batches[idx - 1]
        plan = {
            "schema": "m2-ssot-batch-plan-v1",
            "adr": "ADR-0240 P1-1",
            "batch_index": idx,
            "batch_size_cap": rep["batch_size"],
            "files": chosen["files"],
            "count": chosen["count"],
            "ssot": rep["ssot"],
            "next_action": (
                "Implement generation path DO-NOT-EDIT + 溯源指针; "
                "do not edit m2 yaml semantics in this plan file"
            ),
            "redline": "不碰 LifecycleStage 8 阶段枚举; 不改 m3.yaml 字段语义 (P52)",
        }
        out_path = args.emit_path or (
            REPO / ".omo" / "state" / f"m2-ssot-batch-{idx}.yaml"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            yaml.safe_dump(plan, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        print(f"wrote {out_path} ({chosen['count']} files)")
        if args.json:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0

    print("=" * 60)
    print("📋 MOF D3 M2 SSOT inventory (ADR-0240 P1-1)")
    print("=" * 60)
    print(f"SSOT: {rep['ssot']}")
    print(
        f"schemas: {rep['schema_total']} ok={rep['schema_ok']} err={rep['schema_error']} | "
        f"fields={rep['with_fields']} state_machine={rep['with_state_machine']}"
    )
    print(f"batches (≤{rep['batch_size']}): {rep['batch_count']}")
    for b in rep["batches"][:6]:
        print(f"  batch {b['batch_index']}: {b['count']} → {', '.join(b['files'][:4])}…")
    if len(rep["batches"]) > 6:
        print(f"  … +{len(rep['batches']) - 6} more batches")
    print(f"model-driven py candidates: {rep['model_driven_candidate_count']}")
    print(f"next: {rep['next_action']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
