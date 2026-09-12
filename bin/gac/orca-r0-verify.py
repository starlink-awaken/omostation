#!/usr/bin/env python3
"""Orca R0 read-only admission verifier (BET-Y1Q4-T10-149)."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ALLOWED_ORCA_VERBS = frozenset({
    "status",
    "host",
    "environment",
    "orchestration",
    "run-list",
    "worker-list",
    "worker-show",
    "list",
})
FORBIDDEN_ORCA_VERBS = frozenset({
    "run-create",
    "run-use",
    "worker-start",
    "worker-stop",
    "worker-abandon",
    "worker-release",
    "worker-retain",
    "dispatch",
    "task-create",
    "task-update",
    "gate-create",
    "gate-resolve",
    "send",
    "reply",
    "ask",
    "reset",
    "open",
    "serve",
})
DONE_WORKER = {"succeeded", "stopped", "failed", "cancelled", "abandoned"}
OK_TERMINAL = {"released", "reclaimable"}
LIVE_TERMINAL = {"active", "retained", "release_pending", "release_unknown"}
TIMEOUT_S = 30


def _run(argv: list[str]) -> dict[str, Any]:
    started = time.time()
    try:
        proc = subprocess.run(
            ["orca", *argv],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            check=False,
        )
        return {
            "argv": argv,
            "rc": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "elapsed_ms": int((time.time() - started) * 1000),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "argv": argv,
            "rc": 124,
            "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
            "stderr": f"timeout after {TIMEOUT_S}s",
            "elapsed_ms": int((time.time() - started) * 1000),
        }


def _parse(result: dict[str, Any]) -> tuple[bool, Any | None]:
    raw = (result["stdout"] or "").strip()
    if not raw:
        return False, None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return False, None
    # orca envelopes often use ok:true even for local soft errors
    if isinstance(payload, dict) and payload.get("ok") is False:
        return False, payload
    return True, payload


def _guard_source(executed_argv: list[list[str]]) -> dict[str, Any]:
    offenders: set[str] = set()
    for argv in executed_argv:
        for tok in argv:
            if tok.startswith("--"):
                continue
            if tok in FORBIDDEN_ORCA_VERBS:
                offenders.add(tok)
    return {"id": "write_argv_guard", "ok": not offenders, "offenders": sorted(offenders)}


def _workers(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    result = payload.get("result") if isinstance(payload.get("result"), dict) else payload
    rows = result.get("workers") if isinstance(result, dict) else None
    if not isinstance(rows, list):
        return []
    return [w for w in rows if isinstance(w, dict)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args(argv)

    READ_PROBES: list[tuple[str, list[str]]] = [
        ("status", ["status", "--json"]),
        ("run_list", ["orchestration", "run-list", "--json"]),
        ("worker_list", ["orchestration", "worker-list", "--json", "--limit", str(args.limit)]),
        ("host_list", ["host", "list", "--json"]),
        ("environment_list", ["environment", "list", "--json"]),
    ]

    probes: list[dict[str, Any]] = []
    payloads: dict[str, Any] = {}
    for probe_id, probe_argv in READ_PROBES:
        result = _run(probe_argv)
        ok, payload = _parse(result)
        if ok and payload is not None:
            payloads[probe_id] = payload
        probes.append(
            {
                "id": probe_id,
                "argv": probe_argv,
                "ok": ok,
                "status": "PASS" if ok else "FAIL",
                "rc": result["rc"],
                "elapsed_ms": result["elapsed_ms"],
                "detail": (result["stderr"] or result["stdout"])[:240],
            }
        )

    workers = _workers(payloads.get("worker_list"))
    reconciled = [
        w
        for w in workers
        if w.get("workerState") in DONE_WORKER and w.get("terminalState") in OK_TERMINAL
    ]
    mismatch = [
        w
        for w in workers
        if w.get("workerState") in DONE_WORKER and w.get("terminalState") in LIVE_TERMINAL
    ]
    unsupervised = [w for w in workers if w.get("workerState") == "unsupervised"]

    settlement = {
        "total": len(workers),
        "reconciled": len(reconciled),
        "mismatch": len(mismatch),
        "unsupervised": len(unsupervised),
        "by_worker_state": {},
        "by_terminal_state": {},
    }
    for w in workers:
        ws = str(w.get("workerState") or "unknown")
        ts = str(w.get("terminalState") or "unknown")
        settlement["by_worker_state"][ws] = settlement["by_worker_state"].get(ws, 0) + 1
        settlement["by_terminal_state"][ts] = settlement["by_terminal_state"].get(ts, 0) + 1

    # Prefer a clean accepted triple: succeeded + completed + released/reclaimable
    sample = next(
        (
            w
            for w in workers
            if w.get("workerState") == "succeeded"
            and w.get("dispatchStatus") == "completed"
            and w.get("terminalState") in OK_TERMINAL
            and isinstance(w.get("dispatchId"), str)
        ),
        None,
    )
    if sample is None:
        sample = next((w for w in reconciled if isinstance(w.get("dispatchId"), str)), None)

    tx: dict[str, Any] = {
        "accepted": 0,
        "sample_dispatch_id": None,
        "transactions": [],
    }
    if sample and isinstance(sample.get("dispatchId"), str):
        dispatch_id = sample["dispatchId"]
        tx["sample_dispatch_id"] = dispatch_id
        show = _run(["orchestration", "worker-show", "--dispatch", dispatch_id, "--json"])
        show_ok, show_payload = _parse(show)
        probes.append(
            {
                "id": "worker_show",
                "argv": ["orchestration", "worker-show", "--dispatch", dispatch_id, "--json"],
                "ok": show_ok,
                "status": "PASS" if show_ok else "FAIL",
                "rc": show["rc"],
                "elapsed_ms": show["elapsed_ms"],
                "detail": (show["stderr"] or show["stdout"])[:240],
            }
        )
        result = (show_payload or {}).get("result") if isinstance(show_payload, dict) else {}
        if not isinstance(result, dict):
            result = {}
        dispatch = result.get("dispatch") if isinstance(result.get("dispatch"), dict) else {}
        worker = result.get("worker") if isinstance(result.get("worker"), dict) else {}
        terminal_state = sample.get("terminalState")
        if isinstance(result.get("terminal"), dict) and result["terminal"].get("state"):
            terminal_state = result["terminal"].get("state")

        tx1 = {
            "id": "dispatch_identity",
            "ok": bool(dispatch.get("id") and (dispatch.get("runId") or sample.get("runId")) and (dispatch.get("taskId") or dispatch.get("task_id") or sample.get("taskId"))),
            "detail": {
                "dispatchId": dispatch.get("id") or sample.get("dispatchId"),
                "runId": dispatch.get("runId") or sample.get("runId"),
                "taskId": dispatch.get("taskId") or dispatch.get("task_id") or sample.get("taskId"),
                "dispatchStatus": dispatch.get("status") or sample.get("dispatchStatus"),
            },
        }
        worker_state = worker.get("state") or sample.get("workerState")
        stage = worker.get("stage")
        tx2 = {
            "id": "worker_done_accepted",
            "ok": worker_state == "succeeded" and (stage == "settled" or (dispatch.get("status") == "completed") or sample.get("dispatchStatus") == "completed"),
            "detail": {"workerState": worker_state, "stage": stage},
        }
        tx3 = {
            "id": "resource_reclaimed",
            "ok": terminal_state in OK_TERMINAL,
            "detail": {"terminalState": terminal_state},
        }
        for row in (tx1, tx2, tx3):
            row["status"] = "PASS" if row["ok"] else "FAIL"
        tx["transactions"] = [tx1, tx2, tx3]
        tx["accepted"] = 1 if all(t["ok"] for t in tx["transactions"]) else 0
    else:
        probes.append(
            {
                "id": "worker_show",
                "argv": ["orchestration", "worker-show", "--dispatch", "<none>"],
                "ok": False,
                "status": "FAIL",
                "rc": 2,
                "elapsed_ms": 0,
                "detail": "no settled sample with dispatchId",
            }
        )
        tx["transactions"] = [
            {"id": "dispatch_identity", "ok": False, "status": "FAIL", "detail": "no sample"},
            {"id": "worker_done_accepted", "ok": False, "status": "FAIL", "detail": "no sample"},
            {"id": "resource_reclaimed", "ok": False, "status": "FAIL", "detail": "no sample"},
        ]

    status_payload = payloads.get("status")
    runtime_ready = False
    if isinstance(status_payload, dict):
        result = status_payload.get("result") if isinstance(status_payload.get("result"), dict) else {}
        runtime = result.get("runtime") if isinstance(result.get("runtime"), dict) else {}
        app = result.get("app") if isinstance(result.get("app"), dict) else {}
        runtime_ready = bool(runtime.get("reachable") and runtime.get("state") == "ready" and app.get("running"))

    guard = _guard_source([p["argv"] for p in probes if isinstance(p.get("argv"), list)])
    probe_ok = all(p["ok"] for p in probes if p["id"] != "worker_show") and any(
        p["id"] == "worker_show" and p["ok"] for p in probes
    )
    report = {
        "schema": "orca-r0-verify/v1",
        "ok": bool(runtime_ready and probe_ok and tx["accepted"] == 1 and guard["ok"]),
        "runtime_ready": runtime_ready,
        "probes": {"passed": sum(1 for p in probes if p["ok"]), "total": len(probes), "results": probes},
        "settlement": settlement,
        "r0_transactions": tx,
        "trust": {"write_argv_guard": guard},
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            f"orca-r0-verify: ok={report['ok']} runtime_ready={runtime_ready} "
            f"accepted_triples={tx['accepted']} reconciled={settlement['reconciled']} "
            f"mismatch={settlement['mismatch']}"
        )
        for p in probes:
            if not p["ok"]:
                print(f"  FAIL probe.{p['id']}: {p.get('detail')}")
        for t in tx["transactions"]:
            if not t["ok"]:
                print(f"  FAIL tx.{t['id']}: {t.get('detail')}")
        if not guard["ok"]:
            print(f"  FAIL trust.write_argv_guard: {guard['offenders']}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
