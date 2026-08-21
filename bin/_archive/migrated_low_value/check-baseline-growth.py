#!/usr/bin/env python3
"""check-baseline-growth: baseline 文件受保护 (Z2, 治本).

Z2 根因: 第四次门被绕过, 每次换地方. 共同点: 门守代码, 没人守门的配置.
本 check 守 baseline 文件本身:
  - 任何 baseline 扩大 (条目增加) → BLOCKING (须人类批准)
  - 缩小 (清偿存量) → 自由 (PASS)
  - 不变 → PASS

baseline-baseline.txt (元 baseline): 记录各 baseline 文件当前行数 (Z2 冻结点).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY = WORKSPACE / ".omo/_truth/registry"
BASELINE_META = REGISTRY / "baseline-baseline.txt"
BASELINE_FILES = [
    "baseline-perf-budget.txt",
    "baseline-scenario-detectors.txt",
    "baseline-scenario-growth.txt",
    "baseline-work-landed.txt",
]


def _count_lines(f: Path) -> int:
    if not f.is_file():
        return 0
    return sum(
        1
        for line in f.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    )


def _load_meta() -> dict[str, int]:
    if not BASELINE_META.is_file():
        return {}
    meta: dict[str, int] = {}
    for line in BASELINE_META.read_text(encoding="utf-8").splitlines():
        if ":" not in line or line.startswith("#"):
            continue
        name, n = line.split(":", 1)
        try:
            meta[name.strip()] = int(n.strip())
        except ValueError:
            pass
    return meta


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--dump-meta",
        action="store_true",
        help="dump 当前 baseline 行数 (生成元 baseline, Z2 冻结点)",
    )
    args = parser.parse_args(argv)

    current = {f: _count_lines(REGISTRY / f) for f in BASELINE_FILES}

    if args.dump_meta:
        print("# Z2 baseline 冻结点 (2026-07-29): 各 baseline 文件行数上限")
        print("# 扩大 (current > meta) → blocking; 缩小 (清偿) → 自由")
        for f, n in current.items():
            print(f"{f}: {n}")
        return 0

    meta = _load_meta()
    findings: list[dict] = []
    summary = {"checked": 0, "passed": 0, "blocking": 0}

    for f, n in current.items():
        summary["checked"] += 1
        if f not in meta:
            findings.append({
                "file": f,
                "kind": "no_meta",
                "current": n,
                "message": "无元 baseline 记录 (跑 --dump-meta 生成 baseline-baseline.txt)",
            })
            summary["blocking"] += 1
        elif n > meta[f]:
            findings.append({
                "file": f,
                "kind": "baseline_grew",
                "current": n,
                "meta": meta[f],
                "message": f"baseline 扩大 {meta[f]}→{n} (Z2: 门配置受保护, 须人类批准)",
            })
            summary["blocking"] += 1
        else:
            summary["passed"] += 1

    ok = summary["blocking"] == 0
    report = {"ok": ok, "summary": summary, "findings": findings}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"check-baseline-growth: {'PASS' if ok else 'FAIL'}")
        print(
            f"  checked={summary['checked']} passed={summary['passed']} "
            f"blocking={summary['blocking']}"
        )
        for fnd in findings:
            print(f"  - {fnd['file']} [{fnd['kind']}] {fnd.get('message', '')}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
