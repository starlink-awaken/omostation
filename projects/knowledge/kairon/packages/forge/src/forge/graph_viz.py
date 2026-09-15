#!/usr/bin/env python3
"""
graph_viz.py — T8.1 图谱可视化
从 graph.json 生成 HTML（vis-network）或 Mermaid 图表
"""

import json
import sys
from collections import Counter
from pathlib import Path

# 节点配色和大小常量
COLOR_MAP = {
    "Tool": "#4a90d9",
    "Capability": "#50c878",
    "Knowledge": "#f0c040",
    "Skill": "#9b59b6",
    "Gap": "#e74c3c",
    "Provider": "#95a5a6",
    "Category": "#e67e22",
}
SIZE_MAP = {
    "Tool": 25,
    "Capability": 15,
    "Knowledge": 20,
    "Skill": 20,
    "Gap": 18,
    "Provider": 12,
    "Category": 12,
}

LEGEND_ITEMS = [
    ("#4a90d9", "工具"),
    ("#50c878", "能力"),
    ("#f0c040", "知识"),
    ("#9b59b6", "技能"),
    ("#e74c3c", "缺口"),
    ("#95a5a6", "供应商"),
    ("#e67e22", "分类"),
]

NODE_TYPE_KEYS = ["Tool", "Knowledge", "Skill", "Capability", "Gap", "Category", "Provider"]


def mermaid_id(s: str) -> str:
    """将节点 ID 转为 Mermaid 安全的标识符"""
    return s.replace("-", "_").replace(":", "_")


def generate_html(graph_path: str, output: str) -> None:
    """生成自包含 HTML 可视化页面"""
    g = json.loads(Path(graph_path).read_text())

    nodes_json = []
    for n in g["nodes"]:
        nodes_json.append(
            {
                "id": n["id"],
                "label": n["label"][:30],
                "title": f"{n['type']}: {n['label']}",
                "color": COLOR_MAP.get(n["type"], "#999"),
                "size": SIZE_MAP.get(n["type"], 15),
                "group": n["type"],
            }
        )

    edges_json = [
        {"from": e["source"], "to": e["target"], "label": e["relation"][:15], "arrows": "to"} for e in g["edges"]
    ]

    stats = g.get("stats", {})

    legend_html = "".join(
        f'<span class="legend-item"><span class="legend-dot" style="background:{c}"></span>{label}</span>'
        for c, label in LEGEND_ITEMS
    )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Forge 知识图谱</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
  body {{ margin:0; font-family:sans-serif; }}
  #controls {{ padding:10px 20px; background:#f5f5f5; border-bottom:1px solid #ddd; }}
  #search {{ padding:6px 12px; width:300px; font-size:14px; }}
  #stats {{ display:inline-block; margin-left:20px; color:#666; font-size:13px; }}
  #legend {{ display:inline-block; margin-left:20px; }}
  .legend-item {{ display:inline-block; margin:0 8px; font-size:12px; }}
  .legend-dot {{ display:inline-block; width:12px; height:12px; border-radius:50%;
    margin-right:4px; vertical-align:middle; }}
  #network {{ width:100%; height:calc(100vh - 60px); }}
</style></head><body>
<div id="controls">
  <input id="search" type="text" placeholder="搜索节点..." oninput="searchNodes(this.value)">
  <span id="stats">节点 {stats.get("total_nodes", 0)} | 边 {stats.get("total_edges", 0)}</span>
  <span id="legend">{legend_html}</span>
