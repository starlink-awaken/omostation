#!/usr/bin/env python3
"""
织星 MOF — 全量资产扫描与建模 (mof-model)
=============================================
全面扫描 Documents(L4) + Workspace(L0-L3+I0) 的全部资产，
按 M2 12 类型自动分类建模，生成 M1 节点声明。

扫描维度:
  L4 Documents:
    - CLAUDE.md 文件 → Specification (Agent 契约)
    - STATE.md 文件 → Entity (域状态快照)  
    - 域根目录结构 → Entity (Domain)
    - 驾驶舱/scripts/ → Artifact (脚本)
    - 驾驶舱/CARDS/ → Process (流程)
    
  Workspace:
    - projects/ 下的项目 → Component (服务/库)
    - protocols/ → Protocol (协议实现)
    - agora/ → Component (I0 集成)
    - cockpit/ → Component (L3 入口)
    - runtime/ → Component (L1 运行时)
    - kairon/ → Component (L2 引擎)
    - gbrain/ → Component (L2 记忆)

用法:
    python3 mof-model.py                     # 全量扫描
    python3 mof-model.py --layer L4          # 仅 L4
    python3 mof-model.py --layer Workspace   # 仅 Workspace
    python3 mof-model.py --summary           # 仅统计
"""

import sys
import json
import yaml
import argparse
import re
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
DOCS = HOME / "Documents"
WS = HOME / "Workspace"
L0_NODES = WS / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "nodes"


def now():
    return datetime.now(timezone.utc).isoformat()[:19]


# ══════════════════════════════════════════
# L4 Scanners
# ══════════════════════════════════════════

def scan_claude_md(root: Path) -> list[dict]:
    """扫描所有 CLAUDE.md → Specification 节点"""
    nodes = []
    for md in sorted(root.rglob("CLAUDE.md")):
        if any(skip in str(md) for skip in ["node_modules", ".git", ".venv", "Zotero", ".obsidian"]):
            continue
        try:
            with open(md, encoding='utf-8') as f:
                head = f.read(1000)
        except:
            continue
        
        # Extract version, title, domain
        title = "CLAUDE.md"
        version = "1.0.0"
        domain = "unknown"
        layer = "L4"
        
        for line in head.split('\n'):
            if line.startswith('# ') and 'CLAUDE' not in line:
                title = line[2:].strip()[:60]
                break
            m = re.search(r'v(\d+\.\d+)', line)
            if m:
                version = m.group(0)
        
        # Infer domain from path
        rel = str(md.relative_to(root)) if str(md).startswith(str(root)) else str(md)
        for seg in ['驾驶舱', '学习进化', '工作文档', '工具箱', '领域知识库', '家庭生活']:
            if seg in rel:
                domain = seg
                break
        
        # Infer layer
        if '驾驶舱' in rel: layer = 'L4'
        elif '学习进化' in rel: layer = 'L4'
        elif 'Workspace' in rel: layer = 'L2'
        
        nid = f"SPEC-CLAUDE-{domain}-{md.parent.name if md.parent.name != '.' else 'root'}"
        nid = re.sub(r'[^a-zA-Z0-9_\-]', '-', nid)[:60]
        
        nodes.append({
            "id": nid, "type": "Specification", "subtype": "CLAUDE.md",
            "name": f"{domain}: {title}"[:60],
            "description": f"Agent 操作契约 — {domain} 域",
            "status": "active", "domain": domain, "created": now()[:10],
            "version": version, "layer": layer,
            "properties": {
                "path": rel,
                "format": "markdown",
                "constraints": ["SSOT声明", "快速路由", "维护周期"],
                "scope": [domain],
            },
        })
    return nodes


