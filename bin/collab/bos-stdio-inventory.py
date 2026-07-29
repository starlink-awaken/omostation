#!/usr/bin/env python3
"""BOS stdio 占比盘点 — phase45 residual 工程债可执行面 (非假迁移).

读 projects/agora/etc/bos-services.yaml, 统计 transport 分布与 stdio-ish 比.
红线: 不改 transport 标签冲数; 本工具只读 + 报告.

Usage:
  python3 bin/collab/bos-stdio-inventory.py
  python3 bin/collab/bos-stdio-inventory.py --json
  python3 bin/collab/bos-stdio-inventory.py --target-ratio 0.65
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
DEFAULT_REG = REPO / "projects" / "agora" / "etc" / "bos-services.yaml"
STDIO_ISH = frozenset({"stdio", "mcp_stdio"})


def load_services(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    for doc in yaml.safe_load_all(raw):
        if isinstance(doc, dict) and isinstance(doc.get("services"), list):
            return [s for s in doc["services"] if isinstance(s, dict)]
    raise ValueError(f"no services: list in {path}")


def inventory(path: Path, target_ratio: float) -> dict:
    svcs = load_services(path)
    transports = Counter(str(s.get("transport") or "missing") for s in svcs)
    total = len(svcs)
    stdio_ish = sum(transports[t] for t in STDIO_ISH if t in transports)
    ratio = round(stdio_ish / total, 3) if total else 0.0
    by_domain: dict[str, dict] = {}
    for s in svcs:
        d = str(s.get("domain") or "unknown")
        bucket = by_domain.setdefault(d, {"total": 0, "stdio_ish": 0})
        bucket["total"] += 1
        if str(s.get("transport") or "") in STDIO_ISH:
            bucket["stdio_ish"] += 1
    return {
        "registry": str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path),
        "service_total": total,
        "transport_histogram": dict(transports.most_common()),
        "stdio_ish_count": stdio_ish,
        "stdio_ish_ratio": ratio,
        "target_ratio": target_ratio,
        "meets_target": ratio < target_ratio,
        "gap_services": max(0, stdio_ish - int(target_ratio * total - 1e-9)),
        "by_domain": {
            d: {
                **b,
                "ratio": round(b["stdio_ish"] / b["total"], 3) if b["total"] else 0,
            }
            for d, b in sorted(by_domain.items())
        },
        "redline_note": "只读盘点; 禁止仅改 transport 标签降比 (须真实 internal/mcp_proxy+mcp_tool)",
        "task_ref": ".omo/tasks/planned/needs-human-p80-phase45-bos-stdio.yaml",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="BOS stdio inventory (read-only)")
    ap.add_argument("--registry", type=Path, default=DEFAULT_REG)
    ap.add_argument("--target-ratio", type=float, default=0.65)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if not args.registry.is_file():
        print(f"ERROR: missing {args.registry}", file=sys.stderr)
        return 2
    rep = inventory(args.registry, args.target_ratio)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0
    print("=" * 60)
    print("📦 BOS stdio inventory (read-only)")
    print("=" * 60)
    print(f"registry: {rep['registry']}")
    print(f"services: {rep['service_total']}")
    print(f"stdio-ish: {rep['stdio_ish_count']} / {rep['service_total']} = {rep['stdio_ish_ratio']}")
    print(f"target: < {rep['target_ratio']} → meets={rep['meets_target']}")
    print("transports:")
    for t, n in rep["transport_histogram"].items():
        print(f"  {t:16} {n}")
    print("by domain (top stdio-ish):")
    ranked = sorted(
        rep["by_domain"].items(), key=lambda kv: (-kv[1]["stdio_ish"], kv[0])
    )
    for d, b in ranked[:12]:
        print(f"  {d:16} stdio_ish={b['stdio_ish']:3}/{b['total']:<3} ratio={b['ratio']}")
    print(f"\n{rep['redline_note']}")
    return 0 if rep["meets_target"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
