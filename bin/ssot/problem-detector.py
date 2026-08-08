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


def scan_all() -> dict[str, Any]:
    """Run all problem detection checks."""
    ts = datetime.now(UTC).isoformat()
    all_problems: list[dict[str, Any]] = []
    all_problems.extend(_detect_health_anomalies())
    all_problems.extend(_detect_dormant_tools())
    all_problems.extend(_detect_scene_card_issues())

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
    parser.add_argument("--no-debt", action="store_true", help="只检测不发事件/不建 debt")
    args = parser.parse_args(argv)

    result = scan_all()
    if not args.no_debt:
        for p in result["problems"]:
            _emit_anomaly(p)
            _record_debt(p)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Problem Detection: {result['total_problems']} problems ({result['by_severity']})")
        for p in result["problems"]:
            print(f"  [{p.get('severity', '?').upper():6s}] {p['type']}: {p.get('detail', '')}")
        if not result["problems"]:
            print("  ✅ No problems detected.")

    return 0 if not result["problems"] else 1


# ── 统一事件面 + 债务自动闭环 (observability-unified-architecture 设计) ──
EVENTS_SCRIPT = ROOT / "bin" / "ssot" / "observability-events.py"
DEBT_ITEMS_DIR = ROOT / ".omo" / "debt" / "items"
SEEN_FILE = ROOT / ".omo" / "state" / "problem-detector-seen.json"

_SEVERITY_MAP = {"high": "critical", "medium": "warning", "low": "info"}


def _emit_anomaly(problem: dict[str, Any]) -> None:
    """检测到的异常 → 统一事件面 (governance:anomaly). 非阻断."""
    if not EVENTS_SCRIPT.exists():
        return
    try:
        payload = json.dumps(
            {k: v for k, v in problem.items() if k != "severity"},
            ensure_ascii=False, default=str,
        )
        subprocess.run(
            ["python3", str(EVENTS_SCRIPT), "emit",
             "--domain", "governance", "--type", "governance:anomaly",
             "--severity", _SEVERITY_MAP.get(str(problem.get("severity", "low")), "info"),
             "--source", "problem-detector", "--payload", payload],
            capture_output=True, check=False, timeout=30,
        )
    except Exception:  # noqa: BLE001
        pass


def _record_debt(problem: dict[str, Any]) -> None:
    """high/medium 异常 → 自动创建 debt item (幂等: 同 type 不重复建)."""
    if problem.get("severity") not in {"high", "medium"}:
        return
    seen: dict[str, str] = {}
    if SEEN_FILE.exists():
        try:
            seen = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            seen = {}
    ptype = str(problem.get("type", "unknown"))
    if ptype in seen:
        return  # 已处理过
    try:
        DEBT_ITEMS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        debt_id = f"DEBT-OBS-{ts}"
        item = {
            "id": debt_id,
            "title": f"[observability] {ptype}",
            "description": str(problem.get("detail", "")),
            "severity": problem.get("severity", "medium"),
            "source": "problem-detector",
            "status": "registered",
            "registered_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S") + "Z",
        }
        path = DEBT_ITEMS_DIR / f"{debt_id}.yaml"
        path.write_text(
            "".join(f"{k}: {json.dumps(v, ensure_ascii=False) if isinstance(v, str) else v}\n"
                    for k, v in item.items()),
            encoding="utf-8",
        )
        seen[ptype] = debt_id
        SEEN_FILE.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ➕ debt created: {debt_id} ({ptype})")
    except OSError:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
