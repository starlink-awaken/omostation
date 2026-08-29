#!/usr/bin/env python3
"""探测器心跳矩阵监控.

检查所有探测器的心跳状态，生成报告.
M3 仪式全覆盖.

Usage:
    python3 bin/gac/probe-heartbeat-monitor.py --status
    python3 bin/gac/probe-heartbeat-monitor.py --check
    python3 bin/gac/probe-heartbeat-monitor.py --report
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/Users/xiamingxing/Workspace")
MATRIX_FILE = REPO / ".omo" / "_truth" / "registry" / "probe-heartbeat-matrix.yaml"


def _load_yaml_simple(path: Path) -> dict:
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
        body = docs[-1] if len(docs) > 1 else docs[0]
        return body if isinstance(body, dict) else {}
    except Exception:
        return {}


def _read_json_field(path: Path, field: str) -> str | None:
    """Read a field from a JSON/JSONL file."""
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        # Try JSON first
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return str(data.get(field, ""))
            elif isinstance(data, list) and data:
                # For arrays, check last element
                last = data[-1]
                if isinstance(last, dict):
                    return str(last.get(field, ""))
        except json.JSONDecodeError:
            pass
        # Try JSONL (last line)
        for line in reversed(text.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    return str(data.get(field, ""))
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return None


def _age_hours(ts_str: str) -> float:
    """Calculate age in hours from ISO timestamp."""
    if not ts_str:
        return 9999
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - ts).total_seconds() / 3600
    except (ValueError, TypeError):
        return 9999


def check_heartbeats() -> dict:
    """Check all probe heartbeats."""
    matrix = _load_yaml_simple(MATRIX_FILE)
    heartbeats = matrix.get("heartbeats", [])
    results = []
    failed = []

    for hb in heartbeats:
        file_path = REPO / hb["file"]
        field = hb["field"]
        sla = hb["sla_hours"]

        ts_str = _read_json_field(file_path, field)
        age = _age_hours(ts_str) if ts_str else 9999
        ok = age <= sla

        result = {
            "file": hb["file"],
            "field": field,
            "sla_hours": sla,
            "age_hours": round(age, 1),
            "ok": ok,
            "severity": hb.get("severity", "P3"),
            "description": hb.get("description", ""),
        }
        results.append(result)
        if not ok:
            failed.append(result)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "ok": len(results) - len(failed),
        "failed_count": len(failed),
        "results": results,
        "failures": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="探测器心跳矩阵监控")
    parser.add_argument("--status", action="store_true", help="Show status summary")
    parser.add_argument("--check", action="store_true", help="Run heartbeat check")
    parser.add_argument("--report", action="store_true", help="Generate full report")
    args = parser.parse_args()

    if args.status or args.check or args.report:
        result = check_heartbeats()
        print(f"探测器心跳矩阵 — {result['timestamp']}")
        print(f"  总计: {result['total']}, 正常: {result['ok']}, 异常: {result['failed_count']}")

        if result["failures"]:
            print("\n异常探测器:")
            for f in result["failures"]:
                print(f"  ❌ {f['description']}: {f['age_hours']}h / {f['sla_hours']}h ({f['severity']})")

        if args.report:
            print("\n全部探测器:")
            for r in result["results"]:
                status = "✅" if r["ok"] else "❌"
                print(f"  {status} {r['description']}: {r['age_hours']}h / {r['sla_hours']}h")

        return 1 if result["failed_count"] else 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    main()
