#!/usr/bin/env python3
"""execution-adapter — wire execution workers (Pi) into the resident daemon (WP-G).

Registers a non-safe ``execution_agent`` handler: a matching event's payload
carries the instruction prompt; the handler builds a governed delivery_binding
and calls pi-worker-adapter.run_worker to produce a worker receipt. Because this
handler executes external work it is non-safe — the daemon's human-approval gate
blocks it unless ``--yes`` is supplied.

Multica autopilot integration point is recorded here for later wiring.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
EXECUTE_EVENTS = frozenset({"ExecutionRequested", "WorkPacketDispatched"})
MULTICA_INTEGRATION_NOTE = (
    "multica autopilot integration point: bin/ 零引用; 待确认 multica CLI autopilot 触发接口后接入 (recorded WP-G)"
)


def _load_pi_adapter() -> Any:
    spec = importlib.util.spec_from_file_location(
        "pi_worker_adapter",
        WORKSPACE / "bin" / "gac" / "pi-worker-adapter.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pi_worker_adapter"] = mod
    spec.loader.exec_module(mod)
    return mod


def _execute(event: dict[str, Any], *, execute: bool) -> dict[str, Any]:
    """Build delivery_binding from event payload and run Pi worker (receipt)."""
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    prompt = str(payload.get("prompt") or payload.get("instruction") or "")
    if not prompt:
        return {"error": "execution_requires_prompt"}
    binding = {
        "run_id": str(
            event.get("workflow_run_id") or payload.get("run_id") or "exec-" + str(event.get("event_id", ""))[:8]
        ),
        "packet_id": str(payload.get("packet_id") or f"packet-{str(event.get('event_id'))[:8]}"),
        "packet_hash": str(payload.get("packet_hash") or "sha256:0" * 4),
        "instruction_binding": "resident-workpacket-v1",
    }
    try:
        pi = _load_pi_adapter()
        return pi.run_worker(
            prompt=prompt,
            execute=execute,
            workspace_root=WORKSPACE,
            delivery_binding=binding,
            timeout_seconds=min(int(payload.get("timeout_seconds") or 30), 120),
        )
    except Exception as exc:  # noqa: BLE001 - execution is best-effort
        return {"error": f"execution_failed: {type(exc).__name__}: {exc}", "binding": binding}


def register_with_daemon(daemon_module: Any) -> None:
    """Register the execution handler as NON-safe (requires --yes approval)."""
    for event_type in EXECUTE_EVENTS:
        daemon_module.register_handler("execution_agent", _execution_handler, safe=False)


def _execution_handler(event: dict[str, Any]) -> None:
    receipt = _execute(event, execute=True)
    print(f"[execution-agent] receipt={receipt.get('status') or receipt.get('error', 'ok')[:60]}", file=sys.stderr)


def main() -> int:
    import argparse  # noqa: PLC0415
    import json  # noqa: PLC0415

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", help="event JSON string")
    parser.add_argument("--dry-run", action="store_true", help="validate binding without executing")
    args = parser.parse_args()
    event = json.loads(args.json) if args.json else json.loads(sys.stdin.read())
    receipt = _execute(event, execute=not args.dry_run)
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
