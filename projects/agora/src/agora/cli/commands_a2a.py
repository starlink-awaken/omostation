"""A2A and event commands: a2a, agent-card, transitions, event."""

from __future__ import annotations

import asyncio
import json

from agora.cli.errors import CLIError
from agora.cli.output import OutputFormatter
from agora.core.event_bus import EventBus  # type: ignore[import-not-found]
from agora.core.router import Router  # type: ignore[import-not-found]
from agora.core.state import get_registry  # type: ignore[import-not-found]


def cmd_a2a(args):
    """A2A Task API."""
    registry = get_registry()
    router = Router(registry)
    from agora.a2a.task_manager import TaskManager  # type: ignore[import-not-found]

    out = OutputFormatter(json_mode=getattr(args, 'json', False))
    try:
        tm = TaskManager(router)

        if args.a2a_cmd == "send":
            try:
                arguments = json.loads(args.arguments) if isinstance(args.arguments, str) else {}
            except json.JSONDecodeError:
                arguments = {"raw": args.arguments}
            task = tm.create_task("", args.tool_name, arguments, args.session)
            try:
                result = asyncio.run(tm.execute_task(task.id))
            except Exception as e:
                raise CLIError(f"任务执行失败: {e}", suggestion="检查目标服务和工具")
            if result:
                out.print_json(result.to_dict())
            else:
                out.print_error("Execution failed", suggestion="检查服务日志了解详情")
                return 1

        elif args.a2a_cmd == "get":
            task = tm.get_task(args.task_id)
            if task:
                out.print_json(task.to_dict())
            else:
                out.print_error(f"Task '{args.task_id}' not found", suggestion="使用 'agora a2a list' 查看所有任务")
                return 1

        elif args.a2a_cmd == "cancel":
            if tm.cancel_task(args.task_id):
                out.print_success(f"Canceled: {args.task_id}")
            else:
                out.print_warning(f"Cannot cancel '{args.task_id}' - not found or already completed")

        elif args.a2a_cmd == "list":
            tasks = tm.list_tasks(
                service=getattr(args, "service", ""),
                status=getattr(args, "status", ""),
                since=getattr(args, "since", ""),
                limit=getattr(args, "limit", 50),
            )
            if not tasks:
                out.print_info("(no tasks)")
            for t in tasks:
                icon = {
                    "completed": "OK",
                    "failed": "FAIL",
                    "working": "RUN",
                    "submitted": "PEND",
                    "canceled": "CANCEL",
                }.get(t.status, "?")
                print(f"  [{icon}] [{t.id}] {t.tool_name:30s} -> {t.status:12s} | {t.created_at}")
        return 0
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1


def cmd_agent_card(args):
    """A2A Agent Card operations."""
    registry = get_registry()
    from agora.server.mcp import _build_agent_card  # type: ignore[import-not-found]

    out = OutputFormatter(json_mode=getattr(args, 'json', False))
    try:
        if args.agent_card_cmd == "list":
            cards = {}
            for svc in registry.list_all():
                card, err = _build_agent_card(svc.name)
                cards[svc.name] = card if card else {"error": err}
            out.print_json(cards)
        elif args.agent_card_cmd == "get":
            card, err = _build_agent_card(args.name)
            if card is None:
                out.print_error(f"Agent card not available: {err}", suggestion="检查服务名称和端点")
                return 1
            out.print_json(card)
        return 0
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1


def cmd_transitions(args):
    """State transition history."""
    registry = get_registry()
    out = OutputFormatter(json_mode=getattr(args, 'json', False))
    try:
        transitions = registry.get_transitions(service=args.service, since=args.since, limit=args.limit)
        if args.json:
            out.print_json({"transitions": transitions, "count": len(transitions)})
        else:
            if not transitions:
                out.print_info("(no transitions)")
            for t in transitions:
                src = t.get("state_from", "")
                to_state = t.get("state_to", "")
                print(f"  [{t.get('timestamp', '?')}] {t.get('service', '?'):15s} {src or '':>12s} -> {to_state:<12s} | {t.get('reason', '?')}")
        return 0
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1


def cmd_event(args):
    """Event bus operations."""
    registry = get_registry()
    bus = EventBus(registry=registry)

    out = OutputFormatter(json_mode=getattr(args, 'json', False))
    try:
        if args.event_cmd == "publish":
            try:
                payload = json.loads(args.payload) if args.payload else {}
            except json.JSONDecodeError:
                payload = {"raw": args.payload}
            eid = bus.publish(args.type, payload, args.source)
            out.print_success(f"Published: {eid} ({args.type})")

        elif args.event_cmd == "log":
            events = bus.get_event_log(args.limit)
            if not events:
                out.print_info("(no events)")
            for e in events:
                print(
                    f"  [{e.get('time', '?')}] {e.get('source', '?'):15s} -> {e.get('type', '?'):30s} | {json.dumps(e.get('payload', {}), ensure_ascii=False)[:80]}"
                )

        elif args.event_cmd == "subscribe":
            sid = bus.subscribe("cli", args.pattern, args.callback)
            out.print_success(f"Subscribed: {sid} -> {args.pattern}")

        elif args.event_cmd == "unsubscribe":
            ok = bus.unsubscribe(args.id)
            out.print_success(f"{'Unsubscribed' if ok else 'Not found'}: {args.id}")
        return 0
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1
