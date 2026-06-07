from __future__ import annotations

# ruff: noqa: RUF001, RUF003

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""


import json
import logging
import os
from pathlib import Path

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Execution_Organ ≡ Task_Executor
# 内涵 ≝ {Execute, Orchestrate, Manage}
# 外延 ≝ {e | e ∈ D-Execution ∧ executes(e, Tasks)}
# 功能 ⊢ {ExecuteTasks, ManageWorkspace, OrchestrateAgents}
# =============================================================================

"""
---
Type: Engine
Status: ACTIVE
Version: 1.0.0
Owner: '@Gemini-CLI'
Authority: nucleus/Z-Spore/dna/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
Constraint: "[!!] HIFI_QUERY_ACTIVE"
Summary: 'Hifi 图谱查询器：为 Worker 提供无需读取源码即可理解系统结构与逻辑的接口。'
---
"""

_log = logging.getLogger(__name__)


class HifiQuery:
    def __init__(self, hifi_path: str = os.environ.get("BOS_HIFI_PATH", "support/docs/full_system.hifi.json")) -> None:
        super().__init__()
        self.root = Path(os.environ.get("BOS_ROOT", os.getcwd()))
        self.hifi_path = self.root / hifi_path
        self.graph = self._load_graph()

    def _load_graph(self) -> dict:
        if not self.hifi_path.exists():
            return {}
        with open(self.hifi_path) as f:
            return json.load(f)

    def get_node_info(self, node_id: str) -> dict | None:
        """获取节点的符号信息与摘要"""
        return self.graph.get("nodes", {}).get(node_id)

    def find_dependencies(self, node_id: str) -> list[str]:
        """查找指定节点的所有下游依赖"""
        deps = []
        for edge in self.graph.get("edges", []):
            if edge["from"] == node_id and edge["type"] == "DEPENDS_ON":
                deps.append(edge["to"])
        return deps

    def search_by_summary(self, keyword: str) -> list[str]:
        """根据摘要关键词搜索节点"""
        results = []
        for nid, node in self.graph.get("nodes", {}).items():
            if keyword.lower() in node.get("summary", "").lower():
                results.append(nid)
        return results


if __name__ == "__main__":
    # 事后反思：我是否降低了认知负担？是的，通过结构化查询代替了文件全量读取。
    query = HifiQuery()
    results = query.search_by_summary("Audit")
    _log.info("🔍 [Hifi] 匹配到 'Audit' 的节点: {results}")
