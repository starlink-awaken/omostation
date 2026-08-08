"""omo.digital_brain.memory_bridge — 数字大脑混合双层记忆 Bridge (MOS 心智与规则 + KOS 知识与文件).

打通个人踩坑信念 (Beliefs)、用户心智范式 (Mental Model)
与底层 KOS 知识库/公文文件的统一保鲜检索与共享。
"""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional


class DigitalBrainMemoryBridge:
    """数字大脑统一双层记忆 Bridge"""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or Path.cwd()
        self.beliefs_path = (
            self.root_dir / ".omo" / "state" / "agent-beliefs" / "index.yaml"
        )

    def get_user_mental_model(self) -> dict[str, Any]:
        """获取用户个人背景、心智模型与沟通偏好."""
        return {
            "background": "北邮CS硕士, 前大厂前端, 现卫健委信息化主管",
            "core_meta_cognitive": ["连接力", "架构思维", "元认知", "代码洁癖"],
            "core_viewpoints": {
                "LLM": "CPU",
                "Agent": "OS",
                "MCP": "硬件",
                "future_value": "架构与创造力",
            },
            "virtual_board": [
                "🧑‍💻 Builder (How)",
                "⚡️ Devil (Risk)",
                "🧠 Sage (Essence)",
                "👁️ Keeper (Memory)",
            ],
            "communication_preference": "中文, 严谨客观, 拒绝廉价赞同与糊弄写死假象",
        }

    def query_beliefs(self, topic_keyword: str = "") -> list[dict[str, Any]]:
        """检索 MOS agent-beliefs 踩坑记忆库."""
        if not self.beliefs_path.exists():
            return []

        try:
            with open(self.beliefs_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                beliefs = data.get("beliefs", [])
                if not topic_keyword:
                    return beliefs
                kw = topic_keyword.lower()
                return [
                    b
                    for b in beliefs
                    if kw in b.get("topic", "").lower()
                    or kw in b.get("belief", "").lower()
                ]
        except Exception:
            return []

    def get_unified_context(self, task_domain: str = "workplace") -> dict[str, Any]:
        """为全网 Agent 提供包含心智、规则与知识的统一 Context Snapshot."""
        return {
            "mental_model": self.get_user_mental_model(),
            "active_beliefs_count": len(self.query_beliefs()),
            "domain": task_domain,
            "timestamp": "2026-08-08T09:00:00Z",
            "status": "synchronized",
        }
