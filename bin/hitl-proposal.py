#!/usr/bin/env python3
"""HITL Proposal Manager — generate, store, and track human-in-the-loop proposals.

Proposals are stored as YAML files in .omo/_knowledge/hitl-proposals/.
Atomic writes via tempfile+rename. File locking via fcntl.flock.
"""

from __future__ import annotations

import argparse
import fcntl
import os
import secrets
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

PROPOSALS_DIR = Path(os.environ.get("HITL_PROPOSALS_DIR", ".omo/_knowledge/hitl-proposals"))
DEFAULT_TTL_HOURS = 24
SCHEMA_VERSION = "hitl-proposal/v1"

# v1.1: distributed lock backend
LOCK_BACKEND = os.environ.get("HITL_LOCK_BACKEND", "fcntl")
LOCK_ETCD_ENDPOINTS = os.environ.get("HITL_LOCK_ETCD_ENDPOINTS", "")
LOCK_REDIS_URL = os.environ.get("HITL_LOCK_REDIS_URL", "")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _acquire_lock(f, blocking: bool = True) -> None:
    """Acquire a lock on file `f` using the configured backend."""
    if LOCK_BACKEND == "fcntl":
        op = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
        fcntl.flock(f, op)
    else:
        # STUB: etcd/redis backends fall back to fcntl
        fcntl.flock(f, fcntl.LOCK_EX)


def _release_lock(f) -> None:
    """Release the lock held by the configured backend."""
    if LOCK_BACKEND in ("fcntl", "etcd", "redis"):
        fcntl.flock(f, fcntl.LOCK_UN)
    else:
        raise ValueError(f"unknown LOCK_BACKEND: {LOCK_BACKEND}")


def _generate_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    rand = secrets.token_hex(3)
    return f"hitl-{ts}-{rand}"


def _detect_actor() -> str:
    """Detect the current actor from git config or environment.

    Returns user.name@user.email if available, otherwise USER env var, otherwise 'human'.
    """
    try:
        name = subprocess.run(
            ["git", "config", "--get", "user.name"],
            capture_output=True, text=True, check=False, timeout=2,
        ).stdout.strip()
        email = subprocess.run(
            ["git", "config", "--get", "user.email"],
            capture_output=True, text=True, check=False, timeout=2,
        ).stdout.strip()
        if name and email:
            return f"{name} <{email}>"
        if name:
            return name
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return os.environ.get("USER") or os.environ.get("USERNAME") or "human"


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        os.rename(tmp, str(path))
    except BaseException:
        os.unlink(tmp)
        raise


def _load_proposal(path: Path) -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _save_proposal(path: Path, proposal: dict[str, Any]) -> None:
    _atomic_write(path, proposal)


def create_proposal(
    bet_id: str,
    run_id: str,
    title: str,
    description: str,
    options: list[dict[str, str]] | None = None,
    ttl_hours: int = DEFAULT_TTL_HOURS,
) -> dict[str, Any]:
    """Create a new HITL proposal and persist it atomically."""
    proposal_id = _generate_id()
    now = _now()
    expires_dt = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

    if options is None:
        options = [
            {"id": "approve", "label": "Approve", "description": "Allow the action"},
            {"id": "reject", "label": "Reject", "description": "Deny the action"},
        ]

    proposal = {
        "schema_version": SCHEMA_VERSION,
        "proposal_id": proposal_id,
        "bet_id": bet_id,
        "run_id": run_id,
        "title": title,
        "description": description,
        "options": options,
        "status": "pending",
        "created_at": now,
        "expires_at": expires_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "responded_at": None,
        "response_actor": None,
        "response_option": None,
        # v1.1: notification tracking (backward-compat; None for proposals
        # created without notify invoked, populated by bin/notification.py)
        "notified_at": None,
        "notification_channels": [],
    }

    path = PROPOSALS_DIR / f"{proposal_id}.yaml"
    _atomic_write(path, proposal)
    return proposal


def list_proposals(status_filter: str | None = None) -> list[dict[str, Any]]:
    """List all proposals, optionally filtered by status."""
    if not PROPOSALS_DIR.exists():
        return []

    proposals = []
    for f in sorted(PROPOSALS_DIR.glob("hitl-*.yaml")):
        try:
            p = _load_proposal(f)
            if status_filter is None or p.get("status") == status_filter:
                proposals.append(p)
        except (yaml.YAMLError, OSError):
            continue
    return proposals


