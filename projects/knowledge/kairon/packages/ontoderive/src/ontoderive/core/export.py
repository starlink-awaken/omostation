"""
多格式导出 — HTML / JSON / Markdown
=====================================
将OntoDerive推导结果导出为可浏览器查看的HTML报告或结构化JSON。
内联CSS, 零外部依赖, 单文件自包含。
"""

import json


def to_html(summary: dict, project_name: str = "") -> str:
    """生成单文件HTML报告"""
    cs = summary.get("derived_conclusions", [])
    hints = summary.get("derivation_hints", [])
    conf_dist = summary.get("confidence_distribution", {})

    # 按来源/类型分组
    by_source: dict[str, list[dict]] = {}
    for c in cs:
        src = c.get("source", "?")
        by_source.setdefault(src, []).append(c)

    rows = []
    for src, items in by_source.items():
        for c in items:
            trail = c.get("derivation_trail", "?")
            conf = c.get("confidence", 0)
            conf_color = "#22c55e" if conf >= 0.85 else ("#f59e0b" if conf >= 0.7 else "#ef4444")
            rows.append(f"""
            <tr>
              <td class="src">{src}</td>
              <td class="trail">{trail}</td>
              <td class="conc">{c.get("conclusion", "")[:200]}</td>
              <td class="conf"><span style="color:{conf_color}">{conf:.0%}</span></td>
            </tr>""")

    hint_html = "".join(f"<li>{h}</li>" for h in hints[:10]) if hints else "<li>无结构提示</li>"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>OntoDerive 分析报告{f" — {project_name}" if project_name else ""}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font:14px/1.6 -apple-system,BlinkMacSystemFont,sans-serif;background:#f8fafc;color:#1e293b;padding:20px}}
h1{{font-size:20px;margin-bottom:8px}}h2{{font-size:16px;margin:20px 0 8px;color:#64748b}}
.stats{{display:flex;gap:16px;margin:12px 0;flex-wrap:wrap}}
.stat{{
  background:#fff;border-radius:8px;padding:12px 18px;
  box-shadow:0 1px 3px rgba(0,0,0,.06)
}}
.stat b{{display:block;font-size:22px;color:#2563eb}}.stat s{{font-size:11px;color:#94a3b8}}
table{{
  width:100%;border-collapse:collapse;background:#fff;border-radius:8px;
  overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.06)
}}
th{{background:#f1f5f9;text-align:left;padding:8px 12px;font-size:12px;color:#64748b}}
td{{padding:8px 12px;border-top:1px solid #f1f5f9;font-size:13px}}
.src{{width:80px;color:#6366f1;font-size:11px}}
.trail{{width:100px;font:11px monospace;color:#94a3b8}}
.conf{{width:50px;text-align:right;font-weight:600}}
.hints{{background:#fff;border-radius:8px;padding:12px 18px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.hints li{{font-size:12px;color:#475569;margin:4px 0}}
</style>
</head>
<body>
<h1>OntoDerive 分析报告{f" — {project_name}" if project_name else ""}</h1>
<div class="stats">
  <div class="stat"><b>{summary.get("facts", 0)}</b><s>事实</s></div>
  <div class="stat"><b>{summary.get("entities", 0)}</b><s>实体</s></div>
  <div class="stat"><b>{summary.get("inferences", 0)}</b><s>推论</s></div>
  <div class="stat"><b>{len(cs)}</b><s>结论</s></div>
  <div class="stat"><b>{conf_dist.get("mean", 0):.2f}</b><s>均置信度</s></div>
</div>
<h2>推导结论 ({len(cs)}条)</h2>
<table><thead><tr><th>来源</th><th>推导链</th><th>结论</th><th>置信度</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>
<h2>结构提示</h2>
<div class="hints"><ul>{hint_html}</ul></div>
</body></html>"""


def to_json(summary: dict) -> str:
    return json.dumps(summary, ensure_ascii=False, indent=2)


def to_markdown(summary: dict, project_name: str = "") -> str:
    lines = [f"# OntoDerive 推导报告{f' — {project_name}' if project_name else ''}\n"]
    lines.append(
        f"事实:{summary.get('facts', 0)} | 实体:{summary.get('entities', 0)} | 推论:{summary.get('inferences', 0)}\n"
    )
    for c in summary.get("derived_conclusions", []):
        trail = c.get("derivation_trail", "?")
        conf = c.get("confidence", 0)
        lines.append(f"- [{trail}] {c.get('conclusion', '')[:150]} (置信度:{conf:.0%})")
    return "\n".join(lines)
