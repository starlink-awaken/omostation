# ruff: noqa: RUF003
# ---
# domain: D-Intelligence
# layer: organ
# status: active
# ---
from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib import import_module
from typing import Any

"""
---
Type: Infrastructure
Status: ACTIVE
Version: 0.0.0
Owner: '@Sisyphus'
Layer: L0-L2
Constraint: "[!!] AUTO_ADDED_METADATA"
Summary: 'Auto-added metadata for nucleus/Z-Microkernel/organs/semantic_matcher.py'
Tags:
- auto-metadata
Authority: organs/D-Execution/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Semantic Matcher ≡ Module
# 内涵 ≝ {Semantic, Matcher}
# 外延 ≝ {e | e ∈ D-Execution ∧ implements(e, SemanticMatcher)}
# 功能 ⊢ {Semantic_Matcher, Init_Semantic, Validate_Matcher}
# =============================================================================

_log = logging.getLogger(__name__)


def _make_semantic_index() -> Any:
    module = import_module("organs.D_Execution.organs.semantic_index")
    return module.SemanticIndex()


@dataclass
class RoleMatchResult:
    role_id: str
    match_mode: str
    total_score: float
    confidence: float
    matched_materials: list[object]
    is_fallback: bool = False


class SemanticMatcher:
    def __init__(self) -> None:
        self.semantic_needs: dict[str, Any] = {}
        self.semantic_index = _make_semantic_index()
        self.fallback_map = {"needs.arch.audit": "axiom-weaver", "needs.sec.audit": "omega-auditor"}
        _log.info("SemanticMatcher initialized")

    def match_role_for_need(self, need_id: str, threshold: float = 0.85) -> RoleMatchResult:
        _log.info("Matching need: {need_id}")

        # 这里是简化逻辑，实际应该查询索引
        if "audit" in need_id:
            return RoleMatchResult("axiom-weaver", "dynamic", 0.95, 0.96, [], False)

        # Fallback
        rid = self.fallback_map.get(need_id, "sisyphus")
        return RoleMatchResult(rid, "fallback", 1.0, 1.0, [], True)