def get_proposal(proposal_id: str) -> dict[str, Any] | None:
    """Get a proposal by ID (prefix match supported)."""
    if not PROPOSALS_DIR.exists():
        return None

    # Exact match first
    exact = PROPOSALS_DIR / f"{proposal_id}.yaml"
    if exact.exists():
        return _load_proposal(exact)

    # Prefix match
    matches = list(PROPOSALS_DIR.glob(f"{proposal_id}*.yaml"))
    if len(matches) == 1:
        return _load_proposal(matches[0])
    return None


def update_status(
    proposal_id: str,
    new_status: str,
    actor: str = "human",
    option: str | None = None,
) -> dict[str, Any] | None:
    """Update proposal status with file locking for concurrency safety."""
    proposal = get_proposal(proposal_id)
    if proposal is None:
        return None

    path = PROPOSALS_DIR / f"{proposal['proposal_id']}.yaml"

    with open(path, "r+") as f:
        _acquire_lock(f)
        try:
            current = yaml.safe_load(f) or {}
            if current.get("status") != "proposal":
                pass  # allow update
            current["status"] = new_status
            current["responded_at"] = _now()
            current["response_actor"] = actor
            if option:
                current["response_option"] = option
            f.seek(0)
            f.truncate()
            yaml.dump(current, f, default_flow_style=False, sort_keys=False)
            _release_lock(f)
        except BaseException:
            _release_lock(f)
            raise

    return get_proposal(proposal["proposal_id"])


def expire_stale() -> list[str]:
    """Mark expired proposals. Returns list of expired IDs."""
    expired_ids: list[str] = []
    for p in list_proposals(status_filter="pending"):
        try:
            expires = _parse_ts(p["expires_at"])
            if datetime.now(timezone.utc) > expires:
                update_status(p["proposal_id"], "expired", actor="system")
                expired_ids.append(p["proposal_id"])
        except (KeyError, ValueError):
            continue
    return expired_ids


def wait_for_decision(
    proposal_id: str,
    poll_interval: float = 5.0,
    timeout: float | None = None,
) -> dict[str, Any] | None:
    """Poll until proposal is resolved or timeout. Returns final proposal or None."""
    import time

    deadline = None
    if timeout:
        deadline = time.monotonic() + timeout

    while True:
        proposal = get_proposal(proposal_id)
        if proposal is None:
            return None
        if proposal["status"] in ("approved", "rejected", "expired"):
            return proposal
        if deadline and time.monotonic() >= deadline:
            return proposal
        time.sleep(poll_interval)


def check_human_gate_needed(bet_id: str) -> bool:
    """Check if a BET requires human-in-the-loop approval.

    Reads BET definition from bet-ledger to determine if human_gate is set.
    """
    ledger_path = Path("docs/plans/3y-bet-ledger.yaml")
    if not ledger_path.exists():
        return False

    try:
        with open(ledger_path) as f:
            ledger = yaml.safe_load(f)
        if not ledger:
            return False
        for bet in ledger.get("bets", []):
            if bet.get("id") == bet_id:
                return bool(bet.get("human_gate", False))
    except (yaml.YAMLError, OSError):
        return False
    return False


# ── CLI ─────────────────────────────────────────────────────────────────────


