#!/usr/bin/env python3
"""A2A Adapter — 异构Agent间通信适配器 (ADR-0403 P4).

将omo agent暴露给外部agent (Claude Code/Desktop/龙虾等) 通过A2A协议.
复用agora BOS路由 + gen-agent-constraints的Agent Card.

支持的适配:
  - omo internal: AgentHost tick → jsonl 消息队列
  - Claude Code: MCP tool → BOS URI → message queue
  - Claude Desktop: SSE :7431 → BOS URI → message queue
  - 外部HTTP: A2A HTTP/JSON-RPC → BOS URI → message queue

Usage:
  python3 bin/ssot/a2a-adapter.py --send --to advisor --type task --payload '{"action":"evaluate"}'
  python3 bin/ssot/a2a-adapter.py --recv --for advisor
  python3 bin/ssot/a2a-adapter.py --discover
  python3 bin/ssot/a2a-adapter.py --publish-cards
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _shared import ROOT, append_jsonl, read_jsonl, utc_now, load_yaml

AGENTS_DIR = ROOT / ".omo/_truth/registry/agents"
MESSAGE_QUEUE = ROOT / ".omo/state/a2a-messages.jsonl"
CARD_DIR = ROOT / ".omo/state/agent-cards"


def discover_agents() -> list[dict]:
    """List all registered agents with their Agent Cards."""
    cards = []
    for path in sorted(AGENTS_DIR.glob("*.yaml")):
        data = load_yaml(path)
        if data.get("schema") != "digital_agent/v2":
            continue
        identity = data.get("identity", {})
        cards.append({
            "@type": "AgentCard",
            "id": data.get("id"),
            "name": data.get("display_name", data.get("id")),
            "description": data.get("description", ""),
            "role": identity.get("role"),
            "capabilities": identity.get("capabilities", []),
            "bos_uri": f"bos://a2a/agent/{data.get('id')}",
            "knowledge_sources": data.get("knowledge_sources", []),
        })
    return cards


def publish_cards() -> dict:
    """Write Agent Cards to .omo/state/agent-cards/ for A2A discovery."""
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    cards = discover_agents()
    for card in cards:
        path = CARD_DIR / f"{card['id']}.json"
        path.write_text(json.dumps(card, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    # Also write index
    index_path = CARD_DIR / "index.json"
    index_path.write_text(json.dumps({"agents": cards, "count": len(cards), "updated": utc_now()}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"published": len(cards), "dir": str(CARD_DIR.relative_to(ROOT))}


def send_message(to_agent: str, msg_type: str, payload: dict, *, from_agent: str = "external") -> dict:
    """Send a message to an agent via file-based queue."""
    msg = {
        "ts": utc_now(),
        "from": from_agent,
        "to": to_agent,
        "type": msg_type,
        "payload": payload,
    }
    append_jsonl(MESSAGE_QUEUE, msg)
    return {"status": "sent", "to": to_agent, "type": msg_type}


def recv_messages(for_agent: str) -> list[dict]:
    """Receive pending messages for an agent."""
    all_msgs = read_jsonl(MESSAGE_QUEUE)
    return [m for m in all_msgs if m.get("to") == for_agent and not m.get("consumed")]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--publish-cards", action="store_true")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--recv", action="store_true")
    parser.add_argument("--to", default=None)
    parser.add_argument("--for", dest="for_agent", default=None)
    parser.add_argument("--from", dest="from_agent", default="external")
    parser.add_argument("--type", default="task")
    parser.add_argument("--payload", default="{}")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.discover:
        cards = discover_agents()
        if args.json:
            print(json.dumps(cards, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"A2A Discovery: {len(cards)} agents")
            for c in cards:
                print(f"  {c['id']:25s} role={c['role']:10s} caps={c['capabilities'][:3]}")
        return 0

    if args.publish_cards:
        result = publish_cards()
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if args.send:
        payload = json.loads(args.payload) if args.payload else {}
        result = send_message(args.to, args.type, payload, from_agent=args.from_agent)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if args.recv:
        msgs = recv_messages(args.for_agent)
        print(json.dumps(msgs, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
