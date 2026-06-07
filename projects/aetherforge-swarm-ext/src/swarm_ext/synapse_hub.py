from __future__ import annotations

# ruff: noqa: RUF002, RUF003

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-05_microkernel_fractal_axiom.md
---
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Microkernel_Component ≡ System_Bus
# 内涵 ≝ {Routing, Scheduling, Communication}
# 外延 ≝ {m | m ∈ Z-Microkernel ∧ orchestrates(m, Communication)}
# 功能 ⊢ {RouteMessages, ScheduleTasks, ManageBus}
# =============================================================================

"""
---
Type: Organ
Status: ACTIVE
Version: 1.2.0
Owner: '@Gemini-CLI'
Authority: nucleus/Z-Spore/dna/R0-ACT-SYS-AX01-14_holographic_routing_axiom.md
Layer: L3
Constraint: "[!!] SYNAPSE_HUB_PATH_FIXED"
---
"""
# 🕸️ 通用突触中枢 (Synapse Hub - SH-01)
# 职责: 动态加载 YAML 映射规范，将 20+ 种异构 CLI 工具转化为标准的 B-OS 接口。

_log = logging.getLogger(__name__)


class SynapseHub:
    def __init__(self, archetype_dir: str | None = None) -> None:

        # [物理修复] 显式定位到 nucleus 内部的原型库
        self.root = Path(os.environ.get("BOS_ROOT", os.getcwd()))
        default_archetype_dir = self.root / "nucleus/Z-Spore/archetypes/synapses"
        self.archetype_dir = Path(archetype_dir) if archetype_dir else default_archetype_dir

        self.drivers: dict[str, dict] = {}
        self.load_archetypes()

    def load_archetypes(self) -> None:
        """扫描并加载所有突触原型（支持多文档 YAML）"""
        if not self.archetype_dir.exists():
            _log.info("⚠️ [SynapseHub] 路径不存在: %s", self.archetype_dir)
            return

        for f in self.archetype_dir.glob("*.yaml"):
            try:
                with open(f, encoding="utf-8") as stream:
                    docs = yaml.safe_load_all(stream)
                    for spec in docs:
                        if not spec:
                            continue
                        tool_id = spec.get("tool_id")
                        if tool_id:
                            self.drivers[tool_id] = spec
                            _log.info("✅ [SynapseHub] 已挂载突触驱动: %s", tool_id)
            except (yaml.YAMLError, OSError) as e:
                _log.info("❌ [SynapseHub] 加载原型失败 %s: %s", f.name, e)

    def call(self, tool_id: str, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if tool_id not in self.drivers:
            return {"status": "error", "message": f"Tool {tool_id} not registered."}

        spec = self.drivers[tool_id]
        actions = spec.get("actions", {})
        if action not in actions:
            return {"status": "error", "message": f"Action {action} not defined for {tool_id}."}

        self._constraint_check(f"synapse_call: {tool_id}::{action}")

        cmd_template = actions[action].get("command")
        final_cmd = cmd_template
        for k, v in (params or {}).items():
            final_cmd = final_cmd.replace(f"{{{{{k}}}}}", str(v))

        _log.info("⚙️ [SynapseHub] 执行指令: %s", final_cmd)

        try:
            result = subprocess.run(  # noqa: S602
                final_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=spec.get("timeout", 300),
            )

            parsed_data = self._parse_output(result.stdout)

            response = {
                "status": "success" if result.returncode == 0 else "error",
                "data": parsed_data,
                "stderr": result.stderr,
            }

            # [Evolution V2] 提取 Usage 信息 (Surgery 6.1)
            if isinstance(parsed_data, dict) and "usage" in parsed_data:
                response["usage"] = parsed_data["usage"]

            return response
        except (TypeError, ValueError, AttributeError) as e:
            _log.error("%s: %s", type(e).__name__, e)
            return {"status": "error", "message": str(e)}

    def _parse_output(self, stdout: str) -> Any:
        try:
            return json.loads(stdout)
        except (json.JSONDecodeError, OSError) as e:
            _log.error("%s: %s", type(e).__name__, e)
            return stdout.strip()

    def validate_internal_state(self) -> bool:
        return True

    @staticmethod
    def _constraint_check(_constraint: str) -> None:
        pass


Hub = SynapseHub()