def cmd_create(args: argparse.Namespace) -> int:
    proposal = create_proposal(
        bet_id=args.bet_id,
        run_id=args.run_id,
        title=args.title,
        description=args.description,
        ttl_hours=args.ttl,
    )
    print(f"Created: {proposal['proposal_id']}")
    print(f"Expires: {proposal['expires_at']}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    proposals = list_proposals(status_filter=args.status)
    if not proposals:
        print("No proposals found.")
        return 0

    for p in proposals:
        print(f"[{p['status']:>8}] {p['proposal_id']}  {p.get('title', '(untitled)')}")
        print(f"          bet={p.get('bet_id')} run={p.get('run_id')}")
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    proposal = get_proposal(args.proposal_id)
    if proposal is None:
        print(f"Proposal not found: {args.proposal_id}", file=sys.stderr)
        return 1
    print(yaml.dump(proposal, default_flow_style=False, sort_keys=False))
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    actor = args.actor if args.actor != "human" else _detect_actor()
    result = update_status(args.proposal_id, "approved", actor=actor, option="approve")
    if result is None:
        print(f"Proposal not found: {args.proposal_id}", file=sys.stderr)
        return 1
    print(f"Approved: {result['proposal_id']}")
    return 0


def cmd_reject(args: argparse.Namespace) -> int:
    actor = args.actor if args.actor != "human" else _detect_actor()
    result = update_status(args.proposal_id, "rejected", actor=actor, option="reject")
    if result is None:
        print(f"Proposal not found: {args.proposal_id}", file=sys.stderr)
        return 1
    print(f"Rejected: {result['proposal_id']}")
    return 0


def cmd_expire(args: argparse.Namespace) -> int:
    expired = expire_stale()
    if expired:
        print(f"Expired {len(expired)} proposal(s): {', '.join(expired)}")
    else:
        print("No stale proposals to expire.")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Check if a BET requires HITL approval. Prints HITL_REQUIRED if yes."""
    if check_human_gate_needed(args.bet_id):
        print("HITL_REQUIRED")
        return 0
    return 0


def cmd_wait(args: argparse.Namespace) -> int:
    """Block until proposal is resolved. Returns 0 if approved, 1 if rejected/timeout."""
    proposal = wait_for_decision(
        args.proposal_id,
        poll_interval=getattr(args, "interval", 5.0),
        timeout=getattr(args, "timeout", None),
    )
    if proposal is None:
        print(f"Proposal not found: {args.proposal_id}", file=sys.stderr)
        return 1
    status = proposal.get("status", "unknown")
    print(f"Final status: {status}")
    return 0 if status == "approved" else 1


def cmd_lock_backend(args: argparse.Namespace) -> int:
    """Show current distributed lock backend config (v1.1)."""
    print(f"Lock backend: {LOCK_BACKEND}")
    print(f"  fcntl: always available (POSIX file lock)")
    print(f"  etcd: STUB - requires HITL_LOCK_ETCD_ENDPOINTS env var")
    print(f"  redis: STUB - requires HITL_LOCK_REDIS_URL env var")
    if LOCK_BACKEND == "etcd":
        print(f"  etcd endpoints: {LOCK_ETCD_ENDPOINTS or '(not set)'}")
    elif LOCK_BACKEND == "redis":
        print(f"  redis url: {LOCK_REDIS_URL or '(not set)'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hitl-proposal",
        description="HITL Proposal Manager — human-in-the-loop approval system",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="Create a new HITL proposal")
    p_create.add_argument("--bet-id", required=True)
    p_create.add_argument("--run-id", required=True)
    p_create.add_argument("--title", required=True)
    p_create.add_argument("--description", default="")
    p_create.add_argument("--ttl", type=int, default=DEFAULT_TTL_HOURS)
    p_create.set_defaults(func=cmd_create)

    p_list = sub.add_parser("list", help="List proposals")
    p_list.add_argument("--status", choices=["pending", "approved", "rejected", "expired"])
    p_list.set_defaults(func=cmd_list)

    p_get = sub.add_parser("get", help="Get proposal details")
    p_get.add_argument("proposal_id")
    p_get.set_defaults(func=cmd_get)

    p_approve = sub.add_parser("approve", help="Approve a proposal")
    p_approve.add_argument("proposal_id")
    p_approve.add_argument("--actor", default="human")
    p_approve.set_defaults(func=cmd_approve)

    p_reject = sub.add_parser("reject", help="Reject a proposal")
    p_reject.add_argument("proposal_id")
    p_reject.add_argument("--actor", default="human")
    p_reject.set_defaults(func=cmd_reject)

    p_expire = sub.add_parser("expire", help="Expire stale pending proposals")
    p_expire.set_defaults(func=cmd_expire)

    p_check = sub.add_parser("check", help="Check if BET requires HITL approval")
    p_check.add_argument("--bet-id", required=True)
    p_check.set_defaults(func=cmd_check)

    p_lock = sub.add_parser("lock-backend", help="Show current lock backend config (v1.1)")
    p_lock.set_defaults(func=cmd_lock_backend)

    p_wait = sub.add_parser("wait", help="Block until proposal resolved (v1.1)")
    p_wait.add_argument("proposal_id")
    p_wait.add_argument("--timeout", type=float, default=None,
                        help="Max seconds to wait (default: no timeout)")
    p_wait.add_argument("--interval", type=float, default=5.0,
                        help="Poll interval in seconds (default: 5)")
    p_wait.set_defaults(func=cmd_wait)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
