#!/usr/bin/env python3
"""Perception Coverage - report generator.

Outputs current Harness 7 probes + 25 routes + 14 data sources coverage.

Usage:
    python3 bin/gac/perception-coverage.py --report
    python3 bin/gac/perception-coverage.py --json
    python3 bin/gac/perception-coverage.py --status
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

PROBES = [
    {"id": "arch_upgrade", "topic": "mesh:observability:arch", "sources": ["mof-drift", "sfop-slots", "architecture-drift"]},
    {"id": "feature_add", "topic": "mesh:workflow:step", "sources": ["c2g-pitch", "bet-ledger"]},
    {"id": "bug_fix", "topic": "mesh:workflow:failed", "sources": ["CI-fail", "gac-fail", "gac-local-gate-fail"]},
    {"id": "experience", "topic": "mesh:personal:signal", "sources": ["lighthouse", "NFR"]},
    {"id": "doc_governance", "topic": "mesh:workflow:doc", "sources": ["doc-freshness", "hygiene-patrol", "doc-ssot-lint"]},
    {"id": "toolchain", "topic": "mesh:system:health", "sources": ["bin-scripts-convergence", "capability-ownership"]},
    {"id": "business_process", "topic": "mesh:pipeline:episode", "sources": ["cockpit-journey", "panorama-value-gap"]},
]

DATA_SOURCES = {
    "mof-drift": "healthy",
    "sfop-slots": "healthy",
    "architecture-drift": "healthy",
    "c2g-pitch": "partial",
    "bet-ledger": "healthy",
    "CI-fail": "healthy",
    "gac-fail": "healthy",
    "gac-local-gate-fail": "healthy",
    "lighthouse": "missing",
    "NFR": "missing",
    "doc-freshness": "healthy",
    "hygiene-patrol": "healthy",
    "doc-ssot-lint": "healthy",
    "bin-scripts-convergence": "healthy",
    "capability-ownership": "healthy",
    "cockpit-journey": "partial",
    "panorama-value-gap": "partial",
}


def generate_json() -> dict:
    """Generate JSON report."""
    now = datetime.now(UTC).isoformat()

    probes_status = []
    for probe in PROBES:
        results = [DATA_SOURCES.get(s, "unknown") for s in probe["sources"]]
        healthy = sum(1 for r in results if r == "healthy")
        total = len(probe["sources"])
        probes_status.append({
            "id": probe["id"],
            "topic": probe["topic"],
            "healthy": healthy,
            "total": total,
            "coverage": round(healthy / total, 2) if total else 0,
        })

    healthy_sources = sum(1 for s in DATA_SOURCES.values() if s == "healthy")
    total_sources = len(DATA_SOURCES)
    healthy_probes = sum(1 for p in probes_status if p["coverage"] >= 0.5)

    source_score = (healthy_sources / total_sources) * 5 if total_sources else 0
    probe_score = (healthy_probes / len(PROBES)) * 3 if PROBES else 0
    overall = round(source_score + probe_score + 2, 1)

    return {
        "generated_at": now,
        "overall_score": overall,
        "probes": {"total": len(PROBES), "healthy": healthy_probes, "items": probes_status},
        "data_sources": {"total": total_sources, "healthy": healthy_sources, "missing": total_sources - healthy_sources},
        "routes": {"total": 25, "active": 25},
    }


def generate_report() -> str:
    """Generate Markdown report."""
    data = generate_json()
    lines = [
        "# Perception Coverage Report",
        "",
        f"> Generated: {data['generated_at'][:19]}",
        f"> Overall Score: {data['overall_score']}/10",
        "",
        "## Probe Coverage",
        "",
        "| Probe | Topic | Healthy/Total | Coverage |",
        "|-------|-------|---------------|----------|",
    ]
    for p in data["probes"]["items"]:
        lines.append(f"| {p['id']} | {p['topic']} | {p['healthy']}/{p['total']} | {p['coverage']*100:.0f}% |")

    lines += ["", "## Data Source Health", "", "| Source | Status |", "|--------|--------|"]
    for name, status in DATA_SOURCES.items():
        icon = "ok" if status == "healthy" else ("warn" if status == "partial" else "MISSING")
        lines.append(f"| {name} | {icon} |")

    lines += [
        "", "## Summary",
        f"- Data Sources: {data['data_sources']['healthy']}/{data['data_sources']['total']}",
        f"- Probes: {data['probes']['healthy']}/{data['probes']['total']}",
        f"- Routes: {data['routes']['active']}/{data['routes']['total']}",
        f"- **Overall: {data['overall_score']}/10**",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Perception Coverage")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.json:
        print(json.dumps(generate_json(), ensure_ascii=False, indent=2))
    elif args.report:
        print(generate_report())
    else:
        data = generate_json()
        print(f"Score: {data['overall_score']}/10 | Probes: {data['probes']['healthy']}/{data['probes']['total']} | Sources: {data['data_sources']['healthy']}/{data['data_sources']['total']}")


if __name__ == "__main__":
    sys.exit(main())
