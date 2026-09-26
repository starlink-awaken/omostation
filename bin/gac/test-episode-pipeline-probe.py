#!/usr/bin/env python3
"""test-episode-pipeline-probe.py — BET-Y2Q4-SH-5.2 probe-rebind regression guard.

Hermetic (temp sqlite + temp workspace; never reads or writes the live ledger):

  A. episodes present, zero bridge-sourced rows  -> check() must report ok=False
  B. bridge-sourced rows present                 -> check() must report ok=True
  C. scene map that cannot be parsed             -> the closeout bridge must emit a
     WARN naming the reason

Case A is the whole point.  Before SH-5.2 the probe asserted on
``producer == 'omo-personal-episode'``, a label scene-outcome-recorder stamps on
every row on purpose, so a completely dead bridge kept the probe green.  Any
future re-binding back to a producer-only predicate turns A red.

Usage:
    uv run --with pyyaml python bin/gac/test-episode-pipeline-probe.py [--json]

Exit 0 iff all cases pass.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import sqlite3
import sys
import tempfile
import types
from pathlib import Path
from unittest import mock

WORKSPACE = Path(__file__).resolve().parents[2]

# Subset of the live event_log DDL covering every column the probe reads.
EVENT_LOG_DDL = """
CREATE TABLE event_log (
  sequence        INTEGER PRIMARY KEY AUTOINCREMENT,
  event_type      TEXT NOT NULL,
  principal_id    TEXT NOT NULL,
  correlation_id  TEXT NOT NULL,
  producer        TEXT NOT NULL,
  recorded_at     TEXT NOT NULL,
  payload_json    TEXT NOT NULL CHECK(json_valid(payload_json))
)
"""


def _load(name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(name, WORKSPACE / rel_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed(db_path: Path, rows: list[tuple[str, str, str]]) -> None:
    """rows = (producer, payload_json, correlation_id)."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(EVENT_LOG_DDL)
        conn.executemany(
            "INSERT INTO event_log (event_type, principal_id, correlation_id,"
            " producer, recorded_at, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("Episode.Decision.v1", "principal:x", cid, producer,
                 "2026-09-26T00:00:00Z", payload)
                for producer, payload, cid in rows
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _episode_rows(count: int, *, bridge: bool) -> list[tuple[str, str, str]]:
    source = "scene-outcome-bridge" if bridge else "journey-auto-complete"
    return [
        (
            "omo-personal-episode",
            json.dumps({"verdict": "accept", "source": source}),
            f"run-{i:04d}",
        )
        for i in range(count)
    ]


def case_a_and_b() -> dict:
    probe = _load("probe_ab", "bin/gac/check-episode-pipeline.py")
    with tempfile.TemporaryDirectory() as tmp:
        dead = Path(tmp) / "dead-bridge.sqlite3"
        _seed(dead, _episode_rows(6, bridge=False))
        dead_report = probe.check(dead)

        live = Path(tmp) / "live-bridge.sqlite3"
        _seed(live, _episode_rows(4, bridge=True) + _episode_rows(2, bridge=False))
        live_report = probe.check(live)

    # The producer the old predicate keyed on is present in BOTH databases;
    # only the bridge discriminator separates them.
    producer_key = f"{probe.PRODUCER}_count"
    return {
        "ok": (
            dead_report.get("ok") is False
            and dead_report.get(producer_key, 0) > 0
            and live_report.get("ok") is True
            and live_report.get("bridge_event_count") == 4
            and live_report.get("bridge_closeout_count") == 4
        ),
        "dead_bridge": {
            "ok": dead_report.get("ok"),
            producer_key: dead_report.get(producer_key),
            "bridge_event_count": dead_report.get("bridge_event_count"),
        },
        "live_bridge": {
            "ok": live_report.get("ok"),
            producer_key: live_report.get(producer_key),
            "bridge_event_count": live_report.get("bridge_event_count"),
            "bridge_closeout_count": live_report.get("bridge_closeout_count"),
        },
    }


def _stub_workflow_module() -> contextlib.AbstractContextManager:
    """Make the bridge's run lookup resolve to a fake run record.

    ``omo.workflow.lifecycle`` and ``omo.workflow.load_registry`` are attributes
    on the package, so patching the attributes is what the
    ``from omo.workflow import X`` inside the bridge actually sees.
    """
    lifecycle = types.ModuleType("omo.workflow.lifecycle")
    lifecycle.read_run = lambda registry, run_id: (
        Path(f"/nowhere/{run_id}"),
        {"workflow_id": "wf-under-test"},
    )

    @contextlib.contextmanager
    def apply():
        import omo.workflow as pkg

        with mock.patch.dict(sys.modules, {"omo.workflow.lifecycle": lifecycle}), \
                mock.patch.object(pkg, "lifecycle", lifecycle, create=True), \
                mock.patch.object(pkg, "load_registry", lambda: object(), create=True):
            yield

    return apply()


def case_c() -> dict:
    for rel in ("bin", str(WORKSPACE)):
        if rel not in sys.path:
            sys.path.insert(0, rel)
    bridge = _load("aw_case_c", "bin/agent-workflow.py")

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        scene_map = ws / "bin" / "ssot" / "workflow-scene-map.yaml"
        scene_map.parent.mkdir(parents=True)
        # Two YAML documents in one file: yaml.safe_load raises ComposerError.
        scene_map.write_text("map:\n  a: one\n---\nmap:\n  b: two\n", encoding="utf-8")

        buf = io.StringIO()
        with _stub_workflow_module(), mock.patch.object(bridge, "WORKSPACE", ws), \
                contextlib.redirect_stderr(buf):
            bridge._bridge_closeout_to_scene("20260101T000000Z-case-c-00000000")
        emitted = buf.getvalue()

    return {
        "ok": ("SH-5 bridge emitted no episode" in emitted and "unparseable" in emitted),
        "stderr": emitted.strip()[:300],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    results = {"A_B_probe_predicate": case_a_and_b(), "C_bridge_silence": case_c()}
    all_ok = all(r["ok"] for r in results.values())
    if args.json:
        print(json.dumps({"ok": all_ok, "cases": results}, indent=2, ensure_ascii=False))
    else:
        for name, res in results.items():
            print(f"  [{'PASS' if res['ok'] else 'FAIL'}] {name}")
            for key, val in res.items():
                if key != "ok":
                    print(f"      {key}: {val}")
        print(f"=== episode-pipeline-probe: {'PASS' if all_ok else 'FAIL'} ===")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
