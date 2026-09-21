#!/usr/bin/env python3
"""Agent Federation — 跨 agent 任务 broker + load-balancer (B1.1).

FORWARD-PLAN v2 §B1.1: 多 agent 协同任务分配, 复用 agent profiles +
quota-ledger + a2a-adapter 消息队列, 提供 discover/plan/dispatch/status/
complete/audit 六个子命令.

设计原则:
  - 不替代 ADR-0203 workflow — 只做"谁做"的分配决策, 不做治理门禁
  - 所有分配决策记录到 .omo/state/federation-tasks.jsonl (可审计)
  - 配额感知: 跳过 last_exhausted_at 在冷却期内的 runtime
  - 安全降级: 找不到合适 agent 时返回错误, 不静默跳过

Usage:
  python3 bin/ssot/agent-federation.py discover
  python3 bin/ssot/agent-federation.py plan --task "修复 CI lint 错误" --workflow project-code-change
  python3 bin/ssot/agent-federation.py dispatch --task "..." --agent governance-agent --workflow project-code-change
  python3 bin/ssot/agent-federation.py status
  python3 bin/ssot/agent-federation.py complete --task-id FED-001
  python3 bin/ssot/agent-federation.py audit
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _shared import ROOT, append_jsonl, load_yaml, read_jsonl, utc_now

# ── Paths ────────────────────────────────────────────────────────────

PROFILES_PATH = ROOT / ".omo/_truth/registry/agent-workflows/profiles/_base.yaml"
QUOTA_PATH = ROOT / ".agents/skills/multica-squad-ops/quota-ledger.yaml"
TASKS_PATH = ROOT / ".omo/state/federation-tasks.jsonl"
A2A_QUEUE_PATH = ROOT / ".omo/state/a2a-messages.jsonl"

# ── Scoring weights ─────────────────────────────────────────────────

WEIGHT_LANE = 0.30
WEIGHT_WORKFLOW = 0.25
WEIGHT_QUOTA = 0.20
WEIGHT_AFFINITY = 0.15
WEIGHT_COST = 0.10

# Tier → cost multiplier (lower = cheaper)
TIER_COST = {"T0": 5, "T1": 3, "T2": 2, "T3": 1, "T4": 1}

# Default runtime tier for agent profiles not in quota-ledger
AGENT_TIER_DEFAULT = {
    "governance-agent": "T0",
    "engineering-agent": "T0",
    "sage-planner": "T0",
    "docs-agent": "T1",
    "qa-agent": "T1",
    "state-sync-agent": "T1",
    "c2g-agent": "T1",
    "mof-agent": "T1",
    "adapter-agent": "T1",
    "builder-agent": "T2",
    "keeper-cartridge": "T2",
    "devil-challenger": "T2",
    "strategy-agent": "T2",
    "external-contributor-agent": "T2",
    "release-agent": "T2",
    "observer-agent": "T4",
    "external-readonly-agent": "T4",
    "any-agent": "T1",
}

# ── Agent profiles ───────────────────────────────────────────────────


def load_agent_profiles() -> dict[str, dict[str, Any]]:
    """Load agent profiles from _base.yaml."""
    data = load_yaml(PROFILES_PATH)
    return data.get("agent_profiles", {})


def get_profile(profiles: dict, name: str) -> dict | None:
    """Get a single agent profile by name."""
    return profiles.get(name)


def list_agents(profiles: dict) -> list[dict[str, Any]]:
    """List all registered agents with summary info."""
    agents = []
    for name, profile in sorted(profiles.items()):
        workflows = profile.get("allowed_workflows", [])
        lanes = profile.get("can_write_lanes", [])
        agents.append({
            "name": name,
            "purpose": profile.get("purpose", ""),
            "workflow_count": len(workflows),
            "workflows": workflows if workflows == ["*"] else workflows,
            "lane_count": len(lanes),
            "lanes": lanes,
            "closeout": profile.get("closeout_required", []),
        })
    return agents


# ── Quota awareness ──────────────────────────────────────────────────


def load_quota_ledger() -> dict[str, dict[str, Any]]:
    """Load quota ledger entries by runtime name."""
    if not QUOTA_PATH.exists():
        return {}
    data = load_yaml(QUOTA_PATH)
    entries = {}
    for e in data.get("entries", []):
        runtime = e.get("runtime", "")
        entries[runtime] = e
    return entries


def is_agent_available(runtime: str, quotas: dict) -> tuple[bool, str]:
    """Check if a runtime/agent is available (not in cooldown)."""
    entry = quotas.get(runtime)
    if not entry:
        return True, "unknown (no quota data)"
    exhausted_at = entry.get("last_exhausted_at")
    if not exhausted_at:
        return True, "active"
    cooldown_hours = entry.get("cooldown_hours", 24)
    try:
        exhausted_dt = datetime.fromisoformat(exhausted_at.replace("Z", "+00:00"))
        cooldown_until = exhausted_dt.timestamp() + cooldown_hours * 3600
        if time.time() < cooldown_until:
            hours_left = (cooldown_until - time.time()) / 3600
            return False, f"cooldown ({hours_left:.1f}h remaining)"
        return True, "cooldown expired"
    except (ValueError, OverflowError):
        return True, "active (unparseable timestamp)"


def get_agent_tier(runtime: str, quotas: dict) -> str:
    """Get the tier of a runtime/agent from quota ledger or default mapping."""
    entry = quotas.get(runtime)
    if entry:
        return entry.get("tier", "unknown")
    return AGENT_TIER_DEFAULT.get(runtime, "unknown")


# ── Task scoring ─────────────────────────────────────────────────────


def score_agent(
    agent_name: str,
    profile: dict,
    task_workflow: str | None,
    task_lanes: list[str] | None,
    task_capabilities: list[str] | None,
    quotas: dict,
) -> tuple[float, list[str]]:
    """Score an agent for a task. Returns (score, reasons)."""
    reasons = []
    total = 0.0

    # 1. Lane compatibility (0.30)
    agent_lanes = set(profile.get("can_write_lanes", []))
    if task_lanes:
        match = len(set(task_lanes) & agent_lanes)
        if agent_lanes == set() and task_lanes:
            lane_score = 0.0
            reasons.append("lane_mismatch (no write lanes)")
        elif match > 0:
            lane_score = 1.0
            reasons.append(f"lane_match ({match}/{len(task_lanes)})")
        else:
            lane_score = 0.0
            reasons.append("lane_mismatch")
    elif agent_lanes:
        lane_score = 0.5
        reasons.append("lane_wildcard (task has no lane spec)")
    else:
        lane_score = 0.0
        reasons.append("no_lanes")
    total += WEIGHT_LANE * lane_score

    # 2. Workflow permission (0.25)
    workflows = profile.get("allowed_workflows", [])
    if task_workflow:
        if workflows == ["*"] or task_workflow in workflows:
            wf_score = 1.0
            reasons.append("workflow_allowed")
        else:
            wf_score = 0.0
            reasons.append("workflow_denied")
    else:
        wf_score = 0.5
        reasons.append("workflow_unknown")
    total += WEIGHT_WORKFLOW * wf_score

    # 3. Quota availability (0.20)
    available, status = is_agent_available(agent_name, quotas)
    if available:
        quota_score = 1.0
        reasons.append(f"quota_ok ({status})")
    else:
        quota_score = 0.0
        reasons.append(f"quota_blocked ({status})")
    total += WEIGHT_QUOTA * quota_score

    # 4. Capability affinity (0.15)
    purpose = profile.get("purpose", "").lower()
    if task_capabilities:
        purpose_score = 0.0
        for cap in task_capabilities:
            if cap.lower() in purpose:
                purpose_score = max(purpose_score, 0.8)
                reasons.append(f"capability_match ({cap})")
        if purpose_score == 0.0:
            purpose_score = 0.2
            reasons.append("capability_weak")
    else:
        purpose_score = 0.5
        reasons.append("capability_unknown")
    total += WEIGHT_AFFINITY * purpose_score

    # 5. Cost tier (0.10) — lower tier = better
    tier = get_agent_tier(agent_name, quotas)
    cost = TIER_COST.get(tier, 3)
    cost_score = max(0.0, (5 - cost) / 4)
    total += WEIGHT_COST * cost_score
    reasons.append(f"tier_{tier} (cost={cost})")

    return round(total, 4), reasons


def rank_agents(
    task_workflow: str | None,
    task_lanes: list[str] | None,
    task_capabilities: list[str] | None,
) -> list[dict[str, Any]]:
    """Rank all agents by score for the given task."""
    profiles = load_agent_profiles()
    quotas = load_quota_ledger()
    ranked = []
    for name, profile in sorted(profiles.items()):
        score, reasons = score_agent(
            name, profile, task_workflow, task_lanes, task_capabilities, quotas,
        )
        ranked.append({
            "agent": name,
            "score": score,
            "reasons": reasons,
            "tier": get_agent_tier(name, quotas),
            "purpose": profile.get("purpose", ""),
        })
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked


# ── Task ID generation ───────────────────────────────────────────────


def generate_task_id() -> str:
    """Generate a unique task ID."""
    ts = int(time.time())
    pid = os.getpid()
    return f"FED-{ts}-{pid}"


# ── Task lifecycle ───────────────────────────────────────────────────


def create_task(
    task_desc: str,
    assigned_agent: str,
    workflow: str | None,
    lanes: list[str] | None,
    capabilities: list[str] | None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Create a task record and persist it."""
    tid = task_id or generate_task_id()
    record = {
        "schema": "federation-task/v1",
        "task_id": tid,
        "description": task_desc,
        "assigned_agent": assigned_agent,
        "workflow": workflow,
        "requested_lanes": lanes or [],
        "capabilities": capabilities or [],
        "status": "dispatched",
        "created_at": utc_now(),
        "dispatched_at": utc_now(),
        "completed_at": None,
        "duration_seconds": None,
        "result": None,
        "suggested_runtime": suggest_runtime(assigned_agent),
    }
    append_jsonl(TASKS_PATH, record)
    return record


