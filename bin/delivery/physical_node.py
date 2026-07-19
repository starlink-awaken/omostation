#!/usr/bin/env python3
"""Physical multi-host node agent (ADR-0225).

TCP JSON-lines protocol. Supports multi-request per connection (keep-alive)
until client closes, for sub-100ms sync measurement on LAN.
"""
from __future__ import annotations

import argparse
import json
import socket
import socketserver
import threading
import time
import uuid
from typing import Any


class NodeState:
    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        self.agents: dict[str, dict[str, Any]] = {}
        self.kv: dict[str, Any] = {}
        self.lock = threading.Lock()
        self.tasks_ok = 0
        self.tasks_fail = 0

    def handle(self, req: dict[str, Any]) -> dict[str, Any]:
        op = str(req.get("op") or "")
        if op == "hello":
            return {"ok": True, "node_id": self.node_id, "agents": len(self.agents)}
        if op == "register_agent":
            role = str(req.get("role_id") or "implementer")
            aid = str(req.get("agent_id") or f"agent-{uuid.uuid4().hex[:8]}")
            with self.lock:
                self.agents[aid] = {
                    "agent_id": aid,
                    "role_id": role,
                    "healthy": True,
                    "capacity": int(req.get("capacity") or 4),
                    "inflight": 0,
                }
            return {"ok": True, "agent_id": aid, "node_id": self.node_id}
        if op == "run_task":
            task_id = str(req.get("task_id") or "")
            role = str(req.get("role_id") or "implementer")
            t0 = time.perf_counter()
            with self.lock:
                candidates = [
                    a
                    for a in self.agents.values()
                    if a["role_id"] == role
                    and a["healthy"]
                    and a["inflight"] < a["capacity"]
                ]
                if not candidates:
                    self.tasks_fail += 1
                    return {
                        "ok": False,
                        "success": False,
                        "task_id": task_id,
                        "error": "no_agent",
                        "latency_ms": (time.perf_counter() - t0) * 1000,
                    }
                agent = candidates[0]
                agent["inflight"] += 1
            try:
                time.sleep(float(req.get("work_ms") or 0) / 1000.0)
                success = True
            finally:
                with self.lock:
                    agent["inflight"] = max(0, agent["inflight"] - 1)
                    if success:
                        self.tasks_ok += 1
                    else:
                        self.tasks_fail += 1
            return {
                "ok": True,
                "success": True,
                "task_id": task_id,
                "agent_id": agent["agent_id"],
                "node_id": self.node_id,
                "latency_ms": (time.perf_counter() - t0) * 1000,
            }
        if op == "put":
            key = str(req.get("key") or "")
            val = req.get("value")
            t0 = time.perf_counter()
            with self.lock:
                self.kv[key] = val
            return {
                "ok": True,
                "key": key,
                "latency_ms": (time.perf_counter() - t0) * 1000,
            }
        if op == "get":
            key = str(req.get("key") or "")
            t0 = time.perf_counter()
            with self.lock:
                present = key in self.kv
                val = self.kv.get(key)
            return {
                "ok": present,
                "key": key,
                "value": val,
                "latency_ms": (time.perf_counter() - t0) * 1000,
            }
        if op == "stats":
            with self.lock:
                return {
                    "ok": True,
                    "node_id": self.node_id,
                    "agents": len(self.agents),
                    "kv_keys": len(self.kv),
                    "tasks_ok": self.tasks_ok,
                    "tasks_fail": self.tasks_fail,
                }
        return {"ok": False, "error": f"unknown_op:{op}"}


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        state: NodeState = self.server.state  # type: ignore[attr-defined]
        # Multi-request: read lines until EOF
        while True:
            raw = self.rfile.readline()
            if not raw:
                break
            try:
                req = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self.wfile.write(b'{"ok":false,"error":"bad_json"}\n')
                self.wfile.flush()
                continue
            if not isinstance(req, dict):
                self.wfile.write(b'{"ok":false,"error":"not_object"}\n')
                self.wfile.flush()
                continue
            resp = state.handle(req)
            self.wfile.write((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))
            self.wfile.flush()


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def serve(host: str, port: int, node_id: str) -> None:
    state = NodeState(node_id)
    server = ThreadedTCPServer((host, port), _Handler)
    server.state = state  # type: ignore[attr-defined]
    print(
        json.dumps(
            {"listening": True, "bind": host, "port": port, "node_id": node_id},
            ensure_ascii=False,
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=18765)
    ap.add_argument("--node-id", default=None)
    args = ap.parse_args(argv)
    node_id = args.node_id or f"node-{socket.gethostname()}"
    serve(args.bind, args.port, node_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
