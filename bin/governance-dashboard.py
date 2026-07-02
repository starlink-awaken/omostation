#!/usr/bin/env python3
"""P86 R4: governance dashboard wrapper.

统一调用 P83-P85 治理工具, 输出一份治理健康仪表盘:
- governance-history insight (P83)
- drift-history insight (P83)
- x2 freshness check (P84)
- x2 rule lint (P85)
- adr coverage (P85)
- management cross-ref (P82+P83)
- mof m2 coverage (P84)

每个工具用 subprocess 调用, 失败继续 (dashboard 不阻塞).
输出: 单页 dashboard, 包含每个工具的关键指标.

使用:
  python3 bin/governance-dashboard.py
  python3 bin/governance-dashboard.py --json
  python3 bin/governance-dashboard.py --tools governance-history,adr-coverage  # 子集
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import statistics
from datetime import datetime, timezone
from pathlib import Path

# 工具注册表: (id, 描述, 默认参数列表)
TOOL_REGISTRY: list[tuple[str, str, str, list[str]]] = [
    # (id, 描述, bin_path, args)
    ("governance-history", "P83 governance 评分历史", "bin/governance-history-insight.py", []),
    ("drift-history", "P83 drift 漂移历史", "bin/drift-history-insight.py", []),
    ("x2-freshness", "P84 X2 freshness 11 规则", "bin/x2-freshness-check.py", []),
    ("x2-rule-lint", "P85 X2 rule schema lint", "bin/x2-rule-lint.py", []),
    ("x2-rule-add", "P87 X2 rule 交互式添加 (template 模式)", "bin/x2-rule-add.py", ["--template"]),
    ("adr-coverage", "P85 ADR 治理健康度", "bin/adr-coverage.py", []),
    ("mof-m2-coverage", "P84 M2 schema coverage 修正版", "bin/mof-m2-coverage.py", []),
    ("management-cross-ref", "P82+P83 management 跨文件引用", "bin/management-cross-ref-check.py", ["."]),
    ("god-module-roadmap", "P87 god-module refactor (示例文件)", "bin/god-module-roadmap.py",
     ["projects/omo/src/omo/omo_lint.py", "--top", "3"]),
    ("governance-trend-report", "P88 governance 趋势 (weekly 窗口)", "bin/governance-trend-report.py",
     ["--window", "weekly"]),
    ("rule-history-insight", "P89 X2 rule 状态洞察", "bin/rule-history-insight.py", []),
    ("adr-drift-check", "P89 ADR 引用 drift (信息性, 全量扫描)", "bin/adr-drift-check.py", []),
    ("adr-drift-classify", "P90 ADR drift 归类 (历史 vs 新增)", "bin/adr-drift-classify.py", []),
    ("governance-history-stats", "P91 gov history 深化 (30 天 + 类别趋势)", "bin/governance-history-stats.py",
     ["--days", "30"]),
    ("adr-trend-insight", "P92 ADR 趋势 (phase 分布 + 提交历史)", "bin/adr-trend-insight.py", []),
    ("adr-drift-auto-fix", "P93 ADR drift 自动归类 (TEMPLATE/SUBDIR/TYPO/REAL)", "bin/adr-drift-auto-fix.py", []),
    ("adr-drift-apply", "P94 ADR drift 应用 (touch SUBDIR_MISSING)", "bin/adr-drift-apply.py", []),
    ("god-module-13-list", "P94 god-module 13 error 清单 (24252L excess)", "bin/god-module-13-error-list.py", []),
    ("venv-yaml-check", "P96 venv 依赖一致性检查 (pyyaml 等)", "bin/venv-yaml-check.py", []),
]


def run_tool(workspace: Path, tool_id: str, bin_path: str, args: list[str]) -> dict:
    """运行单个工具, 返回结果摘要."""
    full_path = workspace / bin_path
    if not full_path.exists():
        return {
            "id": tool_id,
            "ok": False,
            "error": f"tool not found: {bin_path}",
        }
    try:
        result = subprocess.run(
            ["python3", str(full_path)] + args,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=60,
        )
        return {
            "id": tool_id,
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout_lines": len(result.stdout.splitlines()),
            "stderr": result.stderr[:500] if result.stderr else "",
            # 截取 stdout 前 30 行作为预览
            "preview": "\n".join(result.stdout.splitlines()[:30]),
        }
    except subprocess.TimeoutExpired:
        return {"id": tool_id, "ok": False, "error": "timeout (60s)"}
    except Exception as e:
        return {"id": tool_id, "ok": False, "error": str(e)}


# ==========================================
# ADR-0115 Phase 4 续: 完全内联的代码段
# ==========================================

def load_snapshots(root: Path, max_n: int = 30) -> list[dict]:
    """加载最近 N 个 readiness 快照."""
    log_dir = root / ".omo" / "_log"
    if not log_dir.exists():
        return []
    files = sorted(log_dir.glob("readiness-*.json"), reverse=True)[:max_n]
    snaps = []
    for f in reversed(files):
        try:
            with open(f, encoding="utf-8") as fh:
                snaps.append(json.load(fh))
        except Exception:
            pass
    return snaps


def build_summary(snaps: list[dict], root: Path) -> dict:
    """构建 dashboard 摘要."""
    now = datetime.now(timezone.utc).isoformat()
    if not snaps:
        return {
            "generated_at": now,
            "workspace_root": str(root),
            "summary_card": {"score": 0, "grade": "无数据", "trend": "no_data", "alerts": []},
            "dimensions_card": {},
            "alerts_card": load_alerts_card(root),
            "history_card": [],
            "stats": {
                "count": 0,
                "mean": 0.0,
                "median": 0.0,
                "min": 0.0,
                "max": 0.0,
                "stdev": 0.0,
            },
        }

    scores = [s.get("score", 0) for s in snaps]
    last = snaps[-1]

    # 趋势判定
    trend = "insufficient_data"
    if len(scores) >= 4:
        recent = scores[-3:]
        prev = scores[:-3] if len(scores) > 3 else scores
        if statistics.mean(recent) < statistics.mean(prev) - 1.0:
            trend = "declining"
        elif statistics.mean(recent) > statistics.mean(prev) + 1.0:
            trend = "improving"
        else:
            trend = "stable"

    # 异常检测
    alerts = []
    # 1. sudden_drop
    for i in range(1, len(scores)):
        delta = scores[i] - scores[i - 1]
        if delta < -5:
            alerts.append({
                "type": "sudden_drop",
                "severity": "high",
                "from": scores[i - 1],
                "to": scores[i],
                "delta": delta,
                "from_ts": snaps[i - 1].get("timestamp"),
                "to_ts": snaps[i].get("timestamp"),
            })
    # 2. stdev 波动
    stdev = statistics.stdev(scores) if len(scores) > 1 else 0
    if stdev > 3:
        alerts.append({
            "type": "high_volatility",
            "severity": "medium",
            "stdev": round(stdev, 2),
            "samples": len(scores),
        })
    # 3. mean < 90
    mean = statistics.mean(scores)
    if mean < 90:
        alerts.append({
            "type": "low_mean",
            "severity": "high",
            "mean": round(mean, 1),
        })

    # summary_card
    summary_card = {
        "score": last.get("score", 0),
        "grade": last.get("grade", ""),
        "phase": last.get("phase", ""),
        "trend": trend,
        "snapshot_count": len(snaps),
        "last_update": last.get("timestamp", ""),
        "alerts": alerts,
    }

    # dimensions_card (5 维)
    dimensions_card = {}
    for dim_name, dim_data in last.get("dimensions", {}).items():
        dimensions_card[dim_name] = {
            "score": dim_data.get("score"),
            "max": dim_data.get("max"),
            "metric": dim_data.get("metric"),
            "percent": round(dim_data.get("score", 0) / max(dim_data.get("max", 1), 1) * 100, 1),
        }

    # history_card (最近 5 快照)
    history_card = [
        {
            "timestamp": s.get("timestamp"),
            "score": s.get("score"),
            "grade": s.get("grade"),
        }
        for s in snaps[-5:]
    ]

    return {
        "generated_at": now,
        "workspace_root": str(root),
        "summary_card": summary_card,
        "dimensions_card": dimensions_card,
        "alerts_card": load_alerts_card(root),
        "history_card": history_card,
        "stats": {
            "count": len(scores),
            "mean": round(mean, 1),
            "median": statistics.median(scores),
            "min": min(scores),
            "max": max(scores),
            "stdev": round(stdev, 2),
        },
    }


def load_alerts_card(root: Path, hours: int = 24) -> dict:
    """告警卡片数据 — 24h 通知 + 抑制统计."""
    from datetime import timedelta
    notif_log = root / ".omo" / "_log" / "alert-notifications.jsonl"
    supp_log = root / ".omo" / "_log" / "alert-suppressions.jsonl"
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    def load_recent(path: Path) -> list[dict]:
        records = []
        if not path.exists():
            return records
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        ts = rec.get("timestamp", "")
                        if ts:
                            rec_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                            if rec_dt >= cutoff:
                                records.append(rec)
                    except Exception:
                        pass
        except Exception:
            pass
        return records

    notifs = load_recent(notif_log)
    supps = load_recent(supp_log)
    total = len(notifs) + len(supps)
    supp_rate = (len(supps) / total) if total > 0 else 0.0
    by_level = {}
    for rec in notifs:
        level = rec.get("level", "?")
        by_level[level] = by_level.get(level, 0) + 1
    return {
        "window_hours": hours,
        "notifications": len(notifs),
        "suppressions": len(supps),
        "suppression_rate": round(supp_rate, 3),
        "by_level": by_level,
    }


def _cmd_readiness_summary(workspace: Path, fmt: str = "json", output_file: str | None = None) -> int:
    """ADR-0115 Phase 4: 完全内联 dashboard-readiness-summary.py."""
    snaps = load_snapshots(workspace)
    summary = build_summary(snaps, workspace)

    if fmt == "json":
        output = json.dumps(summary, indent=2, ensure_ascii=False)
    else:
        sc = summary["summary_card"]
        lines = [
            "=" * 60,
            f"📊 governance readiness 摘要 @ {summary['generated_at']}",
            "=" * 60,
            f"  Score: {sc['score']}/100  Grade: {sc['grade']}",
            f"  Phase: {sc.get('phase', '')}  Trend: {sc['trend']}",
            f"  Snapshots: {sc.get('snapshot_count', 0)}  Last: {sc.get('last_update', '')}",
            f"  Alerts: {len(sc['alerts'])}",
            "",
            "--- 5 维度 ---",
        ]
        for name, d in summary["dimensions_card"].items():
            lines.append(f"  {name:<20s} {d['score']:>3d}/{d['max']:<3d} ({d['percent']:.1f}%)  metric={d['metric']}")
        ac = summary["alerts_card"]
        lines.append("")
        lines.append("--- 告警 (24h) ---")
        lines.append(f"  通知: {ac['notifications']}  抑制: {ac['suppressions']}  抑制率: {ac['suppression_rate'] * 100:.1f}%")
        if ac["by_level"]:
            levels = " ".join(f"{k}={v}" for k, v in sorted(ac["by_level"].items()))
            lines.append(f"  按级别: {levels}")
        output = "\n".join(lines)

    if output_file:
        # audit-exempt: non-atomic-write — dashboard output, low risk
        Path(output_file).write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


def render_html(data: dict) -> str:
    """渲染 HTML 页面."""
    sc = data.get("summary_card", {})
    dc = data.get("dimensions_card", {})
    ac = data.get("alerts_card", {})
    hc = data.get("history_card", [])

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


def _cmd_ui_render(workspace: Path, output_html: str | None = None, open_browser: bool = False) -> int:
    """ADR-0115 Phase 4: 完全内联 dashboard-ui-render.py."""
    snaps = load_snapshots(workspace)
    data = build_summary(snaps, workspace)
    html = render_html(data)

    if output_html:
        out_path = Path(output_html)
        if not out_path.is_absolute():
            out_path = workspace / output_html
        # audit-exempt: non-atomic-write — dashboard output, low risk
        out_path.write_text(html, encoding="utf-8")
        print(f"✅ 已写入 {output_html}")
        if open_browser:
            try:
                subprocess.run(["open", str(out_path)], check=False)
            except Exception:
                pass
    else:
        print(html)
    return 0


def run_healthcheck(workspace: Path) -> dict:
    """跑 gac-healthcheck --json, 返回报告."""
    r = subprocess.run(
        [sys.executable, str(workspace / "bin" / "gac-healthcheck.py"), "--json"],
        capture_output=True,
        text=True,
        cwd=str(workspace),
    )
    try:
        return json.loads(r.stdout) if r.stdout else {}
    except json.JSONDecodeError:
        return {}


def generate_gac_html(report: dict) -> str:
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
<p style="color:#999">ADR-0106 · {report.get("timestamp", "")} · 生成自 bin/governance-dashboard.py</p>

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
<span class="tag">governance-dashboard 📊</span>
</p>
</div>

<div class="card">
<h3>📐 7 动态一致性机制</h3>
<p><span class="tag">1 声明式 ✅</span> <span class="tag">2 schema ✅</span> <span class="tag">3 泛化执行器 🟡(hook✅/MCP待)</span> <span class="tag">4 drift ✅</span> <span class="tag">5 矛盾 ✅</span> <span class="tag">6 lifecycle ✅</span> <span class="tag">7 MOF 🟡(M2✅/集成待)</span></p>
</div>

<p style="color:#bbb;margin-top:40px;font-size:12px">GaC 治理即代码 · 北极星 NORTH-STAR.md · 元治理递归 (GaC 治 GaC)</p>
</body></html>"""


