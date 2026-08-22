#!/usr/bin/env python3
"""decision-agent — event-driven decision proposals (WP-F).

Subscribes to failure/debt/swarm events and, when triggered, scans internal
state (reusing evolution-agent's scan_internal) and writes a proposal JSON under
`.omo/_knowledge/evolution-proposals/` carrying the triggering event's trace_id
for provenance.

WP-F: 事件驱动决策 — 失败/债务事件 → 决策提案(可追溯)。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
PROPOSAL_DIR = WORKSPACE / ".omo" / "_knowledge" / "evolution-proposals"
TRIGGER_EVENTS = frozenset({"WorkflowFailed", "StepFailed", "StepTimeout"})


def _write_proposal(result: dict[str, Any], trace_id: str) -> str | None:
    PROPOSAL_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    slug = (trace_id or "event").replace(":", "-")[-40:]
    path = PROPOSAL_DIR / f"decision-{ts}-{slug}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return str(path.relative_to(WORKSPACE))


def _scan_proposals() -> list[dict[str, Any]]:
    """Reuse evolution-agent's scan_internal to surface improvement opportunities."""
    try:
        agent_path = Path(__file__).resolve().parent / "evolution-agent.py"
        spec = importlib.util.spec_from_file_location("evolution_agent", agent_path)
        assert spec is not None and spec.loader is not None
        agent = importlib.util.module_from_spec(spec)
        sys.modules["evolution_agent"] = agent
        spec.loader.exec_module(agent)
        return agent.scan_internal()
    except Exception:  # noqa: BLE001 - decision scan is best-effort
        return []


def _decide(event: dict[str, Any]) -> str | None:
    """One event → decision proposal (with trace_id provenance)."""
    trace_id = str(event.get("trace_id") or event.get("event_id") or "")
    event_type = str(event.get("event_type") or "")
    if event_type not in TRIGGER_EVENTS:
        return None
    proposals = _scan_proposals()
    result = {
        "schema": "resident-decision/v1",
        "trigger_event": {
            "event_type": event_type,
            "trace_id": trace_id,
            "workflow_run_id": event.get("workflow_run_id"),
            "event_id": event.get("event_id"),
        },
        "proposal_count": len(proposals),
        "proposals": proposals,
    }
    return _write_proposal(result, trace_id)


def register_with_daemon(daemon_module: Any) -> None:
    """Wire the decision handler into resident-orchestrator-daemon.

    Decision writes are read-only-ish (proposal JSON under evolution-proposals)
    so they register as ``safe``.
    """
    daemon_module.register_handler("decision_agent", _decision_handler, safe=True)


def _decision_handler(event: dict[str, Any]) -> None:
    path = _decide(event)
    if path is not None:
        print(f"[decision-agent] proposal_written {path}", file=sys.stderr)


def main() -> int:
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", help="event JSON string")
    args = parser.parse_args()
    event = json.loads(args.json) if args.json else json.loads(sys.stdin.read())
    path = _decide(event)
    print(json.dumps({"written": path is not None, "path": path}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