def suggest_runtime(agent_name: str) -> str | None:
    """Suggest a runtime for an agent based on tier + availability."""
    quotas = load_quota_ledger()
    tier = get_agent_tier(agent_name, quotas)
    # Find available runtimes in the same tier
    available = []
    for runtime, entry in quotas.items():
        if entry.get("tier") == tier:
            avail, _ = is_agent_available(runtime, quotas)
            if avail:
                available.append(runtime)
    if not available:
        return None
    # Prefer multica-native over direct-cli
    native = [r for r in available if quotas[r].get("invocation_mode") == "multica-native"]
    return native[0] if native else available[0]


def dispatch_task(
    task_desc: str,
    agent_name: str,
    workflow: str | None,
    lanes: list[str] | None,
    capabilities: list[str] | None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Dispatch a task to an agent via A2A message queue."""
    record = create_task(task_desc, agent_name, workflow, lanes, capabilities)
    if dry_run:
        record["dry_run"] = True
        return record

    # Send A2A message
    msg = {
        "schema": "a2a-message/v1",
        "from": "federation-broker",
        "to": agent_name,
        "type": "task_dispatch",
        "payload": {
            "task_id": record["task_id"],
            "description": task_desc,
            "workflow": workflow,
            "lanes": lanes or [],
        },
        "ts": record["dispatched_at"],
    }
    append_jsonl(A2A_QUEUE_PATH, msg)
    return record


def get_tasks(status_filter: str | None = None) -> list[dict[str, Any]]:
    """Read all tasks, optionally filter by status."""
    if not TASKS_PATH.exists():
        return []
    tasks = read_jsonl(TASKS_PATH)
    if status_filter:
        tasks = [t for t in tasks if t.get("status") == status_filter]
    return tasks


def complete_task(task_id: str, result: str | None = None) -> dict | None:
    """Mark a task as complete. Updates the JSONL record."""
    tasks = get_tasks()
    for t in tasks:
        if t["task_id"] == task_id and t["status"] != "completed":
            t["status"] = "completed"
            t["completed_at"] = utc_now()
            t["result"] = result
            dispatched = t.get("dispatched_at", "")
            if dispatched:
                try:
                    dispatched_dt = datetime.fromisoformat(dispatched.replace("Z", "+00:00"))
                    t["duration_seconds"] = int(time.time() - dispatched_dt.timestamp())
                except (ValueError, OverflowError):
                    pass
            # Rewrite the task in the JSONL
            _rewrite_task(tasks, t)
            return t
    return None


def _rewrite_task(all_tasks: list[dict], updated: dict) -> None:
    """Rewrite a task in the JSONL file (atomic replace)."""
    lines = TASKS_PATH.read_text(encoding="utf-8").splitlines()
    new_lines = []
    for line in lines:
        try:
            obj = json.loads(line)
            if obj.get("task_id") == updated["task_id"]:
                new_lines.append(json.dumps(updated, ensure_ascii=False, sort_keys=True))
            else:
                new_lines.append(line)
        except json.JSONDecodeError:
            new_lines.append(line)
    TASKS_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


# ── Audit ────────────────────────────────────────────────────────────


def get_audit_stats() -> dict[str, Any]:
    """Generate audit statistics."""
    tasks = get_tasks()
    total = len(tasks)
    if total == 0:
        return {"total": 0, "dispatched": 0, "completed": 0, "failed": 0, "by_agent": {}, "by_workflow": {}}

    by_agent: dict[str, int] = {}
    by_workflow: dict[str, int] = {}
    by_status: dict[str, int] = {}
    durations: list[int] = []

    for t in tasks:
        agent = t.get("assigned_agent", "unknown")
        by_agent[agent] = by_agent.get(agent, 0) + 1
        wf = t.get("workflow", "none")
        by_workflow[wf] = by_workflow.get(wf, 0) + 1
        status = t.get("status", "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        if t.get("duration_seconds") is not None:
            durations.append(t["duration_seconds"])

    return {
        "total": total,
        "by_status": by_status,
        "by_agent": by_agent,
        "by_workflow": by_workflow,
        "avg_duration_seconds": round(sum(durations) / len(durations), 1) if durations else None,
        "dispatched_count": by_status.get("dispatched", 0),
        "completed_count": by_status.get("completed", 0),
        "completion_rate": round(by_status.get("completed", 0) / total * 100, 1) if total > 0 else 0,
    }


# ── CLI ──────────────────────────────────────────────────────────────


def cmd_discover(args: argparse.Namespace) -> int:
    """List all registered agents."""
    agents = list_agents(load_agent_profiles())
    if args.json:
        print(json.dumps(agents, ensure_ascii=False, indent=2))
    else:
        print(f"{'Agent':<30} {'Tier':<6} {'Workflows':<10} {'Lanes':<8} Purpose")
        print("-" * 100)
        quotas = load_quota_ledger()
        for a in agents:
            tier = get_agent_tier(a["name"], quotas)
            print(f"{a['name']:<30} {tier:<6} {a['workflow_count']:<10} {a['lane_count']:<8} {a['purpose'][:40]}")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    """Rank agents for a task."""
    ranked = rank_agents(args.workflow, args.lanes, args.capabilities)
    if args.json:
        print(json.dumps(ranked, ensure_ascii=False, indent=2))
    else:
        print(f"Task: {args.task}")
        if args.workflow:
            print(f"Workflow: {args.workflow}")
        if args.lanes:
            print(f"Lanes: {', '.join(args.lanes)}")
        print()
        print(f"{'Rank':<5} {'Agent':<30} {'Score':<8} {'Tier':<6} Reasons")
        print("-" * 100)
        for i, r in enumerate(ranked[:10], 1):
            reasons_str = "; ".join(r["reasons"][:3])
            print(f"{i:<5} {r['agent']:<30} {r['score']:<8} {r['tier']:<6} {reasons_str}")
    return 0


def cmd_dispatch(args: argparse.Namespace) -> int:
    """Dispatch a task to an agent."""
    if args.agent:
        agent = args.agent
        # Verify agent exists
        profiles = load_agent_profiles()
        if agent not in profiles:
            print(f"Error: agent '{agent}' not registered", file=sys.stderr)
            return 1
    else:
        # Auto-select best agent
        ranked = rank_agents(args.workflow, args.lanes, args.capabilities)
        if not ranked or ranked[0]["score"] == 0:
            print("Error: no suitable agent found", file=sys.stderr)
            return 1
        agent = ranked[0]["agent"]
        print(f"Auto-selected: {agent} (score={ranked[0]['score']})", file=sys.stderr)

    record = dispatch_task(
        task_desc=args.task,
        agent_name=agent,
        workflow=args.workflow,
        lanes=args.lanes,
        capabilities=args.capabilities,
        dry_run=args.dry_run,
    )
    if args.json:
        print(json.dumps(record, ensure_ascii=False, indent=2))
    else:
        print(f"Dispatched task {record['task_id']} to {agent}")
        if args.dry_run:
            print("(dry-run: A2A message not sent)")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show task status."""
    tasks = get_tasks(args.status)
    if args.json:
        print(json.dumps(tasks, ensure_ascii=False, indent=2))
    else:
        if not tasks:
            print("No tasks found.")
            return 0
        print(f"{'Task ID':<20} {'Status':<12} {'Agent':<25} {'Created':<20} {'Description'}")
        print("-" * 110)
        for t in tasks:
            desc = t.get("description", "")[:40]
            print(f"{t['task_id']:<20} {t['status']:<12} {t.get('assigned_agent','?'):<25} {t.get('created_at',''):<20} {desc}")
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    """Complete a task."""
    t = complete_task(args.task_id, args.result)
    if t:
        if args.json:
            print(json.dumps(t, ensure_ascii=False, indent=2))
        else:
            print(f"Completed {args.task_id} (duration: {t.get('duration_seconds', '?')}s)")
        return 0
    else:
        print(f"Error: task {args.task_id} not found or already completed", file=sys.stderr)
        return 1


def cmd_audit(args: argparse.Namespace) -> int:
    """Show audit statistics."""
    stats = get_audit_stats()
    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    else:
        print("Agent Federation Audit")
        print("=" * 50)
        print(f"Total tasks: {stats['total']}")
        print(f"  Dispatched:  {stats['dispatched_count']}")
        print(f"  Completed:   {stats['completed_count']}")
        print(f"  Completion:  {stats['completion_rate']}%")
        if stats.get("avg_duration_seconds") is not None:
            print(f"  Avg duration: {stats['avg_duration_seconds']}s")
        print()
        print("By agent:")
        for agent, count in sorted(stats["by_agent"].items(), key=lambda x: -x[1]):
            print(f"  {agent:<30} {count}")
        print()
        print("By workflow:")
        for wf, count in sorted(stats["by_workflow"].items(), key=lambda x: -x[1]):
            print(f"  {str(wf or '(none)'):<30} {count}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Agent Federation — cross-agent task broker + load-balancer",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # discover
    p = sub.add_parser("discover", help="List all registered agents")
    p.add_argument("--json", action="store_true", help="JSON output")

    # plan
    p = sub.add_parser("plan", help="Rank agents for a task")
    p.add_argument("--task", required=True, help="Task description")
    p.add_argument("--workflow", help="Required workflow ID")
    p.add_argument("--lanes", nargs="*", help="Required write lanes")
    p.add_argument("--capabilities", nargs="*", help="Required capabilities")
    p.add_argument("--json", action="store_true", help="JSON output")

    # dispatch
    p = sub.add_parser("dispatch", help="Dispatch a task to an agent")
    p.add_argument("--task", required=True, help="Task description")
    p.add_argument("--agent", help="Target agent (auto-select if omitted)")
    p.add_argument("--workflow", help="Required workflow ID")
    p.add_argument("--lanes", nargs="*", help="Required write lanes")
    p.add_argument("--capabilities", nargs="*", help="Required capabilities")
    p.add_argument("--dry-run", action="store_true", help="Print only, don't send A2A message")
    p.add_argument("--json", action="store_true", help="JSON output")

    # status
    p = sub.add_parser("status", help="Show task status")
    p.add_argument("--status", help="Filter by status")
    p.add_argument("--json", action="store_true", help="JSON output")

    # complete
    p = sub.add_parser("complete", help="Mark a task as complete")
    p.add_argument("--task-id", required=True, help="Task ID to complete")
    p.add_argument("--result", help="Completion result")
    p.add_argument("--json", action="store_true", help="JSON output")

    # audit
    p = sub.add_parser("audit", help="Show audit statistics")
    p.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    handlers = {
        "discover": cmd_discover,
        "plan": cmd_plan,
        "dispatch": cmd_dispatch,
        "status": cmd_status,
        "complete": cmd_complete,
        "audit": cmd_audit,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
