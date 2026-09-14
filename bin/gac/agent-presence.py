#!/usr/bin/env python3
"""Agent Presence Registry — 跨 worktree 多 agent 在场注册与碰撞检测 (BET-Y1Q3-T10-09 后续).

Storage: runtime/agents/{agent_id}.json  (主仓级, 不受 worktree 切换影响)
TTL:     5 分钟无 heartbeat → 过期(读取方顺手删除)
Usage:
  agent-presence.py register --agent <id> [--branch <b>] [--files <glob,glob>]
  agent-presence.py heartbeat --agent <id>
  agent-presence.py deregister --agent <id>
  agent-presence.py list [--json]
  agent-presence.py check --files <glob,glob> [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

WORKSPACE = Path(os.environ.get("OMO_WORKSPACE_ROOT", Path(__file__).resolve().parents[2]))
AGENTS_DIR = WORKSPACE / "runtime" / "agents"
COORD_DIR = WORKSPACE / "runtime" / "coordination"
HEARTBEAT_TTL = 300  # seconds
HANDOFF_DIR = COORD_DIR / "handoffs"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_dirs():
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)


def _load(agent_id: str) -> dict | None:
    p = AGENTS_DIR / f"{agent_id}.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _save(agent_id: str, data: dict):
    _ensure_dirs()
    data["heartbeat_at"] = _now()
    (AGENTS_DIR / f"{agent_id}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def _is_stale(data: dict) -> bool:
    hb = data.get("heartbeat_at", "")
    try:
        ts = datetime.fromisoformat(hb)
        return (datetime.now(UTC) - ts).total_seconds() > HEARTBEAT_TTL
    except Exception:
        return True


def cmd_register(args):
    locked = [f.strip() for f in (args.files or "").split(",") if f.strip()]
    data = {
        "agent_id": args.agent,
        "worktree": str(WORKSPACE),
        "branch": args.branch or "",
        "locked_files": locked,
        "started_at": _now(),
    }
    existing = _load(args.agent)
    if existing:
        data["started_at"] = existing["started_at"]
    _save(args.agent, data)
    print(f"registered: {args.agent} branch={args.branch or '?'} files={locked or '[]'}")


def cmd_heartbeat(args):
    d = _load(args.agent)
    if not d:
        print(f"error: {args.agent} not registered", file=sys.stderr)
        return 1
    d["heartbeat_at"] = _now()
    (AGENTS_DIR / f"{args.agent}.json").write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
    return 0


def cmd_deregister(args):
    p = AGENTS_DIR / f"{args.agent}.json"
    if p.exists():
        p.unlink()
        print(f"deregistered: {args.agent}")
    else:
        print(f"not found: {args.agent}", file=sys.stderr)
        return 1


def cmd_list(args):
    _ensure_dirs()
    active, stale = [], []
    for p in sorted(AGENTS_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        if _is_stale(d):
            stale.append((p.stem, d))
            p.unlink()
        else:
            active.append((p.stem, d))
    if args.json:
        print(json.dumps({"active": [d for _, d in active], "stale_removed": len(stale)}, ensure_ascii=False, indent=2))
        return 0
    print(f"active agents: {len(active)}")
    for aid, d in active:
        age = "fresh"
        print(f"  {aid}  branch={d.get('branch','?')}  files={d.get('locked_files',[])}")
    if stale:
        print(f"cleaned {len(stale)} stale entries")
    return 0


def cmd_check(args):
    """Check if given file patterns collide with other agents' locks."""
    my_files = set()
    for pat in (args.files or "").split(","):
        pat = pat.strip()
        if not pat:
            continue
        my_files.add(pat)
    _ensure_dirs()
    collisions = []
    for p in sorted(AGENTS_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        other_id = p.stem
        if other_id == getattr(args, "agent", ""):
            continue
        if _is_stale(d):
            continue
        their = set(d.get("locked_files", []))
        import fnmatch
        overlap = set()
        for mf in my_files:
            for tf in their:
                if fnmatch.fnmatch(mf, tf) or fnmatch.fnmatch(tf, mf):
                    overlap.add(mf)
                    break
        if overlap:
            collisions.append({"agent": other_id, "branch": d.get("branch"), "overlap": sorted(overlap)})
    if args.json:
        print(json.dumps({"collisions": collisions}, ensure_ascii=False, indent=2))
        return 1 if collisions else 0
    if collisions:
        print(f"⚠️  COLLISIONS detected ({len(collisions)}):")
        for c in collisions:
            print(f"  agent={c['agent']} branch={c['branch']} files={c['overlap']}")
        return 1
    print("no collisions")
    return 0


def cmd_handoff(args):
    """Write a structured handoff record."""
    _ensure_dirs()
    run_id = args.run_id
    data = {
        "run_id": run_id,
        "agent_id": args.agent,
        "completed": [s for s in (args.completed or "").split(",") if s.strip()],
        "discovered": [s for s in (args.discovered or "").split(",") if s.strip()],
        "blockers": [s for s in (args.blockers or "").split(",") if s.strip()],
        "next_steps": [s for s in (args.next or "").split(",") if s.strip()],
        "written_at": _now(),
    }
    out = HANDOFF_DIR / f"{run_id}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"handoff written: {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd")
    reg = sub.add_parser("register")
    reg.add_argument("--agent", required=True)
    reg.add_argument("--branch", default="")
    reg.add_argument("--files", default="", help="comma-separated glob patterns")
    hb = sub.add_parser("heartbeat")
    hb.add_argument("--agent", required=True)
    der = sub.add_parser("deregister")
    der.add_argument("--agent", required=True)
    lst = sub.add_parser("list")
    lst.add_argument("--json", action="store_true")
    chk = sub.add_parser("check")
    chk.add_argument("--files", required=True)
    chk.add_argument("--agent", default="")
    chk.add_argument("--json", action="store_true")
    hof = sub.add_parser("handoff")
    hof.add_argument("--run-id", required=True)
    hof.add_argument("--agent", default="")
    hof.add_argument("--completed", default="")
    hof.add_argument("--discovered", default="")
    hof.add_argument("--blockers", default="")
    hof.add_argument("--next", default="")
    args = ap.parse_args()
    handlers = {"register": cmd_register, "heartbeat": cmd_heartbeat, "deregister": cmd_deregister,
                "list": cmd_list, "check": cmd_check, "handoff": cmd_handoff}
    fn = handlers.get(args.cmd)
    if fn:
        raise SystemExit(fn(args) or 0)
    ap.print_help()


if __name__ == "__main__":
    main()
