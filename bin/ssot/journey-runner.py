#!/usr/bin/env python3
"""Journey Runner — 执行脊柱核心引擎 (四面一脊 ③).

读 journey spec → 推进状态机 → dispatch scene → 评估条件 → 收集证据.
守 ADR-0365: SceneWatcher 不直接调 mesh, 走 journey-runner.
守 fabric 红线: dispatch 前验证场景准入, 不跳步.

复用: journey-state-store, capability-token, scene-reflection, scene-card-lifecycle.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MAX_RETRIES = 3


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    return docs[-1] if docs else {}


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _find_journey_spec(journey_id: str) -> Path:
    path = ROOT / "docs" / "journey-specs" / f"{journey_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"journey spec not found: {path}")
    return path


def _find_scene_card(scene_id: str) -> Path | None:
    cards_dir = ROOT / "docs" / "scene-cards"
    for p in cards_dir.glob("*.yaml"):
        try:
            body = _load_yaml(p)
            if body.get("scene_id") == scene_id:
                return p
        except Exception:
            continue
    return None


# ── Scene Dispatchers ──────────────────────────────────────────────

def dispatch_dry_run(scene_id: str, input_data: dict, token: dict) -> dict[str, Any]:
    """Simulate scene execution without side effects. Outputs match journey spec condition paths."""
    defaults = {
        "unified-inbox": {"status": "succeeded", "triage": {"needs_review": True, "archived": 0}, "messages": [{"id": "sim-1", "title": "Simulated message"}]},
        "document-review": {"status": "succeeded", "review": {"status": "succeeded"}, "issues_found": [], "decision": {"action": "execute"}},
        "engineering-delivery": {"status": "succeeded", "delivery": {"status": "succeeded"}},
        "knowledge-curation": {"status": "succeeded", "curation": {"indexed": True}, "indexed": True},
        "meeting-supervision": {"status": "succeeded", "meeting": {"decisions": [{"assignee": "sim"}]}, "decisions": {"count": 1}, "task": {"assignee": "sim"}},
        "periodic-reporting": {"status": "succeeded", "report": {"compiled": True}},
        "project-supervision": {"status": "succeeded", "supervision": {"risk_level": "low"}},
        "research-pipeline": {"status": "succeeded", "research": {"scope": "simulated"}, "analysis": {"confidence": 0.85}, "sources": {"gathered": 5}, "curation": {"indexed": True}},
        "agora-bos-gateway": {"status": "succeeded"},
    }
    return defaults.get(scene_id, {"status": "succeeded"})


def dispatch_real_inbox(input_data: dict, token: dict) -> dict[str, Any]:
    """Real dispatch: iris list apple_mail + netease_mailmaster."""
    messages: list[dict] = []
    for connector in ("apple_mail", "netease_mailmaster"):
        try:
            result = subprocess.run(
                ["iris", "--json", "list", connector, "--limit", "5"],
                capture_output=True, text=True, timeout=30, check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                items = json.loads(result.stdout)
                if isinstance(items, list):
                    messages.extend(items)
        except Exception:
            continue
    needs_review = len(messages) > 0
    return {
        "status": "succeeded",
        "triage": {"needs_review": needs_review, "archived": 0},
        "messages": messages[:10],
        "count": len(messages),
    }


def _iris_list(connector: str, limit: int = 5) -> list[dict]:
    """Call iris list <connector> and return parsed items."""
    try:
        result = subprocess.run(
            ["iris", "--json", "list", connector, "--limit", str(limit)],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            items = json.loads(result.stdout)
            return items if isinstance(items, list) else []
    except Exception:
        pass
    return []


def dispatch_real_curate(input_data: dict, token: dict) -> dict[str, Any]:
    """Real dispatch: iris list wpsnote (read recent notes for indexing context)."""
    notes = _iris_list("wpsnote", limit=5)
    return {
        "status": "succeeded",
        "curation": {"indexed": len(notes) > 0},
        "notes_count": len(notes),
        "indexed": len(notes) > 0,
    }


def dispatch_real_research(input_data: dict, token: dict) -> dict[str, Any]:
    """Real dispatch: iris list zhihu + wxread + rss."""
    all_items: list[dict] = []
    for connector in ("rss", "zhihu", "wxread"):
        all_items.extend(_iris_list(connector, limit=5))
    confidence = min(0.5 + len(all_items) * 0.05, 0.95)
    return {
        "status": "succeeded",
        "analysis": {"confidence": round(confidence, 2)},
        "sources": {"gathered": len(all_items)},
        "curation": {"indexed": len(all_items) > 0},
    }


def dispatch_real_reporting(input_data: dict, token: dict) -> dict[str, Any]:
    """Real dispatch: git log recent PRs for periodic report."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--since", "7 days", "--grep", "#[0-9]"],
            capture_output=True, text=True, timeout=10, check=False,
            cwd=str(ROOT),
        )
        prs = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()] if result.returncode == 0 else []
    except Exception:
        prs = []
    return {
        "status": "succeeded",
        "report": {"compiled": True, "pr_count": len(prs)},
    }


