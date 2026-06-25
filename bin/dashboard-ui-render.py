#!/usr/bin/env python3
"""P81 R2: dashboard 卡片 UI 渲染.

读 dashboard-readiness-summary 输出, 渲染为独立 HTML 页面 (rich 风格):
- 6 卡片网格: summary / dimensions / alerts / history
- 渐变色按 score 评分
- 响应式布局
- 离线友好 (无外部 CDN)

使用:
  python3 bin/dashboard-ui-render.py > /tmp/dashboard.html
  python3 bin/dashboard-ui-render.py --output /tmp/dashboard.html
  python3 bin/dashboard-ui-render.py --open    # macOS open
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def render_html(data: dict) -> str:
    """渲染 HTML 页面."""
    sc = data.get("summary_card", {})
    dc = data.get("dimensions_card", {})
    ac = data.get("alerts_card", {})
    hc = data.get("history_card", [])
    stats = data.get("stats", {})

    score = sc.get("score", 0)
    grade = sc.get("grade", "?")
    if score >= 100:
        color = "#10b981"  # 绿
    elif score >= 90:
        color = "#3b82f6"  # 蓝
    elif score >= 80:
        color = "#f59e0b"  # 黄
    else:
        color = "#ef4444"  # 红

    dim_rows = ""
    for name, d in dc.items():
        pct = d.get("percent", 0)
        bar_color = "#10b981" if pct >= 100 else "#3b82f6" if pct >= 80 else "#f59e0b"
        dim_rows += f"""
        <tr>
            <td><strong>{name}</strong></td>
            <td>{d.get('score', 0)}/{d.get('max', '?')}</td>
            <td>{pct:.1f}%</td>
            <td>metric={d.get('metric', '?')}</td>
            <td><div class="bar"><div class="bar-fill" style="width:{pct}%;background:{bar_color}"></div></div></td>
        </tr>"""

    history_rows = ""
    for h in hc:
        history_rows += f"<tr><td>{h.get('timestamp', '?')}</td><td>{h.get('score', '?')}</td><td>{h.get('grade', '?')}</td></tr>"

    alert_info = f"""
    <div class="card">
        <h2>告警 (24h)</h2>
        <p><strong>通知:</strong> {ac.get('notifications', 0)} | <strong>抑制:</strong> {ac.get('suppressions', 0)} | <strong>抑制率:</strong> {ac.get('suppression_rate', 0) * 100:.1f}%</p>
        {f"<p>{ac.get('level_reason', '')}</p>" if ac.get('level_reason') else ''}
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>P81 dashboard - governance readiness</title>
<style>
  body {{ font-family: -apple-system, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 24px; }}
  h1 {{ color: {color}; font-size: 48px; margin: 0; }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; margin-top: 24px; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; }}
  .card h2 {{ margin-top: 0; color: #94a3b8; font-size: 14px; text-transform: uppercase; }}
  .big {{ font-size: 64px; font-weight: bold; color: {color}; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #334155; }}
  th {{ color: #94a3b8; font-size: 12px; }}
  .bar {{ height: 6px; background: #334155; border-radius: 3px; overflow: hidden; }}
  .bar-fill {{ height: 100%; }}
  .meta {{ color: #64748b; font-size: 12px; margin-top: 16px; }}
</style>
</head>
<body>
<div class="container">
  <h1>📊 governance readiness</h1>
  <p class="meta">趋势: {sc.get('trend', '?')} | 快照数: {sc.get('snapshot_count', 0)} | 最后: {sc.get('last_update', '?')}</p>
  <div class="grid">
    <div class="card">
      <h2>总分</h2>
      <div class="big">{score}</div>
      <p>{grade}</p>
    </div>
    <div class="card">
      <h2>5 维度</h2>
      <table>{dim_rows}</table>
    </div>
    {alert_info}
    <div class="card">
      <h2>历史快照</h2>
      <table>{history_rows}</table>
    </div>
  </div>
</div>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P81: dashboard 卡片 UI 渲染 (独立 HTML)"
    )
    parser.add_argument("root", nargs="?", default=".", help="workspace root")
    parser.add_argument("--output", help="输出文件 (默认 stdout)")
    parser.add_argument("--open", action="store_true", help="输出后用 macOS open 打开")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    summary_tool = root / "bin" / "dashboard-readiness-summary.py"
    if not summary_tool.exists():
        print(f"❌ {summary_tool} 不存在")
        return 1

    # 调 dashboard-readiness-summary.py 拿 JSON
    try:
        r = subprocess.run(
            ["python3", str(summary_tool), "--format", "json"],
            capture_output=True, text=True, cwd=str(root), timeout=60,
        )
        if r.returncode != 0:
            print(f"❌ dashboard-readiness-summary 失败: {r.stderr}")
            return 1
        data = json.loads(r.stdout)
    except Exception as e:
        print(f"❌ 错误: {e}")
        return 1

    html = render_html(data)
    if args.output:
        Path(args.output).write_text(html, encoding="utf-8")
        print(f"✅ 已写入 {args.output}")
        if args.open:
            try:
                subprocess.run(["open", args.output], check=False)
            except FileNotFoundError:
                pass
    else:
        print(html)
    return 0


if __name__ == "__main__":
    sys.exit(main())