</div>
<div id="network"></div>
<script>
  const nodes = new vis.DataSet({json.loads(json.dumps(nodes_json))});
  const edges = new vis.DataSet({json.loads(json.dumps(edges_json))});
  const container = document.getElementById('network');
  const data = {{ nodes, edges }};
  const options = {{
    physics: {{ stabilization: {{ iterations: 100 }} }},
    interaction: {{ hover: true, tooltipDelay: 200, navigationButtons: true, keyboard: true }},
    edges: {{ smooth: true, font: {{ size: 10, strokeWidth: 0 }} }},
    nodes: {{ font: {{ size: 12 }} }},
    groups: {{
      Tool: {{ color: '#4a90d9', shape: 'dot', size: 25 }},
      Capability: {{ color: '#50c878', shape: 'dot', size: 15 }},
      Knowledge: {{ color: '#f0c040', shape: 'dot', size: 20 }},
      Skill: {{ color: '#9b59b6', shape: 'dot', size: 20 }},
      Gap: {{ color: '#e74c3c', shape: 'dot', size: 18 }},
      Provider: {{ color: '#95a5a6', shape: 'dot', size: 12 }},
      Category: {{ color: '#e67e22', shape: 'dot', size: 12 }},
    }}
  }};
  const network = new vis.Network(container, data, options);
  function searchNodes(val) {{
    const q = val.toLowerCase();
    nodes.forEach(n => {{
      const match = !q || n.label.toLowerCase().includes(q) || n.id.toLowerCase().includes(q);
      nodes.update({{ id: n.id, hidden: !match }});
    }});
  }}
</script></body></html>"""

    Path(output).write_text(html)
    print(f"✅ 已生成 HTML: {output}")
    print(f"   节点: {stats.get('total_nodes', 0)}, 边: {stats.get('total_edges', 0)}")
    print("   浏览器打开查看交互图谱")


def generate_mermaid(graph_path: str, output: str, max_nodes: int = 100) -> None:
    """生成 Mermaid 格式图"""
    g = json.loads(Path(graph_path).read_text())

    # 取关联度最高的 max_nodes 个节点
    edge_count: Counter[str] = Counter()
    for e in g["edges"]:
        edge_count[e["source"]] += 1
        edge_count[e["target"]] += 1

    all_nodes = sorted(g["nodes"], key=lambda n: -edge_count.get(n["id"], 0))
    nodes = all_nodes[:max_nodes]
    node_ids = {n["id"] for n in nodes}
    edges = [e for e in g["edges"] if e["source"] in node_ids and e["target"] in node_ids]
    if len(edges) > 200:
        print(f"  ⚠️  边数超过 200，截取前 200 条 (实际 {len(edges)})", file=sys.stderr)
        edges = edges[:200]

    lines = ["%% Forge 知识图谱 (Mermaid)", f"%% 节点: {len(nodes)}, 边: {len(edges)}", "graph LR"]

    for n in nodes:
        label = n["label"][:20].replace('"', "")
        lines.append(f'    {mermaid_id(n["id"])}["{label}"]')

    for e in edges:
        rel = e["relation"][:10]
        lines.append(f"    {mermaid_id(e['source'])} --{rel}--> {mermaid_id(e['target'])}")

    content = "\n".join(lines)
    Path(output).write_text(content)
    print(f"✅ 已生成 Mermaid: {output}")
    print(f"   节点: {len(nodes)}, 边: {len(edges)} (截取前 {max_nodes} 节点)")


def main() -> None:
    args = sys.argv[1:]
    if "--help" in args:
        print("用法: python3 src/graph_viz.py --output <path.html> [--max-nodes 100]")
        print("  --output graph/graph.html  生成 HTML")
        print("  --output graph/graph.md    生成 Mermaid")
        print("  --max-nodes 100            Mermaid 最大节点数")
        return

    toolbox = Path(__file__).resolve().parent.parent
    output = None
    max_nodes = 100

    for i, a in enumerate(args):
        if a == "--output" and i + 1 < len(args):
            output = args[i + 1]
        if a == "--max-nodes" and i + 1 < len(args):
            max_nodes = int(args[i + 1])

    if not output:
        print("❌ 请指定 --output")
        return

    output_path = toolbox / output

    if output.endswith(".html"):
        generate_html(str(toolbox / "graph" / "graph.json"), str(output_path))
    elif output.endswith(".md"):
        generate_mermaid(str(toolbox / "graph" / "graph.json"), str(output_path), max_nodes)
    else:
        print(f"❌ 不支持的输出格式: {output}")


if __name__ == "__main__":
    main()
