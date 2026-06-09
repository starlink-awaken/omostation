#!/usr/bin/env python3
"""
织星 MOF — 架构视图生成器 (mof-view)
=====================================
从 L0 M1 节点生成人类/Agent 可读的架构视图。
解决"L0太散太乱，Agent不知道怎么提需求"的问题。

生成视图:
  1. 系统全景 (topology + layers + components)
  2. 协议地图 (protocols + status + decay)
  3. 组件目录 (components by layer)
  4. 约束清单 (constraints + compliance)
  5. ADR 索引 (decisions)
  6. 任务一览 (mechanisms + scheduled tasks)
  7. 实体解析 (cross-domain entities)

输出: Markdown 文档 → 可放入 L4 Documents

用法:
    python3 mof-view.py                  # 生成全量视图到 stdout
    python3 mof-view.py --output view.md # 输出到文件
    python3 mof-view.py --topic topology # 仅拓扑视图
    python3 mof-view.py --json           # JSON (供 Agent MCP 消费)
"""

import json
import yaml
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
L0_M1 = HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1"
REGISTRY = HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "registry"
M0_FILE = HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m0" / "snapshot.yaml"


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


def load_all() -> dict:
    return {t: load_nodes(t) for t in [
        "architecture", "artifact", "component", "convention", "decision",
        "entity", "intent", "action", "constraint_mgmt", "outcome",
        "lesson", "mechanism", "model", "pattern", "process", "protocol", "specification"
    ]}


def view_topology() -> str:
    """系统全景视图"""
    topo = REGISTRY / "topology.yaml"
    if not topo.exists():
        return "拓扑文件不存在"
    
    data = yaml.safe_load(open(topo))
    lines = ["# 织星架构 — 系统全景", "", f"> 生成: {datetime.now(timezone.utc).isoformat()[:19]}", ""]
    
    lines.append("## 层拓扑")
    lines.append("")
    for layer in data.get("layers", []):
        lid = layer.get("id", "?")
        pkgs = layer.get("packages", [])
        deps = layer.get("allowed_dependencies", [])
        desc = layer.get("description", "")
        lines.append(f"### {lid} — {layer.get('name', '')}")
        lines.append("")
        lines.append(f"**包**: {', '.join(pkgs)}")
        lines.append(f"**依赖**: {', '.join(deps) if deps else '无 (底层)'}")
        lines.append(f"**说明**: {desc}")
        lines.append("")
    
    return "\n".join(lines)


def view_protocols() -> str:
    """协议地图"""
    protocols = load_nodes("protocol")
    m0 = {}
    if M0_FILE.exists():
        m0 = yaml.safe_load(open(M0_FILE)).get("protocols", {})
    
    lines = ["# 协议地图", "", "| 协议 | 版本 | 状态 | 衰减 | 价值层级 |", "|------|------|:----:|:----:|:------:|"]
    
    for p in protocols:
        props = p.get("properties", {}) or {}
        pid = p.get("name", p.get("id", "?"))
        ver = props.get("version_spec", "?")
        status = p.get("status", "?")
        tier = props.get("value_tier", "?")
        
        # Get M0 decay
        m0p = m0.get(pid, {})
        decay = m0p.get("remaining_pct", "?")
        m0status = m0p.get("status", "?")
        
        icon = "🟢" if m0status == "fresh" else ("🟡" if m0status == "aging" else "🔴")
        decay_str = f"{decay:.0f}" if isinstance(decay, (int, float)) else str(decay)
        lines.append(f"| {icon} {pid:20s} | {str(ver):10s} | {status:8s} | {decay_str:>5s}% | {tier} |")
    
    lines.append("")
    return "\n".join(lines)


def view_components() -> str:
    """组件目录"""
    comps = load_nodes("component")
    by_layer = {}
    for c in comps:
        layer = c.get("layer", c.get("properties", {}).get("layer", "?"))
        by_layer.setdefault(layer, []).append(c)
    
    lines = ["# 组件目录", ""]
    for layer in sorted(by_layer.keys()):
        lines.append(f"## {layer}")
        lines.append("")
        for c in by_layer[layer]:
            name = c.get("name", "?")
            desc = c.get("description", "")[:80]
            status = c.get("status", "?")
            lines.append(f"- **{name}** ({status}): {desc}")
        lines.append("")
    
    return "\n".join(lines)