def scan_state_md(root: Path) -> list[dict]:
    """扫描所有 STATE.md → Entity 节点"""
    nodes = []
    for md in sorted(root.rglob("STATE.md")):
        if any(skip in str(md) for skip in ["node_modules", ".git", ".venv", "Zotero", ".obsidian"]):
            continue
        try:
            stat = md.stat()
        except:
            continue
        
        rel = str(md.relative_to(root)) if str(md).startswith(str(root)) else str(md)
        parent = md.parent.name
        domain = "unknown"
        for seg in ['驾驶舱', '学习进化', '工作文档', '卫健委', '国转中心', '家庭生活']:
            if seg in rel:
                domain = seg
                break
        
        nid = f"ENTITY-STATE-{domain}-{parent}"
        nid = re.sub(r'[^a-zA-Z0-9_\-]', '-', nid)[:60]
        
        nodes.append({
            "id": nid, "type": "Entity", "subtype": "StateSnapshot",
            "name": f"STATE: {domain}/{parent}",
            "description": f"域状态快照 — {rel}",
            "status": "active", "domain": domain, "created": now()[:10],
            "version": "1.0.0", "layer": "L4",
            "properties": {
                "entity_type": "document",
                "sources": [rel],
                "identity": {"path": rel},
            },
        })
    return nodes


def scan_domains(root: Path) -> list[dict]:
    """扫描域根目录 → Entity (Domain) 节点"""
    nodes = []
    domain_dirs = {
        "驾驶舱": "控制面 — 全局聚合·健康度·信号",
        "学习进化": "Vault — 知识面·三层架构·方法论",
        "工具箱": "工具注册 — 能力发现·模板·管线",
        "领域知识库": "事实面 — 跨域实体·本体",
        "工作文档": "工作域 — 卫健委·国转中心",
        "家庭生活": "家庭域 — 成员·医疗·育儿·资产",
    }
    
    for name, desc in domain_dirs.items():
        d = root / name
        if not d.exists():
            continue
        
        # Count files for size metric
        file_count = sum(1 for _ in d.rglob("*") if _.is_file() and not any(
            s in str(_) for s in [".git", ".obsidian", "node_modules", "Zotero"]))
        
        nodes.append({
            "id": f"ENTITY-DOMAIN-{name}",
            "type": "Entity", "subtype": "Domain",
            "name": name,
            "description": desc[:120],
            "status": "active", "domain": name, "created": now()[:10],
            "version": "1.0.0", "layer": "L4",
            "properties": {
                "entity_type": "domain",
                "identity": {"name": name},
                "sources": [str(d.relative_to(root))],
                "attributes": {"file_count": file_count},
            },
        })
    return nodes


def scan_l4_scripts(root: Path) -> list[dict]:
    """扫描 L4 脚本 → Artifact 节点"""
    nodes = []
    scripts_dir = root / "驾驶舱" / "scripts"
    if not scripts_dir.exists():
        return nodes
    
    for f in sorted(scripts_dir.glob("*.py")):
        stat = f.stat()
        # Infer layer
        layer = "L4"
        name = f.stem
        if 'ecos-daemon' in name: layer = 'L1'
        elif 'ecos-constraint' in name: layer = 'L0'
        elif 'check-' in name: layer = 'X2'
        elif 'vault-value' in name or 'domain-value' in name: layer = 'X3'
        elif 'mof-' in name: layer = 'L0'
        
        nodes.append({
            "id": f"ARTIFACT-L4-{name}",
            "type": "Artifact", "subtype": "Script",
            "name": name,
            "description": f"L4 脚本: {name}",
            "status": "active", "domain": "meta", "created": now()[:10],
            "version": "1.0.0", "layer": layer,
            "properties": {
                "path": str(f.relative_to(root)),
                "format": "python",
                "size": stat.st_size,
            },
        })
    return nodes


# ══════════════════════════════════════════
# Workspace Scanners
# ══════════════════════════════════════════

