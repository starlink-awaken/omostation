#!/usr/bin/env python3
"""
http_api.py — Forge 数字资产查询服务

零外部依赖（仅用 stdlib），提供完整的 REST API 用于查询/浏览/导出数字资产。

启动:
  python3 src/http_api.py [--port 8766]
  python3 src/http_api.py --daemon

端点:
  GET  /health               — 健康检查
  GET  /status               — 项目状态

  GET  /assets               — 查询资产 (?q=&category=&status=&type=&capabilities=&limit=20&offset=0)
  GET  /assets/stats         — 资产统计（按分类/状态/类型聚合）
  GET  /assets/categories    — 分类列表（含计数）
  GET  /assets/:id           — 资产详情
  GET  /assets/export        — 导出资产 (?format=csv|json&q=&category=&status=)

  GET  /graph/stats          — 图谱统计
  GET  /graph/query          — 图谱查询 (?q=)
  GET  /recommend            — 推荐 (?tool_id=)
"""

from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys
import urllib.parse
from collections import Counter
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, cast

from forge.forge_config import (  # type: ignore[import-not-found]
    ALLOWED_CORS_ORIGINS,
    GRAPH,
    MAX_BODY,
    REGISTRY,
    SRC,
)
from forge.forge_config import (
    API_TOKEN as TOKEN,
)
from forge.forge_config import (
    FORGE_ROOT as TOOLBOX_DIR,
)
from forge.forge_config import (
    HTTP_PORT as PORT,
)

REQUIRE_TOKEN = False


def resolve_cors_origin(request_origin: str | None) -> str:
    """返回允许的 CORS 来源，若请求来源在白名单中则回显，否则返回空。"""
    if request_origin == "*":
        return "*"
    if request_origin and request_origin in ALLOWED_CORS_ORIGINS:
        return request_origin
    # 默认允许本地回环（无 Origin 头的同源请求也安全）
    return "http://127.0.0.1:8766"


# ─── 数据加载 ─────────────────────────────────


def load_registry() -> dict:
    try:
        return cast("dict", json.loads(REGISTRY.read_text()))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"tools": [], "schema_version": "?", "event_log": []}


def load_graph() -> dict:
    if GRAPH.exists():
        try:
            return cast("dict", json.loads(GRAPH.read_text()))
        except json.JSONDecodeError:
            pass
    return {"nodes": [], "edges": [], "stats": {}}


# ─── 资产查询引擎 ─────────────────────────────


