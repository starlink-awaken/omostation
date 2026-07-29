#!/usr/bin/env python3
"""P84 对抗场景失败报告 — 能力轨 triage 工具 (不计产能轨).

按失败 criterion 聚合 ADV/GEN-ADV 场景, 支撑 S/C 类分诊 (审计 2026-07-28-p84-w2-27fail).

Usage:
  python3 bin/collab/adv-fail-report.py
  python3 bin/collab/adv-fail-report.py --json
  python3 bin/collab/adv-fail-report.py --dir .omo/_delivery/collab-scenarios
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scenario_lib import load_scenario, run_scenario  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DEFAULT_DIR = REPO / ".omo" / "_delivery" / "collab-scenarios"


def collect(dir_path: Path) -> dict:
    paths = sorted(dir_path.glob("*.yaml"))
    failed: list[dict] = []
    passed_n = 0
    adv_n = 0
    criterion_fail = Counter()
    by_prefix: dict[str, list[str]] = defaultdict(list)

    for p in paths:
        try:
            sc = load_scenario(p)
        except Exception as e:  # noqa: BLE001
            failed.append({"file": p.name, "error": str(e), "adversarial": None})
            continue
        r = run_scenario(sc)
        if not r.adversarial:
            continue
        adv_n += 1
        if r.passed:
            passed_n += 1
            continue
        bad = [c.name for c in r.criteria if not c.passed]
        for name in bad:
            criterion_fail[name] += 1
        prefix = p.name.split("-")[0] if "-" in p.name else p.name
        by_prefix[prefix].append(p.name)
        failed.append(
            {
                "file": p.name,
                "scenario_id": r.scenario_id,
                "category": r.category,
                "failed_criteria": bad,
                "evidence": [
                    {"name": c.name, "evidence": c.evidence}
                    for c in r.criteria
                    if not c.passed
                ],
            }
        )

    return {
        "data_source": "构造场景 (能力轨 only)",
        "adversarial_total": adv_n,
        "adversarial_passed": passed_n,
        "adversarial_failed": len([f for f in failed if "error" not in f or f.get("adversarial") is not False]),
        "fail_count": len(failed),
        "criterion_fail_histogram": dict(criterion_fail.most_common()),
        "by_file_prefix": {k: sorted(v) for k, v in sorted(by_prefix.items())},
        "failures": failed,
        "redline_note": "本报告仅能力轨; 禁止把失败场景数计入产能轨 done",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P84 adversarial fail report (capability track)")
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not args.dir.is_dir():
        print(f"ERROR: scenario dir missing: {args.dir}", file=sys.stderr)
        return 2

    report = collect(args.dir)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print("=" * 60)
    print("🛡️  P84 对抗场景失败报告 (能力轨, 不计产能轨)")
    print("=" * 60)
    print(
        f"对抗集: {report['adversarial_total']} | "
        f"通过 {report['adversarial_passed']} | "
        f"失败条目 {report['fail_count']}"
    )
    print("\n失败 criterion 直方图:")
    for name, n in report["criterion_fail_histogram"].items():
        print(f"  {n:3d}  {name}")
    print("\n按文件前缀:")
    for prefix, files in report["by_file_prefix"].items():
        print(f"  {prefix}: {len(files)} → {', '.join(files[:5])}" + ("…" if len(files) > 5 else ""))
    print("\n明细 (失败 criterion):")
    for f in report["failures"][:40]:
        if "error" in f:
            print(f"  ❌ {f['file']}: load error {f['error']}")
            continue
        print(f"  ❌ {f['file']}: {', '.join(f['failed_criteria'])}")
    if len(report["failures"]) > 40:
        print(f"  … +{len(report['failures']) - 40} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
