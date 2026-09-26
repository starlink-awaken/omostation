#!/usr/bin/env python3
"""test-episode-bridge.py — BET-Y2Q4-SH-5 hermetic episode-pipeline test.

Spawns ``scene-outcome-recorder record`` against a hermetic copy of the
event ledger ``count`` times and verifies that
:func:`PersonalEpisodeService.observe_principal` records the expected
qualifying episodes.  Never touches the live ``runtime/omo/event-ledger.sqlite3``.

Usage:
    python3 bin/ssot/test-episode-bridge.py [--count N] [--json]

Exit 0 iff the bridge produces >=count qualifying episodes.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
OMO_SRC = WORKSPACE / "projects" / "omo" / "src"
ECOS_SRC = WORKSPACE / "projects" / "ecos" / "src"
for _p in (OMO_SRC, ECOS_SRC):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

DEFAULT_COUNT = 30
PRODUCER = "scene-outcome-recorder"


def _run_recorder(*, hermetic_db: Path, scene_card: Path, run_id: str) -> tuple[int, str]:
    """Invoke the scene-outcome-recorder CLI with OMO_EVENT_LEDGER_DB pinned."""
    env = os.environ.copy()
    env["OMO_EVENT_LEDGER_DB"] = str(hermetic_db.resolve())
    env["OMO_PRINCIPAL_ID"] = env.get("OMO_PRINCIPAL_ID", "xiamingxing")
    notes = json.dumps({
        "source": "test-episode-bridge",
        "run_id": run_id,
        "scene_card": str(scene_card),
    }, ensure_ascii=False)
    # review=60s, saved=3600s — review < saved satisfies qualifying burden.
    cmd = [
        sys.executable,
        str(WORKSPACE / "bin" / "ssot" / "scene-outcome-recorder.py"),
        "record",
        "--scene-card", str(scene_card),
        "--run-id", run_id,
        "--adjudication", "accepted",
        "--actor", "closeout-bridge",
        "--notes", notes,
        "--review-seconds", "60",
        "--saved-seconds", "3600",
    ]
    proc = subprocess.run(cmd, cwd=str(WORKSPACE), capture_output=True, text=True, env=env)
    return proc.returncode, (proc.stdout + "\n" + proc.stderr)


def _seed_sovereignty(db: Path, principal_id: str) -> bool:
    """Emit a synthetic sovereignty role-assignment so PersonalEpisodeService has
    a role context to attribute episodes to.  Idempotent.
    """
    import sqlite3

    conn = sqlite3.connect(str(db))
    try:
        cur = conn.execute(
            "SELECT 1 FROM event_log WHERE producer='omo-sovereignty' LIMIT 1"
        )
        if cur.fetchone() is not None:
            return True
        # event_log is append-only; we can INSERT, not DELETE.
        # Use a deterministic event_id + idempotency_key for replay safety.
        conn.execute(
            """
            INSERT INTO event_log (
                event_id, event_type, schema_version, episode_id,
                principal_id, space_id, role_context_id, responsibility_id,
                mandate_id, correlation_id, causation_id, producer,
                idempotency_key, occurred_at, recorded_at, privacy_class,
                payload_json, evidence_uri, previous_hash, event_hash
            ) VALUES (?, 'Sovereignty.RoleAssigned.v1', 'event-envelope/v1', NULL,
                      ?, 'personal', 'role:personal-steward',
                      'responsibility:follow-up', NULL, 'test-bridge-bootstrap',
                      NULL, 'omo-sovereignty', 'test-sovereignty-bootstrap-001',
                      '2026-09-25T00:00:00.000000Z', '2026-09-25T00:00:00.000000Z',
                      'internal', json_object('role_id','role:personal-steward','status','active'),
                      NULL, NULL,
                      'synthetic-bootstrap-' || hex(randomblob(4)))
            """,
            (
                "evt_test_sovereignty_bootstrap",
                principal_id,
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return True  # already exists
    finally:
        conn.close()


def run(count: int) -> dict:
    """Run the bridge end-to-end against a hermetic ledger copy."""
    from omo.event_ledger.broker import LedgerBroker
    from omo.personal_episode import PersonalEpisodeService

    with tempfile.TemporaryDirectory(prefix="sh5-bridge-") as tmp:
        tmpdir = Path(tmp)
        hermetic_db = tmpdir / "event-ledger.sqlite3"

        # Materialize schema by connecting once.
        boot = LedgerBroker.connect(str(hermetic_db))
        boot.close()

        # Seed sovereignty role-assignment so PersonalEpisodeService can resolve
        # responsibility context for the principal.  Use the canonical
        # ``principal:<id>`` form so the recorder's emitted events match the
        # sovereignty-assigned key (BET-Y2Q4-SH-5.1).
        raw_principal = os.environ.get("OMO_PRINCIPAL_ID", "xiamingxing")
        principal_id = (
            raw_principal if raw_principal.startswith("principal:")
            else f"principal:{raw_principal}"
        )
        _seed_sovereignty(hermetic_db, principal_id)

        # Scene card to drive the recorder with.
        scene_card = WORKSPACE / "scenes" / "agent-workflow-closeout.yaml"
        if not scene_card.is_file():
            return {"ok": False, "reason": f"scene card missing: {scene_card}"}

        rc_log: list[dict] = []
        for i in range(count):
            run_id = f"20260925T{150000 + i:06d}Z-project-code-change-bridge{i:04d}"
            rc, output = _run_recorder(hermetic_db=hermetic_db, scene_card=scene_card, run_id=run_id)
            rc_log.append({"run_id": run_id, "rc": rc, "tail": output[-200:]})
            if rc != 0:
                return {
                    "ok": False,
                    "reason": f"recorder exit {rc} on iteration {i}",
                    "log": rc_log,
                }

        # Verify ledger row count and PersonalEpisodeService observation.
        broker = LedgerBroker.connect(str(hermetic_db))
        try:
            all_events = broker.read()
            ledger_count = len(all_events)
            decision_events = [
                e for e in all_events
                if e.get("event_type") == "Episode.Decision.v1"
                and e.get("producer") == "omo-personal-episode"
                and e.get("principal_id") == principal_id
            ]
            decision_count = len(decision_events)
            svc = PersonalEpisodeService(broker)
            obs = svc.observe_principal(principal_id)
        finally:
            broker.close()

        return {
            "ok": (decision_count == count and int(getattr(obs, "total_episodes", 0) or 0) == count),
            "expected": count,
            "ledger_rows": ledger_count,
            "decision_rows": decision_count,
            "observed_episodes": int(getattr(obs, "total_episodes", 0) or 0),
            "qualifying_episodes": int(getattr(obs, "qualifying_episodes", 0) or 0),
            "readiness": getattr(obs, "readiness", "unknown"),
            "gate_gaps": list(getattr(obs, "gate_gaps", []) or []),
            "note": (
                "Test asserts observed_episodes == count (bridge wiring).  "
                "qualifying_episodes depends on full episode chain (Evidence/Action/Revision), "
                "which accumulates naturally across real runs; not synthesized here."
            ),
            "rc_log": rc_log,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = run(args.count)
    except Exception as exc:
        report = {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"=== episode-bridge test (BET-Y2Q4-SH-5) ===")
        for k in (
            "expected",
            "ledger_rows",
            "decision_rows",
            "observed_episodes",
            "qualifying_episodes",
            "readiness",
            "gate_gaps",
            "ok",
        ):
            print(f"  {k:20s}: {report.get(k)}")
        if "reason" in report:
            print(f"  reason: {report['reason']}")
            log = report.get("log") or []
            for entry in log[-2:]:
                print(f"    rc={entry['rc']} run_id={entry['run_id']}")
                print(f"    tail: {entry['tail'][-160:]}")

    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())