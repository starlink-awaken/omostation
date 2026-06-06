"""OMO agora 健康检查 — 验证 agora-routes.json 注册的服务真实可达(从 kairon_governance.agora_health 迁移).

设计:
  - 读 agora-routes.json, 提取每个 service 的可达端点
  - HTTP GET 探活 (5s 超时)
  - 4xx 也算 healthy (服务可达但路径错也是"可达")
  - 默认并发 5 个请求
  - 容错: 服务不可达不抛异常, 记为 unhealthy
  - 不修改任何 .omo/ 平面文件 (只读)

迁移自: kairon_governance.agora_health (P30-W1 GOV-MERGE 落地)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

from omo.omo_paths import AGORA_ROUTES_PATH

# ── omostation 服务端口约定 (fallback, 实际以 agora-routes.json _meta.routing_table 为准) ──────
# P31-W0-AGORA-ACTUAL-FIX: 修正错配端口 + 删除 stdio-only 服务
DEFAULT_SERVICE_PORTS: dict[str, int] = {
    # HTTP-reachable services (实际端口)
    "agora-internal": 7430,            # FastAPI dashboard, 启动: agora-web
    "agent-runtime-mcp": 9876,         # 实际端口 9876 (旧表错为 7440)
    "cron-service-mcp": 7450,          # 实际端口 7450 (旧表错为 7438)
    "sharedbrain-bridge-mcp": 8001,    # sharedbrain standalone MCP 端口 (旧表错为 7439)
    "minerva": 8765,                   # minerva web 端口 (非 MCP)
    # stdio-only MCP services (无 HTTP endpoint, 不应出现在 HTTP 健康检查)
    # - iris-mcp, codeanalyze-mcp, sophia-mcp, llm-gateway-mcp: stdio-only, 由 Hermes spawn
    # - eidos: stdio-only, 自定义 JSON-RPC over stdin/stdout
    # - shared-lib-mcp: 已废弃, 不存在
    # 占位: 未来若需 HTTP 暴露, 在 agora-routes.json _meta.routing_table 添加
}

DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_CONCURRENCY = 5
HEALTH_PATH = "/health"

# 环境变量: skip agora 探活 (daemon 场景, 避免每 tick 11 HTTP 请求)
ENV_SKIP_AGORA = "OMO_AUDIT_SKIP_AGORA"


# ── 数据结构 ────────────────────────────────────────────


@dataclass
class HealthCheckResult:
    """单服务探活结果."""

    service: str
    endpoint: str
    is_healthy: bool
    status_code: int | None
    response_ms: float | None
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# ── 路由表加载与端点推导 ────────────────────────────────


def load_agora_routes(path: Path | None = None) -> dict:
    """读 agora-routes.json. 缺失或损坏返回空骨架."""
    target = path if path is not None else AGORA_ROUTES_PATH
    if not target.exists():
        return {"routes": {}, "_meta": {}}
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"routes": {}, "_meta": {}}


def derive_endpoints(
    routes: dict | None = None,
    *,
    default_ports: dict[str, int] | None = None,
) -> dict[str, str]:
    """从 routes 推导 service -> health endpoint URL 映射.

    优先 _meta.routing_table (含 host/port); 否则 fallback 到
    DEFAULT_SERVICE_PORTS + localhost.
    """
    if routes is None:
        routes = load_agora_routes()
    ports = default_ports if default_ports is not None else DEFAULT_SERVICE_PORTS
    out: dict[str, str] = {}

    routing_table = routes.get("_meta", {}).get("routing_table", {}) if isinstance(routes, dict) else {}
    for svc, info in routing_table.items():
        if not isinstance(info, dict):
            continue
        if "host" in info and "port" in info:
            health_path = info.get("health_path", HEALTH_PATH)
            out[svc] = f"http://{info['host']}:{info['port']}{health_path}"
            continue
        if "endpoint" in info:
            out[svc] = info["endpoint"]

    routes_data = routes.get("routes", {}) if isinstance(routes, dict) else {}
    services: set[str] = set()
    if isinstance(routes_data, dict):
        services.update(v for v in routes_data.values() if isinstance(v, str))
    for svc in sorted(services):
        if svc in out:
            continue
        port = ports.get(svc)
        if port:
            out[svc] = f"http://localhost:{port}{HEALTH_PATH}"
    return out


# ── 单服务探活 ──────────────────────────────────────────


async def _probe_one(
    client: httpx.AsyncClient,
    service: str,
    endpoint: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> HealthCheckResult:
    """单服务探活 (GET). 4xx 视为可达."""
    t0 = time.time()
    try:
        resp = await client.get(endpoint, timeout=timeout)
        elapsed = (time.time() - t0) * 1000
        return HealthCheckResult(
            service=service,
            endpoint=endpoint,
            is_healthy=200 <= resp.status_code < 500,
            status_code=resp.status_code,
            response_ms=round(elapsed, 1),
            error=None,
        )
    except Exception as exc:
        elapsed = (time.time() - t0) * 1000
        return HealthCheckResult(
            service=service,
            endpoint=endpoint,
            is_healthy=False,
            status_code=None,
            response_ms=round(elapsed, 1),
            error=str(exc)[:200],
        )


async def check_all_health(
    endpoints: dict[str, str] | None = None,
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[HealthCheckResult]:
    """并发探活所有 agora 服务."""
    if endpoints is None:
        routes = load_agora_routes()
        endpoints = derive_endpoints(routes)
    if not endpoints:
        return []

    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(follow_redirects=True) as client:

        async def _bounded(svc: str, ep: str) -> HealthCheckResult:
            async with sem:
                return await _probe_one(client, svc, ep, timeout=timeout)

        results = await asyncio.gather(
            *[_bounded(s, e) for s, e in endpoints.items()],
            return_exceptions=False,
        )
    return list(results)


def is_skipped() -> bool:
    """daemon 跑时跳过 agora 探活的环境变量开关."""
    return os.environ.get(ENV_SKIP_AGORA) == "1"


# ── 汇总与渲染 ────────────────────────────────────────


def health_summary(results: list[HealthCheckResult]) -> dict:
    """汇总健康度指标."""
    total = len(results)
    if total == 0:
        return {
            "total": 0,
            "healthy": 0,
            "unhealthy": 0,
            "health_rate": 0.0,
            "avg_response_ms": 0.0,
        }
    healthy = sum(1 for r in results if r.is_healthy)
    response_times = [r.response_ms for r in results if r.response_ms is not None]
    avg_ms = round(sum(response_times) / len(response_times), 1) if response_times else 0.0
    return {
        "total": total,
        "healthy": healthy,
        "unhealthy": total - healthy,
        "health_rate": round(healthy / total, 3),
        "avg_response_ms": avg_ms,
    }


def render_report(results: list[HealthCheckResult]) -> str:
    """生成 Markdown 报告."""
    summary = health_summary(results)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = [
        f"# agora 健康检查报告 — {ts}",
        "",
        f"**健康度**: {summary['healthy']}/{summary['total']} ({summary['health_rate'] * 100:.1f}%)",
        f"**平均响应**: {summary['avg_response_ms']}ms",
        "",
        "## 详情",
        "",
        "| 服务 | 端点 | 状态 | 状态码 | 响应 | 错误 |",
        "|---|---|---|---|---|---|",
    ]
    for r in sorted(results, key=lambda x: (x.is_healthy, x.service)):
        status = "OK" if r.is_healthy else "DOWN"
        lines.append(
            f"| {r.service} | {r.endpoint} | {status} | "
            f"{r.status_code if r.status_code is not None else '-'} | "
            f"{r.response_ms if r.response_ms is not None else 0}ms | "
            f"{(r.error or '-')[:60]} |"
        )
    return "\n".join(lines)


# ── CLI 入口 ────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omo health",
        description="OMO agora 服务健康检查 — 探活 agora-routes.json 注册的端点",
    )
    parser.add_argument("--output", "-o", default=None, help="Markdown 报告输出路径(默认 stdout)")
    parser.add_argument("--json", action="store_true", help="同时输出 JSON 摘要")
    parser.add_argument(
        "--routes-path",
        type=Path,
        default=None,
        help="agora-routes.json 路径(测试或自定义场景)",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="单服务超时秒数")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY, help="并发请求数")
    args = parser.parse_args(argv)

    routes = load_agora_routes(args.routes_path)
    endpoints = derive_endpoints(routes)

    if not endpoints:
        print(
            "WARN: agora-routes.json 中无可探活端点",
            file=sys.stderr,
        )
        if args.json:
            print(json.dumps({"summary": health_summary([]), "results": []}, indent=2))
        return 0

    results = asyncio.run(
        check_all_health(
            endpoints,
            concurrency=args.concurrency,
            timeout=args.timeout,
        )
    )
    summary = health_summary(results)
    md = render_report(results)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"[omo-health] 报告: {out}")
    else:
        print(md)

    if args.json:
        payload = {
            "summary": summary,
            "results": [r.to_dict() for r in results],
        }
        if args.output:
            json_path = Path(args.output).with_suffix(".json")
            json_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[omo-health] JSON: {json_path}")
        else:
            print()
            print(json.dumps(payload, ensure_ascii=False, indent=2))

    print(
        f"\n[omo-health] 健康度: {summary['health_rate'] * 100:.1f}% "
        f"({summary['healthy']}/{summary['total']})"
    )
    return 0


__all__ = (
    "AGORA_ROUTES_PATH",
    "DEFAULT_CONCURRENCY",
    "DEFAULT_SERVICE_PORTS",
    "DEFAULT_TIMEOUT_SECONDS",
    "ENV_SKIP_AGORA",
    "HEALTH_PATH",
    "HealthCheckResult",
    "check_all_health",
    "derive_endpoints",
    "health_summary",
    "is_skipped",
    "load_agora_routes",
    "render_report",
)


if __name__ == "__main__":
    raise SystemExit(main())
