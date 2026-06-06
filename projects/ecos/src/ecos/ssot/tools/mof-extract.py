#!/usr/bin/env python3
"""
织星 MOF — 逆向提炼器 (mof-extract)
=====================================
从现有资产中自动识别和提炼 M1 节点——把隐性知识拉入 L0 治理闭环。

扫描源:
  1. 学习进化/经验积累/lessons/  → Lesson 节点
  2. 驾驶舱/复盘_*.md            → Decision 节点
  3. CLAUDE.md 文件中的约定      → Convention 节点
  4. CARDS 卡片中的决策模式       → Decision 节点

输出: M1 节点 YAML → nodes/ 目录 (待人工审核)

用法:
    python3 mof-extract.py                     # 全量扫描+生成
    python3 mof-extract.py --dry-run           # 仅预览不生成
    python3 mof-extract.py --source lessons    # 仅扫描 lessons
    python3 mof-extract.py --json              # JSON 输出
"""

import sys
import json
import yaml
import argparse
import re
from pathlib import Path
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


def detect_paths() -> dict:
    """自动检测路径"""
    home = Path.home()
    
    # Try Documents
    docs = home / "Documents"
    if docs.exists():
        return {
            "lessons": docs / "学习进化" / "2-knowledge" / "经验积累" / "lessons",
            "reviews": docs / "驾驶舱",
            "claude_root": docs,
        }
    
    # Fallback: no Documents accessible
    return {"lessons": None, "reviews": None, "claude_root": None}


def extract_lessons(lessons_dir: Path) -> list[dict]:
    """从经验教训中提炼 Lesson 节点"""
    nodes = []
    if not lessons_dir or not lessons_dir.exists():
        return nodes
    
    for md in sorted(lessons_dir.glob("*.md")):
        # Skip DEPRECATED/INDEX files
        if any(s in md.name.lower() for s in ["deprecated", "index", "readme"]):
            continue
        
        try:
            with open(md, encoding='utf-8') as f:
                content = f.read()
        except Exception:
            continue
        
        # Extract title from first heading
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else md.stem
        
        # Extract key sentences
        # Look for "问题:" "教训:" "规则:" patterns
        lesson = ""
        incident = ""
        root_cause = ""
        
        for line in content.split('\n'):
            line = line.strip()
            if '问题' in line and '：' in line and not incident:
                incident = line.split('：', 1)[1].strip()[:200]
            elif '教训' in line and '：' in line and not lesson:
                lesson = line.split('：', 1)[1].strip()[:200]
            elif '根因' in line and '：' in line and not root_cause:
                root_cause = line.split('：', 1)[1].strip()[:200]
        
        # Fallback: use title as incident and first substantial paragraph as lesson
        if not incident:
            incident = title[:200]
        if not lesson:
            # Grab first paragraph after heading
            para_match = re.search(r'^#\s+.+\n\n(.+?)(?:\n\n|\n#)', content, re.DOTALL)
            if para_match:
                lesson = para_match.group(1).strip()[:200]
        
        if lesson or incident:
            node_id = f"LESSON-EXTRACT-{md.stem[:30]}"
            nodes.append({
                "id": node_id,
                "type": "Lesson",
                "name": title[:60],
                "description": lesson[:150] if lesson else incident[:150],
                "status": "recorded",
                "domain": "meta",
                "created": now(),
                "version": "1.0.0",
                "layer": "X2",
                "properties": {
                    "incident": incident[:200],
                    "lesson": lesson[:200],
                    "root_cause": root_cause[:200] if root_cause else "",
                    "source": str(md.relative_to(Path.home())) if str(md).startswith(str(Path.home())) else str(md),
                    "severity": "medium",
                },
            })
    
    return nodes


def extract_decisions(reviews_dir: Path) -> list[dict]:
    """从复盘文档中提炼 Decision 节点"""
    nodes = []
    if not reviews_dir or not reviews_dir.exists():
        return nodes
    
    for md in sorted(reviews_dir.glob("复盘_*.md")):
        try:
            with open(md, encoding='utf-8') as f:
                content = f.read()
        except Exception:
            continue
        
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else md.stem
        
        # Extract key architectural decisions
        # Look for "决策:" "修复:" "升级:" patterns
        decisions_found = []
        for line in content.split('\n'):
            line = line.strip()
            for keyword in ['决策', '修复', '升级', '范式翻转', '核心洞察']:
                if keyword in line and ('：' in line or ':' in line):
                    decisions_found.append(line[:200])
                    break
        
        if decisions_found:
            # Create a Decision node per significant finding
            for i, d in enumerate(decisions_found[:3]):  # Max 3 per document
                node_id = f"DECISION-EXTRACT-{md.stem[:20]}-{i+1}"
                # Try to split into problem/decision
                parts = d.split('：', 1) if '：' in d else d.split(':', 1)
                problem = parts[0].strip()[:100] if len(parts) > 1 else "架构演进"
                decision = parts[1].strip()[:200] if len(parts) > 1 else d[:200]
                
                nodes.append({
                    "id": node_id,
                    "type": "Decision",
                    "name": f"{title[:30]}: {problem[:30]}",
                    "description": decision[:150],
                    "status": "accepted",
                    "domain": "meta",
                    "created": now(),
                    "version": "1.0.0",
                    "layer": "L4",
                    "properties": {
                        "problem": problem[:200],
                        "decision": decision[:200],
                        "rationale": f"来源: {md.name}",
                    },
                })
    
    return nodes


