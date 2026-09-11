#!/usr/bin/env python3
"""Scene Signal Poller — v3 trigger-driven automatic scene execution.

Polls signal sources declared in v3 scene cards' `triggers` section,
deduplicates via watermark, and dispatches matching scenes through
journey-engine (dry-run for shadow, live for assisted+).

Pipeline:
  v3 scene cards (triggers.type=signal) → iris list <connector>
    → dedup (watermark per scene+connector) → journey-engine execute

Usage:
  python3 bin/ssot/scene-signal-poller.py poll [--limit N]
  python3 bin/ssot/scene-signal-poller.py status
  python3 bin/ssot/scene-signal-poller.py poll --scene-id <id>   # single scene
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = _ROOT / ".omo" / "_truth" / "scenarios" / "v3"
JOURNEY_ENGINE = _ROOT / "bin" / "ssot" / "journey-engine.py"
WATERMARK_PATH = _ROOT / ".omo" / "_delivery" / "signal-poller" / "watermarks.json"
POLL_LOG = _ROOT / ".omo" / "_delivery" / "signal-poller" / "poll-log.jsonl"

# Live execution allowed only at these lifecycle levels
LIVE_LIFECYCLES = {"assisted", "supervised", "routine"}


def _load_scene_cards() -> list[dict[str, Any]]:
    import yaml

    cards = []
    if SCENES_DIR.is_dir():
        for p in sorted(SCENES_DIR.glob("*.yaml")):
            try:
                with open(p, encoding="utf-8") as f:
                    docs = list(yaml.safe_load_all(f))
                body = docs[-1] if len(docs) > 1 else docs[0]
                if isinstance(body, dict):
                    cards.append(body)
            except Exception:
                continue
    return cards


def _load_watermarks() -> dict[str, Any]:
    try:
        return json.loads(WATERMARK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_watermarks(wm: dict[str, Any]) -> None:
    WATERMARK_PATH.parent.mkdir(parents=True, exist_ok=True)
    WATERMARK_PATH.write_text(json.dumps(wm, ensure_ascii=False, indent=2), encoding="utf-8")


def _iris_list(connector: str, limit: int = 10) -> list[dict[str, Any]]:
    """Call iris --json list <connector>."""
    try:
        result = subprocess.run(
            ["iris", "--json", "list", connector, "--limit", str(limit)],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        raw = result.stdout
        for ch in ("[", "{"):
            idx = raw.find(ch)
            if idx >= 0:
                raw = raw[idx:]
                break
        data = json.loads(raw)
        return data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    except Exception:
        return []


def _signal_id(item: dict[str, Any]) -> str:
    """Extract a stable dedup id from a signal item."""
    for key in ("id", "message_id", "uid", "url", "subject"):
        if item.get(key):
            return f"{item.get(key)}"
    return json.dumps(item, sort_keys=True)[:128]


def poll(dry_run: bool = False, scene_filter: str | None = None,
         limit_per_connector: int = 10) -> dict[str, Any]:
    """Poll all signal-type triggers from v3 scene cards."""
    cards = _load_scene_cards()
    watermarks = _load_watermarks()
    results = {
        "polled_at": datetime.now(UTC).isoformat(),
        "scenes_with_triggers": 0,
        "connectors_polled": 0,
        "new_signals": 0,
        "dispatched": 0,
        "dry_run": dry_run,
        "details": [],
    }

    seen_connectors: set[str] = set()
    connector_cache: dict[str, list[dict[str, Any]]] = {}

    for card in cards:
        scene_id = card.get("scene_id", "")
        lifecycle = card.get("lifecycle", "draft")
        activation = card.get("activation", "preview")

        if not scene_id:
            continue
        if scene_filter and scene_id != scene_filter:
            continue
        # Draft/preview scenes don't trigger
        if lifecycle not in LIVE_LIFECYCLES and activation == "preview":
            continue

        triggers = card.get("triggers", [])
        signal_triggers = [
            t for t in triggers
            if isinstance(t, dict) and t.get("type") == "signal"
        ]
        if not signal_triggers:
            continue
        results["scenes_with_triggers"] += 1

        for trig in signal_triggers:
            # Parse connector from signal field: "email.received" → iris connector
            signal_name = trig.get("signal", "")
            connector = _resolve_connector(signal_name, trig)
            if not connector:
                continue

            if connector not in connector_cache:
                connector_cache[connector] = _iris_list(connector, limit_per_connector)
                seen_connectors.add(connector)

            items = connector_cache[connector]
            wm_key = f"{scene_id}:{connector}"
            seen_ids = set(watermarks.get(wm_key, {}).get("seen_ids", []))

            new_items = []
            for item in items:
                sid = _signal_id(item)
                if sid not in seen_ids:
                    new_items.append((sid, item))

            for sid, item in new_items[:3]:  # cap per-poll dispatches
                results["new_signals"] += 1
                watermarks.setdefault(wm_key, {"seen_ids": []})["seen_ids"].append(sid)
                # Keep watermark bounded
                watermarks[wm_key]["seen_ids"] = watermarks[wm_key]["seen_ids"][-200:]
                watermarks[wm_key]["last_poll"] = results["polled_at"]

                use_dry_run = dry_run or lifecycle not in LIVE_LIFECYCLES
                signal_payload = {
                    "source": connector,
                    "content": item.get("subject", item.get("title", str(item)[:200])),
                    "raw_item": item,
                    "signal": signal_name,
                }

                detail = {
                    "scene_id": scene_id,
                    "connector": connector,
                    "signal_id": sid[:64],
                    "dry_run": use_dry_run,
                }

                if not use_dry_run:
                    try:
                        proc = subprocess.run(
                            [sys.executable, str(JOURNEY_ENGINE), "execute", scene_id,
                             "--signal", json.dumps(signal_payload, ensure_ascii=False)],
                            capture_output=True, text=True, cwd=str(_ROOT), timeout=300,
                        )
                        out = json.loads(proc.stdout.strip()) if proc.stdout.strip() else {}
                        detail["run_id"] = out.get("run_id")
                        detail["status"] = out.get("status", "error")
                        results["dispatched"] += 1
                    except Exception as e:
                        detail["status"] = "error"
                        detail["error"] = str(e)
                else:
                    detail["status"] = "dry_run_skipped"
                    results["dispatched"] += 1

                results["details"].append(detail)

                # Log to poll log
                POLL_LOG.parent.mkdir(parents=True, exist_ok=True)
                with open(POLL_LOG, "a", encoding="utf-8") as f:
                    f.write(json.dumps({**detail, "ts": results["polled_at"]}, ensure_ascii=False) + "\n")

    results["connectors_polled"] = len(seen_connectors)

    if not dry_run:
        _save_watermarks(watermarks)

    return results


def _resolve_connector(signal_name: str, trigger: dict[str, Any]) -> str | None:
    """Resolve iris connector name from a signal trigger."""
    # Explicit connector in trigger
    if trigger.get("connector"):
        return trigger["connector"]
    # Map signal types to iris connectors
    mapping = {
        "email.received": "apple_mail",
        "email": "apple_mail",
        "mail": "apple_mail",
    }
    for key, conn in mapping.items():
        if key in signal_name.lower():
            return conn
    # Direct iris:<connector> format
    if signal_name.startswith("iris:"):
        return signal_name.split(":", 1)[1]
    return None


def status() -> dict[str, Any]:
    """Show poller status."""
    wm = _load_watermarks()
    cards = _load_scene_cards()
    with_triggers = []
    for card in cards:
        triggers = card.get("triggers", [])
        signal_triggers = [t for t in triggers if isinstance(t, dict) and t.get("type") == "signal"]
        if signal_triggers:
            with_triggers.append({
                "scene_id": card.get("scene_id"),
                "lifecycle": card.get("lifecycle"),
                "activation": card.get("activation"),
                "triggers": [
                    {"signal": t.get("signal"), "connector": _resolve_connector(t.get("signal", ""), t)}
                    for t in signal_triggers
                ],
            })

    return {
        "watermark_entries": len(wm),
        "scenes_with_signal_triggers": len(with_triggers),
        "scenes": with_triggers[:20],
        "watermarks": {k: {"seen": len(v.get("seen_ids", [])), "last": v.get("last_poll")} for k, v in list(wm.items())[:20]},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")

    poll_p = sub.add_parser("poll", help="Poll signal sources and dispatch scenes")
    poll_p.add_argument("--dry-run", action="store_true", help="Don't save watermarks or execute live")
    poll_p.add_argument("--scene-id", help="Poll single scene")
    poll_p.add_argument("--limit", type=int, default=10, help="Items per connector")

    sub.add_parser("status", help="Show poller status")

    args = parser.parse_args(argv)
    command = args.command or "status"

    if command == "poll":
        result = poll(
            dry_run=getattr(args, "dry_run", False),
            scene_filter=args.scene_id,
            limit_per_connector=args.limit,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if command == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
