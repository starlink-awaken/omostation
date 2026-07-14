#!/usr/bin/env python3
"""bus-e2e-harness — Round 5 follow-up: real cross-process e2e for bus-foundation.

Round 0-4 verified cross-project flow in-process. This harness covers
the **real cross-process** case: publisher and subscriber run in
**separate Python processes** and communicate over a real ZMQ socket.

Usage:
    # Default: ZMQ cross-process, 50 messages
    python3 bin/ssot/bus-e2e-harness.py

    # Custom: 100 messages
    python3 bin/ssot/bus-e2e-harness.py --count 100

    # JSON output (no banner)
    python3 bin/ssot/bus-e2e-harness.py --json

Exit code 0 on success (every message delivered), 1 on any loss.

NOTE: requires ``pyzmq`` to be installed. If your Python lacks it, the
script prints an actionable error pointing to bus-foundation's venv
which always ships with the [zmq] extra.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import socket
import sys
import tempfile
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
REPOROOT_BUS_SRC = WORKSPACE / "projects" / "bus-foundation" / "src"
TOPIC = "bus-e2e-harness:test"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _subscriber_process(port: int, count: int, output_file: Path) -> None:
    """Subprocess: subscribe on ZMQ, collect N messages, write to file."""
    sys.path.insert(0, str(REPOROOT_BUS_SRC))
    try:
        from bus_foundation.backends.zmq import ZeroMQBackend
    except ImportError as e:
        output_file.write_text(json.dumps({"error": f"SKIP: pyzmq missing: {e}"}))
        sys.exit(2)

    received: list[str] = []
    backend = ZeroMQBackend(port=0, peers=[f"tcp://127.0.0.1:{port}"])
    backend.subscribe(TOPIC, lambda env: received.append(env.id))
    deadline = time.monotonic() + 15.0
    while len(received) < count and time.monotonic() < deadline:
        time.sleep(0.05)
    output_file.write_text(json.dumps({"received": received, "count": len(received)}))
    backend.close()


def _publisher_process(port: int, count: int, output_file: Path) -> None:
    """Subprocess: bind a ZMQ PUB on `port`, publish N envelopes."""
    sys.path.insert(0, str(REPOROOT_BUS_SRC))
    try:
        from bus_foundation.backends.zmq import ZeroMQBackend
    except ImportError as e:
        output_file.write_text(json.dumps({"error": f"SKIP: pyzmq missing: {e}"}))
        sys.exit(2)
    from bus_foundation.envelope import BusEnvelope

    backend = ZeroMQBackend(port=port)
    time.sleep(0.5)  # give the SUB a moment to connect
    sent_ids: list[str] = []
    for i in range(count):
        env = BusEnvelope(type=TOPIC, source="bus-e2e-harness", payload={"i": i})
        backend.publish(env)
        sent_ids.append(env.id)
        time.sleep(0.001)
    output_file.write_text(json.dumps({"sent": sent_ids, "count": len(sent_ids)}))
    backend.close()


def run_zmq_harness(port: int, count: int) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        sub_out = Path(tmp) / "sub.json"
        pub_out = Path(tmp) / "pub.json"
        sub_proc = mp.Process(target=_subscriber_process, args=(port, count, sub_out))
        sub_proc.start()
        time.sleep(0.3)  # let SUB socket connect
        pub_proc = mp.Process(target=_publisher_process, args=(port, count, pub_out))
        pub_proc.start()
        pub_proc.join(timeout=20.0)
        sub_proc.join(timeout=20.0)
        if sub_proc.is_alive() or pub_proc.is_alive():
            sub_proc.terminate()
            pub_proc.terminate()
            return {"ok": False, "error": "subprocess timeout"}
        if not sub_out.exists() or not pub_out.exists():
            return {"ok": False, "error": "subprocess did not write output"}
        sub_data = json.loads(sub_out.read_text())
        pub_data = json.loads(pub_out.read_text())
        if "error" in sub_data:
            return {"ok": False, "error": sub_data["error"]}
        if "error" in pub_data:
            return {"ok": False, "error": pub_data["error"]}
        sent = set(pub_data["sent"])
        received = set(sub_data["received"])
        lost = sent - received
        extra = received - sent
        return {
            "ok": not lost,
            "sent": len(sent),
            "received": len(received),
            "lost": len(lost),
            "extra": len(extra),
            "lost_ids": sorted(lost)[:5],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default="zmq", choices=["zmq"])
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        import zmq as _zmq_check  # noqa: F401
    except ImportError:
        bf_venv = WORKSPACE / "projects" / "bus-foundation" / ".venv" / "bin" / "python"
        if bf_venv.exists():
            print(
                f"SKIP: pyzmq not importable in current Python ({sys.executable}).\n"
                f"  Re-run with the bus-foundation venv python:\n"
                f"  {bf_venv} bin/ssot/bus-e2e-harness.py {' '.join(sys.argv[1:])}",
                file=sys.stderr,
            )
        else:
            print(
                "SKIP: pyzmq not installed. Install with: pip install bus-foundation[zmq]",
                file=sys.stderr,
            )
        return 0  # optional dep — skip, don't fail the gate

    port = args.port or _free_port()
    if not args.json:
        print(f"bus-e2e-harness: backend={args.backend} port={port} count={args.count}")
    t0 = time.monotonic()
    summary = run_zmq_harness(port=port, count=args.count)
    elapsed = time.monotonic() - t0
    summary["elapsed_s"] = round(elapsed, 2)
    summary["port"] = port

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        if summary.get("ok"):
            print(f"PASS: {summary['sent']} sent, {summary['received']} received, "
                  f"{summary['lost']} lost, {summary['extra']} extra, "
                  f"{summary['elapsed_s']}s")
        else:
            err = summary.get("error", "unknown")
            print(f"FAIL: {err}")
            print(f"  sent={summary.get('sent', '?')}, "
                  f"received={summary.get('received', '?')}, "
                  f"lost={summary.get('lost', '?')}, "
                  f"extra={summary.get('extra', '?')}")
            if "lost_ids" in summary:
                print(f"  first 5 lost ids: {summary['lost_ids']}")
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
