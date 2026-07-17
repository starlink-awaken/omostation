#!/usr/bin/env python3
"""G-CONV.7 / ADR-0220 swarm coordination discipline — pure gates + FS helpers.

Decision functions are pure (injectable paths) so unit tests drive the real
logic without a multi-agent swarm. Side effects (locks, event log) live here
but stay thin.

Gates:
  D1 ADR atomic claim
  D2 branch occupancy lock
  D3 shared worktree claim-before-write
  D4 escape-hatch allowlist
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

UTC = timezone.utc

DEFAULT_REGISTRY = ".omo/_truth/registry/swarm-coordination.yaml"
ADR_FILE_RE = re.compile(r"^\.omo/_knowledge/decisions/(\d{4})-.*\.md$")
BRANCH_RE = re.compile(r"^work/[a-z0-9][a-z0-9-]*$")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc_iso(dt: datetime | None = None) -> str:
    d = dt or _utc_now()
    return d.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_registry(root: Path) -> dict[str, Any]:
    path = root / DEFAULT_REGISTRY
    if not path.is_file():
        return {"version": 0, "escape_hatch_exemptions": [], "delivery": {}}
    try:
        import yaml  # noqa: PLC0415

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {"version": 0, "escape_hatch_exemptions": [], "delivery": {}}


def delivery_path(root: Path, key: str, default: str) -> Path:
    reg = load_registry(root)
    rel = (reg.get("delivery") or {}).get(key) or default
    return root / rel


def emit_conflict_event(
    root: Path,
    kind: str,
    detail: dict[str, Any],
    *,
    session: str = "",
) -> Path:
    """Append a structured conflict event for the 72h observation window."""
    events = delivery_path(
        root, "conflict_events", ".omo/_delivery/swarm-conflicts/events.jsonl"
    )
    events.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": _utc_iso(),
        "kind": kind,
        "session": session or None,
        "detail": detail,
    }
    with events.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return events


# ── D1 ADR atomic claim ──────────────────────────────────────────────


def list_existing_adr_numbers(decisions_dir: Path) -> set[int]:
    nums: set[int] = set()
    if not decisions_dir.is_dir():
        return nums
    for path in decisions_dir.iterdir():
        m = re.match(r"^(\d{4})-", path.name)
        if m:
            nums.add(int(m.group(1)))
    return nums


def load_adr_claims(claims_dir: Path) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    if not claims_dir.is_dir():
        return out
    for path in claims_dir.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        n = payload.get("number")
        if isinstance(n, int):
            out[n] = {**payload, "_claim_file": path.name}
    return out


def next_free_adr(existing: set[int], claimed: dict[int, dict]) -> int:
    taken = set(existing) | set(claimed)
    candidate = (max(taken) + 1) if taken else 1
    while candidate in taken:
        candidate += 1
    return candidate


def acquire_adr_claim(
    root: Path,
    session: str,
    *,
    number: int | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Atomically claim next (or specific) ADR number for session.

    Uses an exclusive flock on .omo/_delivery/adr-claims/.lock so concurrent
    claimers cannot double-allocate the same number (D1).
    """
    if not session:
        return False, {"error": "session required"}
    claims_dir = delivery_path(root, "adr_claims_dir", ".omo/_delivery/adr-claims")
    claims_dir.mkdir(parents=True, exist_ok=True)
    lock_path = claims_dir / ".lock"
    decisions = root / ".omo" / "_knowledge" / "decisions"

    with lock_path.open("a+", encoding="utf-8") as lock_fh:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        existing = list_existing_adr_numbers(decisions)
        claimed = load_adr_claims(claims_dir)
        # session already has a claim → return it
        for n, payload in claimed.items():
            if payload.get("session") == session:
                return True, {
                    "number": n,
                    "next_id": f"{n:04d}",
                    "session": session,
                    "reused": True,
                    "claim_path": str(claims_dir / f"{session}.json"),
                }
        target = number if number is not None else next_free_adr(existing, claimed)
        if target in existing:
            emit_conflict_event(
                root,
                "adr_renumber_race",
                {"number": target, "reason": "already_on_disk", "session": session},
                session=session,
            )
            return False, {
                "error": f"ADR-{target:04d} already exists on disk",
                "number": target,
            }
        holder = claimed.get(target)
        if holder and holder.get("session") != session:
            emit_conflict_event(
                root,
                "adr_renumber_race",
                {
                    "number": target,
                    "holder": holder.get("session"),
                    "challenger": session,
                },
                session=session,
            )
            return False, {
                "error": f"ADR-{target:04d} claimed by session={holder.get('session')}",
                "number": target,
                "holder": holder.get("session"),
            }
        payload = {
            "number": target,
            "next_id": f"{target:04d}",
            "session": session,
            "claimed_at": _utc_iso(),
            "gate": "d1_adr_atomic_claim",
            "note": "ADR-0220 D1; release by deleting claim after ADR lands on main",
        }
        claim_path = claims_dir / f"{session}.json"
        claim_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return True, {
            "number": target,
            "next_id": f"{target:04d}",
            "session": session,
            "reused": False,
            "claim_path": str(claim_path.relative_to(root)),
        }


