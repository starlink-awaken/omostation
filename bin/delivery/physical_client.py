"""TCP client for physical_node agents (ADR-0225).

Supports one-shot RPC and persistent Session connections for low-latency measure.
"""
from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class Endpoint:
    node_id: str
    host: str
    port: int

    @property
    def addr(self) -> str:
        return f"{self.host}:{self.port}"


def rpc(endpoint: Endpoint, req: dict[str, Any], *, timeout: float = 10.0) -> dict[str, Any]:
    """One-shot connection (hello / ad-hoc)."""
    with Session(endpoint, timeout=timeout) as sess:
        return sess.call(req)


class Session:
    """Persistent TCP session — multi-request keep-alive (matches physical_node)."""

    def __init__(self, endpoint: Endpoint, *, timeout: float = 10.0) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._file_r: Any = None
        self._file_w: Any = None

    def __enter__(self) -> Session:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def open(self) -> None:
        if self._sock is not None:
            return
        sock = socket.create_connection(
            (self.endpoint.host, self.endpoint.port), timeout=self.timeout
        )
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._sock = sock
        self._file_r = sock.makefile("rb")
        self._file_w = sock.makefile("wb")

    def close(self) -> None:
        for f in (self._file_r, self._file_w):
            if f is not None:
                try:
                    f.close()
                except OSError:
                    pass
        self._file_r = self._file_w = None
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def call(self, req: dict[str, Any]) -> dict[str, Any]:
        if self._sock is None:
            self.open()
        assert self._file_r is not None and self._file_w is not None
        t0 = time.perf_counter()
        payload = (json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8")
        self._file_w.write(payload)
        self._file_w.flush()
        raw = self._file_r.readline()
        wall_ms = (time.perf_counter() - t0) * 1000
        if not raw:
            return {"ok": False, "error": "empty_response", "wall_ms": wall_ms}
        try:
            resp = json.loads(raw.decode("utf-8").strip())
        except json.JSONDecodeError:
            return {
                "ok": False,
                "error": "bad_json",
                "raw": raw[:200].decode("utf-8", errors="replace"),
                "wall_ms": wall_ms,
            }
        if isinstance(resp, dict):
            resp["wall_ms"] = wall_ms
            return resp
        return {"ok": False, "error": "not_object", "wall_ms": wall_ms}


def parse_hosts(specs: list[str]) -> list[Endpoint]:
    """Parse node_id=host[:port] list."""
    out: list[Endpoint] = []
    for spec in specs:
        if "=" not in spec:
            raise ValueError(f"host spec must be node_id=host[:port], got {spec!r}")
        nid, rest = spec.split("=", 1)
        if ":" in rest:
            host, port_s = rest.rsplit(":", 1)
            port = int(port_s)
        else:
            host, port = rest, 18765
        out.append(Endpoint(node_id=nid.strip(), host=host.strip(), port=port))
    return out