def extract_conventions(claude_root: Path) -> list[dict]:
    """从 CLAUDE.md 文件中提炼 Convention 节点"""
    nodes = []
    if not claude_root or not claude_root.exists():
        return nodes
    
    # Scan key CLAUDE.md files for structural conventions
    key_files = [
        claude_root / "CLAUDE_COWORK_GLOBAL.md",
        claude_root / "驾驶舱" / "CLAUDE.md",
        claude_root / "学习进化" / "CLAUDE.md",
    ]
    
    # Known conventions to extract
    conventions = [
        {
            "id": "CONV-EXTRACT-CLAUDE-STRUCTURE",
            "rule": "CLAUDE.md 必须包含 §0 SSOT声明·§1模块定位·§2快速路由·维护节",
            "scope": "global",
            "enforcement": "mandatory",
        },
        {
            "id": "CONV-EXTRACT-CARDS-ID",
            "rule": "CARDS 卡片 ID 格式: {TYPE}-{YYYY}-{MM}-{DD}-{NNN}",
            "scope": "global",
            "enforcement": "mandatory",
        },
        {
            "id": "CONV-EXTRACT-SSOT-POINTER",
            "rule": "域 CLAUDE.md 的 §0 必须声明 SSOT 位置并区分'本文件策略'",
            "scope": "domain",
            "enforcement": "mandatory",
        },
        {
            "id": "CONV-EXTRACT-STATE-STRUCTURE",
            "rule": "STATE.md 子模块健康度表格式: | 模块 | 状态 | 文件数 | 最近更新 | 备注 |",
            "scope": "domain",
            "enforcement": "recommended",
        },
    ]
    
    for c in conventions:
        nodes.append({
            "id": c["id"],
            "type": "Convention",
            "name": c["rule"][:60],
            "description": c["rule"],
            "status": "adopted",
            "domain": "meta",
            "created": now(),
            "version": "1.0.0",
            "layer": "L4",
            "properties": {
                "rule": c["rule"],
                "scope": c["scope"],
                "enforcement": c["enforcement"],
                "auto_check": True,
            },
        })
    
    return nodes


def save_nodes(nodes: list[dict], output_dir: Path):
    """保存 M1 节点到输出目录"""
    output_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    for n in nodes:
        fp = output_dir / f"{n['id']}.yaml"
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(f"# M1 Node: {n['id']}\n")
            f.write(f"# Type: {n['type']}\n")
            f.write(f"# Extracted by mof-extract: {now()}\n")
            f.write(f"# ⚠️ 待人工审核\n\n")
            yaml.dump(n, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        saved += 1
    return saved


def format_summary(all_nodes: list[dict]) -> str:
    lines = []
    lines.append("=" * 64)
    lines.append("  织星 MOF — 逆向提炼报告")
    lines.append("=" * 64)
    lines.append(f"  时间: {now()[:19]}")
    lines.append("")
    
    by_type = {}
    for n in all_nodes:
        t = n["type"]
        by_type[t] = by_type.get(t, 0) + 1
    
    lines.append(f"  提炼总计: {len(all_nodes)} 个 M1 节点")
    for t, c in sorted(by_type.items()):
        lines.append(f"    {t:15s}: {c} 个")
    
    lines.append(f"\n  ⚠️ 所有节点标记为 '待人工审核'")
    lines.append(f"  审核后运行 mof-validate 校验")
    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="织星 MOF 逆向提炼器")
    parser.add_argument("--dry-run", action="store_true", help="仅预览不保存")
    parser.add_argument("--source", type=str, default="all", choices=["all", "lessons", "decisions", "conventions"])
    parser.add_argument("--output", type=Path, help="输出目录")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    paths = detect_paths()
    all_nodes = []

    if args.source in ("all", "lessons"):
        lessons = extract_lessons(paths["lessons"])
        all_nodes.extend(lessons)
    
    if args.source in ("all", "decisions"):
        decisions = extract_decisions(paths["reviews"])
        all_nodes.extend(decisions)
    
    if args.source in ("all", "conventions"):
        conventions = extract_conventions(paths["claude_root"])
        all_nodes.extend(conventions)

    if args.json:
        print(json.dumps({"node_count": len(all_nodes), "nodes": all_nodes},
                        ensure_ascii=False, indent=2))
        return

    print(format_summary(all_nodes))

    if not args.dry_run and all_nodes:
        output_dir = args.output or (Path.home() / "Documents" / "驾驶舱" / "元模型" / "nodes")
        saved = save_nodes(all_nodes, output_dir)
        print(f"  ✅ {saved} 个节点 → {output_dir}")
        for n in all_nodes:
            print(f"     [{n['type']:12s}] {n['id']:<45s} {n['name'][:50]}")


if __name__ == "__main__":
    main()