def check_adr_write_authorized(
    root: Path,
    rel_path: str,
    session: str | None,
) -> tuple[bool, str]:
    """D1: writing a new ADR file requires matching session claim."""
    m = ADR_FILE_RE.match(rel_path.replace("\\", "/"))
    if not m:
        return True, "not_an_adr_path"
    number = int(m.group(1))
    decisions = root / ".omo" / "_knowledge" / "decisions"
    # existing file on disk (edit) is allowed
    if (decisions / Path(rel_path).name).is_file():
        return True, "existing_adr_edit"
    claims = load_adr_claims(
        delivery_path(root, "adr_claims_dir", ".omo/_delivery/adr-claims")
    )
    holder = claims.get(number)
    if holder is None:
        emit_conflict_event(
            root,
            "adr_renumber_race",
            {"number": number, "path": rel_path, "reason": "no_claim"},
            session=session or "",
        )
        return False, f"ADR-{number:04d} write requires prior claim (next-adr-id --claim)"
    if session and holder.get("session") != session:
        emit_conflict_event(
            root,
            "adr_renumber_race",
            {
                "number": number,
                "path": rel_path,
                "holder": holder.get("session"),
                "writer": session,
            },
            session=session or "",
        )
        return False, (
            f"ADR-{number:04d} claimed by session={holder.get('session')}, "
            f"not {session}"
        )
    return True, "claim_ok"


# ── D2 branch occupancy ──────────────────────────────────────────────


