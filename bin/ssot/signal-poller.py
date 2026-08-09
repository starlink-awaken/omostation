#!/usr/bin/env python3
"""Signal Poller — 感知面信号检测器 (四面一脊 ①).

Reads signal-sources.yaml, polls each source for changes,
emits trigger events when new signals detected. Supports
local_filesystem transport (mtime/hash based change detection).

Output: one JSON line per detected signal trigger.
Usage: python3 bin/ssot/signal-poller.py [--watch] [--interval 300]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

from _shared import ROOT, load_yaml, utc_now

SIGNAL_SOURCES = ROOT / ".omo" / "_truth" / "registry" / "signal-sources.yaml"
STATE_FILE = ROOT / ".omo" / "state" / "signal-poller-state.json"


def _load_signal_sources() -> list[dict[str, Any]]:
    """Load registered signal sources."""
    data = load_yaml(SIGNAL_SOURCES)
    return data.get("sources", [])


def _load_state() -> dict[str, str]:
    """Load last-known signal hashes for dedup."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state: dict[str, str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _hash_path(path: str) -> str:
    """Compute a lightweight hash of a filesystem path.

    Uses mtime + child count (no recursion); directory mtime
    """
    import os

    p = os.path.expanduser(path)
    if not os.path.exists(p):
        return "unreachable"
    try:
        st = os.stat(p)
        dir_mtime = int(st.st_mtime)
        # Count direct children only — directory mtime changes on add/remove
        try:
            children = sum(1 for _ in os.scandir(p))
        except OSError:
            children = 0
        key = f"{dir_mtime}:{children}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]
    except OSError:
        return "error"


def poll_once(root: Path | None = None) -> list[dict[str, Any]]:
    """Poll all signal sources once. Returns list of trigger events."""
    sources = _load_signal_sources()
    state = _load_state()
    triggers: list[dict[str, Any]] = []
    new_state = dict(state)

    for source in sources:
        source_id = source.get("id", "?")
        transport = source.get("transport", "")
        bos_uri = source.get("bos_uri", "")

        if transport == "local_filesystem":
            path = source.get("path", "")
            current_hash = _hash_path(path)
            last_hash = state.get(source_id)

            if (
                current_hash != last_hash
                and current_hash not in ("unreachable", "error")
            ):
                trigger = {
                    "ts": utc_now(),
                    "source_id": source_id,
                    "bos_uri": bos_uri,
                    "transport": transport,
                    "signal": "content_changed",
                    "hash": current_hash,
                }
                triggers.append(trigger)

            new_state[source_id] = current_hash

    # Write state once after all sources processed
    # (was inside loop — N writes per poll)
    _save_state(new_state)

    return triggers


SIGNAL_TO_JOURNEY = {
    "apple_mail_inbox": "inbox-to-decision",
    "netease_mailmaster_inbox": "inbox-to-decision",
    "seeyon_oa_pending": "inbox-to-decision",
    "github_push": "meeting-to-delivery",
    "inbox_folder": "inbox-to-decision",
}


def _write_mos_snapshot(trigger: dict[str, Any], root: Path) -> dict[str, Any]:
    """T-B1: 信号 → MOS world_snapshot bridge.

    Reuse omo.omo_belief.MOSBeliefManager (MOS 三表真实实现, mesh-iris-executor 同款).
    信号变化写入系统认知, Advisor 可读取. 失败静默 (不阻塞 poll).
    """
    try:
        import sys

        omo_src = str(root / "projects/omo/src")
        if omo_src not in sys.path:
            sys.path.insert(0, omo_src)
        from omo.omo_belief import MOSBeliefManager

        manager = MOSBeliefManager(root=root)
        ws_id = manager.record_world_snapshot(
            source=f"signal-poller:{trigger.get('source_id', 'unknown')}",
            domain="perception",
            observations={
                "signal": trigger.get("signal", ""),
                "source_id": trigger.get("source_id", ""),
                "bos_uri": trigger.get("bos_uri", ""),
                "hash": trigger.get("hash", ""),
            },
            confidence=0.8,
        )
        return {"ok": True, "ws_id": ws_id}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _auto_trigger(triggers: list[dict[str, Any]], root: Path) -> list[str]:
    """Auto-start journeys for detected signals."""
    import subprocess

    triggered: list[str] = []
    for t in triggers:
        # MOS bridge: 信号 → 系统认知 (T-B1)
        mos_result = _write_mos_snapshot(t, root)
        if mos_result.get("ok"):
            triggered.append(f"MOS: {t.get('source_id')} → world_snapshot")
        else:
            triggered.append(
                f"MOS: {t.get('source_id')} "
                f"(skipped: {mos_result.get('error', '')[:40]})"
            )

        source_id = t.get("source_id", "")
        journey_id = SIGNAL_TO_JOURNEY.get(source_id)
        if not journey_id:
            continue
        try:
            subprocess.run(
                ["python3", str(root / "bin/ssot/journey-runner.py"),
                 "run", "--journey", journey_id, "--live"],
                timeout=120, capture_output=True, text=True, check=False,
            )
            triggered.append(f"{source_id} → {journey_id}")
        except Exception as exc:
            print(f"[signal-poller] {source_id}: {exc}", file=sys.stderr)
    return triggered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--watch", action="store_true", help="continuous polling mode"
    )
    parser.add_argument(
        "--interval", type=int, default=300,
        help="poll interval in seconds (watch mode)",
    )
    parser.add_argument(
        "--auto-trigger", action="store_true",
        help="auto-start journeys on signal detection",
    )
    args = parser.parse_args(argv)

    if args.watch:
        auto_info = (
            f"interval={args.interval}s, "
            f"auto-trigger={args.auto_trigger}"
        )
        print(f"Watching signal sources ({auto_info})...", flush=True)
        while True:
            triggers = poll_once()
            for t in triggers:
                print(
                    json.dumps(t, ensure_ascii=False), flush=True
                )
            if triggers and args.auto_trigger:
                fired = _auto_trigger(triggers, ROOT)
                for f in fired:
                    print(f"🚀 Auto-triggered: {f}", flush=True)
            time.sleep(args.interval)
    else:
        triggers = poll_once()
        if triggers:
            for t in triggers:
                print(json.dumps(t, ensure_ascii=False))
            if args.auto_trigger:
                fired = _auto_trigger(triggers, ROOT)
                for f in fired:
                    print(f"🚀 Auto-triggered: {f}")
        else:
            no_change_msg = {
                "status": "no_changes",
                "ts": utc_now(),
            }
            print(json.dumps(no_change_msg, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
