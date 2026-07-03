#!/usr/bin/env python3
# bin/gac-consensus-inject.py — KOS 避坑共识跨会话基因注入特权代理

import os
import sys
import sqlite3
import re
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
db_path = WORKSPACE / "kos/kos-index.sqlite"
claude_md_path = WORKSPACE / "CLAUDE.md"

def extract_clean_description(md_path: Path) -> str:
    """提取 markdown 中剔除 frontmatter 和一级标题后的纯文本简介"""
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 移除 frontmatter
        content = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL)
        
        # 提取行
        lines = content.split("\n")
        desc_lines = []
        for line in lines:
            cleaned = line.strip()
            if not cleaned:
                continue
            if cleaned.startswith("#") or cleaned.startswith(">"):
                continue
            desc_lines.append(cleaned)
            if len(desc_lines) >= 3:
                break
        
        desc = " ".join(desc_lines)
        return desc[:200] + ("..." if len(desc) > 200 else "")
    except Exception:
        return "Consensus pattern guidelines."

def main() -> int:
    if not db_path.is_file() or not claude_md_path.is_file():
        return 0
    try:
        # 1. 从 KOS SQLite 读取所有的 Consensus 实体
        db_conn = sqlite3.connect(str(db_path))
        db_conn.row_factory = sqlite3.Row
        consensuses = db_conn.execute(
            "SELECT entity_id, label, source_file FROM kos_entities WHERE entity_type='Consensus'"
        ).fetchall()
        db_conn.close()

        if not consensuses:
            return 0

        # 2. 拼接共识基因 MD 内容
        consensus_lines = [
            "## 🧬 Onboarding Consensus (🧬 历史演进避坑基因)",
            "",
            "> **自动刷新时间**: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " (KOS 自动进化注入)",
            "> 新进 Agent 必须通读并深度对齐以下前人沉淀的历史避坑基因，严禁在同一坑中二次栽倒：",
            ""
        ]

        for item in consensuses:
            eid = item["entity_id"]
            label = item["label"]
            src_file = item["source_file"]
            
            relative_path = Path(src_file).relative_to(WORKSPACE)
            clean_desc = extract_clean_description(Path(src_file))
            
            consensus_lines.append(f"* **{label}** ([{relative_path.name}](file://{src_file}))")
            consensus_lines.append(f"  > {clean_desc}")
            consensus_lines.append("")

        # 3. 读取当前 CLAUDE.md
        with open(claude_md_path, "r", encoding="utf-8") as f:
            claude_content = f.read()

        # 4. 替换或追加基因章节
        split_token = "## 🧬 Onboarding Consensus"
        if split_token in claude_content:
            parts = claude_content.split(split_token)
            base_content = parts[0].strip()
        else:
            base_content = claude_content.strip()

        new_claude_content = base_content + "\n\n" + "\n".join(consensus_lines)

        # 5. 合规重写 CLAUDE.md (由于脚本以 gac- 开头，拥有直接写文件的特权)
        with open(claude_md_path, "w", encoding="utf-8") as f:
            f.write(new_claude_content)

        print(f"🧬 KOS Consensus Injection: Successfully injected {len(consensuses)} evolutionary genes into CLAUDE.md")
        return 0
    except Exception as e:
        print(f"❌ KOS Consensus Injection Failed: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    from datetime import datetime
    sys.exit(main())