def load_branch_claims(claims_dir: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not claims_dir.is_dir():
        return out
    for path in claims_dir.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        branch = payload.get("branch")
        if isinstance(branch, str):
            out[branch] = {**payload, "_claim_file": path.name}
    return out


def acquire_branch_lock(
    root: Path,
    session: str,
    branch: str | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Register occupancy for work/<session>. Refuse if held by another session."""
    if not session:
        return False, {"error": "session required"}
    branch = branch or f"work/{session}"
    if not BRANCH_RE.match(branch):
        return False, {"error": f"invalid branch name: {branch}"}
    claims_dir = delivery_path(
        root, "branch_claims_dir", ".omo/_delivery/branch-claims"
    )
    claims_dir.mkdir(parents=True, exist_ok=True)
    lock_path = claims_dir / ".lock"
    with lock_path.open("a+", encoding="utf-8") as lock_fh:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        claims = load_branch_claims(claims_dir)
        holder = claims.get(branch)
        if holder and holder.get("session") != session:
            emit_conflict_event(
                root,
                "branch_hijack",
                {
                    "branch": branch,
                    "holder": holder.get("session"),
                    "challenger": session,
                },
                session=session,
            )
            return False, {
                "error": f"branch {branch} occupied by session={holder.get('session')}",
                "holder": holder.get("session"),
                "branch": branch,
            }
        payload = {
            "branch": branch,
            "session": session,
            "claimed_at": _utc_iso(),
            "gate": "d2_branch_occupancy",
        }
        path = claims_dir / f"{session}.json"
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return True, {
            "branch": branch,
            "session": session,
            "claim_path": str(path.relative_to(root)),
            "reused": bool(holder),
        }


def check_branch_available(
    root: Path, branch: str, session: str
) -> tuple[bool, str]:
    claims = load_branch_claims(
        delivery_path(root, "branch_claims_dir", ".omo/_delivery/branch-claims")
    )
    holder = claims.get(branch)
    if holder is None:
        return True, "free"
    if holder.get("session") == session:
        return True, "owned"
    return False, f"occupied by {holder.get('session')}"


def release_branch_lock(root: Path, session: str) -> bool:
    claims_dir = delivery_path(
        root, "branch_claims_dir", ".omo/_delivery/branch-claims"
    )
    path = claims_dir / f"{session}.json"
    if path.is_file():
        path.unlink()
        return True
    return False


# ── D3 shared worktree claim ─────────────────────────────────────────


def is_isolated_work_branch(branch: str) -> bool:
    return bool(re.match(r"^(work|pr)/", branch or ""))


def git_current_branch(root: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        return (r.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def active_workflow_claimed_paths(root: Path) -> list[str]:
    """Collect claimed paths from active agent-workflow runs (if any)."""
    runs_dir = root / ".omo" / "_delivery" / "agent-workflows" / "runs"
    if not runs_dir.is_dir():
        return []
    paths: list[str] = []
    for path in sorted(runs_dir.glob("*.yaml"), reverse=True)[:40]:
        try:
            import yaml  # noqa: PLC0415

            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(data, dict):
            continue
        status = str(data.get("status") or data.get("state") or "").lower()
        if status in {"closed", "closeout", "done", "failed", "cancelled"}:
            continue
        for claim in data.get("claims") or []:
            if isinstance(claim, dict):
                for p in claim.get("paths") or []:
                    if isinstance(p, str):
                        paths.append(p)
            elif isinstance(claim, str):
                paths.append(claim)
        # alternate shapes
        for p in data.get("claimed_paths") or []:
            if isinstance(p, str):
                paths.append(p)
    return paths


def path_covered_by_claim(claimed: list[str], changed: str) -> bool:
    changed = changed.replace("\\", "/").lstrip("./")
    for c in claimed:
        c = c.replace("\\", "/").lstrip("./")
        if changed == c or changed.startswith(c.rstrip("/") + "/"):
            return True
        if c.endswith("/**") and changed.startswith(c[:-3]):
            return True
    return False


def path_matches_allow_globs(path: str, globs: list[str]) -> bool:
    import fnmatch  # noqa: PLC0415

    path = path.replace("\\", "/").lstrip("./")
    for g in globs:
        g = g.replace("\\", "/")
        if fnmatch.fnmatch(path, g) or fnmatch.fnmatch(path, g.lstrip("./")):
            return True
        # directory ** style
        if g.endswith("/**") and path.startswith(g[:-3]):
            return True
    return False


def check_shared_worktree_writes(
    root: Path,
    staged_paths: list[str],
    *,
    branch: str | None = None,
    claimed_paths: list[str] | None = None,
    allow_globs: list[str] | None = None,
) -> tuple[bool, list[str]]:
    """D3: on shared (non-work/*) tree, every staged path needs claim or allowlist."""
    branch = branch if branch is not None else git_current_branch(root)
    if is_isolated_work_branch(branch):
        return True, []
    # Also treat presence of AGENT_WORKFLOW_RUN_ID + claims as compliant on main
    if claimed_paths is None:
        claimed_paths = active_workflow_claimed_paths(root)
    if allow_globs is None:
        reg = load_registry(root)
        allow_globs = list(reg.get("shared_worktree_allow_path_globs") or [])
    violations: list[str] = []
    for p in staged_paths:
        rel = p.replace("\\", "/").lstrip("./")
        if path_matches_allow_globs(rel, allow_globs):
            continue
        if path_covered_by_claim(claimed_paths, rel):
            continue
        # D1 ADR special case
        if ADR_FILE_RE.match(rel):
            ok, reason = check_adr_write_authorized(
                root, rel, os.environ.get("AGENT_WORKFLOW_SESSION") or ""
            )
            if ok:
                continue
            violations.append(f"{rel}: {reason}")
            continue
        violations.append(
            f"{rel}: unclaimed write on shared worktree (branch={branch or 'unknown'})"
        )
    if violations:
        emit_conflict_event(
            root,
            "unclaimed_write",
            {"branch": branch, "paths": staged_paths, "violations": violations},
            session=os.environ.get("AGENT_WORKFLOW_SESSION") or "",
        )
        return False, violations
    return True, []


# ── D4 escape hatch ──────────────────────────────────────────────────


def list_escape_exemptions(root: Path) -> list[dict[str, Any]]:
    reg = load_registry(root)
    items = reg.get("escape_hatch_exemptions") or []
    return [x for x in items if isinstance(x, dict) and x.get("active", True)]


def check_escape_hatch(
    root: Path,
    *,
    flag: str,
    escape_id: str | None,
) -> tuple[bool, str]:
    """D4: flag in {ci_local_skip, no_verify_push, no_verify_commit} needs allowlist id."""
    flag = flag.strip().lower().replace("-", "_")
    if flag not in {"ci_local_skip", "no_verify_push", "no_verify_commit"}:
        return False, f"unknown escape flag: {flag}"
    if not escape_id:
        emit_conflict_event(
            root,
            "escape_hatch_abuse",
            {"flag": flag, "reason": "missing_escape_id"},
        )
        return False, f"{flag} requires SWARM_ESCAPE_ID / --escape-id from allowlist"
    for item in list_escape_exemptions(root):
        if item.get("id") != escape_id:
            continue
        allow = [str(a).lower().replace("-", "_") for a in (item.get("allow") or [])]
        if flag in allow:
            # record legitimate use
            log_dir = delivery_path(
                root, "escape_log_dir", ".omo/_delivery/swarm-escape"
            )
            log_dir.mkdir(parents=True, exist_ok=True)
            rec = {
                "ts": _utc_iso(),
                "flag": flag,
                "escape_id": escape_id,
                "reason": item.get("reason"),
            }
            (log_dir / f"{_utc_now().strftime('%Y%m%dT%H%M%SZ')}-{escape_id}.json").write_text(
                json.dumps(rec, indent=2) + "\n", encoding="utf-8"
            )
            return True, f"exempt:{escape_id}"
        return False, f"escape_id={escape_id} does not allow {flag}"
    emit_conflict_event(
        root,
        "escape_hatch_abuse",
        {"flag": flag, "escape_id": escape_id, "reason": "unknown_id"},
    )
    return False, f"escape_id={escape_id} not in allowlist"


# ── 72h observation window ───────────────────────────────────────────


def start_conflict_window(root: Path) -> dict[str, Any]:
    path = delivery_path(
        root, "conflict_window", ".omo/_delivery/swarm-conflicts/window.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    reg = load_registry(root)
    hours = int((reg.get("observation") or {}).get("window_hours") or 72)
    now = _utc_now()
    payload = {
        "window_start": _utc_iso(now),
        "window_hours": hours,
        "window_end_target": _utc_iso(now + timedelta(hours=hours)),
        "gate": "g-conv.7",
        "adr": "0220",
        "note": "M1 concurrent_main_conflict_zero observation; pass only after full window with count=0",
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def read_conflict_events(root: Path, since_iso: str | None = None) -> list[dict]:
    events_path = delivery_path(
        root, "conflict_events", ".omo/_delivery/swarm-conflicts/events.jsonl"
    )
    if not events_path.is_file():
        return []
    since = None
    if since_iso:
        try:
            since = datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
        except ValueError:
            since = None
    out: list[dict] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if since:
            try:
                ts = datetime.fromisoformat(str(rec.get("ts", "")).replace("Z", "+00:00"))
            except ValueError:
                continue
            if ts < since:
                continue
        out.append(rec)
    return out


def conflict_window_status(root: Path) -> dict[str, Any]:
    path = delivery_path(
        root, "conflict_window", ".omo/_delivery/swarm-conflicts/window.json"
    )
    if not path.is_file():
        return {
            "window_start": None,
            "window_end_or_null": None,
            "elapsed_hours": 0.0,
            "conflict_count": 0,
            "event_breakdown": {},
            "m1_conflict_zero_verdict": "window_open",
            "note": "window not started; call swarm-discipline-cli.py window-start",
        }
    meta = json.loads(path.read_text(encoding="utf-8"))
    start_s = meta.get("window_start")
    try:
        start = datetime.fromisoformat(str(start_s).replace("Z", "+00:00"))
    except ValueError:
        start = _utc_now()
    now = _utc_now()
    elapsed = (now - start).total_seconds() / 3600.0
    hours = float(meta.get("window_hours") or 72)
    events = read_conflict_events(root, since_iso=start_s)
    breakdown: dict[str, int] = {}
    for e in events:
        k = str(e.get("kind") or "unknown")
        breakdown[k] = breakdown.get(k, 0) + 1
    count = len(events)
    if elapsed < hours:
        verdict = "window_open"
    elif count == 0:
        verdict = "pass"
    else:
        verdict = "fail"
    return {
        "window_start": start_s,
        "window_end_or_null": None if elapsed < hours else _utc_iso(now),
        "window_hours_target": hours,
        "elapsed_hours": round(elapsed, 3),
        "conflict_count": count,
        "event_breakdown": breakdown,
        "m1_conflict_zero_verdict": verdict,
        "events_sample": events[:20],
    }


def main_probe() -> int:
    """Minimal self-check when executed as script."""
    root = Path(__file__).resolve().parents[2]
    print(json.dumps({"root": str(root), "registry": load_registry(root).get("version")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main_probe())
