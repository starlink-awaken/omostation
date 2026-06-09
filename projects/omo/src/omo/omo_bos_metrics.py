"""BOS URI 可观测性 — W3 声明式 + 可观测性 配套.

记录每次 invoke 的: uri, status (resolved/invalid/timeout/error), elapsed_ms.
落点: .omo/_knowledge/bos-metrics.jsonl (append-only JSONL).

API:
    record(uri, status, elapsed_ms)   — 1 次调用记录
    get_metrics(uri=None)             — 单 URI 或全 URI 汇总
    summary()                          — 5-domain 全景

设计: 不引入新依赖 (stdlib only). 文件锁防并发写.
    - P33 已有 omo_bos.py 用 tempfile+rename 原子写
    - 本模块追加而非覆盖, 保留历史
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

# 复用 omo_bos 的 parse_bos_uri (顶层 import, summary() 每次调用都需用到)
from omo.omo_bos import parse_bos_uri  # noqa: E402

# 复用 omo_bos 的工作区根
_WORKSPACE = Path(
    os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace"))
)
DEFAULT_METRICS_PATH = _WORKSPACE / ".omo" / "_knowledge" / "bos-metrics.jsonl"

# 文件锁 (跨进程; 单进程内 thread-safe 用 _LOCK)
_LOCK = threading.Lock()

# Status 白名单
Status = Literal[
    "resolved",         # invoke 成功 (含 agora / stdio / internal 各种 transport)
    "agora_unavailable",  # agora 不可达 (offline 模式)
    "invalid_uri",      # URI 格式错
    "endpoint_missing", # 模块找不到
    "timeout",          # invoke 超时
    "error",            # 其他 exception
]


@dataclass
class BosInvokeRecord:
    """单次 invoke 记录."""

    uri: str
    status: Status
    elapsed_ms: float
    transport: str = ""  # internal / stdio / http / agora
    error: str = ""  # 仅 status != resolved 时填
    recorded_at: str = ""

    def __post_init__(self) -> None:
        if not self.recorded_at:
            self.recorded_at = datetime.now(timezone.utc).isoformat()


def record(
    uri: str,
    status: Status,
    elapsed_ms: float,
    transport: str = "",
    error: str = "",
    path: Path | None = None,
) -> None:
    """记录 1 次 invoke 结果 (append-only, 文件锁).

    ``path`` 缺省走 ``DEFAULT_METRICS_PATH`` (运行时读, 支持 monkeypatch).
    """
    if path is None:
        path = DEFAULT_METRICS_PATH
    rec = BosInvokeRecord(
        uri=uri,
        status=status,
        elapsed_ms=elapsed_ms,
        transport=transport,
        error=error,
    )
    line = json.dumps(asdict(rec), ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        # 原子追加: tempfile + rename 不能用于 append. 改用 'a' mode + flush.
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass  # 某些 fs 不支持 fsync


def time_invoke(uri: str, transport: str = "") -> "_Timer":
    """上下文管理器: 测 invoke 耗时并自动 record.

    用法:
        with time_invoke("bos://memory/kos/search", "stdio") as t:
            r = invoke(...)
        t.set_status("resolved")
    """
    return _Timer(uri, transport)


class _Timer:
    """time_invoke() 返回的上下文管理器."""

    def __init__(self, uri: str, transport: str) -> None:
        self.uri = uri
        self.transport = transport
        self.status: Status = "resolved"
        self.error: str = ""
        self._t0: float = 0.0

    def __enter__(self) -> "_Timer":
        self._t0 = time.monotonic()
        return self

    def __exit__(self, _exc_type, exc, _tb) -> None:
        elapsed_ms = (time.monotonic() - self._t0) * 1000.0
        if exc is not None:
            self.status = "error"
            self.error = f"{type(exc).__name__}: {exc}"[:200]
        record(
            self.uri,
            self.status,
            elapsed_ms,
            transport=self.transport,
            error=self.error,
        )

    def set_status(self, status: Status, error: str = "") -> None:
        self.status = status
        if error:
            self.error = error[:200]


def _read_all(path: Path = DEFAULT_METRICS_PATH) -> list[dict[str, Any]]:
    """读所有 metrics 记录 (内存级)."""
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def get_metrics(
    uri: str | None = None,
    path: Path | None = None,
    limit: int = 0,
) -> list[dict[str, Any]]:
    """读 metrics 记录. uri 过滤; limit=0 全量, 否则取最近 N 条."""
    if path is None:
        path = DEFAULT_METRICS_PATH
    recs = _read_all(path)
    if uri is not None:
        recs = [r for r in recs if r.get("uri") == uri]
    if limit > 0:
        recs = recs[-limit:]
    return recs


def summary(
    path: Path | None = None,
) -> dict[str, Any]:
    """全 URI 汇总: count, success/error/timeout 分桶, p50/p95/p99 latency.

    返回结构:
        {
          "total_invocations": int,
          "by_uri": {uri: {count, success, error, timeout, p50_ms, p95_ms, p99_ms, max_ms}},
          "by_domain": {domain: {count, success_rate}},
          "by_status": {status: count},
          "generated_at": iso8601
        }
    """
    if path is None:
        path = DEFAULT_METRICS_PATH
    recs = _read_all(path)
    by_uri: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in recs:
        by_uri[r.get("uri", "unknown")].append(r)

    per_uri_summary: dict[str, dict[str, Any]] = {}
    by_domain_count: dict[str, int] = defaultdict(int)
    by_domain_success: dict[str, int] = defaultdict(int)
    by_status: dict[str, int] = defaultdict(int)

    for uri, items in by_uri.items():
        # parse_bos_uri 依赖只与 uri 相关 — 在外层 group 内调用一次而非内层 record
        try:
            domain_for_uri = parse_bos_uri(uri)["domain"]
        except ValueError:
            domain_for_uri = None

        latencies = sorted(r.get("elapsed_ms", 0.0) for r in items)
        n = len(items)
        success = sum(1 for r in items if r.get("status") == "resolved")
        err = sum(1 for r in items if r.get("status") == "error")
        timeout = sum(1 for r in items if r.get("status") == "timeout")

        per_uri_summary[uri] = {
            "count": n,
            "success": success,
            "error": err,
            "timeout": timeout,
            "success_rate": round(success / n, 3) if n else 0.0,
            "p50_ms": round(latencies[n // 2], 2) if n else 0.0,
            "p95_ms": round(latencies[int(n * 0.95)] if n > 1 else latencies[-1], 2) if n else 0.0,
            "p99_ms": round(latencies[int(n * 0.99)] if n > 1 else latencies[-1], 2) if n else 0.0,
            "max_ms": round(max(latencies), 2) if n else 0.0,
        }
        for r in items:
            by_status[r.get("status", "unknown")] += 1
            if domain_for_uri is None:
                continue
            by_domain_count[domain_for_uri] += 1
            if r.get("status") == "resolved":
                by_domain_success[domain_for_uri] += 1

    by_domain = {
        d: {
            "count": by_domain_count[d],
            "success_rate": round(by_domain_success[d] / by_domain_count[d], 3)
            if by_domain_count[d]
            else 0.0,
        }
        for d in sorted(by_domain_count)
    }

    return {
        "total_invocations": len(recs),
        "by_uri": per_uri_summary,
        "by_domain": by_domain,
        "by_status": dict(by_status),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def reset(path: Path | None = None) -> int:
    """清空 metrics 文件. 返回清空前行数 (用于审计)."""
    if path is None:
        path = DEFAULT_METRICS_PATH
    if not path.exists():
        return 0
    lines = [
        line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    n = len(lines)
    # 原子清空
    fd, tmp = tempfile.mkstemp(prefix=".bos-metrics.", suffix=".jsonl.tmp", dir=path.parent)
    try:
        Path(tmp).write_text("", encoding="utf-8")
        Path(tmp).replace(path)
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
    return n


__all__ = (
    "DEFAULT_METRICS_PATH",
    "Status",
    "BosInvokeRecord",
    "record",
    "time_invoke",
    "get_metrics",
    "summary",
    "reset",
)


if __name__ == "__main__":
    # 快速自检
    import time as _t

    for i in range(5):
        with time_invoke("bos://memory/kos/search", "stdio") as timer:
            _t.sleep(0.001)
        timer.set_status("resolved")
    for i in range(2):
        record("bos://analysis/minerva/research", "error", 50.0, error="timeout")

    s = summary()
    print(f"[OK] total_invocations: {s['total_invocations']}")
    print(f"[OK] by_status: {s['by_status']}")
    print(f"[OK] by_domain: {s['by_domain']}")
    print(f"[OK] sample URI stats: {list(s['by_uri'].items())[0]}")
