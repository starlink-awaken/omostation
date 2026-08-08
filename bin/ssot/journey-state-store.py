#!/usr/bin/env python3
"""Journey state persistence — append-only state transitions with checkpoint/resume."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _state_dir(root: Path, journey_id: str) -> Path:
    return root / ".omo" / "_knowledge" / "workflow-mesh" / "journey-states" / journey_id


def _new_run_id(journey_id: str) -> str:
    ts = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    salt = hashlib.sha256(f"{journey_id}:{ts}".encode()).hexdigest()[:8]
    return f"{ts}-{salt}"


def save_state(
    root: Path,
    journey_id: str,
    run_id: str,
    state_name: str,
    *,
    scene_id: str = "",
    status: str = "entered",
    context: dict[str, Any] | None = None,
    checkpoint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one state transition record."""
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "journey_id": journey_id,
        "run_id": run_id,
        "state": state_name,
        "scene": scene_id,
        "status": status,
        "context": context or {},
    }
    if checkpoint:
        entry["checkpoint"] = checkpoint

    log_dir = _state_dir(root, journey_id)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{run_id}.jsonl"

    import fcntl

    with open(log_path, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    return entry


def load_run(root: Path, journey_id: str, run_id: str) -> list[dict[str, Any]]:
    """Load all state records for a run (for resume)."""
    log_path = _state_dir(root, journey_id) / f"{run_id}.jsonl"
    if not log_path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").strip().split("\n"):
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def current_state(root: Path, journey_id: str, run_id: str) -> dict[str, Any] | None:
    """Get the latest state record for a run."""
    entries = load_run(root, journey_id, run_id)
    return entries[-1] if entries else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])

    sub = parser.add_subparsers(dest="command")

    save_parser = sub.add_parser("save", help="save one state transition")
    save_parser.add_argument("--journey-id", required=True)
    save_parser.add_argument("--run-id", default=None)
    save_parser.add_argument("--state", required=True)
    save_parser.add_argument("--scene", default="")
    save_parser.add_argument("--status", default="entered")

    resume_parser = sub.add_parser("resume", help="show current state for resume")
    resume_parser.add_argument("--journey-id", required=True)
    resume_parser.add_argument("--run-id", required=True)

    sub.add_parser("new-run", help="generate a new run_id").add_argument("--journey-id", required=True)

    args = parser.parse_args(argv)
    command = args.command or "help"

    if command == "new-run":
        print(_new_run_id(args.journey_id))
        return 0

    if command == "save":
        run_id = args.run_id or _new_run_id(args.journey_id)
        entry = save_state(args.root, args.journey_id, run_id, args.state, scene_id=args.scene, status=args.status)
        entry["run_id"] = run_id
        print(json.dumps(entry, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if command == "resume":
        state = current_state(args.root, args.journey_id, args.run_id)
        if state:
            print(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"No state found for journey={args.journey_id} run={args.run_id}")
            return 1
        return 0

    print("Commands: new-run, save, resume")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
