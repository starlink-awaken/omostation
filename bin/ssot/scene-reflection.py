#!/usr/bin/env python3
"""Scene reflection executor — reads reflection_contract, generates self-evaluation, stores results.

Implements the Reflection Loop pattern (20-40% quality improvement per industry data).
After a scene executes, this tool generates structured self-evaluation questions
and persists the reflection for feedforward to future executions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from _shared import append_jsonl, load_yaml, read_jsonl, utc_now

REFLECTION_SCHEMA = "scene-reflection/v1"


def _load_scene_card(path: Path) -> dict[str, Any]:
    body = load_yaml(path)
    if not body:
        raise ValueError(f"scene card must be an object: {path}")
    return body


def generate_reflection(
    root: Path,
    scene_card_path: Path,
    *,
    run_id: str = "",
    execution_status: str = "succeeded",
    output_summary: str = "",
    actor: str = "agent",
) -> dict[str, Any]:
    """Generate a reflection entry from a scene card's reflection_contract."""
    card = _load_scene_card(scene_card_path)
    scene_id = card.get("scene_id", "unknown")

    contract = card.get("reflection_contract", {})
    if not isinstance(contract, dict) or not contract.get("enabled", False):
        return {"schema": REFLECTION_SCHEMA, "status": "skipped", "detail": "reflection_contract not enabled"}

    questions = contract.get("questions", [])
    if not isinstance(questions, list) or not questions:
        return {"schema": REFLECTION_SCHEMA, "status": "skipped", "detail": "no questions defined"}

    # Build reflection entry
    ts = utc_now()
    digest_input = f"{scene_id}:{run_id}:{ts}:{execution_status}"
    entry = {
        "ts": ts,
        "schema": REFLECTION_SCHEMA,
        "scene_id": scene_id,
        "run_id": run_id,
        "execution_status": execution_status,
        "output_summary": output_summary[:500],
        "questions": questions,
        "answers": {},  # Populated by reviewer (human or agent)
        "feedforward": contract.get("feedforward", False),
        "actor": actor,
        "digest": f"sha256:{hashlib.sha256(digest_input.encode()).hexdigest()[:16]}",
    }

    # Persist to reflection log
    log_path = root / ".omo" / "_knowledge" / "workflow-mesh" / "scene-reflections.jsonl"
    append_jsonl(log_path, entry)

    entry["status"] = "recorded"

    # T-B3: reflection → evolution trigger.
    # 执行异常时触发 evolution-agent 扫描, 让反思进入进化提案.
    if execution_status not in ("succeeded", "skipped"):
        triggered = _trigger_evolution(root, scene_id, execution_status)
        entry["evolution_triggered"] = triggered

    return entry


def _trigger_evolution(root: Path, scene_id: str, execution_status: str) -> bool:
    """Trigger evolution-agent scan when execution shows anomalies."""
    import subprocess

    try:
        proc = subprocess.run(
            ["python3", str(root / "bin/ssot/evolution-agent.py"), "--json"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if proc.returncode == 0 and proc.stdout:
            import json as _json

            data = _json.loads(proc.stdout)
            n = int(data.get("total_proposals", 0))
            # Record trigger trace
            trace_path = root / ".omo" / "_knowledge" / "workflow-mesh" / "evolution-triggers.jsonl"
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            with open(trace_path, "a", encoding="utf-8") as f:
                f.write(
                    _json.dumps(
                        {
                            "ts": datetime.now(UTC).isoformat(),
                            "scene_id": scene_id,
                            "execution_status": execution_status,
                            "proposals_generated": n,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            return True
    except Exception:
        pass
    return False


def list_reflections(root: Path, scene_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """List recent reflections, optionally filtered by scene_id."""
    log_path = root / ".omo" / "_knowledge" / "workflow-mesh" / "scene-reflections.jsonl"
    if not log_path.exists():
        return []

    entries = read_jsonl(log_path)
    if scene_id is not None:
        entries = [e for e in entries if e.get("scene_id") == scene_id]
    return entries[-limit:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])

    sub = parser.add_subparsers(dest="command")

    gen_parser = sub.add_parser("generate", help="generate reflection entry")
    gen_parser.add_argument("--scene-card", type=Path, required=True)
    gen_parser.add_argument("--run-id", default="")
    gen_parser.add_argument("--execution-status", default="succeeded")
    gen_parser.add_argument("--output-summary", default="")
    gen_parser.add_argument("--actor", default="agent")

    list_parser = sub.add_parser("list", help="list recent reflections")
    list_parser.add_argument("--scene-id", default=None)
    list_parser.add_argument("--limit", type=int, default=20)

    args = parser.parse_args(argv)
    command = args.command or "list"

    if command == "generate":
        result = generate_reflection(
            args.root, args.scene_card,
            run_id=args.run_id, execution_status=args.execution_status,
            output_summary=args.output_summary, actor=args.actor,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result.get("status") in ("recorded", "skipped") else 1

    if command == "list":
        entries = list_reflections(args.root, scene_id=args.scene_id, limit=args.limit)
        if not entries:
            print("No reflections found.")
            return 0
        print(f"Recent reflections ({len(entries)} entries):")
        for e in entries:
            q_count = len(e.get("questions", []))
            print(f"  {e['ts'][:19]}  {e.get('scene_id','?'):25s}  status={e.get('execution_status','?')}  questions={q_count}  feedforward={e.get('feedforward',False)}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
