"""Load omo-doctor-cron artifacts for cockpit API (ADR-0201)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _workspace_root() -> Path:
    env = os.environ.get("WORKSPACE_ROOT")
    if env:
        return Path(env)
    # helpers_doctor_cron.py → dashboard → cockpit → src → project → projects → ws
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "runtime" / "cron").exists() or (parent / ".omo").exists():
            return parent
    return here.parents[5]


def load_doctor_cron_status(
    workspace_root: Path | None = None,
    *,
    history_limit: int = 14,
) -> dict[str, Any]:
    """Return latest doctor-cron snapshot + recent history for UI/API."""
    root = workspace_root or _workspace_root()
    latest_path = root / "runtime" / "cron" / "omo-doctor-latest.json"
    history_path = root / "runtime" / "cron" / "omo-doctor-history.jsonl"

    empty = {
        "schema": "omo.doctor.cron.v1",
        "adr": "0201",
        "status": "missing",
        "available": False,
        "latest_path": str(latest_path),
        "history_path": str(history_path),
        "highlights": {
            "path_acl_status": "missing",
            "path_acl_warn_streak": 0,
            "path_acl_alert": False,
            "path_acl_alert_threshold": 3,
            "ok": 0,
            "warn": 0,
            "fail": 0,
            "error": 0,
            "total": 0,
        },
        "written_at": None,
        "history_tail": [],
        "hint": "run: uv run --with pyyaml python bin/gac/omo-doctor-cron.py",
    }

    if not latest_path.is_file():
        return empty

    try:
        snap = json.loads(latest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {
            **empty,
            "status": "error",
            "error": f"{type(e).__name__}: {e}"[:200],
        }

    if not isinstance(snap, dict):
        return {**empty, "status": "error", "error": "latest snapshot not an object"}

    highlights = snap.get("highlights") if isinstance(snap.get("highlights"), dict) else {}
    # recompute streak from history if missing (older files)
    if "path_acl_warn_streak" not in highlights:
        try:
            from importlib.util import module_from_spec, spec_from_file_location

            cron_py = root / "bin" / "gac" / "omo-doctor-cron.py"
            if cron_py.is_file():
                spec = spec_from_file_location("omo_doctor_cron", cron_py)
                if spec and spec.loader:
                    mod = module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    prior = []
                    if history_path.is_file():
                        for line in history_path.read_text(encoding="utf-8").splitlines():
                            try:
                                prior.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
                    # history already includes last run; don't double-count current
                    # use last history row as current if present
                    if prior:
                        last = prior[-1]
                        lh = last.get("highlights") if isinstance(last.get("highlights"), dict) else {}
                        st = str(lh.get("path_acl_status") or "missing")
                        streak = mod.compute_path_acl_warn_streak(prior[:-1], st)
                        highlights = {**highlights, **streak}
        except Exception:
            highlights.setdefault("path_acl_warn_streak", 0)
            highlights.setdefault("path_acl_alert", False)
            highlights.setdefault("path_acl_alert_threshold", 3)

    history_tail: list[dict[str, Any]] = []
    if history_path.is_file():
        try:
            lines = [ln for ln in history_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            for ln in lines[-history_limit:]:
                try:
                    obj = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    h = obj.get("highlights") if isinstance(obj.get("highlights"), dict) else {}
                    history_tail.append(
                        {
                            "ts": obj.get("ts"),
                            "path_acl_status": h.get("path_acl_status"),
                            "path_acl_warn_streak": h.get("path_acl_warn_streak"),
                            "warn": h.get("warn"),
                            "fail": h.get("fail"),
                            "trigger": obj.get("trigger"),
                        }
                    )
        except OSError:
            pass

    status = "ok"
    if highlights.get("path_acl_alert"):
        status = "alert"
    elif highlights.get("path_acl_status") == "warn":
        status = "warn"
    elif highlights.get("fail") or highlights.get("error"):
        status = "fail"
    elif highlights.get("path_acl_status") in ("error", "missing"):
        status = str(highlights.get("path_acl_status"))

    return {
        "schema": "omo.doctor.cron.v1",
        "adr": "0201",
        "status": status,
        "available": True,
        "latest_path": str(latest_path),
        "history_path": str(history_path),
        "written_at": snap.get("written_at"),
        "highlights": highlights,
        "history_tail": history_tail,
        "doctor_summary": (snap.get("doctor") or {}).get("summary"),
        "hint": ("omo acl plan --json" if highlights.get("path_acl_status") == "warn" else "ok"),
    }
