from __future__ import annotations

# ruff: noqa: RUF002, RUF003
import logging
import os
import re
import subprocess
from typing import Any

from ._compat import AgentDaemonBase

"""
---
Type: Infrastructure
Status: ACTIVE
Version: 0.0.0
Owner: '@Sisyphus'
Layer: L0-L2
Constraint: "[!!] AUTO_ADDED_METADATA"
Summary: 'Auto-added metadata for nucleus/Z-Microkernel/organs/opencode_worker.py'
Tags:
- auto-metadata
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-GN01-01_differentiation_protocol.md
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Microkernel_Component ≡ System_Bus
# 内涵 ≝ {Routing, Scheduling, Communication}
# 外延 ≝ {m | m ∈ Z-Microkernel ∧ orchestrates(m, Communication)}
# 功能 ⊢ {RouteMessages, ScheduleTasks, ManageBus}
# =============================================================================

_log = logging.getLogger(__name__)


class OpenCodeWorker(AgentDaemonBase):
    """真·侦察兵：执行物理磁盘扫描并生成结构化报告"""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            agent_id="OpenCode",
            persona="Scout / Telemetry / Scanning Specialist",
            capabilities=["infra.scan", "telemetry.*"],
            **kwargs,
        )

    def process_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        summary = payload.get("summary", "Scanning Task")
        content = payload.get("content", "")
        _log.info("[%s] 🔍 Deep Scanning: %s", self.agent_id, summary)

        # 1. 动态提取路径 (从 Markdown 内容中解析绝对路径)
        paths = re.findall(r"(/[^\s`]+)", content)
        target_path = paths[0] if paths else "support/trash"

        if not os.path.exists(target_path):
            return {"status": "ERROR", "message": f"Path not found: {target_path}"}

        # 2. 执行物理扫描 (Real Action)
        _log.info("[%s] 🚀 Scanning physical path: %s", self.agent_id, target_path)

        try:
            # 限制扫描深度，避免内存爆炸
            res = subprocess.run(  # noqa: S603
                ["find", target_path, "-maxdepth", "2", "-not", "-path", "*/.*"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=60,
            )
            file_list = res.stdout.splitlines()

            # 3. 构造深度报告
            report_content = f"# 📜 扫描报告: {target_path}\n\n"
            report_content += f"- **总计项**: {len(file_list)}\n"
            report_content += "- **顶级拓扑**:\n"
            report_content += "\n".join([f"  - `{f}`" for f in file_list[:50]])  # 仅展示前50项

            if len(file_list) > 50:
                report_content += f"\n\n... 还有 {len(file_list) - 50} 项未显示。"

            return {
                "status": "SUCCESS",
                "handover": {
                    "target": "Gemini-CLI",
                    "summary": f"📜 扫描结果汇总: {target_path}",
                    "content": report_content,
                    "phase": 4,
                },
            }
        except (TypeError, ValueError, AttributeError) as e:
            _log.error("%s: %s", type(e).__name__, e)
            return {"status": "ERROR", "message": str(e)}


if __name__ == "__main__":
    OpenCodeWorker().run()
