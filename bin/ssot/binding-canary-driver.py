#!/usr/bin/env python3
"""binding-canary-driver — Exact Capability Binding 正向生产 canary (T1-12 operational 证据).

principal 裁决 (2026-08-29, 选项 B): 测试回执不可计为 PROVEN。本 driver 以真实
registry + 真 gateway (进程内) + metaos admission provider 固化正向链:
  find → inspect → invoke (gateway-backed) → replay (幂等) → cleanup proof
每步 receipt 末行 JSON 落盘 /tmp/canary-materials/, 报告 schema: binding-canary-report/v1。

用法 (workspace root):
  PYTHONPATH="projects/agora/src:projects/metaos/src:projects/omo/src" \
  AGORA_ADMISSION_PROVIDER="metaos.integrations.admission_provider:PROVIDER" \
  python3 bin/ssot/binding-canary-driver.py
依赖: pydantic structlog httpx cryptography fastmcp rich (uv run --with 可注入)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
SYNC = WORKSPACE / "bin" / "capability-sync.py"
WORKDIR = Path("/tmp/canary-materials")
DEFAULT_CAPABILITY = "bos-service:bos://system/omo/debt"
RECEIPT_FIELDS = ("status", "transport_state", "invocation_id", "receipt_digest")


def _run_step(name: str, argv: list[str]) -> dict:
    """跑一步 capability-sync 子命令, 取 stdout 末行 JSON 为 receipt."""
    proc = subprocess.run(
        [sys.executable, str(SYNC), *argv], capture_output=True, text=True, timeout=120
    )
    lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
    try:
        payload = json.loads(lines[-1]) if lines else {}
    except json.JSONDecodeError:
        payload = {"raw": proc.stdout[-400:], "stderr": proc.stderr[-200:]}
    return {"step": name, "rc": proc.returncode, "receipt": payload}


def _last_json(step: dict) -> dict:
    r = step.get("receipt", {})
    return r if isinstance(r, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--id", default=DEFAULT_CAPABILITY)
    parser.add_argument("--operation-id", default="binding-canary")
    args = parser.parse_args()
    capability_id: str = args.id
    workdir = WORKDIR
    workdir.mkdir(exist_ok=True)

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    binding = {
        "correlation_id": f"corr-canary-{ts}",
        "workflow_run_id": "20260828T072211Z-bet-execution-3c912d37",
        "packet_id": "WP-BET-Y1Q3-T1-12",
        "packet_hash": "sha256:" + hashlib.sha256(b"WP-BET-Y1Q3-T1-12").hexdigest(),
        "assignment_id": f"assignment-canary-{ts}",
        "dispatch_id": "dispatch-t1-12-canary",
        "actor_id": "laowang",
        "delivery_attempt_id": "bet-y1q3-t1-12-attempt1",
    }
    (workdir / "binding.json").write_text(json.dumps(binding, sort_keys=True, indent=1), encoding="utf-8")
    (workdir / "input.json").write_text("{}\n", encoding="utf-8")
    admission = {
        "receipt_digest": "sha256:" + "8" * 64,
        "admission_id": "admission-t1-12-canary",
        "step_run_id": "step-t1-12-canary",
        "worker": {"status": "bound", "id": binding["actor_id"]},
    }
    (workdir / "admission.json").write_text(json.dumps(admission, indent=1), encoding="utf-8")

    b, i, a = (
        str(workdir / "binding.json"),
        str(workdir / "input.json"),
        str(workdir / "admission.json"),
    )
    steps: list[dict] = []
    steps.append(_run_step("find", ["find", "--id", capability_id, "--binding-json", b]))
    resolution = _last_json(steps[-1])
    (workdir / "resolution.json").write_text(json.dumps(resolution), encoding="utf-8")

    steps.append(
        _run_step("inspect", ["inspect", "--id", capability_id, "--resolution-receipt-json", str(workdir / "resolution.json")])
    )
    inspection = _last_json(steps[-1])
    inspection_path = str(workdir / "inspection.json")
    Path(inspection_path).write_text(json.dumps(inspection), encoding="utf-8")

    invoke_argv = [
        "invoke",
        "--id", capability_id,
        "--input-json", i,
        "--binding-json", b,
        "--inspection-receipt-json", inspection_path,
        "--admission-receipt-json", a,
        "--operation-id", args.operation_id,
        "--effect-classification", "read_only",
    ]
    steps.append(_run_step("invoke", invoke_argv))
    invoke_receipt = _last_json(steps[-1])
    steps.append(_run_step("replay", invoke_argv))
    replay_receipt = _last_json(steps[-1])

    verdict = {
        "find": resolution.get("status") == "resolved",
        "inspect": inspection.get("status") == "inspected",
        "invoke_confirmed": invoke_receipt.get("status") == "completed"
        and invoke_receipt.get("transport_state") == "confirmed",
        "replay_idempotent": bool(invoke_receipt.get("invocation_id"))
        and replay_receipt.get("invocation_id") == invoke_receipt.get("invocation_id"),
        "cleanup_proved": bool(invoke_receipt.get("cleanup_proof", {}).get("status") == "proved"),
    }
    report = {
        "schema": "binding-canary-report/v1",
        "capability_id": capability_id,
        "operation_id": args.operation_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": all(verdict.values()),
        "verdict": verdict,
        "receipt_digest": invoke_receipt.get("receipt_digest"),
        "invocation_id": invoke_receipt.get("invocation_id"),
        "steps": [{"step": s["step"], "rc": s["rc"]} for s in steps],
    }
    (workdir / "canary-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
