#!/usr/bin/env python3
"""探测器心跳矩阵监控."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

_CHECKOUT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_CHECKOUT / "bin" / "lib"))
from repo_root import code_root, state_root

MATRIX_FILE = code_root() / ".omo" / "_truth" / "registry" / "probe-heartbeat-matrix.yaml"

# ADR-0129 Phase 2: the matrix keeps the legacy key for report continuity, but
# canonical evidence under state/runtime/ wins whenever it exists.
CANONICAL_FILES: dict[str, str] = {
    ".omo/state/system_health.yaml": ".omo/state/runtime/system_health.yaml",
    ".omo/state/health.yaml": ".omo/state/runtime/health.yaml",
    ".omo/_control/governance-data.json": ".omo/state/runtime/governance-data.json",
}


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
    root = state_root()
    results = []
    failed = []
    absent = []
    for hb in heartbeats:
        rel = hb["file"]
        canonical_rel = CANONICAL_FILES.get(rel)
        file_path = root / rel
        if canonical_rel and (root / canonical_rel).is_file():
            file_path = root / canonical_rel
        result = {
            "file": rel,
            "checked_file": str(file_path.relative_to(root)) if file_path.is_relative_to(root) else str(file_path),
            "sla_hours": hb["sla_hours"],
            "severity": hb.get("severity", "P3"),
            "description": hb.get("description", ""),
        }
        if not file_path.exists():
            # Absent means the generator has not run here yet — a runtime
            # product, not a lapsed heartbeat. Reported, never counted as a
            # failure, so fresh checkouts do not inherit a permanent red.
            result.update({"age_hours": None, "ok": True, "absent": True})
            results.append(result)
            absent.append(result)
            continue
        # 根据文件扩展名选择读取方式 (.json 和 .jsonl 用 JSON 解析)
        if file_path.suffix in (".json", ".jsonl"):
            ts_str = _read_json_field(file_path, hb["field"])
        else:
            data = _load_yaml_simple(file_path)
            ts_str = data.get(hb["field"]) if isinstance(data, dict) else None
            ts_str = str(ts_str) if ts_str is not None else None
        age = _age_hours(ts_str) if ts_str else 9999
        ok = age <= hb["sla_hours"]
        result.update({"age_hours": round(age, 1), "ok": ok, "absent": False})
        results.append(result)
        if not ok:
            failed.append(result)
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "total": len(results),
        "ok": len(results) - len(failed) - len(absent),
        "failed_count": len(failed),
        "absent_count": len(absent),
        "results": results,
        "failures": failed,
        "absences": absent,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="探测器心跳矩阵监控")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--report", action="store_true", help="Full report")
    args = parser.parse_args()

    if args.status or args.report:
        result = check_heartbeats()
        print(f"探测器心跳矩阵 — {result['timestamp']}")
        print(
            f"  总计: {result['total']}, 正常: {result['ok']}, "
            f"异常: {result['failed_count']}, 未生成: {result['absent_count']}"
        )
        if result["failures"]:
            print("\n异常探测器:")
            for f in result["failures"]:
                print(f"  ❌ {f['description']}: {f['age_hours']}h / {f['sla_hours']}h")
        return 1 if result["failed_count"] else 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    main()
