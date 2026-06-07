from __future__ import annotations

# ruff: noqa: RUF002
import importlib
import logging
import os
import re
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


class RefinementDaemon:
    def __init__(self) -> None:
        self.root = Path(os.environ.get("BOS_ROOT", "."))

    def run_auto_distill(self, task_report: Any) -> bool:
        """根据报告内容，决定是否执行萃取"""
        _log.info("\n🧙 [RefinementDaemon] 正在扫描复盘报告中的演化线索...")

        if "[🔥 ARCHE_CANDIDATE]" in str(task_report):
            match = re.search(r"path:([\w/\._-]+)\s+cat:(\w+)", str(task_report))
            if match:
                src_path, category = match.groups()
                _log.info("  ✨ 识别到进化候选者: {src_path} -> {category}")
                # 执行物理萃取
                distiller = importlib.import_module("organs.D_Execution.organs.engine.archetype_distiller").Distiller
                distiller.distill(src_path, category)
                return True

        _log.info("  └─ 本次循环未发现显著的通用演化资产。")
        return False


Daemon = RefinementDaemon()