def scan_workspace_projects(ws_root: Path) -> list[dict]:
    """扫描 Workspace 项目 → Component 节点"""
    nodes = []
    projects_dir = ws_root / "projects"
    if not projects_dir.exists():
        return nodes
    
    # Key projects with layer assignments
    project_map = {
        "ecos": ("L0", "eCOS 核心 — 协议编织·SSB·涌现"),
        "agora": ("I0", "Agora 服务网格 — MCP路由·动态代理"),
        "cockpit": ("L3", "Cockpit — 入口桥接·多Agent接入"),
        "runtime": ("L1", "Runtime Matrix — 服务编排·健康监控"),
        "kairon": ("L2", "Kairon 知识引擎 — 31包·KOS·Minerva"),
        "gbrain": ("L2", "gBrain 记忆引擎 — 知识图谱·语义检索"),
        "omo": ("L2", "OMO 治理引擎 — Phase规划·债务追踪"),
        "codeanalyze": ("L2", "CodeAnalyze — 代码分析·审计"),
        "kronos": ("L2", "Kronos — 内容摄取管线"),
        "forge": ("L2", "Forge — Agent能力集市"),
        "kos": ("L2", "KOS — 知识索引·搜索"),
        "agent-runtime": ("L1", "Agent Runtime — 任务执行"),
        "agentmesh": ("L3", "AgentMesh — Agent网格"),
    }
    
    for proj_dir in sorted(projects_dir.iterdir()):
        if not proj_dir.is_dir() or proj_dir.name.startswith('.') or proj_dir.name.startswith('_'):
            continue
        
        name = proj_dir.name
        # Skip archived snapshots
        if 'archived' in name.lower() or 'snapshot' in name.lower() or 'legacy' in name.lower():
            continue
        
        layer, desc = project_map.get(name, ("L2", f"项目: {name}"))
        
        # Check for pyproject.toml or package.json
        has_py = (proj_dir / "pyproject.toml").exists()
        has_js = (proj_dir / "package.json").exists()
        has_tests = (proj_dir / "tests").exists()
        
        nodes.append({
            "id": f"COMP-WS-{name}",
            "type": "Component", "subtype": "Project",
            "name": name,
            "description": desc[:120],
            "status": "active", "domain": "infra", "created": now()[:10],
            "version": "1.0.0", "layer": layer,
            "properties": {
                "layer": layer,
                "runtime": "active",
                "has_pyproject": has_py,
                "has_package_json": has_js,
                "has_tests": has_tests,
            },
        })
    
    # Also scan standalone projects (not in projects/)
    standalone = {
        ws_root / "agora": ("I0", "Agora Service Mesh"),
        ws_root / "cockpit": ("L3", "Cockpit Entry Bridge"),
        ws_root / "ecos": ("L0", "eCOS Protocol Core"),
        ws_root / "runtime": ("L1", "Runtime Matrix"),
        ws_root / "kairon": ("L2", "Kairon Knowledge Engine"),
        ws_root / "gbrain": ("L2", "gBrain Memory Engine"),
    }
    
    for path, (layer, desc) in standalone.items():
        if path.exists() and path.is_dir():
            name = path.name
            if not any(n["id"] == f"COMP-WS-{name}" for n in nodes):
                nodes.append({
                    "id": f"COMP-WS-{name}",
                    "type": "Component", "subtype": "Project",
                    "name": name, "description": desc,
                    "status": "active", "domain": "infra", "created": now()[:10],
                    "version": "1.0.0", "layer": layer,
                    "properties": {"layer": layer, "runtime": "active"},
                })
    
    return nodes


def scan_protocols(ws_root: Path) -> list[dict]:
    """扫描协议目录 → Protocol 节点"""
    nodes = []
    protocols_dir = ws_root / "protocols"
    if not protocols_dir.exists():
        return nodes
    
    for f in sorted(protocols_dir.glob("*.yaml")):
        try:
            with open(f) as fh:
                data = yaml.safe_load(fh)
        except:
            continue
        
        if not isinstance(data, dict):
            continue
        
        pid = data.get("id", f.stem)
        nodes.append({
            "id": f"PROTOCOL-WS-{pid}",
            "type": "Protocol", "subtype": "ProtocolImpl",
            "name": data.get("name", f.stem)[:60],
            "description": data.get("description", "")[:120],
            "status": data.get("status", "active"),
            "domain": "infra", "created": data.get("introduced", now()[:10]),
            "version": data.get("version", "1.0.0"),
            "layer": "L0",
            "properties": {
                "version_spec": data.get("version", "1.0.0"),
                "introduced": data.get("introduced", ""),
                "half_life": data.get("half_life_days", 180),
                "registered": True,
                "value_tier": data.get("value_tier", 3),
            },
        })
    return nodes


