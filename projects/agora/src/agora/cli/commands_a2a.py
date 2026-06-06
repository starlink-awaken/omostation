"""A2A and event commands: a2a, agent-card, transitions, event."""

from __future__ import annotations

import asyncio
import json

from agora.core.event_bus import EventBus  # type: ignore[import-not-found]
from agora.core.router import Router  # type: ignore[import-not-found]
from agora.core.state import get_registry  # type: ignore[import-not-found]


def cmd_a2a(args):
    """A2A Task API."""
    registry = get_registry()
    router = Router(registry)
    from agora.a2a.task_manager import TaskManager  # type: ignore[import-not-found]

    tm = TaskManager(router)

    if args.a2a_cmd == "send":
        try:
            arguments = json.loads(args.arguments) if isinstance(args.arguments, str) else {}
        except json.JSONDecodeError:
            arguments = {"raw": args.arguments}
        task = tm.create_task("", args.tool_name, arguments, args.session)
        result = asyncio.run(tm.execute_task(task.id))
        if result:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        else:
            print("Execution failed")

    elif args.a2a_cmd == "get":
        task = tm.get_task(args.task_id)
        if task:
            print(json.dumps(task.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(f"Task '{args.task_id}' not found")

    elif args.a2a_cmd == "cancel":
        if tm.cancel_task(args.task_id):
            print(f"Canceled: {args.task_id}")
        else:
            print(f"Cannot cancel '{args.task_id}' - not found or already completed")

    elif args.a2a_cmd == "list":
        tasks = tm.list_tasks(
            service=getattr(args, "service", ""),
            status=getattr(args, "status", ""),
            since=getattr(args, "since", ""),
            limit=getattr(args, "limit", 50),
        )
        if not tasks:
            print("(no tasks)")
        for t in tasks:
            icon = {
                "completed": "OK",
                "failed": "FAIL",
                "working": "RUN",
                "submitted": "PEND",
                "canceled": "CANCEL",
            }.get(t.status, "?")
            print(f"  [{icon}] [{t.id}] {t.tool_name:30s} -> {t.status:12s} | {t.created_at}")


def cmd_agent_card(args):
    """A2A Agent Card operations."""
    registry = get_registry()
    from agora.server.mcp import _build_agent_card  # type: ignore[import-not-found]

    if args.agent_card_cmd == "list":
        cards = {}
        for svc in registry.list_all():
            card, err = _build_agent_card(svc.name)
            cards[svc.name] = card if card else {"error": err}
        print(json.dumps(cards, indent=2, ensure_ascii=False, default=str))
    elif args.agent_card_cmd == "get":
        card, err = _build_agent_card(args.name)
        if card is None:
            print(f"Error: {err}")
        else:
            print(json.dumps(card, indent=2, ensure_ascii=False, default=str))


def cmd_transitions(args):
    """State transition history."""
    registry = get_registry()
    transitions = registry.get_transitions(service=args.service, since=args.since, limit=args.limit)
    if args.json:
        print(json.dumps({"transitions": transitions, "count": len(transitions)}, indent=2, ensure_ascii=False))
    else:
        if not transitions:
            print("(no transitions)")
        for t in transitions:
            src = t["state_from"]
            to_state = t["state_to"]
            print(f"  [{t['timestamp']}] {t['service']:15s} {src or '':>12s} -> {to_state:<12s} | {t['reason']}")


def cmd_event(args):
    """Event bus operations."""
    registry = get_registry()
    bus = EventBus(registry=registry)

    if args.event_cmd == "publish":
        try:
            payload = json.loads(args.payload) if args.payload else {}
        except json.JSONDecodeError:
            payload = {"raw": args.payload}
        eid = bus.publish(args.type, payload, args.source)
        print(f"Published: {eid} ({args.type})")

    elif args.event_cmd == "log":
        events = bus.get_event_log(args.limit)
        if not events:
            print("(no events)")
        for e in events:
            print(
                f"  [{e['time']}] {e['source']:15s} -> {e['type']:30s} | {json.dumps(e.get('payload', {}), ensure_ascii=False)[:80]}"
            )

    elif args.event_cmd == "subscribe":
        sid = bus.subscribe("cli", args.pattern, args.callback)
        print(f"Subscribed: {sid} -> {args.pattern}")

    elif args.event_cmd == "unsubscribe":
        ok = bus.unsubscribe(args.id)
        print(f"{'Unsubscribed' if ok else 'Not found'}: {args.id}")