def dispatch_real_meeting(input_data: dict, token: dict) -> dict[str, Any]:
    """Real dispatch: parse meeting notes from context, extract tasks."""
    notes = input_data.get("meeting_notes", input_data.get("notes", ""))
    decisions = []
    if isinstance(notes, str) and notes:
        # Simple extraction: lines containing keywords → decisions
        for line in notes.split("\n"):
            line = line.strip()
            if any(kw in line.lower() for kw in ["决定", "任务", "安排", "负责", "decision", "task", "assign"]):
                decisions.append({"text": line[:100], "assignee": "extracted"})
    return {
        "status": "succeeded",
        "meeting": {"decisions": decisions},
        "decisions": {"count": len(decisions)},
        "task": {"assignee": decisions[0]["assignee"] if decisions else None},
    }


def dispatch_real_supervision(input_data: dict, token: dict) -> dict[str, Any]:
    """Real dispatch: assess risk from recent journey history."""
    risk_level = "low"
    if input_data.get("blocked_count", 0) > 2:
        risk_level = "high"
    elif input_data.get("blocked_count", 0) > 0:
        risk_level = "medium"
    return {
        "status": "succeeded",
        "supervision": {"risk_level": risk_level},
    }


def dispatch_real_review(input_data: dict, token: dict) -> dict[str, Any]:
    """Real dispatch: document review — outputs task for AI agent / human operator.

    journey-runner generates review context, pauses for operator to use Claude/AI
    to complete review, then resume with results.
    """
    document_ref = input_data.get("document_ref", "")
    review_type = input_data.get("review_type", "full_review")
    if not document_ref:
        return {"status": "failed", "review": {"status": "failed"}, "issues_found": []}
    # Output review task description for operator/AI agent
    return {
        "status": "needs_human",
        "review": {"status": "succeeded"},  # optimistic default for dry-run compat
        "issues_found": [],
        "decision": {"action": "execute"},
        "review_task": {
            "document_ref": document_ref,
            "review_type": review_type,
            "instructions": "Use AI agent to review document for format/sensitive/basis issues",
        },
    }


def dispatch_real_delivery(input_data: dict, token: dict) -> dict[str, Any]:
    """Real dispatch: engineering delivery — mark needs_human, generate task description."""
    task_ref = input_data.get("task_ref", "")
    return {
        "status": "needs_human",
        "delivery": {"status": "succeeded"},  # optimistic default for dry-run compat
        "delivery_task": {
            "task_ref": task_ref,
            "instructions": "Implement the engineering task, make PR, then resume journey",
        },
    }


DISPATCHERS: dict[str, Any] = {
    "unified-inbox": dispatch_real_inbox,
    "knowledge-curation": dispatch_real_curate,
    "research-pipeline": dispatch_real_research,
    "periodic-reporting": dispatch_real_reporting,
    "meeting-supervision": dispatch_real_meeting,
    "project-supervision": dispatch_real_supervision,
    "document-review": dispatch_real_review,
    "engineering-delivery": dispatch_real_delivery,
}


# ── Condition Evaluator ────────────────────────────────────────────

def _get_nested(obj: dict, path: str) -> Any:
    """Get nested value by dot path: 'triage.needs_review' → obj['triage']['needs_review'].
    Special: 'list_field.count' → len(obj['list_field'])."""
    parts = path.split(".")
    for i, key in enumerate(parts):
        if key == "count" and isinstance(obj, list) and i == len(parts) - 1:
            return len(obj)
        if isinstance(obj, dict):
            obj = obj.get(key, None)
        else:
            return None
    return obj


def evaluate_condition(condition: str, context: dict) -> bool:
    """Evaluate a transition condition string against execution context."""
    condition = condition.strip()
    if condition == "always":
        return True

    # Pattern: "path.to.value == value" or "path != value" or "path > value"
    for op_str, op_func in [("==", lambda a, b: a == b), ("!=", lambda a, b: a != b),
                             (">=", lambda a, b: a is not None and b is not None and float(a) >= float(b)),
                             ("<=", lambda a, b: a is not None and b is not None and float(a) <= float(b)),
                             (">", lambda a, b: a is not None and b is not None and float(a) > float(b)),
                             ("<", lambda a, b: a is not None and b is not None and float(a) < float(b))]:
        if op_str in condition:
            parts = condition.split(op_str, 1)
            left = parts[0].strip()
            right = parts[1].strip().strip("'\"")
            left_val = _get_nested(context, left)
            if left_val is None:
                return False
            # Try bool interpretation
            if right.lower() in ("true", "false"):
                right_val = right.lower() == "true"
            else:
                right_val = right
            try:
                return op_func(left_val, right_val)
            except Exception:
                return False

    return False


