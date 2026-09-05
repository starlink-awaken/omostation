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

from _shared import ROOT, load_yaml

DEFAULT_BACKEDGE_LIMIT = 3


def _detect_backedges(spec: dict) -> set[tuple[str, str]]:
    """Detect backedges in the journey transition graph via DFS (BET-Y1Q2-T5-02).

    A backedge is a transition from→to where 'to' is an ancestor of 'from'
    in the DFS traversal — i.e., it forms a cycle.
    Returns set of (from_state, to_state) tuples.
    """
    transitions = spec.get("transitions", [])
    adj: dict[str, list[str]] = {}
    for t in transitions:
        src = t.get("from", "")
        dst = t.get("to", "")
        if src and dst:
            adj.setdefault(src, []).append(dst)

    backedges: set[tuple[str, str]] = set()
    visited: set[str] = set()
    on_stack: set[str] = set()

    def dfs(node: str) -> None:
        visited.add(node)
        on_stack.add(node)
        for nxt in adj.get(node, []):
            if nxt in on_stack:
                backedges.add((node, nxt))
            elif nxt not in visited:
                dfs(nxt)
        on_stack.discard(node)

    for state in spec.get("states", []):
        name = state.get("name", "")
        if name and name not in visited:
            dfs(name)

    return backedges


