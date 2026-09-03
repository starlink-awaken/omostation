#!/usr/bin/env python3
"""探测器心跳矩阵监控."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timezone
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
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return str(data.get(field, ""))
            elif isinstance(data, list) and data:
                last = data[-1]
                if isinstance(last, dict):
                    return str(last.get(field, ""))
        except json.JSONDecodeError:
            pass
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
    if not ts_str:
        return 9999
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        now = datetime.now(UTC)
        return (now - ts).total_seconds() / 3600
    except (ValueError, TypeError):
        return 9999


def check_heartbeats() -> dict:
    matrix = _load_yaml_simple(MATRIX_FILE)
    heartbeats = matrix.get("heartbeats", [])
    results = []
    failed = []
    for hb in heartbeats:
        file_path = REPO / hb["file"]
        # 根据文件扩展名选择读取方式 (.json 和 .jsonl 用 JSON 解析)
        if file_path.suffix in (".json", ".jsonl"):
            ts_str = _read_json_field(file_path, hb["field"])
        else:
            data = _load_yaml_simple(file_path)
            ts_str = data.get(hb["field"]) if isinstance(data, dict) else None
            ts_str = str(ts_str) if ts_str is not None else None
        age = _age_hours(ts_str) if ts_str else 9999
        ok = age <= hb["sla_hours"]
        result = {
            "file": hb["file"],
            "sla_hours": hb["sla_hours"],
            "age_hours": round(age, 1),
            "ok": ok,
            "severity": hb.get("severity", "P3"),
            "description": hb.get("description", ""),
        }
        results.append(result)
        if not ok:
            failed.append(result)
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "total": len(results),
        "ok": len(results) - len(failed),
        "failed_count": len(failed),
        "results": results,
        "failures": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="探测器心跳矩阵监控")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--report", action="store_true", help="Full report")
    args = parser.parse_args()

    if args.status or args.report:
        result = check_heartbeats()
        print(f"探测器心跳矩阵 — {result['timestamp']}")
        print(f"  总计: {result['total']}, 正常: {result['ok']}, 异常: {result['failed_count']}")
        if result["failures"]:
            print("\n异常探测器:")
            for f in result["failures"]:
                print(f"  ❌ {f['description']}: {f['age_hours']}h / {f['sla_hours']}h")
        return 1 if result["failed_count"] else 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    main()
