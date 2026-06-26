#!/usr/bin/env python3
"""GaC 仪表盘 HTML 生成器 (ADR-0106, 阶段 4 可视化原型).

生成 GaC 体系状态 HTML (读 gac-healthcheck --json), 浏览器打开看.
阶段 4 仪表盘的**可视化原型** (独立 HTML, 不依赖 cockpit 前端/TS 构建).

用法:
  python3 bin/gac-dashboard.py              # 生成 .omo/_delivery/gac-dashboard.html
  python3 bin/gac-dashboard.py --open       # 生成 + 浏览器打开 (macOS)
  python3 bin/gac-dashboard.py --json       # JSON (仪表盘数据, cockpit 前端用)

CI 可移植: Path(__file__).resolve().parents[1]. 数据源 gac-healthcheck --json.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
OUTPUT = WORKSPACE / ".omo" / "_delivery" / "gac-dashboard.html"


def run_healthcheck() -> dict:
    """跑 gac-healthcheck --json, 返回报告."""
    r = subprocess.run(
        [sys.executable, str(WORKSPACE / "bin" / "gac-healthcheck.py"), "--json"],
        capture_output=True,
        text=True,
        cwd=WORKSPACE,
    )
    try:
        return json.loads(r.stdout) if r.stdout else {}
    except json.JSONDecodeError:
        return {}


def generate_html(report: dict) -> str:
    """生成仪表盘 HTML (读 healthcheck 报告)."""
    healthy = report.get("healthy", False)
    color = "#4caf50" if healthy else "#f44336"
    overall = "✅ 全绿 (闭环生效)" if healthy else "❌ 有红 (见检查)"
    coverage = report.get("coverage", {})
    dims = coverage.get("dimension", {})
    layers = coverage.get("layer", {})
    drift = report.get("drift", {})
    validate = report.get("validate", {})
    m2 = report.get("m2_type", {})
    files = report.get("files", {})

    dim_tags = "".join(
        f'<span class="tag">{d}</span><b>{n}</b> ' for d, n in dims.items()
    )
    layer_tags = "".join(
        f'<span class="tag">{layer}</span><b>{n}</b> ' for layer, n in layers.items()
    )
    drift_closed = " (闭环归零)" if drift.get("drift_count", 1) == 0 else ""

    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>GaC 仪表盘</title>
<style>
body {{ font-family: -apple-system, "PingFang SC", sans-serif; margin: 40px; background: #fafafa; color: #333; }}
h1 {{ color: #2c3e50; }}
.card {{ background: white; border-radius: 8px; padding: 20px 24px; margin: 16px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.08); }}
.metric {{ display: inline-block; margin: 0 24px 0 0; text-align: center; }}
.metric .v {{ font-size: 36px; font-weight: bold; color: {color}; }}
.metric .l {{ font-size: 12px; color: #888; margin-top: 4px; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 8px; }}
td, th {{ border: 1px solid #e0e0e0; padding: 8px 12px; text-align: left; }}
th {{ background: #f5f5f5; font-size: 13px; }}
.tag {{ display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 11px; background: #e3f2fd; color: #1565c0; margin: 2px; }}
b {{ color: #2c3e50; }}
.ok {{ color: #4caf50; font-weight: bold; }}
.warn {{ color: #ff9800; font-weight: bold; }}
.fail {{ color: #f44336; font-weight: bold; }}
</style></head><body>

<h1>🛡️ GaC 治理即代码 仪表盘</h1>
<p style="color:#999">ADR-0106 · {report.get("timestamp", "")} · 生成自 bin/gac-dashboard.py</p>

<div class="card">
<h2 style="color:{color}">总体: {overall}</h2>
<div class="metric"><div class="v">{coverage.get("rules", 0)}</div><div class="l">规则数</div></div>
<div class="metric"><div class="v">{drift.get("drift_count", 0)}</div><div class="l">drift 数{drift_closed}</div></div>
<div class="metric"><div class="v">{files.get("ok", 0)}/{files.get("total", 0)}</div><div class="l">核心文件</div></div>
<div class="metric"><div class="v">{m2.get("fields", 0)}</div><div class="l">M2 字段</div></div>
</div>

<div class="card">
<h3>📊 Dimension 覆盖 (X1-X4)</h3>
<p>{dim_tags}</p>
<h3>📊 Layer 覆盖 (M0-L3-meta)</h3>
<p>{layer_tags}</p>
</div>

<div class="card">
<h3>🔍 引擎检查 (机制 2/4/5/6/7)</h3>
<table>
<tr><th>检查</th><th>状态</th><th>详情</th></tr>
<tr><td>gac-validate <span class="tag">机制2/5/6</span></td>
<td class="{"ok" if validate.get("ok") else "fail"}">{"✅" if validate.get("ok") else "❌"}</td>
<td>errors={validate.get("errors", 0)} warnings={validate.get("warnings", 0)}</td></tr>
<tr><td>gac-drift <span class="tag">机制4</span></td>
<td class="{"ok" if drift.get("drift_count", 1) == 0 else "warn"}">{"✅" if drift.get("drift_count", 1) == 0 else "⚠️"}</td>
<td>drift_count={drift.get("drift_count", 0)} {drift_closed}</td></tr>
<tr><td>GacRule M2 <span class="tag">机制7</span></td>
<td class="{"ok" if m2.get("ok") else "fail"}">{"✅" if m2.get("ok") else "❌"}</td>
<td>fields={m2.get("fields", 0)} 状态机={m2.get("states", 0)} 机制={m2.get("mechanisms", 0)}</td></tr>
<tr><td>ADR 引用一致 <span class="tag">X4</span></td>
<td class="{"ok" if report.get("adr_residue_0104", 1) == 0 else "fail"}">{"✅" if report.get("adr_residue_0104", 1) == 0 else "❌"}</td>
<td>0104 残留={report.get("adr_residue_0104", 0)}</td></tr>
</table>
</div>

<div class="card">
<h3>🛠️ GaC 引擎 (6 工具)</h3>
<p>
<span class="tag">gac-validate 🔍</span>
<span class="tag">gac-drift 📡</span>
<span class="tag">gac-healthcheck 🏥</span>
<span class="tag">gac-gc ♻️</span>
<span class="tag">gac-hook-pre-edit 🪝</span>
<span class="tag">gac-dashboard 📊</span>
</p>
</div>

<div class="card">
<h3>📐 7 动态一致性机制</h3>
<p><span class="tag">1 声明式 ✅</span> <span class="tag">2 schema ✅</span> <span class="tag">3 泛化执行器 🟡(hook✅/MCP待)</span> <span class="tag">4 drift ✅</span> <span class="tag">5 矛盾 ✅</span> <span class="tag">6 lifecycle ✅</span> <span class="tag">7 MOF 🟡(M2✅/集成待)</span></p>
</div>

<p style="color:#bbb;margin-top:40px;font-size:12px">GaC 治理即代码 · 北极星 NORTH-STAR.md · 元治理递归 (GaC 治 GaC)</p>
</body></html>"""


def main() -> int:
    args = sys.argv[1:]
    report = run_healthcheck()

    if "--json" in args:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    html = generate_html(report)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    healthy = report.get("healthy", False)
    print(f"✅ GaC 仪表盘生成: {OUTPUT.relative_to(WORKSPACE)}")
    print(
        f"   总体: {'✅ 全绿' if healthy else '❌ 有红'} | "
        f"规则 {report.get('coverage', {}).get('rules', 0)} | "
        f"drift {report.get('drift', {}).get('drift_count', 0)}"
    )

    if "--open" in args:
        subprocess.run(["open", str(OUTPUT)])  # macOS

    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
