#!/usr/bin/env python3
"""omostation 观测性 dashboard — P38-W2 真正落地.

基于 .omo/_knowledge/governance-history.jsonl 生成单页 HTML dashboard.
可被 ``python -m omo.omo_observability_dashboard`` 启动 HTTP 服务 (默认 :9090).

设计目标:
    * 零外部依赖 (无 JS / 无 React / 无 Vue)
    * 单页 HTML, 浏览器内自洽
    * ASCII 字符条形图渲染健康分趋势
    * 仅 spawn 一次验证可服务化, 立即 kill

P38-W2 真正落地, 让 P36-W2 的观测性从"可调"演进到"可视化".
"""
from __future__ import annotations

import argparse
import http.server
import json
import socketserver
import sys
from pathlib import Path

HISTORY_PATH = Path(os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace"))) / ".omo" / "_knowledge" / "governance-history.jsonl"


def load_history() -> list[dict]:
    """加载治理历史 JSONL.

    容错: 文件不存在 / 行为空 / 单行 JSON 错误均不会让 dashboard 崩溃.
    """
    if not HISTORY_PATH.exists():
        return []
    try:
        text = HISTORY_PATH.read_text(encoding="utf-8")
    except OSError:
        return []
    entries: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def compute_dashboard_data() -> dict:
    """计算 dashboard 数据.

    Returns:
        {
            "entries": 最近 20 条 (新→旧倒序前 20),
            "summary": {
                "count": 总条数,
                "date_count": 独立日期数,
                "first_date": 最早日期,
                "last_date":  最近日期,
                "avg_score":  有效平均分,
                "max_score":  最高分,
                "min_score":  最低分,
            },
            "daily": { "YYYY-MM-DD": {"scores": [...], "grades": [...]} },
        }
    """
    entries = load_history()
    if not entries:
        return {"entries": [], "summary": {"count": 0, "avg_score": 0.0}, "daily": {}}

    # 按日期聚合
    daily: dict[str, dict] = {}
    for e in entries:
        date = e.get("date", "unknown")
        if date not in daily:
            daily[date] = {"scores": [], "grades": []}
        score = e.get("total_score")
        if isinstance(score, (int, float)):
            daily[date]["scores"].append(float(score))
        grade = e.get("grade")
        if grade:
            daily[date]["grades"].append(str(grade))

    dates = sorted(daily.keys())
    valid_scores = [
        float(e.get("total_score", 0))
        for e in entries
        if isinstance(e.get("total_score"), (int, float))
    ]
    summary = {
        "count": len(entries),
        "date_count": len(dates),
        "first_date": dates[0] if dates else None,
        "last_date": dates[-1] if dates else None,
        "avg_score": sum(valid_scores) / len(valid_scores) if valid_scores else 0.0,
        "max_score": max(valid_scores) if valid_scores else 0.0,
        "min_score": min(valid_scores) if valid_scores else 0.0,
    }
    return {
        "entries": entries[-20:],
        "summary": summary,
        "daily": daily,
    }


def _bar(value: float, max_value: float = 100.0, width: int = 40) -> str:
    """ASCII 水平条形图."""
    if max_value <= 0:
        max_value = 1.0
    ratio = max(0.0, min(1.0, value / max_value))
    filled = int(ratio * width)
    return "█" * filled + "░" * (width - filled)


def render_dashboard_html() -> str:
    """生成单页 HTML dashboard."""
    data = compute_dashboard_data()
    summary = data["summary"]
    entries = data["entries"]
    daily = data.get("daily", {})

    # 健康分趋势 (最近 14 天)
    chart_rows: list[str] = []
    recent_dates = sorted(daily.keys())[-14:]
    for date in recent_dates:
        scores = daily[date].get("scores", [])
        if not scores:
            continue
        avg = sum(scores) / len(scores)
        bar = _bar(avg, 100.0, 40)
        chart_rows.append(f"  {date}  {bar}  {avg:5.1f}  (n={len(scores)})")

    chart_html = "<br>".join(chart_rows) if chart_rows else "<i>无历史数据</i>"

    # 最近 10 条历史 (倒序)
    table_rows = []
    for e in reversed(entries[-10:]):
        ts = (e.get("timestamp") or "")[:19]
        score = e.get("total_score", "?")
        grade = e.get("grade", "?")
        watch = e.get("watchlist_count", "?")
        source = e.get("source", "?")
        table_rows.append(
            f"<tr><td>{ts}</td><td>{score}</td><td>{grade}</td>"
            f"<td>{watch}</td><td>{source}</td></tr>"
        )
    rows_html = "\n        ".join(table_rows) if table_rows else "<tr><td colspan='5'>无数据</td></tr>"

    last_date = summary.get("last_date") or "-"
    first_date = summary.get("first_date") or "-"
    avg_score = summary.get("avg_score", 0.0)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="30">
    <title>omostation Governance Dashboard</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 1200px; margin: 0 auto; padding: 2rem; background: #f8f9fa; color: #2c3e50; }}
        h1 {{ color: #2c3e50; margin-bottom: 0.25rem; }}
        .subtitle {{ color: #7f8c8d; font-size: 0.9rem; margin-top: 0; }}
        .summary {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 1rem; margin: 2rem 0; }}
        .card {{ background: white; padding: 1.25rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .card h3 {{ margin: 0 0 0.5rem; color: #7f8c8d; font-size: 0.85rem; font-weight: 500; }}
        .card .value {{ font-size: 1.8rem; font-weight: bold; color: #2980b9; }}
        .card .value-small {{ font-size: 1rem; font-weight: 600; color: #2980b9; }}
        .chart {{ background: white; padding: 1.5rem; border-radius: 8px; font-family: ui-monospace, Menlo, monospace; white-space: pre; line-height: 1.5; font-size: 0.85rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        th, td {{ padding: 0.6rem 0.75rem; text-align: left; border-bottom: 1px solid #ecf0f1; font-size: 0.9rem; }}
        th {{ background: #34495e; color: white; font-size: 0.85rem; font-weight: 500; }}
        tr:hover {{ background: #f8f9fa; }}
        footer {{ margin-top: 2rem; color: #95a5a6; font-size: 0.8rem; text-align: center; }}
    </style>
</head>
<body>
    <h1>omostation Governance Dashboard</h1>
    <p class="subtitle">P38-W2 真正落地 | 观测性从可调到可视化 | 数据源: governance-history.jsonl</p>

    <div class="summary">
        <div class="card"><h3>治理历史条数</h3><div class="value">{summary.get('count', 0)}</div></div>
        <div class="card"><h3>独立日期数</h3><div class="value">{summary.get('date_count', 0)}</div></div>
        <div class="card"><h3>平均健康分</h3><div class="value">{avg_score:.1f}</div></div>
        <div class="card"><h3>首次记录</h3><div class="value-small">{first_date}</div></div>
        <div class="card"><h3>最近记录</h3><div class="value-small">{last_date}</div></div>
    </div>

    <h2>健康分趋势 (最近 14 天)</h2>
    <div class="chart">{chart_html}</div>

    <h2>最近 10 条治理历史</h2>
    <table>
        <thead>
        <tr><th>时间</th><th>总分</th><th>等级</th><th>Watchlist</th><th>源</th></tr>
        </thead>
        <tbody>
        {rows_html}
        </tbody>
    </table>

    <footer>
        omostation governance dashboard | 阶段 P38-W2 | 2026-06-07
    </footer>
</body>
</html>"""


class _DashboardHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler: GET / -> 单页 HTML dashboard, GET /health -> ok JSON."""

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler 约定)
        if self.path in ("/", "/index.html"):
            html = render_dashboard_html()
            payload = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/health":
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"not found")

    def log_message(self, fmt, *args) -> None:  # noqa: A003
        # 静默默认 logging 到 stderr, 但保留可见性
        sys.stderr.write(f"[obs-dashboard] {fmt % args}\n")


class _ReusableTCPServer(socketserver.TCPServer):
    """允许端口立即重用, 避免 TIME_WAIT."""

    allow_reuse_address = True


def run_dashboard_server(port: int = 9090, daemon: bool = True) -> int:
    """启 dashboard HTTP server.

    Args:
        port:   监听端口
        daemon: True = serve_forever; False = handle_request 一次后退出
    """
    httpd = _ReusableTCPServer(("0.0.0.0", port), _DashboardHandler)  # noqa: S104
    print(f"omostation dashboard: http://localhost:{port}/", flush=True)
    if daemon:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            httpd.server_close()
    else:
        # 测一次, 跑完就关
        httpd.handle_request()
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI 入口: ``python -m omo.omo_observability_dashboard --port 9090``."""
    parser = argparse.ArgumentParser(
        prog="omo-observability-dashboard",
        description="omostation 观测性 dashboard (基于 governance-history.jsonl)",
    )
    parser.add_argument("--port", type=int, default=9090, help="监听端口 (默认 9090)")
    parser.add_argument(
        "--once",
        action="store_true",
        help="只服务一次请求后退出 (开发/自检用)",
    )
    args = parser.parse_args(argv)
    return run_dashboard_server(port=args.port, daemon=not args.once)


if __name__ == "__main__":
    raise SystemExit(main())