def view_decisions() -> str:
    """ADR 索引"""
    decs = load_nodes("decision")
    lines = ["# 架构决策记录 (ADR)", "", f"共 {len(decs)} 条", ""]
    
    for d in sorted(decs, key=lambda x: x.get("created", ""), reverse=True):
        status = d.get("status", "?")
        name = d.get("name", "?")[:80]
        created = d.get("created", "?")
        props = d.get("properties", {}) or {}
        rationale = props.get("rationale", "")[:100]
        
        icon = {"accepted": "✅", "proposed": "📋", "rejected": "❌"}.get(status, "❓")
        lines.append(f"### {icon} {name}")
        lines.append(f"- 日期: {created} | 状态: {status}")
        lines.append(f"- 理由: {rationale}")
        lines.append("")
    
    return "\n".join(lines)


def view_quick() -> str:
    """Agent 快速索引 — 最精简的入口视图"""
    lines = ["# 织星架构 — Agent 快速索引", "",
             "## 怎么提需求", "",
             "1. 架构变更 → `mof adr create \"标题\"` (会自动创建 Decision 节点)",
             "2. 查看系统状态 → `mof status`",
             "3. 查看全部协议 → `mof view protocols`",
             "4. 注册新资产 → 运行 `mof-scan` 自动发现",
             "5. 校验合规 → `mof validate`",
             "",
             "## 系统速览", ""]
    
    # Quick counts
    all_nodes = load_all()
    lines.append("| 维度 | 数量 |")
    lines.append("|------|:---:|")
    for t, nodes in sorted(all_nodes.items()):
        if nodes:
            lines.append(f"| {t:25s} | {len(nodes):4d} |")
    
    # Key decisions
    decs = all_nodes.get("decision", [])
    active_decs = [d for d in decs if d.get("status") == "accepted"]
    lines.append("")
    lines.append("## 当前架构决策")
    lines.append("")
    for d in active_decs[-5:]:
        lines.append(f"- ✅ {d.get('name', '?')[:60]}")
    
    # Protocols at risk
    protocols = all_nodes.get("protocol", [])
    m0 = {}
    if M0_FILE.exists():
        m0 = yaml.safe_load(open(M0_FILE)).get("protocols", {})
    aging = []
    for p in protocols:
        pid = p.get("name", "")
        if m0.get(pid, {}).get("status") in ("aging", "expired"):
            aging.append(pid)
    if aging:
        lines.append("")
        lines.append("## ⚠️ 需关注的协议")
        lines.append("")
        for a in aging:
            lines.append(f"- 🟡 {a}: {m0[a].get('remaining_pct','?')}% 剩余")
    
    lines.append("")
    lines.append("> 完整视图: `mof view` | 状态: `mof status` | 校验: `mof validate`")
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", type=str, default="all",
                       choices=["all", "topology", "protocols", "components", "decisions", "quick"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.json:
        all_nodes = load_all()
        summary = {t: [{"id": n.get("id"), "name": n.get("name"), "status": n.get("status")} for n in nodes[:5]]
                   for t, nodes in all_nodes.items() if nodes}
        print(json.dumps({"summary": summary, "total_nodes": sum(len(v) for v in all_nodes.values())},
                        ensure_ascii=False, indent=2))
        return

    generators = {
        "topology": view_topology,
        "protocols": view_protocols,
        "components": view_components,
        "decisions": view_decisions,
        "quick": view_quick,
    }

    if args.topic == "all":
        output = []
        for name, gen in generators.items():
            output.append(gen())
        result = "\n\n---\n\n".join(output)
    else:
        result = generators.get(args.topic, lambda: "?")()
    
    if args.output:
        args.output.write_text(result, encoding='utf-8')
        print(f"✅ 视图已生成: {args.output}")
    else:
        print(result)


if __name__ == "__main__":
    main()