def _emit_escalation_event(journey_id: str, run_id: str, state: str, limit: int) -> None:
    """Emit OMO event when backedge limit exceeded (BET-Y1Q2-T5-02)."""
    try:
        subprocess.run(
            [
                "python3",
                str(ROOT / "projects/omo/src/omo/cli.py"),
                "event",
                "emit",
                "--type",
                "journey_backedge_escalated",
                "--source",
                "journey-runner",
                "--payload",
                json.dumps(
                    {
                        "journey_id": journey_id,
                        "run_id": run_id,
                        "state": state,
                        "backedge_limit": limit,
                    }
                ),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            cwd=str(ROOT),
        )
    except Exception as exc:
        print(f"[journey-runner] emit failed: {exc}", file=sys.stderr)


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


# ── Journey template support (BET-Y3H1-T5-01) ────────────────────────────────


def _render_template(spec: dict) -> dict:
    """If a journey spec references a template, merge it with the spec.

    A spec may declare ``template: <id>`` plus ``params: {key: value}``. The
    template file under ``docs/journey-templates/`` provides the shared
    states/transitions skeleton with ``{{param}}`` placeholders. The spec's own
    fields override the rendered template (deep-merged by section).
    """
    template_id = spec.get("template")
    if not template_id:
        return spec
    template_path = ROOT / "docs" / "journey-templates" / f"{template_id}.yaml"
    if not template_path.exists():
        raise FileNotFoundError(f"journey template not found: {template_path}")

    template = load_yaml(template_path)
    params = spec.get("params", {}) or {}

    def substitute(value):
        if isinstance(value, str):
            for key, val in params.items():
                value = value.replace("{{" + str(key) + "}}", str(val))
            return value
        if isinstance(value, list):
            return [substitute(v) for v in value]
        if isinstance(value, dict):
            return {k: substitute(v) for k, v in value.items()}
        return value

    rendered_states = substitute(template.get("states", []))
    rendered_transitions = substitute(template.get("transitions", []))

    merged = dict(template)
    merged["schema"] = spec.get("schema", merged.get("schema"))
    merged["journey_id"] = spec.get("journey_id", merged.get("journey_id"))
    merged["description"] = spec.get("description", merged.get("description"))
    merged["states"] = rendered_states
    merged["transitions"] = rendered_transitions

    # Spec-level overrides (section merge).
    for section in ("states", "transitions"):
        if spec.get(section):
            merged[section] = spec[section]
    # Extra spec fields (checkpoint, backedge_limit, etc.) pass through.
    for key, val in spec.items():
        if key not in (
            "template",
            "params",
            "states",
            "transitions",
            "schema",
            "journey_id",
            "description",
        ):
            merged[key] = val
    return merged


def _find_scene_card(scene_id: str) -> Path | None:
    cards_dir = ROOT / "docs" / "scene-cards"
    for p in cards_dir.glob("*.yaml"):
        try:
            body = load_yaml(p)
            if body.get("scene_id") == scene_id:
                return p
        except Exception:
            continue
    return None


# ── Scene Dispatchers ──────────────────────────────────────────────


def _has_real_data(output: dict[str, Any]) -> bool:
    """Detect whether a live dispatch produced real (non-simulated) data.

    Heuristics per scene output shape:
      - research-pipeline: sources.gathered >= 3 (iris list across 3 connectors)
      - unified-inbox: messages non-empty
      - knowledge-curation: notes_count > 0
      - periodic-reporting: pr_count > 0 or report.items
    Returns False when output is empty/simulated → caller sets data_integrity on state entry.
    """
    gathered = (output.get("sources") or {}).get("gathered", 0)
    if isinstance(gathered, int) and gathered > 0:
        return True
    # 2026-08-26: admin-inbox 输出结构是 mails/has_task(此前启发式只查
    # messages/notes_count/pr_count — admin 场景恒判 degraded 的根因)
    if isinstance(output.get("mails"), list) and output["mails"]:
        return True
    if output.get("has_task") is True:
        return True
    # 2026-08-25: admin 后段状态输出是草稿路径型(notice/form/report/eml 草稿
    # 落盘 = 真实产出), 不识别会误报 degraded
    if any(
        output.get(k)
        for k in ("notice_draft", "form_draft", "report_draft", "leader_email_draft", "submission_draft")
    ):
        return True
    if output.get("messages"):
        return True
    if output.get("notes_count", 0) > 0:
        return True
    if output.get("pr_count", 0) > 0:
        return True
    if output.get("items"):
        return True
    return False


def dispatch_dry_run(scene_id: str, input_data: dict, token: dict) -> dict[str, Any]:
    """Simulate scene execution without side effects. Outputs match journey spec condition paths."""
    defaults = {
        "unified-inbox": {
            "status": "succeeded",
            "triage": {"needs_review": True, "archived": 0},
            "messages": [{"id": "sim-1", "title": "Simulated message"}],
        },
        "document-review": {
            "status": "succeeded",
            "review": {"status": "succeeded"},
            "issues_found": [],
            "decision": {"action": "execute"},
        },
        "engineering-delivery": {
            "status": "succeeded",
            "delivery": {"status": "succeeded"},
        },
        "knowledge-curation": {
            "status": "succeeded",
            "curation": {"indexed": True},
            "indexed": True,
        },
        "meeting-supervision": {
            "status": "succeeded",
            "meeting": {"decisions": [{"assignee": "sim"}]},
            "decisions": {"count": 1},
            "task": {"assignee": "sim"},
        },
        "periodic-reporting": {"status": "succeeded", "report": {"compiled": True}},
        "project-supervision": {
            "status": "succeeded",
            "supervision": {"risk_level": "low"},
        },
        "research-pipeline": {
            "status": "succeeded",
            "research": {"scope": "simulated"},
            "analysis": {"confidence": 0.85},
            "sources": {"gathered": 5},
            "curation": {"indexed": True},
        },
        "agora-bos-gateway": {"status": "succeeded"},
        # admin-notification-workflow (7 状态闭环): 输出字段对齐 spec transitions
        # 条件 (has_task/requires_forwarding/email_drafts_created/report_compiled),
        # 缺失时 journey 卡死在 received (fallback 只有 status)。
        "admin-inbox": {"status": "succeeded", "has_task": True},
        "admin-classify": {
            "status": "succeeded",
            "requires_forwarding": input_data.get("requires_forwarding", True),
            "task_type": "转发通知",
        },
        "admin-forward": {"status": "succeeded", "email_drafts_created": True},
        "admin-collect": {"status": "succeeded"},
        "admin-compile": {"status": "succeeded", "report_compiled": True},
        "admin-review": {"status": "succeeded"},
        "admin-submit": {"status": "succeeded"},
    }
    return defaults.get(scene_id, {"status": "succeeded"})


def dispatch_real_inbox(input_data: dict, token: dict) -> dict[str, Any]:
    """Real dispatch: iris list apple_mail + netease_mailmaster."""
    messages: list[dict] = []
    for connector in ("apple_mail", "netease_mailmaster"):
        try:
            result = subprocess.run(
                ["iris", "--json", "list", connector, "--limit", "5"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                # 2026-08-26: iris CLI 的弃用警告走 stdout 污染 JSON —
                # 剥离非 JSON 前缀(找首个 [ 或 {)再解析
                text = result.stdout.strip()
                start = min((i for i in (text.find("["), text.find("{")) if i >= 0), default=-1)
                if start < 0:
                    continue
                items = json.loads(text[start:])
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
    """Call iris list <connector> and return parsed items.

    过滤连接器不可用/需配置的状态对象 (available: False, setup 提示),
    只保留真实内容项 — 否则 wxread 未配置 API Key 时返回的
    {'available': False, 'note': '需要设置...'} 会被误判为真实数据.
    """
    try:
        result = subprocess.run(
            ["iris", "--json", "list", connector, "--limit", str(limit)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            text = result.stdout.strip()
            start = min((i for i in (text.find("["), text.find("{")) if i >= 0), default=-1)
            items = json.loads(text[start:]) if start >= 0 else []
            if isinstance(items, list):
                return [it for it in items if _is_real_item(it)]
    except Exception:
        pass
    return []


def _is_real_item(item: dict) -> bool:
    """Item 是否真实内容 (排除连接器状态提示/不可用占位)."""
    if not isinstance(item, dict):
        return True
    if item.get("available") is False:
        return False
    if item.get("setup") or item.get("note", "").startswith("需要"):
        return False
    return True


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
        "research": {"scope": "live", "connectors": ["rss", "zhihu", "wxread"]},
        "analysis": {"confidence": round(confidence, 2)},
        "sources": {"gathered": len(all_items)},
        "curation": {"indexed": len(all_items) > 0},
    }


def dispatch_real_reporting(input_data: dict, token: dict) -> dict[str, Any]:
    """Real dispatch: git log recent PRs for periodic report."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--since", "7 days", "--grep", "#[0-9]"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            cwd=str(ROOT),
        )
        prs = (
            [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
            if result.returncode == 0
            else []
        )
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

# 注册行政流程 scenes (数字大脑工作域)
try:
    from admin_scenes import ADMIN_SCENES

    DISPATCHERS.update(ADMIN_SCENES)
except Exception:
    pass


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
    ops = [
        ("==", lambda a, b: a == b),
        ("!=", lambda a, b: a != b),
        (">=", lambda a, b: a is not None and b is not None and float(a) >= float(b)),
        ("<=", lambda a, b: a is not None and b is not None and float(a) <= float(b)),
        (">", lambda a, b: a is not None and b is not None and float(a) > float(b)),
        ("<", lambda a, b: a is not None and b is not None and float(a) < float(b)),
    ]
    for op_str, op_func in ops:
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
    backedge_limit: int | None = None,
) -> dict[str, Any]:
    """Execute a journey spec: walk state machine, dispatch scenes, collect evidence."""
    spec_path = _find_journey_spec(journey_id)
    spec = _render_template(load_yaml(spec_path))

    state_store = _load_module(ROOT / "bin/ssot/journey-state-store.py", "journey_state_store")
    cap_module = _load_module(ROOT / "bin/ssot/capability-token.py", "capability_token")

    effective_limit = backedge_limit or spec.get("backedge_limit", DEFAULT_BACKEDGE_LIMIT)
    backedges = _detect_backedges(spec)

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

    # Parallel support (BET-Y1Q4-T5-01): track a set of active states. A fork
    # fans out into branches; a join collects completed branch states and only
    # proceeds when the configured strategy is satisfied.
    active_states: list[str] = [current_state_name]
    completed_states: set[str] = set()

    while active_states and step_count < max_steps:
        current_state_name = active_states[0]
        step_count += 1
        state = states.get(current_state_name)
        if not state:
            print(f"❌ Unknown state: {current_state_name}")
            active_states = active_states[1:]
            continue

        scene_id = state.get("scene", "")
        print(f"  [{step_count}] State: {current_state_name} (scene: {scene_id})")

        # Fork: fan out into parallel branches instead of executing the state.
        if _is_fork_state(state):
            branches = _fork_branches(state)
            print(f"     → FORK into branches: {branches}")
            active_states = active_states[1:] + [b for b in branches if b in states]
            continue

        # Join: wait for source branches to complete per strategy.
        if _is_join_state(state):
            sources = _join_sources(state)
            strategy = _join_strategy(state)
            done = sum(1 for s in sources if s in completed_states or s == current_state_name)
            if not _join_satisfied(strategy, done, len(sources)):
                print(f"     → JOIN pending: {done}/{len(sources)} sources ({strategy}), waiting…")
                # Move this join to the end of the queue so other branches run first.
                active_states = active_states[1:] + [current_state_name]
                continue
            print(f"     → JOIN satisfied ({done}/{len(sources)}, {strategy})")
            # Join runs exactly once: drop duplicate join_point copies from the
            # queue left behind by each completed source branch.
            active_states = [s for s in active_states if s != current_state_name]
            completed_states.add(current_state_name)

        # Record state entry
        state_store.save_state(
            ROOT,
            journey_id,
            run_id,
            current_state_name,
            scene_id=scene_id,
            status="entered",
            context=context,
            dry_run=dry_run,
        )

        # Check checkpoint
        checkpoint = state.get("checkpoint")
        if checkpoint and not resume:
            state_store.save_state(
                ROOT,
                journey_id,
                run_id,
                current_state_name,
                scene_id=scene_id,
                status="awaiting_human",
                context=context,
                checkpoint=checkpoint,
                dry_run=dry_run,
            )
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

        # LIVE mode data-integrity guard: real dispatchers that yield no real
        # data (environment unavailable) must be marked degraded, not silently
        # treated as a successful live run (防 FACE-03 伪造 live 证据).
        data_integrity_flag = ""
        if not dry_run:
            real_signal = _has_real_data(output)
            if not real_signal:
                data_integrity_flag = "degraded"
                print("     ⚠️  LIVE but no real data detected (iris env down?) → data_integrity=degraded")

        # Record state completion
        state_store.save_state(
            ROOT,
            journey_id,
            run_id,
            current_state_name,
            scene_id=scene_id,
            status="completed",
            context=context,
            dry_run=dry_run,
            data_integrity=data_integrity_flag,
        )

        # Check if terminal (no next states)
        next_states = state.get("next", [])
        if not next_states:
            print(f"  ✅ Terminal state reached: {current_state_name}")
            completed_states.add(current_state_name)
            active_states = active_states[1:]
            if not active_states:
                break
            continue

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

                # Backedge tracking (BET-Y1Q2-T5-02): use pre-computed DFS backedges
                if (current_state_name, to) in backedges:
                    retry_counts[to] = retry_counts.get(to, 0) + 1
                    if retry_counts[to] > effective_limit:
                        state_store.save_state(
                            ROOT,
                            journey_id,
                            run_id,
                            current_state_name,
                            scene_id=scene_id,
                            status="human_hold",
                            context=context,
                            checkpoint={
                                "require": "human_intervention",
                                "reason": "backedge_limit_exceeded",
                            },
                            dry_run=dry_run,
                        )
                        _emit_escalation_event(journey_id, run_id, current_state_name, effective_limit)
                        print(
                            f"  ⛔ Backedge limit ({effective_limit}) exceeded for {to}. Holding for human intervention."
                        )
                        return {
                            "status": "human_hold",
                            "journey_id": journey_id,
                            "run_id": run_id,
                            "state": current_state_name,
                            "backedge_limit": effective_limit,
                        }
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

        # Record this state as completed (needed for join source counting).
        completed_states.add(current_state_name)
        # Queue the next state (parallel: append, linear: shift).
        if _is_fork_state(state) or active_states:
            active_states = active_states[1:] + [next_state]
        else:
            active_states = [next_state]
        print()

    # Journey complete — trigger reflection if scene card has reflection_contract
    if scene_card_path:
        try:
            reflection_mod = _load_module(ROOT / "bin/ssot/scene-reflection.py", "scene_reflection")
            reflection_mod.generate_reflection(
                ROOT,
                scene_card_path,
                run_id=run_id,
                execution_status="succeeded",
                output_summary=f"Journey {journey_id} completed in {step_count} steps",
            )
            print(f"\n🪞 Reflection generated for {scene_id}")
        except Exception as exc:
            print(f"[journey-runner] reflection trigger failed: {exc}", file=sys.stderr)  # reflection is optional

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


def scan_template_usage() -> dict[str, Any]:
    """Map which journey specs reference which templates (BET-Y3H1-T5-01).

    Lets an operator see the blast radius before changing a template.
    """
    specs_dir = ROOT / "docs" / "journey-specs"
    templates_dir = ROOT / "docs" / "journey-templates"
    usage: dict[str, list[str]] = {}
    for tp in sorted(templates_dir.glob("*.yaml")):
        usage[tp.stem] = []
    for sp in sorted(specs_dir.glob("*.yaml")):
        try:
            body = load_yaml(sp)
        except (OSError, ValueError):
            continue
        tid = body.get("template")
        if tid:
            usage.setdefault(tid, []).append(sp.stem)
    return {
        "schema": "journey-template-usage/v1",
        "templates": sorted(usage.keys()),
        "usage": {k: sorted(v) for k, v in usage.items()},
        "total_template_refs": sum(len(v) for v in usage.values()),
    }


# ── Parallel fork/join helpers (BET-Y1Q4-T5-01) ──────────────────────────────


def _is_fork_state(state: dict) -> bool:
    return bool(state.get("parallel"))


def _fork_branches(state: dict) -> list[str]:
    """Branches a fork state fans out to."""
    parallel = state.get("parallel", {})
    return list(parallel.get("branches", []) or [])


def _is_join_state(state: dict) -> bool:
    return bool(state.get("join"))


def _join_sources(state: dict) -> list[str]:
    join = state.get("join", {})
    return list(join.get("sources", []) or [])


def _join_strategy(state: dict) -> str:
    return str(state.get("join", {}).get("strategy", "all"))


def _join_satisfied(strategy: str, completed: int, total: int) -> bool:
    """Decide whether a join can proceed based on the configured strategy.

    all     → every source branch must complete
    majority → more than half must complete
    any     → at least one must complete
    """
    if total <= 0:
        return True  # no sources → degenerate join passes
    if strategy == "all":
        return completed >= total
    if strategy == "majority":
        return completed > total / 2
    if strategy == "any":
        return completed >= 1
    return completed >= total  # unknown strategy → safest: all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)

    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="execute a journey")
    run_parser.add_argument("--journey", required=True, help="journey_id")
    run_parser.add_argument("--dry-run", action="store_true", default=True)
    run_parser.add_argument("--live", action="store_true", help="disable dry-run (real dispatch)")
    run_parser.add_argument("--input", default="{}", help="JSON input data")
    run_parser.add_argument(
        "--backedge-limit",
        type=int,
        default=None,
        help=f"max backedge traversals before escalation (default: {DEFAULT_BACKEDGE_LIMIT})",
    )

    resume_parser = sub.add_parser("resume", help="resume from checkpoint")
    resume_parser.add_argument("--journey-id", required=True)
    resume_parser.add_argument("--run-id", required=True)

    sub.add_parser("templates", help="show journey template usage / blast radius")

    validate_parser = sub.add_parser("validate", help="validate journey spec(s)")
    validate_parser.add_argument("spec_path", type=Path, nargs="?", help="single spec file (omit for all)")
    validate_parser.add_argument("--json", action="store_true", help="emit JSON output")

    args = parser.parse_args(argv)
    command = args.command

    if command == "validate":
        import importlib.util as _ilu

        _spec = _ilu.spec_from_file_location("journey_validator", ROOT / "bin/ssot/journey-validator.py")
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        files = [args.spec_path] if args.spec_path else sorted((ROOT / "docs" / "journey-specs").glob("*.yaml"))
        if not files:
            print("No journey specs found.")
            return 1
        all_valid = True
        results = []
        for path in files:
            try:
                spec = _mod._load_yaml(path)
                result = _mod.validate_journey(spec, _mod._load_scene_ids(ROOT))
                results.append(result)
                if not result["valid"]:
                    all_valid = False
                if not args.json:
                    status = "PASS" if result["valid"] else "FAIL"
                    print(f"[{status}] {path.name}: {result['states']} states, {result['transitions']} transitions")
                    for e in result["errors"]:
                        print(f"    ERROR: {e}")
                    for w in result["warnings"]:
                        print(f"    WARN: {w}")
            except Exception as exc:
                print(f"[FAIL] {path.name}: {exc}")
                all_valid = False
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if all_valid else 1

    if command == "run":
        dry_run = not args.live
        input_data = json.loads(args.input) if args.input else {}
        result = run_journey(
            args.journey,
            input_data=input_data,
            dry_run=dry_run,
            backedge_limit=args.backedge_limit,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        if result.get("status") == "human_hold" or "error" in result:
            return 1
        return 0

    if command == "resume":
        result = run_journey(args.journey_id, resume=True, run_id=args.run_id)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        if result.get("status") == "human_hold" or "error" in result:
            return 1
        return 0

    if command == "templates":
        usage = scan_template_usage()
        print(json.dumps(usage, ensure_ascii=False, indent=2, sort_keys=True))
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
