"""ecos.l0.ssot.cli_graph — cmd_graph 拆分 (P110 步骤3).

TASK-F7114ABA (omo lint god-module 800L 硬规则).
ecos/l0/ssot/cli.py 836L 拆分: cmd_graph (~111L) 独立到本模块,
cli.py 降至 <725L (<800L 阈值).

业务: 可视化 (实体关系图/状态机).

模式: 顶层 re-export (PFC) 保持 `from .cli import cmd_graph` 仍可用.
调用方 `from ecos.l0.ssot.cli import cmd_graph` 不破.
"""

from __future__ import annotations

import io
from pathlib import Path

from .cli import (
    cmd_graph as _cmd_graph_compat,
)
from .config_loader import load_domain


def cmd_graph(args):
    """生成可视化（支持 --html 输出）"""
    config = load_domain(args.dir)

    # 收集 mermaid 输出到缓冲区
    buf = io.StringIO()

    def _emit(text: str = ""):
        buf.write(text + "\n")

    if args.type == "entities":
        _emit("```mermaid")
        _emit("graph LR")
        for e in config.entities[:20]:
            label = e.name.replace('"', "'")
            _emit(f'    {e.id}["{label}"]')
        for r in config.relations[:30]:
            _emit(f"    {r.source_id} -->|{r.relation_type}| {r.target_id}")
        _emit("```")
    elif args.type == "state-machine":
        for sm in config.state_machines:
            _emit(f"## {sm.name}")
            _emit("```mermaid")
            _emit("stateDiagram-v2")
            for s in sm.states:
                _emit(f"    state {s.id}")
            for t in sm.transitions:
                label = t.condition.replace('"', "'") if t.condition else ""
                if label:
                    _emit(f"    {t.from_state} --> {t.to_state}: {label}")
                else:
                    _emit(f"    {t.from_state} --> {t.to_state}")
            _emit("```")
    else:
        if config.state_machines:
            args.type = "state-machine"
            return cmd_graph(args)
        else:
            args.type = "entities"
            return cmd_graph(args)

    mermaid_text = buf.getvalue()

    # --html 模式：输出自包含 HTML
    if args.html:
        # 从 mermaid 文本提取纯 mermaid 代码（去掉 ```mermaid 包装）
        pure_lines = []
        in_block = False
        for line in mermaid_text.split("\n"):
            if line.strip().startswith("```mermaid"):
                in_block = True
                continue
            if line.strip() == "```" and in_block:
                in_block = False
                continue
            if in_block:
                pure_lines.append(line)

        # 多图时每个图单独 mermaid 块
        diagram_blocks = []
        current: list[str] = []
        for line in mermaid_text.split("\n"):
            if line.startswith("## "):
                if current:
                    diagram_blocks.append("\n".join(current))
                    current = []
                continue
            if line.strip().startswith("```"):
                continue
            if line.strip():
                current.append(line)
        if current:
            diagram_blocks.append("\n".join(current))

        if not diagram_blocks:
            diagram_blocks = ["\n".join(pure_lines)]

        diagrams_html = "\n".join(
            f'<pre class="mermaid">\n{block}\n</pre>' for block in diagram_blocks
        )

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SSOT Graph — {args.type}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js">
  </script>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 1200px; margin: 0 auto; padding: 2rem; }}
    h1 {{ color: #333; border-bottom: 2px solid #4f46e5; padding-bottom: 0.5rem; }}
    .mermaid {{ margin: 2rem 0; }}
  </style>
</head>
<body>
  <h1>SSOT {args.type}</h1>
  {diagrams_html}
  <script>mermaid.initialize({{startOnLoad:true, theme:"neutral"}})</script>
</body>
</html>"""

        out_path = args.output or str(Path(args.dir) / f"{args.type}.html")
        Path(out_path).write_text(html, encoding="utf-8")
        print(f"✅ HTML 已生成: {out_path}")
        print("   用浏览器打开即可查看")
    else:
        # 普通文本模式：直接输出
        print(mermaid_text)

    return 0
