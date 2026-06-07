from __future__ import annotations

# ruff: noqa: RUF001, RUF003
from ._compat import ProjectPaths

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
import sqlite3
import subprocess
from typing import Any

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
Version: 1.0.0
Owner: '@Gemini-CLI'
Authority: organs/D-Execution/AGENTS.md
Layer: L3
Constraint: "[!!] COMPUTE_ASSET_HARVESTER"
---
"""
# 🚜 算力资产收割机 (Compute Asset Harvester - CH-01)
# 职责: 从物理系统（cc-switch, antigravity, ollama, codexbar）中抓取实时资产元数据，并同步至认知网关。

_log = logging.getLogger(__name__)


class ComputeHarvester:
    def __init__(self, cognitive_db: str = str(ProjectPaths.get_core_db_path("cognitive.db"))) -> None:
        super().__init__()
        self.cognitive_db = cognitive_db
        # 使用环境变量，无默认值（必须在运行时配置）
        self.cc_switch_db = os.environ.get("BOS_CC_SWITCH_DB", "")
        self.antigravity_cfg = os.environ.get("BOS_ANTIGRAVITY_CFG", "")

        # 警告：如果环境变量未设置，相关功能将不可用
        if not self.cc_switch_db:
            _log.warning("BOS_CC_SWITCH_DB 环境变量未设置，cc-switch 资产抓取功能将不可用")
        if not self.antigravity_cfg:
            _log.warning("BOS_ANTIGRAVITY_CFG 环境变量未设置，antigravity 账号池抓取功能将不可用")

    def harvest_all(self) -> None:
        """全量收割并同步"""
        _log.info("🚜 [Harvester] 启动全域算力资产抓取...")
        all_nodes = []

        # 1. 抓取 Ollama (本地物理大脑)
        all_nodes.extend(self._harvest_ollama())

        # 2. 抓取 cc-switch (代理与聚合资产)
        all_nodes.extend(self._harvest_cc_switch())

        # 3. 抓取 antigravity (账号池)
        all_nodes.extend(self._harvest_antigravity())

        # 4. 抓取 Trae (双核 IDE)
        all_nodes.extend(self._harvest_trae())

        # 5. 同步至认知池
        self._sync_to_gateway(all_nodes)
        _log.info("✅ [Harvester] 成功收割 {len(all_nodes)} 个算力节点。")

    def _harvest_trae(self) -> list[dict[str, Any]]:
        nodes = []
        # 探测物理路径
        trae_intl = "/Applications/Trae.app/Contents/Resources/app/bin/trae"
        trae_cn = "/Applications/Trae CN.app/Contents/Resources/app/bin/trae"

        if os.path.exists(trae_intl):
            nodes.append(
                {
                    "id": "trae-intl-claude",
                    "synapse": "synapse-trae-intl",
                    "provider": "trae-global",
                    "iq": 9.5,
                    "cost": 0.0,
                    "free": 1,
                    "specialties": '["code", "ide"]',
                }
            )
        if os.path.exists(trae_cn):
            nodes.append(
                {
                    "id": "trae-cn-claude",
                    "synapse": "synapse-trae-cn",
                    "provider": "trae-domestic",
                    "iq": 9.5,
                    "cost": 0.0,
                    "free": 1,
                    "specialties": '["code", "ide"]',
                }
            )
            nodes.append(
                {
                    "id": "trae-cn-qwen",
                    "synapse": "synapse-trae-cn",
                    "provider": "trae-domestic",
                    "iq": 8.0,
                    "cost": 0.0,
                    "free": 1,
                    "specialties": '["code", "fast"]',
                }
            )
        return nodes

    def _harvest_ollama(self) -> list[dict[str, Any]]:
        nodes = []
        try:
            res = subprocess.run(["ollama", "list"], capture_output=True, text=True)  # noqa: S607
            for line in res.stdout.splitlines()[1:]:
                parts = line.split()
                if parts:
                    nodes.append(
                        {
                            "id": parts[0],
                            "synapse": "synapse-ollama",
                            "provider": "local-gpu",
                            "iq": 7.0 if "14b" in parts[0] else 5.0,  # 粗略估算
                            "cost": 0.0,
                            "free": 1,
                            "specialties": '["local", "privacy"]',
                        }
                    )
        except (subprocess.CalledProcessError, OSError):
            _log.debug("Failed to harvest Ollama nodes", exc_info=True)
        return nodes

    def _harvest_cc_switch(self) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        if not os.path.exists(self.cc_switch_db):
            return nodes
        try:
            conn = sqlite3.connect(self.cc_switch_db)
            cursor = conn.cursor()
            rows = cursor.execute("SELECT model_id, display_name FROM model_pricing").fetchall()
            for r in rows:
                nodes.append(
                    {
                        "id": r[0],
                        "synapse": "synapse-cc-switch",
                        "provider": "cc-proxy",
                        "iq": 9.0 if "opus" in r[0] or "5.2" in r[0] else 7.5,
                        "cost": 1.0,
                        "free": 0,
                        "specialties": '["aggregator", "varied"]',
                    }
                )
            conn.close()
        except sqlite3.Error:
            _log.debug("Failed to harvest CC-Switch nodes", exc_info=True)
        return nodes

    def _harvest_antigravity(self) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        if not os.path.exists(self.antigravity_cfg):
            return nodes
        try:
            with open(self.antigravity_cfg) as f:
                data = json.load(f)
                for acc in data.get("accounts", []):
                    # 每个账号映射为一个虚拟节点组
                    nodes.append(
                        {
                            "id": f"antigravity-{acc['email'].split('@')[0]}",
                            "synapse": "synapse-antigravity",
                            "provider": "google-multi",
                            "iq": 8.5,
                            "cost": 0.0,
                            "free": 1,
                            "specialties": '["account-pool"]',
                        }
                    )
        except (json.JSONDecodeError, OSError):
            _log.debug("Failed to harvest Antigravity nodes", exc_info=True)
        return nodes

    def _sync_to_gateway(self, nodes: list[dict[str, Any]]) -> None:
        conn = sqlite3.connect(self.cognitive_db)
        for n in nodes:
            conn.execute(
                """
            INSERT OR REPLACE INTO cognitive_pools
            (model_id, synapse_id, provider_id, iq_level, cost_per_1k, is_free, specialties, last_update)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    n["id"],
                    n["synapse"],
                    n["provider"],
                    n["iq"],
                    n["cost"],
                    n["free"],
                    n["specialties"],
                    1740830400,
                ),
            )
        conn.commit()
        conn.close()


if __name__ == "__main__":
    ComputeHarvester().harvest_all()
