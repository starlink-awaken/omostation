#!/usr/bin/env python3
"""
织星 MOF — L4 Agent 技能发现桥 (mof-skills)
=============================================
从 L0 M1 节点生成 Agent 可读的技能清单。
供 Agent 启动时读取——让 Agent 知道系统中有哪些可用技能/工具。

输出: Markdown → L4 Documents/驾驶舱/ 或 stdout

用法:
    python3 mof-skills.py                  # 生成技能清单
    python3 mof-skills.py --output file.md # 输出到文件
    python3 mof-skills.py --json           # JSON (供 Agent MCP 消费)
"""

import json
import yaml
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
L0_M1 = HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1"


def load_nodes(m2type: str) -> list[dict]:
    ndir = L0_M1 / m2type.lower()
    if not ndir.exists():
        return []
    nodes = []
    for f in sorted(ndir.glob("*.yaml")):
        try:
            data = yaml.safe_load(open(f))
            if isinstance(data, dict):
                nodes.append(data)
        except Exception:
            pass
    return nodes


def generate_skills_md() -> str:
    skills = load_nodes("skill")
    mcp_tools = load_nodes("mcptool")
    mechanisms = load_nodes("mechanism")
    
    lines = ["# Agent 可用能力清单", "",
             f"> 自动生成自 L0 M1 节点 | {datetime.now(timezone.utc).isoformat()[:19]}",
             f"> Skills: {len(skills)} · MCP Tools: {len(mcp_tools)} · Mechanisms: {len(mechanisms)}",
             ""]
    
    # Skills
    lines.append("## 🛠️ Skills (Agent 可调用)")
    lines.append("")
    for s in skills:
        name = s.get("name", "?")[:60]
        desc = s.get("description", "")[:80]
        s.get("status", "?")
        trigger = (s.get("properties", {}) or {}).get("trigger", "?")
        lines.append(f"- **{name}** `[{trigger}]` — {desc}")
    lines.append("")
    
    # MCP Tools
    lines.append("## 🔧 MCP Tools (Agent 可调用端点)")
    lines.append("")
    by_server = {}
    for t in mcp_tools:
        server = (t.get("properties", {}) or {}).get("server", "?")
        by_server.setdefault(server, []).append(t.get("name", "?"))
    
    for server, tools in sorted(by_server.items()):
        lines.append(f"### {server} ({len(tools)} tools)")
        for t in tools:
            lines.append(f"- `{t}`")
        lines.append("")
    
    # Mechanisms (scheduled/automated)
    lines.append("## ⚙️ Mechanisms (自动执行)")
    lines.append("")
    freq_map = {}
    for m in mechanisms:
        props = m.get("properties", {}) or {}
        interval = props.get("interval", 0)
        if interval > 0:
            freq = f"{interval}s"
        else:
            freq = "event-driven"
        freq_map.setdefault(freq, []).append(m.get("name", "?")[:50])
    
    for freq, mechs in sorted(freq_map.items()):
        lines.append(f"### {freq}")
        lines.append("")
        for m in mechs[:5]:
            lines.append(f"- {m}")
        lines.append("")
    
    lines.append("> 完整架构视图: `mof view quick` | 技能注册: `mof-scan`")
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.json:
        skills = [{"id": s.get("id"), "name": s.get("name"), "trigger": (s.get("properties",{}) or {}).get("trigger","?")} for s in load_nodes("skill")]
        tools = [{"name": t.get("name"), "server": (t.get("properties",{}) or {}).get("server","?")} for t in load_nodes("mcptool")]
        print(json.dumps({"skills": skills, "mcptools": tools}, ensure_ascii=False, indent=2))
        return

    md = generate_skills_md()
    if args.output:
        args.output.write_text(md, encoding='utf-8')
        print(f"✅ Agent 技能清单 → {args.output}")
    else:
        print(md)


if __name__ == "__main__":
    main()
