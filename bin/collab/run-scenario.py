#!/usr/bin/env python3
"""P84 W1 协作场景 runner — 跑场景库, 输出 verdict.

Usage:
  run-scenario.py <scenario.yaml>
  run-scenario.py --dir <scenarios_dir>      # 全量跑批
  run-scenario.py ... --json                 # 机器可读 JSON 输出

能力轨专用 (P84 §0): 结果只计能力轨, 绝不计产能轨.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scenario_lib import load_scenario, run_scenario  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="P84 W1 协作场景 runner (能力轨)")
    ap.add_argument("scenario", nargs="?", help="单场景 YAML 路径")
    ap.add_argument("--dir", dest="dir", help="批量跑目录")
    ap.add_argument("--json", action="store_true", help="机器可读 JSON 输出")
    args = ap.parse_args()

    paths: list[Path] = []
    if args.dir:
        paths = sorted(Path(args.dir).rglob("*.yaml"))
    elif args.scenario:
        paths = [Path(args.scenario)]
    else:
        ap.error("需提供 scenario 或 --dir")

    results = []
    for p in paths:
        try:
            sc = load_scenario(p)
            r = run_scenario(sc)
            results.append({"file": str(p), "result": r.to_dict()})
        except Exception as e:  # noqa: BLE001
            results.append({"file": str(p), "error": str(e)})

    passed_n = sum(1 for r in results if "result" in r and r["result"]["passed"])
    failed_n = len(results) - passed_n
    summary = {"total": len(results), "passed": passed_n, "failed": failed_n}

    if args.json:
        print(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2))
    else:
        print("=" * 60)
        print("🔍 P84 W1 协作场景跑批 (能力轨, 不计产能轨)")
        print("=" * 60)
        for r in results:
            if "error" in r:
                print(f"❌ {r['file']}: {r['error']}")
                continue
            res = r["result"]
            mark = "✅" if res["passed"] else "❌"
            adv = " [对抗]" if res["adversarial"] else ""
            print(
                f"{mark} {res['scenario_id']} ({res['category']}{adv}) "
                f"rounds={res['resolution_rounds']} silent={res['silent_loss']}"
            )
            for c in res["criteria"]:
                cm = "✅" if c["passed"] else "❌"
                print(f"    {cm} {c['name']}: {c['evidence']}")
        print(f"\n📊 合计: {summary['total']} | 通过 {summary['passed']} | 失败 {summary['failed']}")
        adv_total = sum(1 for r in results if "result" in r and r["result"]["adversarial"])
        adv_fail = sum(
            1
            for r in results
            if "result" in r and r["result"]["adversarial"] and not r["result"]["passed"]
        )
        if adv_total:
            pct = adv_total / max(summary["total"], 1) * 100
            print(
                f"🛡️  对抗集: {adv_total}/{summary['total']} ({pct:.0f}%), "
                f"其中失败 {adv_fail} (P84: 全过=对抗不足须加强)"
            )
    return 0 if failed_n == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
