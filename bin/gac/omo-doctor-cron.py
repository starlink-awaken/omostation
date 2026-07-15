#!/usr/bin/env python3
"""omo-doctor-cron.py — operating-rhythm daily hook for omo doctor (ADR-0200).

Runs ``omo doctor --json``, writes a machine-readable snapshot for ops, and
echoes a one-line summary (path-acl + fails) to stdout for cron logs.

Does not mutate host ACL. Exit 0 unless doctor hard-fails (fail/error counts).

Usage:
  uv run --with pyyaml python bin/gac/omo-doctor-cron.py
  uv run --with pyyaml python bin/gac/omo-doctor-cron.py --json
  OPC_TRIGGER=cron uv run --with pyyaml python bin/gac/omo-doctor-cron.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WS = Path(__file__).resolve().parents[2]
OUT_DIR = WS / "runtime" / "cron"
LATEST = OUT_DIR / "omo-doctor-latest.json"
HISTORY = OUT_DIR / "omo-doctor-history.jsonl"
MAX_HISTORY = 90


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _run_doctor() -> tuple[dict, int]:
    """Invoke omo doctor --json; return (payload, exit_code)."""
    cmd = [
        "uv",
        "run",
        "--project",
        str(WS / "projects" / "omo"),
        "python",
        "-m",
        "omo.cli",
        "doctor",
        "--json",
    ]
    env = os.environ.copy()
    # Prefer workspace root for path-acl surfaces
    env.setdefault("WORKSPACE_ROOT", str(WS))
    omo_src = WS / "projects" / "omo" / "src" / "omo" / "cli.py"
    if not omo_src.is_file():
        return {
            "generated_at": _now(),
            "error": "projects/omo not initialized (missing cli.py)",
            "checks": [],
            "summary": {"total": 0, "ok": 0, "warn": 0, "fail": 0, "error": 1},
        }, 1

    try:
        r = subprocess.run(
            cmd,
            cwd=str(WS),
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {
            "generated_at": _now(),
            "error": f"{type(e).__name__}: {e}",
            "checks": [],
            "summary": {"total": 0, "ok": 0, "warn": 0, "fail": 0, "error": 1},
        }, 1

    payload: dict
    try:
        payload = json.loads(r.stdout or "{}")
        if not isinstance(payload, dict):
            raise ValueError("doctor stdout not a JSON object")
        if not payload.get("checks") and r.returncode != 0:
            # uv/module failure often leaves empty object
            raise ValueError(
                (r.stderr or r.stdout or "doctor failed with empty JSON")[:240]
            )
    except (json.JSONDecodeError, ValueError) as e:
        payload = {
            "generated_at": _now(),
            "error": f"parse/run: {e}",
            "raw_stdout_head": (r.stdout or "")[:400],
            "raw_stderr_head": (r.stderr or "")[:400],
            "checks": [],
            "summary": {"total": 0, "ok": 0, "warn": 0, "fail": 0, "error": 1},
        }
        return payload, 1

    payload.setdefault("generated_at", _now())
    payload["exit_code"] = r.returncode
    payload["trigger"] = os.environ.get("OPC_TRIGGER") or "manual"
    return payload, r.returncode


def _extract_highlights(payload: dict) -> dict:
    checks = payload.get("checks") or []
    by_id = {c.get("id"): c for c in checks if isinstance(c, dict)}
    path_acl = by_id.get("path-acl") or {}
    summary = payload.get("summary") or {}
    path_status = path_acl.get("status")
    if not path_status:
        path_status = "error" if payload.get("error") else "missing"
    path_detail = path_acl.get("detail") or payload.get("error") or ""
    return {
        "path_acl_status": path_status,
        "path_acl_detail": path_detail,
        "warn": summary.get("warn", 0),
        "fail": summary.get("fail", 0),
        "error": summary.get("error", 0),
        "ok": summary.get("ok", 0),
        "total": summary.get("total", 0),
    }


def _write_artifacts(payload: dict, highlights: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "written_at": _now(),
        "highlights": highlights,
        "doctor": payload,
    }
    LATEST.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")

    line = json.dumps(
        {
            "ts": _now(),
            "highlights": highlights,
            "exit_code": payload.get("exit_code"),
            "trigger": payload.get("trigger"),
        },
        ensure_ascii=False,
    )
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")

    # trim history
    try:
        rows = HISTORY.read_text(encoding="utf-8").splitlines()
        if len(rows) > MAX_HISTORY:
            HISTORY.write_text("\n".join(rows[-MAX_HISTORY:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="operating-rhythm omo doctor hook (ADR-0200)")
    ap.add_argument("--json", action="store_true", help="Print full snapshot JSON")
    ap.add_argument(
        "--no-write",
        action="store_true",
        help="Do not write runtime/cron artifacts (test mode)",
    )
    args = ap.parse_args(argv)

    payload, code = _run_doctor()
    highlights = _extract_highlights(payload)
    if not args.no_write:
        try:
            _write_artifacts(payload, highlights)
        except OSError as e:
            print(f"[omo-doctor-cron] write failed: {e}", file=sys.stderr)

    one_line = (
        f"[omo-doctor-cron] ok={highlights['ok']} warn={highlights['warn']} "
        f"fail={highlights['fail']} error={highlights['error']} "
        f"path-acl={highlights['path_acl_status']}"
    )
    if highlights["path_acl_status"] == "warn":
        one_line += f" detail={highlights['path_acl_detail'][:120]}"
    print(one_line)

    if args.json:
        print(
            json.dumps(
                {
                    "highlights": highlights,
                    "latest_path": str(LATEST),
                    "history_path": str(HISTORY),
                    "doctor": payload,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    # Non-zero only on hard fail (doctor fail/error); warn/path-acl stays 0
    if highlights["fail"] or highlights["error"] or code != 0:
        # code!=0 with only warn is still 0 from doctor — trust summary
        if highlights["fail"] or highlights["error"]:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