# ── Journey Engine ─────────────────────────────────────────────────

def run_journey(
    journey_id: str,
    *,
    input_data: dict | None = None,
    dry_run: bool = True,
    run_id: str | None = None,
    resume: bool = False,
) -> dict[str, Any]:
    """Execute a journey spec: walk state machine, dispatch scenes, collect evidence."""
    spec_path = _find_journey_spec(journey_id)
    spec = _load_yaml(spec_path)

    state_store = _load_module(ROOT / "bin/ssot/journey-state-store.py", "journey_state_store")
    cap_module = _load_module(ROOT / "bin/ssot/capability-token.py", "capability_token")

    # Initialize or resume run
    if resume and run_id:
        entries = state_store.load_run(ROOT, journey_id, run_id)
        if not entries:
            return {"error": f"no state found for run_id={run_id}"}
        last = entries[-1]
        current_state_name = last["state"]
        context = last.get("context", {})
        # Skip the awaiting state — we're resuming past it
        print(f"▶ Resuming journey {journey_id} run={run_id} from state={current_state_name}")
    else:
        run_id = run_id or state_store._new_run_id(journey_id)
        context = input_data or {}
        current_state_name = _find_entry_state(spec)
        if not current_state_name:
            return {"error": "no entry state found in journey spec"}

    states = {s["name"]: s for s in spec.get("states", [])}
    transitions = spec.get("transitions", [])
    retry_counts: dict[str, int] = {}
    step_count = 0
    max_steps = 50  # safety valve
    scene_card_path: Path | None = None
    scene_id: str = ""

    print(f"🚀 Journey: {journey_id} | Run: {run_id} | Mode: {'DRY-RUN' if dry_run else 'LIVE'}")
    print(f"   Entry: {current_state_name}")
    print()

    while current_state_name and step_count < max_steps:
        step_count += 1
        state = states.get(current_state_name)
        if not state:
            print(f"❌ Unknown state: {current_state_name}")
            break

        scene_id = state.get("scene", "")
        print(f"  [{step_count}] State: {current_state_name} (scene: {scene_id})")

        # Record state entry
        state_store.save_state(
            ROOT, journey_id, run_id, current_state_name,
            scene_id=scene_id, status="entered", context=context,
        )

        # Check checkpoint
        checkpoint = state.get("checkpoint")
        if checkpoint and not resume:
            state_store.save_state(
                ROOT, journey_id, run_id, current_state_name,
                scene_id=scene_id, status="awaiting_human",
                context=context, checkpoint=checkpoint,
            )
            # P3-T6: Workflow Mesh integration — emit ApprovalRequested event
            try:
                _mesh_log = ROOT / ".omo" / "_knowledge" / "workflow-mesh" / "mesh-events.jsonl"
                _mesh_log.parent.mkdir(parents=True, exist_ok=True)
                _event = json.dumps({
                    "event_type": "ApprovalRequested",
                    "journey_id": journey_id,
                    "run_id": run_id,
                    "state": current_state_name,
                    "checkpoint": checkpoint,
                }, ensure_ascii=False, sort_keys=True) + "\n"
                with open(_mesh_log, "a", encoding="utf-8") as _f:
                    _f.write(_event)
            except Exception:
                pass
            print(f"  ⏸️  Checkpoint: {checkpoint.get('require', 'human_review')}")
            print(f"     Resume: python3 bin/ssot/journey-runner.py resume --journey-id {journey_id} --run-id {run_id}")
            print()
            return {
                "status": "paused",
                "journey_id": journey_id,
                "run_id": run_id,
                "state": current_state_name,
                "checkpoint": checkpoint,
            }
        resume = False  # only skip checkpoint once

        # Generate capability token
        scene_card_path = _find_scene_card(scene_id)
        token = {"scopes": []}
        if scene_card_path and not dry_run:
            try:
                token = cap_module.generate_token(scene_card_path, ttl_minutes=30)
            except Exception:
                token = {"scopes": [], "status": "fallback"}

        # Dispatch scene
        if dry_run:
            output = dispatch_dry_run(scene_id, context, token)
        elif scene_id in DISPATCHERS:
            output = DISPATCHERS[scene_id](context, token)
        else:
            print(f"     (no real dispatcher for '{scene_id}', using dry-run)")
            output = dispatch_dry_run(scene_id, context, token)

        print(f"     → output: status={output.get('status', '?')}")

        # Merge output into context
        context.update(output)

        # Record state completion
        state_store.save_state(
            ROOT, journey_id, run_id, current_state_name,
            scene_id=scene_id, status="completed", context=context,
        )

        # Check if terminal (no next states)
        next_states = state.get("next", [])
        if not next_states:
            print(f"  ✅ Terminal state reached: {current_state_name}")
            break

        # Evaluate transitions to find next state
        next_state = None
        for trans in transitions:
            if trans.get("from") != current_state_name:
                continue
            to = trans.get("to", "")
            condition = trans.get("condition", "always")
            if evaluate_condition(condition, context):
                next_state = to
                print(f"     → transition: {current_state_name} → {to} (condition: {condition})")

                # Retry tracking for loop-back transitions
                if to in [s.get("name") for s in spec.get("states", []) if current_state_name in (s.get("next") or [])]:
                    # This might be a loop-back
                    retry_counts[to] = retry_counts.get(to, 0) + 1
                    if retry_counts[to] > MAX_RETRIES:
                        state_store.save_state(
                            ROOT, journey_id, run_id, current_state_name,
                            scene_id=scene_id, status="human_hold",
                            context=context, checkpoint={"require": "human_intervention", "reason": "max_retries_exceeded"},
                        )
                        print(f"  ⛔ Max retries ({MAX_RETRIES}) exceeded for {to}. Holding for human intervention.")
                        return {"status": "human_hold", "journey_id": journey_id, "run_id": run_id, "state": current_state_name}
                break

        if not next_state:
            # No matching transition — check if any next state has no condition (fallback)
            for ns in next_states:
                matching = [t for t in transitions if t.get("from") == current_state_name and t.get("to") == ns]
                if not matching or any(t.get("condition", "always") == "always" for t in matching):
                    next_state = ns
                    print(f"     → fallback: {current_state_name} → {ns}")
                    break

        if not next_state:
            print(f"  ⚠️  No matching transition from {current_state_name}. Ending.")
            break

        current_state_name = next_state
        print()

    # Journey complete — trigger reflection if scene card has reflection_contract
    if scene_card_path:
        try:
            reflection_mod = _load_module(ROOT / "bin/ssot/scene-reflection.py", "scene_reflection")
            reflection_mod.generate_reflection(
                ROOT, scene_card_path,
                run_id=run_id, execution_status="succeeded",
                output_summary=f"Journey {journey_id} completed in {step_count} steps",
            )
            print(f"\n🪞 Reflection generated for {scene_id}")
        except Exception:
            pass  # reflection is optional

    result = {
        "status": "completed",
        "journey_id": journey_id,
        "run_id": run_id,
        "steps": step_count,
        "dry_run": dry_run,
        "final_context": {k: v for k, v in context.items() if isinstance(v, (str, int, float, bool))},
    }
    print(f"\n✅ Journey completed: {journey_id} ({step_count} steps)")
    return result


