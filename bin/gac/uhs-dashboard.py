#!/usr/bin/env python3
"""UHS Dashboard — 统一健康评分趋势仪表盘.

启动一个本地 Web 服务器, 展示 UHS 6 维度趋势.
用法:
    python3 uhs-dashboard.py              # 启动服务器 (默认端口 8899)
    python3 uhs-dashboard.py --port 9000  # 指定端口
"""

import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse

REPO = Path(__file__).resolve().parents[1]  # bin/gac/ → Workspace/
HISTORY_FILE = REPO / ".omo/state/history/uhs.jsonl"
TARGETS = {
    "tools": 90,
    "governance": 95,
    "scenes": 87,
    "docs": 90,
    "value": 85,
    "runtime": 95,
}
WEIGHTS = {
    "tools": 0.20,
    "governance": 0.20,
    "scenes": 0.15,
    "docs": 0.10,
    "value": 0.25,
    "runtime": 0.10,
}


def load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    records = []
    with open(HISTORY_FILE) as f:
        for line in f:
            try:
                records.append(json.loads(line.strip()))
            except Exception:
                continue
    return records


def get_latest() -> dict | None:
    history = load_history()
    return history[-1] if history else None


def generate_html() -> str:
    latest = get_latest()
    history = load_history()

    # 生成趋势数据 (JSON for Chart.js)
    labels = [r.get("timestamp", "")[:10] for r in history]
    datasets = {}
    for dim in WEIGHTS:
        datasets[dim] = [r.get(dim, 0) for r in history]

    # 当前分数
    current_scores = {dim: latest.get(dim, 0) if latest else 0 for dim in WEIGHTS}
    uhs = round(sum(WEIGHTS[k] * current_scores[k] for k in WEIGHTS), 1) if latest else 0

    # 生成 HTML
    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UHS Dashboard — 统一健康评分</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
        .uhs-score {{ font-size: 48px; font-weight: bold; color: {'#22c55e' if uhs >= 90 else '#f59e0b' if uhs >= 80 else '#ef4444'}; }}
        .uhs-grade {{ font-size: 24px; color: #666; }}
        .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px; }}
        .card {{ background: white; border-radius: 8px; padding: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .card-title {{ font-size: 12px; color: #666; text-transform: uppercase; }}
        .card-value {{ font-size: 28px; font-weight: bold; margin: 5px 0; }}
        .card-target {{ font-size: 12px; color: #999; }}
        .card-status {{ font-size: 14px; margin-top: 5px; }}
        .status-pass {{ color: #22c55e; }}
        .status-fail {{ color: #ef4444; }}
        .chart-container {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        .gaps {{ background: white; border-radius: 8px; padding: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .gap-item {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>UHS Dashboard</h1>
                <p style="color: #666;">统一健康评分 — 最后更新: {latest.get('timestamp', 'N/A')[:19] if latest else 'N/A'}</p>
            </div>
            <div style="text-align: right;">
                <div class="uhs-score">{uhs}</div>
                <div class="uhs-grade">/ 100 (Grade: {'A' if uhs >= 90 else 'B' if uhs >= 80 else 'C' if uhs >= 70 else 'D'})</div>
            </div>
        </div>

        <div class="grid">
            {"".join(f'''
            <div class="card">
                <div class="card-title">{dim.upper()}</div>
                <div class="card-value" style="color: {'#22c55e' if current_scores[dim] >= TARGETS[dim] else '#ef4444'}">{current_scores[dim]}%</div>
                <div class="card-target">目标: {TARGETS[dim]}%</div>
                <div class="card-status {'status-pass' if current_scores[dim] >= TARGETS[dim] else 'status-fail'}">{'✓ 达标' if current_scores[dim] >= TARGETS[dim] else f'↓ {TARGETS[dim] - current_scores[dim]:.1f}'}</div>
            </div>
            ''' for dim in WEIGHTS)}
        </div>

        <div class="chart-container">
            <h3>趋势 (最近 30 天)</h3>
            <canvas id="trendChart" height="100"></canvas>
        </div>

        <div class="gaps">
            <h3>差距分析</h3>
            {''.join(f'<div class="gap-item"><span>{dim}</span><span style="color: #ef4444">需 +{TARGETS[dim] - current_scores[dim]:.1f} 点</span></div>' for dim in WEIGHTS if current_scores[dim] < TARGETS[dim]) if any(current_scores[dim] < TARGETS[dim] for dim in WEIGHTS) else '<p style="color: #22c55e;">✓ 所有维度已达标!</p>'}
        </div>
    </div>

    <script>
        const ctx = document.getElementById('trendChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(labels[-30:])},
                datasets: [
                    {''.join(f'''
                    {{
                        label: '{dim}',
                        data: {json.dumps(datasets[dim][-30:])},
                        borderColor: {'#3b82f6' if i == 0 else '#10b981' if i == 1 else '#f59e0b' if i == 2 else '#ef4444' if i == 3 else '#8b5cf6' if i == 4 else '#06b6d4'},
                        tension: 0.3,
                    }},''' for i, dim in enumerate(WEIGHTS))}
                ]
            }},
            options: {{
                responsive: true,
                scales: {{
                    y: {{ min: 0, max: 100 }}
                }}
            }}
        }});
    </script>
</body>
</html>"""
    return html


class UHSHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            html = generate_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())
        elif self.path == "/api/uhs":
            latest = get_latest()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(latest or {}).encode())
        elif self.path == "/api/history":
            history = load_history()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(history).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # 静默日志


def main():
    import argparse
    parser = argparse.ArgumentParser(description="UHS Dashboard")
    parser.add_argument("--port", type=int, default=8899)
    args = parser.parse_args()

    server = HTTPServer(("127.0.0.1", args.port), UHSHandler)
    print(f"UHS Dashboard running at http://127.0.0.1:{args.port}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")


if __name__ == "__main__":
    sys.exit(main())
