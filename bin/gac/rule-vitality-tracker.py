"""rule-vitality-tracker.py — 规则活力追踪读写工具 (BET-Y1Q2-T6-01).

Per-rule vitality JSONL at .omo/state/rule-vitality.jsonl.
Each line: {rule_id, gate_check, timestamp, evaluated, violated, enforcement, duration_ms}.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
VITALITY_PATH = WORKSPACE_ROOT / ".omo" / "state" / "rule-vitality.jsonl"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def record_vitality(
    rule_id: str,
    gate_check: str,
    *,
    violated: bool = False,
    enforcement: str = "required",
    duration_ms: int = 0,
    details: str = "",
    path: Path | None = None,
) -> None:
    """Append a vitality entry for a rule evaluation."""
    target = path or VITALITY_PATH
    entry = {
        "rule_id": rule_id,
        "gate_check": gate_check,
        "timestamp": _utc_now(),
        "evaluated": True,
        "violated": violated,
        "enforcement": enforcement,
        "duration_ms": duration_ms,
    }
    if details:
        entry["details"] = details[:200]
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def read_vitality(path: Path | None = None) -> list[dict[str, Any]]:
    """Read all vitality entries."""
    target = path or VITALITY_PATH
    if not target.exists():
        return []
    entries = []
    with target.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def query_vitality(
    rule_id: str,
    window_days: int = 30,
    path: Path | None = None,
) -> dict[str, Any]:
    """Query vitality summary for a single rule within a time window."""
    entries = read_vitality(path)
    cutoff = time.time() - (window_days * 86400)

    relevant = []
    for e in entries:
        if e.get("rule_id") != rule_id:
            continue
        ts = e.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.timestamp() >= cutoff:
                relevant.append(e)
        except (ValueError, OSError):
            relevant.append(e)

    if not relevant:
        return {
            "rule_id": rule_id,
            "total_evaluations": 0,
            "total_violations": 0,
            "violation_rate": 0.0,
            "last_violation": None,
            "days_since_violation": None,
        }

    violations = [e for e in relevant if e.get("violated")]
    last_violation = violations[-1]["timestamp"] if violations else None

    days_since = None
    if last_violation:
        try:
            dt = datetime.fromisoformat(last_violation.replace("Z", "+00:00"))
            days_since = (datetime.now(UTC) - dt).days
        except (ValueError, OSError):
            pass

    return {
        "rule_id": rule_id,
        "total_evaluations": len(relevant),
        "total_violations": len(violations),
        "violation_rate": len(violations) / len(relevant) if relevant else 0.0,
        "last_violation": last_violation,
        "days_since_violation": days_since,
        "enforcement": relevant[-1].get("enforcement", ""),
    }


def compute_all_summaries(
    window_days: int = 30,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Compute vitality summaries for all rules seen in the vitality store."""
    entries = read_vitality(path)
    rule_ids = sorted({e.get("rule_id", "") for e in entries if e.get("rule_id")})
    return [query_vitality(rid, window_days, path) for rid in rule_ids]


def gate_to_rules_mapping() -> dict[str, list[str]]:
    """Extract gate_check_id → [rule source_ref scripts] from DEFAULT_POLICY.

    Returns mapping of gate IDs to the script paths they execute.
    """
    import ast
    import re

    gate_file = WORKSPACE_ROOT / "bin" / "gac" / "gac-local-gate.py"
    content = gate_file.read_text(encoding="utf-8")

    match = re.search(r'"gates":\s*\[(.*?)\]\s*\}', content, re.DOTALL)
    if not match:
        return {}

    gates_block = match.group(0)
    gate_ids = re.findall(r'"id":\s*"([^"]+)"', gates_block)
    commands = re.findall(r'"command":\s*\[([^\]]+)\]', gates_block)

    mapping = {}
    for gid, cmd_str in zip(gate_ids, commands):
        scripts = re.findall(r'"([^"]+\.py)"', cmd_str)
        mapping[gid] = scripts

    return mapping


__all__ = [
    "VITALITY_PATH",
    "compute_all_summaries",
    "gate_to_rules_mapping",
    "query_vitality",
    "read_vitality",
    "record_vitality",
]
