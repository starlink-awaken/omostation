#!/usr/bin/env python3
"""governance-summary: GaC 治理系统摘要指标.

Outputs key governance metrics: rule counts, dimension balance,
ADR coverage, CI gate coverage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    registry_path = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
    if not registry_path.exists():
        if args.json:
            print(json.dumps({"ok": False, "reason": "governance-checks.yaml not found"}))
        else:
            print("governance-summary: FAIL (registry not found)")
        return 1

    with open(registry_path) as f:
        docs = list(yaml.safe_load_all(f))

    for doc in docs:
        if 'gac' not in doc:
            continue
        rules = doc['gac']['rules']
        active = [r for r in rules if r.get('lifecycle') == 'active']
        draft = [r for r in rules if r.get('lifecycle') == 'draft']

        dims = {}
        for r in active:
            d = r.get('dimension', '?')
            dims[d] = dims.get(d, 0) + 1

        no_adr = [r['id'] for r in active if not r.get('adr')]
        adr_cov = len(active) - len(no_adr)
        with_ci = [r['id'] for r in active if 'ci_gate' in r.get('executor', [])]
        freeze = doc['gac'].get('freeze', {}).get('max_rules', 0)

        report = {
            "ok": True,
            "rule_count": {"active": len(active), "draft": len(draft), "total": len(rules), "freeze": freeze},
            "dimension_balance": dims,
            "adr_coverage": {"covered": adr_cov, "total": len(active), "percent": round(adr_cov / len(active) * 100, 1) if active else 0},
            "ci_gate_coverage": {"with_ci": len(with_ci), "total": len(active), "percent": round(len(with_ci) / len(active) * 100, 1) if active else 0},
        }

        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print(f"GaC: {len(active)} active, {len(draft)} draft, {len(rules)} total (freeze={freeze})")
            print(f"维度: X1={dims.get('X1',0)} X2={dims.get('X2',0)} X3={dims.get('X3',0)} X4={dims.get('X4',0)}")
            print(f"ADR: {adr_cov}/{len(active)} ({round(adr_cov/len(active)*100,1) if active else 0}%)")
            print(f"CI: {len(with_ci)}/{len(active)} ({round(len(with_ci)/len(active)*100,1) if active else 0}%)")
        return 0

    if args.json:
        print(json.dumps({"ok": False, "reason": "no gac section found"}))
    else:
        print("governance-summary: FAIL (no gac section)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
