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
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SIGNAL_SOURCES = ROOT / ".omo" / "_truth" / "registry" / "signal-sources.yaml"
STATE_FILE = ROOT / ".omo" / "state" / "signal-poller-state.json"


def _load_signal_sources() -> list[dict[str, Any]]:
    """Load registered signal sources."""
    import yaml

    if not SIGNAL_SOURCES.exists():
        return []
    data = yaml.safe_load(SIGNAL_SOURCES.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return []
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
    """Compute a lightweight hash of a filesystem path (mtime + file count)."""
    import os

    p = os.path.expanduser(path)
    if not os.path.exists(p):
        return "unreachable"
    total_mtime = 0
    file_count = 0
    try:
        for root_dir, _dirs, files in os.walk(p):
            for f in files[:100]:  # sample first 100 files
                fp = os.path.join(root_dir, f)
                total_mtime += int(os.path.getmtime(fp))
                file_count += 1
    except OSError:
        return "error"
    return hashlib.sha256(f"{total_mtime}:{file_count}".encode()).hexdigest()[:16]


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

            if current_hash != last_hash and current_hash not in ("unreachable", "error"):
                trigger = {
                    "ts": datetime.now(UTC).isoformat(),
                    "source_id": source_id,
                    "bos_uri": bos_uri,
                    "transport": transport,
                    "signal": "content_changed",
                    "hash": current_hash,
                }
                triggers.append(trigger)

            new_state[source_id] = current_hash

        _save_state(new_state)

    return triggers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true", help="continuous polling mode")
    parser.add_argument("--interval", type=int, default=300, help="poll interval in seconds (watch mode)")
    args = parser.parse_args(argv)

    if args.watch:
        print(f"Watching signal sources (interval={args.interval}s)...", flush=True)
        while True:
            triggers = poll_once()
            for t in triggers:
                print(json.dumps(t, ensure_ascii=False), flush=True)
            time.sleep(args.interval)
    else:
        triggers = poll_once()
        if triggers:
            for t in triggers:
                print(json.dumps(t, ensure_ascii=False))
        else:
            print(json.dumps({"status": "no_changes", "ts": datetime.now(UTC).isoformat()}, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
