#!/usr/bin/env python3
"""Read-only Direct Local Reference Cell R0 evidence verifier."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA = "reference-cell-direct-local-r0-verification/v1"
EVIDENCE_SCHEMA = "direct-local-reference-cell-r0-canary/v1"


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("observed_at is not a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("observed_at has no timezone")
    return parsed.astimezone(UTC)


def _find_summaries(root: Path) -> list[Path]:
    return sorted(root.glob("*/evidence/**/summary.json"))


def verify_latest(root: Path, *, max_age_hours: int = 168, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    candidates = _find_summaries(root)
    parsed: list[tuple[datetime, Path, dict]] = []
    invalid_count = 0
    for path in candidates:
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(report, dict) or report.get("schema") != EVIDENCE_SCHEMA:
                raise ValueError("schema mismatch")
            observed_at = _parse_timestamp(report.get("observed_at"))
            parsed.append((observed_at, path, report))
        except Exception:
            invalid_count += 1

    base = {
        "schema": SCHEMA,
        "candidate_count": len(candidates),
        "invalid_count": invalid_count,
        "max_age_hours": max_age_hours,
        "checked_at": now.isoformat(),
        "latest_observed_at": None,
        "evidence_digest": None,
        "result": None,
        "execution_backend": None,
        "risk": None,
        "external_side_effects": None,
        "workspace_writes": None,
        "verification_verdict": None,
        "mesh_final_state": None,
        "mesh_replay_status": None,
        "value_indicator_policy": None,
    }
    if not parsed:
        return {**base, "ok": False, "verdict": "UNAVAILABLE", "reason": "no_valid_evidence"}

    observed_at, path, report = max(parsed, key=lambda item: item[0])
    execution = report.get("execution") if isinstance(report.get("execution"), dict) else {}
    verification = report.get("verification") if isinstance(report.get("verification"), dict) else {}
    mesh = report.get("mesh") if isinstance(report.get("mesh"), dict) else {}
    result_ok = (
        report.get("result") == "PASS"
        and report.get("ledger_bound") is False
        and report.get("value_indicator_policy") is False
        and report.get("external_side_effects") == "disabled"
        and report.get("workspace_writes") == 0
        and execution.get("backend") == "local"
        and execution.get("risk") == "R0"
        and execution.get("completed") is True
        and execution.get("action") == "read_file"
        and isinstance(execution.get("source"), str)
        and bool(execution.get("source"))
        and isinstance(execution.get("result_digest"), str)
        and execution.get("result_digest", "").startswith("sha256:")
        and verification.get("verdict") == "accept"
        and mesh.get("final_state") == "verified"
        and mesh.get("replay_status") == "replayed"
        and mesh.get("replay_event_count_delta") == 0
    )
    age_seconds = (now - observed_at).total_seconds()
    fresh = 0 <= age_seconds <= max_age_hours * 3600
    verdict = "PASS" if result_ok and fresh else ("STALE" if result_ok else "FAILED")
    return {
        **base,
        "latest_observed_at": observed_at.isoformat(),
        "evidence_digest": _sha256(path),
        "result": report.get("result"),
        "execution_backend": execution.get("backend"),
        "risk": execution.get("risk"),
        "external_side_effects": report.get("external_side_effects"),
        "workspace_writes": report.get("workspace_writes"),
        "verification_verdict": verification.get("verdict"),
        "mesh_final_state": mesh.get("final_state"),
        "mesh_replay_status": mesh.get("replay_status"),
        "value_indicator_policy": report.get("value_indicator_policy"),
        "age_seconds": age_seconds,
        "ok": verdict == "PASS",
        "verdict": verdict,
        "reason": None if verdict == "PASS" else ("evidence_stale" if verdict == "STALE" else "invalid_evidence"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Reference Cell attempts root (test only)")
    parser.add_argument("--max-age-hours", type=int, default=168)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = args.root or (Path(pwd.getpwuid(os.getuid()).pw_dir) / "agents/codex-agent-os-reference-cell/attempts")
    report = verify_latest(root, max_age_hours=args.max_age_hours)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