def scan_cards_system() -> list[dict]:
    """CARDS 系统本身 → Process + Entity 节点"""
    nodes = []
    cards_db = WS / "data" / "cards" / "cards.db"
    
    nodes.append({
        "id": "PROC-CARDS-SYSTEM",
        "type": "Process", "subtype": "TrackingSystem",
        "name": "CARDS 统一追踪体系",
        "description": "想法→研究→任务→债务→交付的全生命周期追踪",
        "status": "active", "domain": "meta", "created": "2026-06-05",
        "version": "2.0.0", "layer": "L4",
        "properties": {
            "states": ["flash→incubating→promoted", "planned→active→done", "draft→published→maintained"],
            "steps": [{"order": 1, "name": "创建"}, {"order": 2, "name": "执行"}, {"order": 3, "name": "交付"}],
            "sla": {"incubating_max_days": 14, "active_max": 50},
        },
    })
    
    nodes.append({
        "id": "ENTITY-CARDS-DB",
        "type": "Entity", "subtype": "DataSource",
        "name": "CARDS SQLite 数据库",
        "description": "追踪体系 SSOT — cards.db",
        "status": "active", "domain": "meta", "created": "2026-06-05",
        "version": "1.0.0", "layer": "L4",
        "properties": {
            "entity_type": "system",
            "sources": [str(cards_db.relative_to(HOME)) if cards_db.exists() else "N/A"],
        },
    })
    
    return nodes


# ══════════════════════════════════════════
# Save & Report
# ══════════════════════════════════════════

def save_nodes(nodes: list[dict], output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    for n in nodes:
        fp = output_dir / f"{n['id']}.yaml"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(f"# M1 Node: {n['id']}\n# Type: {n['type']}\n# Modeled: {now()}\n\n")
            yaml.dump(n, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        saved += 1
    return saved


def format_summary(all_nodes: list[dict]) -> str:
    lines = ["=" * 64, "  织星 MOF — 全量资产建模报告", "=" * 64,
             f"  时间: {now()}", f"  节点总计: {len(all_nodes)}", ""]
    
    by_type = {}
    by_layer = {}
    for n in all_nodes:
        t = n["type"]
        by_type[t] = by_type.get(t, 0) + 1
        l = n.get("layer", "?")
        by_layer[l] = by_layer.get(l, 0) + 1
    
    lines.append("  ── 按类型 ──")
    for t, c in sorted(by_type.items()):
        lines.append(f"  {t:20s}: {c:3d}")
    
    lines.append("")
    lines.append("  ── 按层 ──")
    for l in ["L0", "L1", "L2", "L3", "L4", "I0", "X1", "X2", "X3", "X4", "multi"]:
        if l in by_layer:
            lines.append(f"  {l:6s}: {by_layer[l]:3d}")
    
    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--layer", type=str, default="all")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--save", action="store_true", default=True)
    parser.add_argument("--output", type=Path, default=L0_NODES)
    args = parser.parse_args()

    all_nodes = []
    
    if args.layer in ("all", "L4"):
        if DOCS.exists():
            all_nodes.extend(scan_claude_md(DOCS))
            all_nodes.extend(scan_state_md(DOCS))
            all_nodes.extend(scan_domains(DOCS))
            all_nodes.extend(scan_l4_scripts(DOCS))
            all_nodes.extend(scan_cards_system())
    
    if args.layer in ("all", "Workspace"):
        if WS.exists():
            all_nodes.extend(scan_workspace_projects(WS))
            all_nodes.extend(scan_protocols(WS))

    print(format_summary(all_nodes))

    if args.save and all_nodes:
        saved = save_nodes(all_nodes, args.output)
        print(f"  ✅ {saved} 个节点 → {args.output}")


if __name__ == "__main__":
    main()
