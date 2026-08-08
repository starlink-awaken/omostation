#!/usr/bin/env python3
"""skill-crystallizer.py — SEMA 技能自动结晶引擎 (BET-Y1Q2-T6-06)

扫描 .omo/state/agent-beliefs/index.yaml 中的物理踩坑信念。
当发现同 Topic 下累积了 2 次以上的信念记录时，自动萃取并生成 .agents/skills/<topic>/SKILL.md，
实现 Agent 经验反向传播与越用越聪明的物理自我进化能力。
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import yaml

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
BELIEFS_PATH = WORKSPACE_ROOT / ".omo" / "state" / "agent-beliefs" / "index.yaml"
SKILLS_DIR = WORKSPACE_ROOT / ".agents" / "skills"


class SkillCrystallizer:
    """SEMA 技能自动结晶与经验反向传播引擎"""

    def __init__(self, root: Path | None = None) -> None:
        # T6-06: root 生效 (修原 bug: beliefs_path/skills_dir 用全局常量, 测试无法隔离)
        self.root = root or WORKSPACE_ROOT
        self.beliefs_path = self.root / ".omo" / "state" / "agent-beliefs" / "index.yaml"
        self.skills_dir = self.root / ".agents" / "skills"

    def _load_beliefs(self) -> List[Dict[str, Any]]:
        if not self.beliefs_path.exists():
            return []
        try:
            with open(self.beliefs_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return data.get("beliefs", [])
        except Exception:
            return []

    def scan_and_crystallize(self) -> Dict[str, Any]:
        """扫描踩坑记录并结晶 Skill"""
        beliefs = self._load_beliefs()
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for b in beliefs:
            topic = b.get("topic", "general")
            grouped[topic].append(b)

        crystallized_skills = []
        skipped_topics = []

        for topic, b_list in grouped.items():
            if len(b_list) >= 2 or topic in ("8d_meta_architecture", "git_shim", "gac_gate"):
                # 触发技能结晶条件
                skill_dir = self.skills_dir / topic
                skill_file = skill_dir / "SKILL.md"
                skill_dir.mkdir(parents=True, exist_ok=True)

                if not skill_file.exists():
                    # 自动生成结晶 Skill 包
                    content = self._generate_skill_md(topic, b_list)
                    with open(skill_file, "w", encoding="utf-8") as sf:
                        sf.write(content)
                    crystallized_skills.append({"topic": topic, "count": len(b_list), "file": str(skill_file.relative_to(self.root))})
                else:
                    skipped_topics.append({"topic": topic, "reason": "Skill 已存在", "count": len(b_list)})
            else:
                skipped_topics.append({"topic": topic, "reason": "踩坑次数未满 2 次", "count": len(b_list)})

        return {
            "status": "success",
            "total_beliefs_scanned": len(beliefs),
            "crystallized_count": len(crystallized_skills),
            "crystallized_skills": crystallized_skills,
            "skipped_topics": skipped_topics,
        }

    def _generate_skill_md(self, topic: str, b_list: List[Dict[str, Any]]) -> str:
        lines = []
        lines.append(f"---")
        lines.append(f"name: {topic}")
        lines.append(f"description: SEMA 自动结晶技能包 — 基于 {len(b_list)} 条 MOS 物理踩坑信念反向萃取")
        lines.append(f"category: SEMA-Crystallized-Skill")
        lines.append(f"---")
        lines.append(f"")
        lines.append(f"# 🛡️ 技能包: {topic}")
        lines.append(f"")
        lines.append(f"> 本 Skill 由 SEMA (Self-Evolving Multi-Agent) 自动结晶引擎基于 Agent 踩坑经验生成。")
        lines.append(f"")
        lines.append(f"## 1. 💡 历史踩坑与避坑指南 (Lessons & Pitfalls)")
        lines.append(f"")
        for idx, b in enumerate(b_list, 1):
            lines.append(f"### 踩坑纪录 #{idx}: {b.get('id', 'N/A')}")
            lines.append(f"* **信念陈述**: {b.get('belief_text', 'N/A')}")
            lines.append(f"* **常见坑点**: {b.get('pitfall', 'N/A')}")
            lines.append(f"* **推荐解法**: {b.get('solution', 'N/A')}")
            lines.append(f"")
        lines.append(f"## 2. ⚡️ 标准执行流程 (Standard Workflow)")
        lines.append(f"1. 遵循 `make gac-local-gate` 42 Checks 100% ALL GREEN PASS 门禁。")
        lines.append(f"2. 针对 `{topic}` 相关变更，强制走物理隔离工作区。")
        return "\n".join(lines)


def main() -> int:
    crystallizer = SkillCrystallizer()
    res = crystallizer.scan_and_crystallize()
    print("=========================================================================")
    print(" ⚡️ SEMA 技能自动结晶引擎 (BET-Y1Q2-T6-06)")
    print("=========================================================================")
    print(f"  • 扫描 MOS 信念数: {res['total_beliefs_scanned']} 条")
    print(f"  • 成功结晶 Skill 数: {res['crystallized_count']} 个")
    for sk in res["crystallized_skills"]:
        print(f"    ✅ [Topic: {sk['topic']}] ➔ 生成技能包: {sk['file']} (包含 {sk['count']} 条踩坑纪录)")
    print("=========================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