def query_assets(
    query: str = "",
    category: str = "",
    status: str = "",
    asset_type: str = "",
    capabilities: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """查询资产，返回 (结果列表, 总数)。"""
    reg = load_registry()
    tools = reg.get("tools", [])
    results: list[tuple[float, dict]] = []

    q = query.lower().strip() if query else ""
    caps = [c.lower().strip() for c in (capabilities or []) if c.strip()]
    cat_filter = category.strip().lower() if category else ""
    stat_filter = status.strip().lower() if status else ""
    type_filter = asset_type.strip().lower() if asset_type else ""

    for tool in tools:
        score = 0.0

        # 分面过滤
        if cat_filter:
            tool_cats = [c.lower().strip() for c in tool.get("category", [])]
            if cat_filter not in tool_cats:
                continue

        if stat_filter:
            if tool.get("status", "").lower() != stat_filter:
                continue

        if type_filter:
            if tool.get("type", "").lower() != type_filter:
                continue

        if caps:
            tool_caps = [c.lower().strip() for c in tool.get("capabilities", [])]
            if not any(rc in tool_caps for rc in caps):
                continue

        # 文本匹配评分
        if q:
            if q in tool.get("id", "").lower():
                score += 1.0
            if q in tool.get("name", "").lower():
                score += 0.8
            if any(q in c.lower() for c in tool.get("capabilities", [])):
                score += 0.5
            if q in tool.get("notes", "").lower():
                score += 0.3
            if any(q in c.lower() for c in tool.get("category", [])):
                score += 0.3
            if q in tool.get("source", {}).get("provider", "").lower():
                score += 0.2
            if q in str(tool.get("_discovery", {}).get("source", "")).lower():
                score += 0.1
        else:
            score = 1.0  # 无查询词时全部返回

        if score > 0:
            results.append((score, tool))

    results.sort(key=lambda x: (-x[0], x[1].get("id", "")))
    total = len(results)
    page = results[offset : offset + limit]
    return [r[1] for r in page], total


def build_asset_stats() -> dict:
    """构建资产统计聚合。"""
    reg = load_registry()
    tools = reg.get("tools", [])

    by_category: Counter = Counter()
    by_status: Counter = Counter()
    by_type: Counter = Counter()
    sources: Counter = Counter()
    total_caps = 0

    for t in tools:
        for c in t.get("category", []):
            by_category[c] += 1
        by_status[t.get("status", "unknown")] += 1
        by_type[t.get("type", "unknown")] += 1
        src = t.get("source", {}).get("provider", "unknown")
        sources[src] += 1
        total_caps += len(t.get("capabilities", []))

    return {
        "total": len(tools),
        "by_category": dict(by_category.most_common()),
        "by_status": dict(by_status),
        "by_type": dict(by_type),
        "top_sources": dict(sources.most_common(20)),
        "total_capabilities": total_caps,
        "avg_capabilities": round(total_caps / len(tools), 1) if tools else 0,
    }


def get_categories() -> list[dict]:
    """获取分类列表（含计数）。"""
    reg = load_registry()
    counter: Counter = Counter()
    for t in reg.get("tools", []):
        for c in t.get("category", []):
            counter[c] += 1
    return [{"name": name, "count": count} for name, count in counter.most_common()]


def export_assets(
    format: str = "json",
    query: str = "",
    category: str = "",
    status: str = "",
) -> str:
    """导出资产为 JSON 或 CSV。"""
    tools, _ = query_assets(
        query=query,
        category=category,
        status=status,
        limit=99999,
        offset=0,
    )

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "name",
                "type",
                "status",
                "category",
                "capabilities",
                "source",
                "version",
                "cost_model",
                "notes",
                "added",
                "updated",
            ]
        )
        for t in tools:
            writer.writerow(
                [
                    t.get("id", ""),
                    t.get("name", ""),
                    t.get("type", ""),
                    t.get("status", ""),
                    "; ".join(t.get("category", [])),
                    "; ".join(t.get("capabilities", [])),
                    t.get("source", {}).get("provider", ""),
                    t.get("source", {}).get("version", ""),
                    t.get("cost_model", ""),
                    t.get("notes", ""),
                    t.get("added", ""),
                    t.get("updated", ""),
                ]
            )
        return output.getvalue()

    return json.dumps(tools, ensure_ascii=False, indent=2)


# ─── HTTP Handler ────────────────────────────


def respond(handler: BaseHTTPRequestHandler, data: object, status: int = 200) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", resolve_cors_origin(handler.headers.get("Origin")))
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(json.dumps(data, ensure_ascii=False).encode())


def respond_csv(handler: BaseHTTPRequestHandler, csv_text: str, filename: str) -> None:
    handler.send_response(200)
    handler.send_header("Content-Type", "text/csv; charset=utf-8")
    handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
    handler.send_header("Access-Control-Allow-Origin", resolve_cors_origin(handler.headers.get("Origin")))
    handler.end_headers()
    handler.wfile.write(csv_text.encode("utf-8"))


def error(handler: BaseHTTPRequestHandler, msg: str, status: int = 400) -> None:
    respond(handler, {"error": msg}, status)


def _check_auth(handler: BaseHTTPRequestHandler) -> bool:
    if not TOKEN and not REQUIRE_TOKEN:
        return True
    auth = handler.headers.get("Authorization", "")
    return bool(auth == f"Bearer {TOKEN}")


def query_graph(query: str) -> list[dict]:
    g = load_graph()
    q = query.lower()
    matched = {n["id"] for n in g["nodes"] if q in n["label"].lower() or q in n["id"].lower()}
    related = set()
    for e in g["edges"]:
        if e["source"] in matched or e["target"] in matched:
            related.add(e["source"])
            related.add(e["target"])
    return [n for n in g["nodes"] if n["id"] in related]


class ForgeAPIHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器 —— 路由到对应处理函数。"""

    def _parse_path(self) -> tuple[str, dict[str, str]]:
        path = self.path.split("?")[0].rstrip("/")
        qs: dict[str, str] = {}
        if "?" in self.path:
            for part in self.path.split("?", 1)[1].split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    qs[urllib.parse.unquote(k)] = urllib.parse.unquote(v)
        return path, qs

    def _read_body(self) -> dict | None:
        length_s = self.headers.get("Content-Length", "0")
        try:
            length = int(length_s)
        except (ValueError, TypeError):
            length = 0
        if length > MAX_BODY:
            return None
        if length:
            try:
                return cast("dict", json.loads(self.rfile.read(length)))
            except json.JSONDecodeError:
                return {}
        return {}

    # ─── GET ───

    def do_GET(self) -> None:
        if not _check_auth(self):
            return error(self, "unauthorized", 401)
        path, qs = self._parse_path()

        # 健康检查
        if path == "/health":
            reg = load_registry()
            g = load_graph()
            return respond(
                self,
                {
                    "status": "ok",
                    "schema": reg.get("schema_version"),
                    "tools": len(reg.get("tools", [])),
                    "active": sum(1 for t in reg["tools"] if t.get("status") == "active"),
                    "events": len(reg.get("event_log", [])),
                    "graph_nodes": g.get("stats", {}).get("total_nodes", 0),
                },
            )

        # 项目状态
        if path == "/status":
            reg = load_registry()
            g = load_graph()
            tools = reg.get("tools", [])
            return respond(
                self,
                {
                    "schema": reg.get("schema_version"),
                    "tools": len(tools),
                    "active": sum(1 for t in tools if t.get("status") == "active"),
                    "candidates": sum(1 for t in tools if t.get("status") == "candidate"),
                    "evaluating": sum(1 for t in tools if t.get("status") == "evaluating"),
                    "deprecated": sum(1 for t in tools if t.get("status") == "deprecated"),
                    "stale": sum(1 for t in tools if t.get("status") == "stale"),
                    "events": len(reg.get("event_log", [])),
                    "telemetry": sum(1 for t in tools if t.get("telemetry", {}).get("use_count", 0) > 0),
                    "graph_nodes": g.get("stats", {}).get("total_nodes", 0),
                    "graph_edges": g.get("stats", {}).get("total_edges", 0),
                    "categories": len(set(c for t in tools for c in t.get("category", []))),
                },
            )

        # 资产统计
        if path == "/assets/stats":
            return respond(self, build_asset_stats())

        # 分类列表
        if path == "/assets/categories":
            return respond(self, get_categories())

        # 导出
        if path == "/assets/export":
            fmt = qs.get("format", "json")
            if fmt == "csv":
                csv_data = export_assets(
                    format="csv",
                    query=qs.get("q", ""),
                    category=qs.get("category", ""),
                    status=qs.get("status", ""),
                )
                return respond_csv(self, csv_data, "forge-assets.csv")
            assets, total = query_assets(
                query=qs.get("q", ""),
                category=qs.get("category", ""),
                status=qs.get("status", ""),
                limit=99999,
            )
            return respond(self, {"total": total, "assets": assets})

        # 资产查询（核心端点）
        if path == "/assets":
            try:
                limit = int(qs.get("limit", 20))
            except (ValueError, TypeError):
                limit = 20
            limit = max(1, min(limit, 200))
            try:
                offset = int(qs.get("offset", 0))
            except (ValueError, TypeError):
                offset = 0
            offset = max(0, offset)

            caps = qs.get("capabilities", "").split(",") if qs.get("capabilities") else None

            assets, total = query_assets(
                query=qs.get("q", ""),
                category=qs.get("category", ""),
                status=qs.get("status", ""),
                asset_type=qs.get("type", ""),
                capabilities=caps,
                limit=limit,
                offset=offset,
            )
            return respond(
                self,
                {
                    "total": total,
                    "offset": offset,
                    "limit": limit,
                    "assets": assets,
                },
            )

        # 资产详情
        if path.startswith("/assets/"):
            asset_id = path[len("/assets/") :]
            if not asset_id or "/" in asset_id:
                return error(self, "invalid asset id", 400)
            reg = load_registry()
            for t in reg.get("tools", []):
                if t.get("id") == asset_id:
                    return respond(self, t)
            return respond(self, {"error": "not found"}, 404)

        # 图谱统计
        if path == "/graph/stats":
            g = load_graph()
            return respond(self, g.get("stats", {}))

        # 图谱查询
        if path == "/graph/query":
            q = qs.get("q", "")
            return respond(self, query_graph(q))

        # 推荐
        if path == "/recommend":
            tid = qs.get("tool_id", "")
            g = load_graph()
            related: set[str] = set()
            for e in g.get("edges", []):
                if e["source"] == tid:
                    related.add(e["target"])
                elif e["target"] == tid:
                    related.add(e["source"])
            result: dict[str, list[dict]] = {}
            for n in g.get("nodes", []):
                if n["id"] in related:
                    result.setdefault(n["type"], []).append({"id": n["id"], "label": n["label"]})
            return respond(self, result)

        error(self, f"not found: {path}", 404)

    # ─── POST ───

    def do_POST(self) -> None:
        if not _check_auth(self):
            return error(self, "unauthorized", 401)
        path, qs = self._parse_path()

        if path == "/graph/build":
            result = subprocess.run(
                [sys.executable, str(SRC / "build_graph.py")],
                capture_output=True,
                text=True,
                cwd=TOOLBOX_DIR,
            )
            return respond(self, {"output": result.stdout.strip(), "exit_code": result.returncode})

        if path == "/insight":
            mode = qs.get("mode", "gaps")
            flag = "--gaps" if mode == "gaps" else "--weekly"
            result = subprocess.run(
                ["bash", str(TOOLBOX_DIR / "scripts" / "insight-report.sh"), flag, "--json"],
                capture_output=True,
                text=True,
                cwd=TOOLBOX_DIR,
            )
            return respond(self, {"mode": mode, "output": result.stdout.strip()})

        error(self, f"not found: {path}", 404)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", resolve_cors_origin(self.headers.get("Origin")))
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:  # type: ignore[override]
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] {args[0] if args else ''} {args[1] if len(args) > 1 else ''} {args[2] if len(args) > 2 else ''}"
        )


# ─── 启动 ────────────────────────────────────


def main() -> None:
    global REQUIRE_TOKEN
    port = PORT
    daemon = False
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
        if a == "--daemon":
            daemon = True
        if a == "--require-token":
            REQUIRE_TOKEN = True
            if not TOKEN:
                print("错误: --require-token 要求设置 FORGE_API_TOKEN 环境变量", file=sys.stderr)
                sys.exit(1)

    if "--help" in args or "-h" in args:
        print(__doc__)
        return

    if daemon:
        pid = os.fork()
        if pid > 0:
            print(f"Forge API 后台运行 PID={pid}, http://127.0.0.1:{port}")
            sys.exit(0)

    server = HTTPServer(("127.0.0.1", port), ForgeAPIHandler)
    print(f"Forge 数字资产查询服务 → http://127.0.0.1:{port}")
    print(f"  资产搜索:  curl 'http://127.0.0.1:{port}/assets?q=PDF'")
    print(f"  资产统计:  curl 'http://127.0.0.1:{port}/assets/stats'")
    print(f"  分类浏览:  curl 'http://127.0.0.1:{port}/assets/categories'")
    print(f"  导出 CSV:  curl 'http://127.0.0.1:{port}/assets/export?format=csv'")
    print(f"  健康检查:  curl 'http://127.0.0.1:{port}/health'")
    print(f"  图谱统计:  curl 'http://127.0.0.1:{port}/graph/stats'")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        print("\n已停止")


if __name__ == "__main__":
    main()
