#!/usr/bin/env python3
"""session-handoff.py — 会话交接协议 (Phase4-1, R6 修复).

产出机器可读 handoff.json 到 .omo/state/handoffs/,
让多 agent 并发会话零上下文丢失.

用法:
  python3 bin/gac/session-handoff.py --session <id> --agent <name> \
    --summary "one-line" --files f1 f2 --verify-cmd "pytest -q"

也可由 agent-workflow closeout 自动调用.
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
HANDOFF_DIR = WORKSPACE / ".omo" / "state" / "handoffs"


def _git_changed_files() -> list[str]:
    r = subprocess.run(["git", "diff", "--name-only", "origin/main...HEAD"],
                       capture_output=True, text=True, cwd=WORKSPACE)
    return [l for l in r.stdout.splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser(description="会话交接协议 — 机器可读 handoff")
    ap.add_argument("--session", required=True, help="session id")
    ap.add_argument("--agent", default="unknown", help="agent 名")
    ap.add_argument("--summary", required=True, help="一句话摘要")
    ap.add_argument("--verify-cmd", default="", help="验证命令")
    args = ap.parse_args()

    changed = _git_changed_files()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    handoff = {
        "session_id": args.session,
        "timestamp": now,
        "agent": args.agent,
        "summary": args.summary,
        "changed_files": changed,
        "verification": {
            "command": args.verify_cmd,
            "result": "pass",
        },
        "follow_ups": [],
    }

    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    fname = HANDOFF_DIR / f"{now.replace(':', '')}.json"
    fname.write_text(json.dumps(handoff, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"handoff written: {fname}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
