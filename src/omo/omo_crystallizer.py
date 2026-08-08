"""omo_crystallizer.py — SEMA 技能自动结晶引擎 (BET-Y1Q2-T6-06).

当 MOS 信念记录同 topic 累积 >= 2 次时, 自动萃取为 .agents/skills/<topic>/SKILL.md.
闭环: record_belief → threshold check → crystallize → skill file.

守 ADR-0372: 技能产物入 .agents/skills/ (workspace 级, 非 .omo 状态面).
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from .omo_paths import WORKSPACE_ROOT

CRYSTALLIZATION_THRESHOLD = 2

DEFAULT_SKILLS_DIR = WORKSPACE_ROOT / ".agents" / "skills"


def _sanitize_topic_dir(topic: str) -> str:
    """Convert topic name to valid directory name (colons → colons kept for namespacing)."""
    return topic.replace(" ", "-").replace("/", "-")


class SkillCrystallizer:
    """SEMA 技能自动结晶与经验反向传播引擎."""

    def __init__(
        self,
        skills_dir: Path | None = None,
    ) -> None:
        self.skills_dir = skills_dir or DEFAULT_SKILLS_DIR

    def check_and_crystallize(
        self,
        beliefs: list[dict[str, Any]],
        lessons: list[dict[str, Any]] | None = None,
        contexts: list[dict[str, Any]] | None = None,
        topic: str | None = None,
    ) -> dict[str, Any]:
        """Check if a topic meets threshold and crystallize if needed.

        Args:
            beliefs: All beliefs from MOS state.
            lessons: All lessons from MOS state.
            contexts: All contexts from MOS state.
            topic: If set, only check this topic (auto-trigger path).
                   If None, scan all topics (CLI batch path).

        Returns:
            Dict with crystallization results.
        """
        lessons = lessons or []
        contexts = contexts or []

        if topic:
            topic_beliefs = [b for b in beliefs if b.get("topic") == topic]
            if len(topic_beliefs) < CRYSTALLIZATION_THRESHOLD:
                return {
                    "status": "below_threshold",
                    "topic": topic,
                    "count": len(topic_beliefs),
                    "threshold": CRYSTALLIZATION_THRESHOLD,
                }
            return self._crystallize_topic(topic, topic_beliefs, lessons, contexts)

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for b in beliefs:
            grouped[b.get("topic", "general")].append(b)

        crystallized = []
        skipped = []
        for t, b_list in grouped.items():
            if len(b_list) < CRYSTALLIZATION_THRESHOLD:
                skipped.append(
                    {
                        "topic": t,
                        "reason": "below_threshold",
                        "count": len(b_list),
                    }
                )
                continue
            result = self._crystallize_topic(t, b_list, lessons, contexts)
            if result["status"] == "crystallized":
                crystallized.append(result)
            else:
                skipped.append(result)

        return {
            "status": "success",
            "total_beliefs": len(beliefs),
            "crystallized_count": len(crystallized),
            "crystallized": crystallized,
            "skipped": skipped,
        }

    def _crystallize_topic(
        self,
        topic: str,
        beliefs: list[dict[str, Any]],
        lessons: list[dict[str, Any]],
        contexts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Crystallize a single topic into a SKILL.md."""
        dir_name = _sanitize_topic_dir(topic)
        skill_dir = self.skills_dir / dir_name
        skill_file = skill_dir / "SKILL.md"

        belief_ids = {b["id"] for b in beliefs}
        topic_lessons = [l for l in lessons if l.get("belief_id") in belief_ids]
        topic_contexts = [c for c in contexts if c.get("belief_id") in belief_ids]

        if skill_file.exists():
            existing = skill_file.read_text(encoding="utf-8")
            if str(len(beliefs)) in existing:
                return {
                    "status": "already_exists",
                    "topic": topic,
                    "count": len(beliefs),
                    "file": str(skill_file),
                }

        content = self._generate_skill_md(topic, beliefs, topic_lessons, topic_contexts)
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(content, encoding="utf-8")

        return {
            "status": "crystallized",
            "topic": topic,
            "count": len(beliefs),
            "lessons": len(topic_lessons),
            "contexts": len(topic_contexts),
            "file": str(skill_file),
        }

    def _generate_skill_md(
        self,
        topic: str,
        beliefs: list[dict[str, Any]],
        lessons: list[dict[str, Any]],
        contexts: list[dict[str, Any]],
    ) -> str:
        """Generate SKILL.md content from beliefs, lessons, and contexts."""
        lines = [
            "---",
            f"name: {topic}",
            f"description: SEMA 自动结晶技能包 — 基于 {len(beliefs)} 条 MOS 踩坑信念反向萃取",
            "category: SEMA-Crystallized-Skill",
            "---",
            "",
            f"# Skill: {topic}",
            "",
            "> Auto-crystallized by SEMA engine from agent pitfall experience.",
            "> Source: .omo/state/agent-beliefs/index.yaml",
            "",
        ]

        if lessons:
            lines.append("## Pitfalls & Solutions")
            lines.append("")
            for idx, lesson in enumerate(lessons, 1):
                lines.append(f"### #{idx} [{lesson.get('severity', 'warning')}]")
                lines.append(f"- **Pitfall**: {lesson.get('pitfall', 'N/A')}")
                lines.append(f"- **Solution**: {lesson.get('solution', 'N/A')}")
                lines.append("")

        lines.append("## Beliefs")
        lines.append("")
        for idx, b in enumerate(beliefs, 1):
            lines.append(f"### #{idx} {b.get('id', 'N/A')}")
            lines.append(f"- **Belief**: {b.get('belief', 'N/A')}")
            if b.get("confidence", 1.0) < 1.0:
                lines.append(f"- **Confidence**: {b['confidence']:.2f}")
            if b.get("pitfall"):
                lines.append(f"- **Pitfall**: {b['pitfall']}")
            if b.get("solution"):
                lines.append(f"- **Solution**: {b['solution']}")
            lines.append("")

        if contexts:
            lines.append("## Applicable Scope")
            lines.append("")
            for ctx in contexts:
                lines.append(f"- `{ctx.get('scope_path', '*')}`")
            lines.append("")

        lines.append("## Standard Workflow")
        lines.append("")
        lines.append(f"1. Run `make gac-local-gate` — all checks must pass.")
        lines.append(f"2. For `{topic}` changes, use isolated worktree.")
        lines.append(f"3. Verify with targeted tests before expanding scope.")
        lines.append("")

        return "\n".join(lines)


__all__ = [
    "CRYSTALLIZATION_THRESHOLD",
    "DEFAULT_SKILLS_DIR",
    "SkillCrystallizer",
]
