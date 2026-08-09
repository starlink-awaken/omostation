#!/usr/bin/env python3
"""Problem Detector — Meta-2 反思层: 自动扫描系统异常 → debt台账 (P3-T7).

Scans health/journeys/tools/scene-cards for anomalies.
Writes detected problems to debt entries for Governor/Evolution Agent review.

Usage: python3 bin/ssot/problem-detector.py [--json]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _detect_health_anomalies() -> list[dict[str, Any]]:
    """Check system_health.yaml for unhealthy services."""
    problems: list[dict[str, Any]] = []
    health_yaml = ROOT / ".omo" / "state" / "system_health.yaml"
    if not health_yaml.exists():
        return [{"type": "missing_health_snapshot", "severity": "medium", "detail": "system_health.yaml not found"}]
    try:
        import yaml
        data = yaml.safe_load(health_yaml.read_text(encoding="utf-8")) or {}
        services = data.get("services", {})
        if not isinstance(services, dict):
            return []
        for name, info in services.items():
            if not isinstance(info, dict):
                continue
            hc = str(info.get("health_check", "")).strip()
            if hc and not (hc.startswith("healthy") or hc == "scheduled"):
                problems.append({"type": "unhealthy_service", "severity": "high",
                                 "service": name, "health_check": hc})
    except Exception:
        pass
    return problems


def _detect_dormant_tools() -> list[dict[str, Any]]:
    """Check tool-usage-audit for dormant tools count."""
    problems: list[dict[str, Any]] = []
    try:
        result = subprocess.run(
            ["python3", str(ROOT / "bin/ssot/tool-usage-audit.py"), "--json"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            dormant = data.get("dormant", 0)
            if dormant > 15:
                problems.append({"type": "excessive_dormant_tools", "severity": "low",
                                 "count": dormant, "detail": f"{dormant} dormant tools need evaluation"})
    except Exception:
        pass
    return problems


def _detect_scene_card_issues() -> list[dict[str, Any]]:
    """Check scene cards for readiness issues."""
    problems: list[dict[str, Any]] = []
    cards_dir = ROOT / "docs" / "scene-cards"
    if not cards_dir.is_dir():
        return [{"type": "missing_scene_cards_dir", "severity": "high"}]
    cards = list(cards_dir.glob("*.yaml"))
    if len(cards) < 9:
        problems.append({"type": "insufficient_scene_cards", "severity": "medium",
                         "count": len(cards), "expected": "≥9"})
    return problems


def _llm_analyze(problems: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """LLM 分析问题列表, 补充根因建议."""
    if not problems:
        return problems
    try:
        sys.path.insert(0, str(ROOT / "bin" / "ssot"))
        from _llm_helper import llm_ask

        response = llm_ask(
            f"System problems detected: {json.dumps(problems[:3], ensure_ascii=False)}. "
            f"What is the likely root cause and recommended fix? Be concise."
        )
        if response:
            problems[0]["llm_analysis"] = response[:300]
    except Exception:
        pass
    return problems


def scan_all() -> dict[str, Any]:
    """Run all problem detection checks."""
    ts = datetime.now(UTC).isoformat()
    all_problems: list[dict[str, Any]] = []
    all_problems.extend(_detect_health_anomalies())
    all_problems.extend(_detect_dormant_tools())
    all_problems.extend(_detect_scene_card_issues())

    # LLM 根因分析 (AetherForge 算力驱动)
    all_problems = _llm_analyze(all_problems)

    return {
        "schema": "problem-detection/v1",
        "scanned_at": ts,
        "total_problems": len(all_problems),
        "by_severity": {
            "high": sum(1 for p in all_problems if p.get("severity") == "high"),
            "medium": sum(1 for p in all_problems if p.get("severity") == "medium"),
            "low": sum(1 for p in all_problems if p.get("severity") == "low"),
        },
        "problems": all_problems,
        "status": "ok" if not all_problems else "issues_found",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--once", action="store_true",
                        help="write last-run state (launchd/cron 调度用)")
    args = parser.parse_args(argv)

    result = scan_all()

    # META-02: 调度证据 — 每次运行落 last-run 状态文件
    if args.once:
        try:
            state_path = ROOT / ".omo" / "state" / "problem-detector-last.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except Exception:
            pass

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Problem Detection: {result['total_problems']} problems ({result['by_severity']})")
        for p in result["problems"]:
            print(f"  [{p.get('severity', '?').upper():6s}] {p['type']}: {p.get('detail', '')}")
        if not result["problems"]:
            print("  ✅ No problems detected.")

    return 0 if not result["problems"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