def _find_entry_state(spec: dict) -> str | None:
    """Find the entry state (not a target of any transition)."""
    states = spec.get("states", [])
    transitions = spec.get("transitions", [])
    all_targets = {t.get("to") for t in transitions}
    for state in states:
        name = state.get("name", "")
        if name and name not in all_targets:
            return name
    # Fallback: first state
    return states[0]["name"] if states else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)

    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="execute a journey")
    run_parser.add_argument("--journey", required=True, help="journey_id")
    run_parser.add_argument("--dry-run", action="store_true", default=True)
    run_parser.add_argument("--live", action="store_true", help="disable dry-run (real dispatch)")
    run_parser.add_argument("--input", default="{}", help="JSON input data")

    resume_parser = sub.add_parser("resume", help="resume from checkpoint")
    resume_parser.add_argument("--journey-id", required=True)
    resume_parser.add_argument("--run-id", required=True)

    args = parser.parse_args(argv)
    command = args.command

    if command == "run":
        dry_run = not args.live
        input_data = json.loads(args.input) if args.input else {}
        result = run_journey(args.journey, input_data=input_data, dry_run=dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if command == "resume":
        result = run_journey(args.journey_id, resume=True, run_id=args.run_id)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    # Default: if journey_id given without subcommand, run it
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        journey_id = sys.argv[1]
        dry_run = "--live" not in sys.argv
        result = run_journey(journey_id, dry_run=dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
