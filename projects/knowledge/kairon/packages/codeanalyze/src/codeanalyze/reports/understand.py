"""Understand Anything 仪表盘集成

Understand Anything (https://github.com/Lum1104/Understand-Anything)
是一个基于 React Flow 的交互式代码知识图谱仪表盘。

本模块提供：
  - 启动 /understand-dashboard 兼容仪表盘
  - 复用 graphify/graph.json 作为数据源
  - 代码库路由入口
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def is_installed() -> bool:
    """检查 Understand Anything 插件是否已安装。"""
    # Claude Code plugin 位置
    plugin_dirs = [
        Path.home() / ".claude" / "plugins" / "understand-anything",
        Path.home() / ".understand-anything",
    ]
    for d in plugin_dirs:
        if d.exists() and (d / "package.json").exists():
            return True
    # 独立安装脚本
    if shutil.which("understand-anything"):
        return True
    return False


def get_install_path() -> str | None:
    """获取安装路径。"""
    for d in [
        Path.home() / ".claude" / "plugins" / "understand-anything",
        Path.home() / ".understand-anything",
    ]:
        if d.exists() and (d / "package.json").exists():
            return str(d)
    return None


def get_graph_path(project_path: str = ".") -> str | None:
    """获取 Understand Anything 生成的图谱路径。"""
    target = Path(project_path) / ".understand-anything" / "knowledge-graph.json"
    if target.exists():
        return str(target)
    return None


def launch_dashboard(project_path: str = ".", port: int = 3456) -> dict:
    """启动 Understand Anything 仪表盘（如已安装）。"""
    install_path = get_install_path()

    result: dict[str, str | int | None] = {
        "status": "unavailable",
        "error": None,
        "url": None,
        "pid": None,
    }

    # 优先用已安装的 npm package
    if install_path:
        try:
            r = subprocess.Popen(
                ["npx", "vite", "--port", str(port)],
                cwd=install_path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            result["status"] = "launched"
            result["url"] = f"http://localhost:{port}"
            result["pid"] = r.pid
            return result
        except Exception as e:
            result["error"] = str(e)[:200]

    # 降级：检查已有图谱文件
    kg_path = get_graph_path(project_path)
    if kg_path:
        result["status"] = "graph_available"
        result["error"] = f"UAD 未安装，但图谱已存在: {kg_path}"
    else:
        result["error"] = (
            "Understand Anything 未安装。安装: "
            "curl -fsSL https://raw.githubusercontent.com/Lum1104/"
            "Understand-Anything/main/install.sh | bash"
        )

    return result


def generate_standalone_html(path: str = ".") -> str | None:
    """从 graphify 的 graph.json 生成独立的交互式 HTML 仪表盘。

    类似 Understand Anything 的简化版，使用 D3.js 力导向图。
    参考 code-review-graph 的 visualize 实现。
    """
    import json as _json

    graph_file = Path(path) / "graphify-out" / "graph.json"
    if not graph_file.exists():
        return None

    try:
        data = _json.loads(graph_file.read_text(encoding="utf-8"))
    except Exception:
        return None

    nodes = data.get("nodes", [])
    links = data.get("links", [])

    # 生成简化版 D3 力导向图 HTML
    html = (
        """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>codeanalyze 知识图谱</title>
<style>
  body { margin:0; font-family:sans-serif; background:#1a1a2e; color:#eee; }
  #graph { width:100vw; height:100vh; }
  .controls { position:fixed; top:10px; left:10px; z-index:10; background:rgba(0,0,0,.7); padding:10px; border-radius:8px; }
  .controls input { padding:6px; width:200px; border-radius:4px; border:1px solid #555; background:#2a2a3e; color:#eee; }
  .info { position:fixed; bottom:10px; left:10px; z-index:10; background:rgba(0,0,0,.7); padding:8px 12px; border-radius:8px; font-size:12px; }
  .tooltip { position:absolute; background:rgba(0,0,0,.85); color:#eee; padding:8px; border-radius:6px; font-size:13px; max-width:300px; pointer-events:none; }
  .legend { position:fixed; top:60px; left:10px; z-index:10; background:rgba(0,0,0,.7); padding:8px; border-radius:8px; font-size:11px; }
</style></head>
<body>
<div class="controls"><input id="search" placeholder="搜索节点..." oninput="filterNodes(this.value)"/></div>
<div class="legend" id="legend"></div>
<div class="info">节点: """
        + str(len(nodes))
        + """ | 边: """
        + str(len(links))
        + """</div>
<div id="graph"></div>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const data = """
        + _json.dumps({"nodes": nodes, "links": links}, ensure_ascii=False)
        + """;
const types = [...new Set(data.nodes.map(n => n.type || n.file_type || 'unknown'))];
const colors = d3.scaleOrdinal(d3.schemeTableau10).domain(types);
const legend = d3.select('#legend');
types.forEach(t => legend.append('div').style('color', colors(t)).text(t));
const width = window.innerWidth, height = window.innerHeight;
const svg = d3.select('#graph').append('svg').attr('width',width).attr('height',height);
const tooltip = d3.select('body').append('div').attr('class','tooltip').style('display','none');
const simulation = d3.forceSimulation(data.nodes)
  .force('link',d3.forceLink(data.links).id(d=>d.id).distance(100))
  .force('charge',d3.forceManyBody().strength(-200))
  .force('center',d3.forceCenter(width/2,height/2))
  .force('collision',d3.forceCollide(20));
const link = svg.append('g').selectAll('line').data(data.links).join('line')
  .attr('stroke','#555').attr('stroke-opacity',.4).attr('stroke-width',d=>Math.sqrt(d.weight||1));
const node = svg.append('g').selectAll('g').data(data.nodes).join('g').call(d3.drag()
  .on('start',(e,d)=>simulation.alphaTarget(.3).restart(),d.fx=d.x,d.fy=d.y)
  .on('drag',(e,d)=>{d.fx=e.x;d.fy=e.y;})
  .on('end',(e,d)=>{simulation.alphaTarget(0);d.fx=null;d.fy=null;}));
node.append('circle').attr('r',8).attr('fill',d=>colors(d.type||d.file_type||'unknown')).attr('stroke','#fff').attr('stroke-width',1);
node.append('text').text(d=>(d.label||d.id||'').slice(0,20)).attr('x',12).attr('y',4).attr('fill','#ccc').attr('font-size','11px');
node.on('mouseover',(e,d)=>{tooltip.style('display','block').html('<b>'+(d.label||d.id)+'</b><br/>类型: '+(d.type||d.file_type||'?')+'<br/>文件: '+(d.source_file||'?')).style('left',e.pageX+10+'px').style('top',e.pageY-20+'px');})
  .on('mouseout',()=>tooltip.style('display','none'));
simulation.on('tick',()=>{link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);node.attr('transform',d=>'translate('+d.x+','+d.y+')');});
function filterNodes(q){const v=q.toLowerCase();node.style('display',d=>(d.label||d.id||'').toLowerCase().includes(v)?null:'none');}
</script></body></html>"""
    )

    target = str(Path(path).resolve() / "codeanalyze-dashboard.html")
    Path(target).write_text(html, encoding="utf-8")
    return target
