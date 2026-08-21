#!/usr/bin/env python3
"""G-DEL.2b collab CLI — process-local CollabBus with durable history + G-DEL.4 handoff link.

Usage:
  python3 bin/delivery/collab_cli.py run-handshake
  python3 bin/delivery/collab_cli.py history --task-ref task-xxx
  python3 bin/delivery/collab_cli.py handoff-link --task-ref task-xxx \\
      --writer agent-A --scope bet-b7da
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from role_collab import CollabBus, CollabMessage, run_collab_handshake  # noqa: E402
from shared_context_store import FileSharedContextStore, default_store_root  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HISTORY = ROOT / ".omo" / "_delivery" / "collab"


def _history_dir(root: Path | None = None) -> Path:
    d = (root or DEFAULT_HISTORY)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _append_history(task_ref: str, event: dict[str, Any], *, hist_root: Path) -> Path:
    path = _history_dir(hist_root) / f"{task_ref}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return path


def _read_history(task_ref: str, *, hist_root: Path) -> list[dict[str, Any]]:
    path = _history_dir(hist_root) / f"{task_ref}.jsonl"
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def cmd_run_handshake(args: argparse.Namespace) -> int:
    hist = Path(args.history_root) if args.history_root else DEFAULT_HISTORY
    result = run_collab_handshake(fail_verify=bool(args.fail_verify))
    event = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kind": "handshake",
        "task_ref": result.task_ref,
        "completed": result.completed,
        "steps": result.steps,
        "error": result.error,
    }
    path = _append_history(result.task_ref, event, hist_root=hist)
    # Also log each step as message summary for audit
    for step in result.steps:
        _append_history(
            result.task_ref,
            {"ts": event["ts"], "kind": "step", "step": step},
            hist_root=hist,
        )
    print(
        json.dumps(
            {
                "ok": result.completed,
                "task_ref": result.task_ref,
                "steps": result.steps,
                "error": result.error,
                "history_path": str(path),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if result.completed else 1


def cmd_history(args: argparse.Namespace) -> int:
    hist = Path(args.history_root) if args.history_root else DEFAULT_HISTORY
    events = _read_history(args.task_ref, hist_root=hist)
    print(json.dumps({"ok": True, "task_ref": args.task_ref, "n": len(events), "events": events}, indent=2))
    return 0


def cmd_handoff_link(args: argparse.Namespace) -> int:
    """Write collab handoff summary into G-DEL.4 shared-context for the next agent."""
    hist = Path(args.history_root) if args.history_root else DEFAULT_HISTORY
    events = _read_history(args.task_ref, hist_root=hist)
    handshake = next((e for e in events if e.get("kind") == "handshake"), None)
    if not handshake:
        print(json.dumps({"ok": False, "error": "no_handshake_in_history"}))
        return 1
    store = FileSharedContextStore(
        Path(args.context_root) if args.context_root else default_store_root(ROOT)
    )
    value = json.dumps(
        {
            "task_ref": args.task_ref,
            "completed": handshake.get("completed"),
            "steps": handshake.get("steps"),
            "linked_from": "G-DEL.2b collab_cli",
        },
        ensure_ascii=False,
    )
    rec = store.write(
        args.writer,
        args.key,
        value,
        scope=args.scope,
        tags=["handoff", "g-del-2b"],
    )
    print(
        json.dumps(
            {
                "ok": True,
                "shared_context": {
                    "scope": args.scope,
                    "key": rec.key,
                    "writer": rec.writer,
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    """Publish one message onto an in-process bus and persist to history (audit)."""
    hist = Path(args.history_root) if args.history_root else DEFAULT_HISTORY
    task_ref = args.task_ref or f"task-{uuid.uuid4().hex[:8]}"
    msg = CollabMessage(
        id=uuid.uuid4().hex,
        type=args.type,
        from_agent=args.from_agent,
        from_role=args.from_role,
        to_role=args.to_role,
        task_ref=task_ref,
        payload=json.loads(args.payload) if args.payload else {},
    )
    bus = CollabBus()
    bus.publish(msg)
    _append_history(
        task_ref,
        {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "kind": "message",
            "message": {
                "id": msg.id,
                "type": msg.type,
                "from_agent": msg.from_agent,
                "from_role": msg.from_role,
                "to_role": msg.to_role,
                "payload": msg.payload,
            },
        },
        hist_root=hist,
    )
    print(json.dumps({"ok": True, "task_ref": task_ref, "message_id": msg.id}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--history-root", type=Path, default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)

    rh = sub.add_parser("run-handshake", help="run full G-DEL.2a handshake once")
    rh.add_argument("--fail-verify", action="store_true")
    rh.set_defaults(func=cmd_run_handshake)

    hi = sub.add_parser("history", help="show durable collab history")
    hi.add_argument("--task-ref", required=True)
    hi.set_defaults(func=cmd_history)

    hl = sub.add_parser("handoff-link", help="link handshake result into G-DEL.4 shared-context")
    hl.add_argument("--task-ref", required=True)
    hl.add_argument("--writer", default="orchestrator")
    hl.add_argument("--key", default="collab.handoff")
    hl.add_argument("--scope", default="default")
    hl.add_argument("--context-root", type=Path, default=None)
    hl.set_defaults(func=cmd_handoff_link)

    pu = sub.add_parser("publish", help="publish one collab message + history")
    pu.add_argument("--type", required=True)
    pu.add_argument("--from-agent", default="cli")
    pu.add_argument("--from-role", required=True)
    pu.add_argument("--to-role", default=None)
    pu.add_argument("--task-ref", default=None)
    pu.add_argument("--payload", default=None, help="JSON object string")
    pu.set_defaults(func=cmd_publish)

    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