def _cmd_gac_html(workspace: Path, output_html: str | None, open_browser: bool, output_json: bool = False) -> int:
    """ADR-0115 Phase 4 续: 完全内联 bin/gac-dashboard.py."""
    report = run_healthcheck(workspace)

    if output_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    html = generate_gac_html(report)

    # 默认输出路径为 .omo/_delivery/gac-dashboard.html
    target = Path(output_html) if output_html else (workspace / ".omo" / "_delivery" / "gac-dashboard.html")
    if not target.is_absolute():
        target = workspace / target

    target.parent.mkdir(parents=True, exist_ok=True)
    # audit-exempt: non-atomic-write — dashboard output, low risk
    target.write_text(html, encoding="utf-8")

    healthy = report.get("healthy", False)
    try:
        rel = target.relative_to(workspace)
    except ValueError:
        rel = target

    print(f"✅ GaC 仪表盘生成: {rel}")
    print(
        f"   总体: {'✅ 全绿' if healthy else '❌ 有红'} | "
        f"规则 {report.get('coverage', {}).get('rules', 0)} | "
        f"drift {report.get('drift', {}).get('drift_count', 0)}"
    )

    if open_browser:
        try:
            subprocess.run(["open", str(target)], check=False)
        except Exception:
            pass

    return 0 if healthy else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="P86: governance dashboard")
    parser.root_default = "."
    parser.add_argument("--root", default=".", help="workspace root")
    parser.add_argument("--tools", default=None,
                        help="逗号分隔的 tool id 子集 (默认全部)")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    # ADR-0115 Phase 4 (partial): 2 合并的 dashboard 子命令
    parser.add_argument("--readiness-summary", action="store_true",
                        help="合并 dashboard-readiness-summary 功能")
    # 新增对 format 和 output 的处理, 保持对 cockpit-readiness 的兼容
    parser.add_argument("--format", choices=["json", "text"], default="json",
                        help="readiness-summary 输出格式")
    parser.add_argument("--output", help="readiness-summary / ui-render / gac-html 输出到指定文件")
    parser.add_argument("--ui-render", action="store_true",
                        help="合并 dashboard-ui-render 功能, 输出到 HTML 文件 (配合 --output / stdout)")
    # ADR-0115 Phase 4 续: 合并 gac-dashboard
    parser.add_argument("--gac-html", action="store_true",
                        help="合并 gac-dashboard 功能, 输出到 HTML 文件 (配合 --output / stdout)")
    parser.add_argument("--gac-open", action="store_true",
                        help="合并 gac-dashboard 功能, 生成 + 浏览器打开")
    args = parser.parse_args()

    workspace = Path(args.root).resolve()
    if not (workspace / ".omo").exists():
        print(f"❌ {workspace} 不存在 .omo")
        return 1

    # ADR-0115 Phase 4: 合并 dashboard-readiness-summary 子命令
    if args.readiness_summary:
        return _cmd_readiness_summary(workspace, fmt=args.format, output_file=args.output)

    # ADR-0115 Phase 4: 合并 dashboard-ui-render 子命令
    if args.ui_render:
        return _cmd_ui_render(workspace, output_html=args.output, open_browser=args.gac_open)

    # ADR-0115 Phase 4 续: 合并 gac-dashboard 子命令
    if args.gac_html or args.gac_open:
        # 如果有 --json 则输出 json
        return _cmd_gac_html(workspace, output_html=args.output, open_browser=args.gac_open, output_json=args.json)

    # 默认: 原 P86 仪表盘 (调用 19 个治理工具)

    # 选择工具
    selected = set(args.tools.split(",")) if args.tools else None
    tools_to_run = [
        (tid, desc, bp, a)
        for tid, desc, bp, a in TOOL_REGISTRY
        if selected is None or tid in selected
    ]

    print("=" * 60)
    print("📊 P86 governance dashboard")
    print("=" * 60)
    print(f"🔧 工具数: {len(tools_to_run)}")
    print()

    results: list[dict] = []
    for tid, desc, bp, tool_args in tools_to_run:
        result = run_tool(workspace, tid, bp, tool_args)
        result["description"] = desc
        result["path"] = bp
        results.append(result)
        icon = "✅" if result["ok"] else "❌"
        print(f"  {icon} {tid:<25s} ({desc})")
        if not result["ok"]:
            err = result.get("error") or result.get("stderr", "")[:200]
            if err:
                print(f"      ⚠️  {err.splitlines()[0] if err else '(unknown)'}")

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0

    # 汇总
    print()
    print("=" * 60)
    print("📈 治理工具健康度")
    print("=" * 60)
    ok = sum(1 for r in results if r["ok"])
    fail = len(results) - ok
    print(f"✅ OK: {ok} / {len(results)}")
    print(f"❌ FAIL: {fail}")
    if fail == 0:
        print("\n🎉 所有治理工具通过!")
        return 0
    print(f"\n⚠️  {fail} 个工具失败, 详情见上面 output")
    return 1


if __name__ == "__main__":
    sys.exit(main())
