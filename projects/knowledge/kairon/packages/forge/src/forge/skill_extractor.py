"""skill_extractor — 从成功任务执行中提取技能原型。

提取自 D_Extension organ，已移除 SharedBrain 依赖。
独立运行，不依赖 SharedBrain 运行时。
"""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)


class SkillExtractor:
    """技能提取器：从成功任务执行中提取技能原型。

    分析成功的任务模式，将其反馈给上游系统用于原型提炼和技能进化。
    """

    def __init__(self) -> None:
        self._extraction_count: int = 0

    def extract_from_task(
        self,
        task_id: str | None = None,
        content: str | None = None,
        task_type: str = "generic",
        **params: Any,
    ) -> dict[str, Any]:
        """从任务记录中提取技能。

        Args:
            task_id: 任务唯一标识
            content: 任务内容/代码
            task_type: 任务类型/类别 (默认 "generic")
            **params: 额外参数（兼容旧 params dict 调用）

        Returns:
            包含 status, message 和提取结果的字典。
        """
        # 兼容旧式 params dict 调用
        tid: str | None = task_id or params.get("task_id")
        tcontent: str | None = content or params.get("content")
        ttype: str = task_type if task_type != "generic" else params.get("type", "generic")

        if not tid or not tcontent:
            return {"status": "error", "message": "Missing task_id or content"}

        _log.info("SkillExtractor: high-value task detected: %s. Starting skill feedback loop...", tid)

        self._extraction_count += 1

        # 技能指纹提取（本地逻辑，不再跨域调用）
        skill_fingerprint: dict[str, Any] = {
            "component_name": f"skill_{ttype}_{self._extraction_count}",
            "source_task": tid,
            "sample_code": tcontent,
            "task_type": ttype,
        }

        return {
            "status": "success",
            "message": "Skill extracted successfully",
            "skill_fingerprint": skill_fingerprint,
            "extraction_count": self._extraction_count,
        }

    def extract_batch(
        self,
        tasks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """批量提取技能。

        Args:
            tasks: 任务字典列表，每个需含 task_id 和 content。

        Returns:
            每个任务的提取结果列表。
        """
        results: list[dict[str, Any]] = []
        for task in tasks:
            result = self.extract_from_task(**task)
            results.append(result)
        return results

    @property
    def extraction_count(self) -> int:
        """已提取的技能数量。"""
        return self._extraction_count


# 模块级单例
extractor = SkillExtractor()
