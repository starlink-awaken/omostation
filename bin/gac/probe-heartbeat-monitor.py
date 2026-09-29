#!/usr/bin/env python3
"""探测器心跳矩阵监控."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

_CHECKOUT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_CHECKOUT / "bin" / "lib"))
from repo_root import code_root, projection_name_for, projection_read, state_root

MATRIX_FILE = code_root() / ".omo" / "_truth" / "registry" / "probe-heartbeat-matrix.yaml"


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
    raw = ts_str.strip()
    try:
        # system_health.yaml 的 last_scan 是 epoch 浮点而不是 ISO 串; 只走
        # fromisoformat 会把「刚跑过」判成 9999h 老化。口径对齐
        # meta-doctor._parse_stamp 与 state-freshness-check._parse_iso。
        if re.fullmatch(r"\d+(\.\d+)?", raw):
            ts = datetime.fromtimestamp(float(raw), tz=UTC)
        else:
            ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return (datetime.now(UTC) - ts).total_seconds() / 3600
    except (ValueError, TypeError, OSError, OverflowError):
        return 9999


def check_heartbeats() -> dict:
    matrix = _load_yaml_simple(MATRIX_FILE)
    heartbeats = matrix.get("heartbeats", [])
    checkout_root = code_root()
    runtime_root = state_root()
    results = []
    failed = []
    absent = []
    for hb in heartbeats:
        rel = hb["file"]
        # The matrix keys are legacy paths for report continuity; which file to
        # read is one question with one answer (repo_root.projection_read), so
        # no reader keeps a second copy of the canonical mapping.
        name = projection_name_for(rel, registry_root=checkout_root)
        if name:
            file_path, source = projection_read(
                checkout_root,
                name,
                registry_root=checkout_root,
                state_root=runtime_root,
            )
        else:
            file_path, source = checkout_root / rel, "legacy"
        result = {
            "file": rel,
            "checked_file": str(file_path.relative_to(checkout_root)) if file_path.is_relative_to(checkout_root) else str(file_path),
            "source": source,
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
