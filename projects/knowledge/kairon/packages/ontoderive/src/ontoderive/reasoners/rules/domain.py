"""Domain-specific reasoning checks."""

import re
from typing import Any

from .common import (
    calc_depth,
)


def shared_premise_check(engine: Any, inferences: Any) -> Any:
    """R2: 共享前提检测 — 两个推论引用相同事实可能互补或矛盾"""
    results = []
    inf_list = list(inferences.items())
    for i in range(len(inf_list)):
        for j in range(i + 1, len(inf_list)):
            a_id, a_info = inf_list[i]
            b_id, b_info = inf_list[j]
            shared = set(a_info.get("derives_from", [])) & set(b_info.get("derives_from", []))
            if len(shared) >= 2:
                results.append(
                    {
                        "type": "shared_premise",
                        "conclusion": (f"推论'{a_id[:30]}'和'{b_id[:30]}'共享{len(shared)}个前提({list(shared)[:3]})"),
                        "derived_from": list(shared),
                        "confidence": 0.75,
                        "method": "rule_engine",
                    }
                )
    return results


def missing_ref_check(engine: Any, inferences: Any, all_ids: Any) -> Any:
    """R3: 缺失引用 — 三段论的前提断裂"""
    results = []
    for title, info in inferences.items():
        for ref in info.get("derives_from", []):
            if ref not in all_ids:
                results.append(
                    {
                        "type": "missing_reference",
                        "conclusion": f"推论'{title[:30]}'引用了未定义的'{ref}'",
                        "derived_from": [ref],
                        "confidence": 0.99,
                        "method": "rule_engine",
                    }
                )
    return results


def evidence_gap_check(engine: Any, inferences: Any) -> Any:
    """R4: 证据缺口 — 前提不足以支持推论"""
    results = []
    for title, info in inferences.items():
        n = len(info.get("derives_from", []))
        if 0 < n < 2:
            results.append(
                {
                    "type": "evidence_gap",
                    "conclusion": f"推论'{title[:30]}'仅{n}个前提，建议增加到2+",
                    "derived_from": info.get("derives_from", []),
                    "confidence": 0.80,
                    "method": "rule_engine",
                }
            )
    return results


def threshold_check(engine: Any, facts: Any, thresholds: Any = None) -> Any:
    """R5: 阈值触发 — 预设基准检查"""
    if thresholds is None:
        thresholds = {
            "转化率": 10.0,
            "成功率": 80.0,
            "覆盖率": 60.0,
            "满意度": 70.0,
            "测试覆盖率": 60.0,
        }
    results = []
    for fid, info in facts.items():
        desc = info.get("desc", "")
        for metric, threshold in thresholds.items():
            if metric in desc:
                m = re.search(r"(\d+\.?\d*)", str(info.get("value", "")))
                if m:
                    val = float(m.group(1))
                    if val < threshold:
                        results.append(
                            {
                                "type": "threshold_alert",
                                "conclusion": f"{desc}({val})低于基准{threshold}",
                                "derived_from": [fid],
                                "confidence": 0.90,
                                "method": "rule_engine",
                            }
                        )
    return results


def chain_integrity_check(engine: Any, inferences: Any) -> Any:
    """R6: 推导链完整性 — INF→INF链是否完整"""
    results = []
    inf_ids = set(inferences.keys())
    for title, info in inferences.items():
        for ref in info.get("derives_from", []):
            if ref.startswith("INF") and ref not in inf_ids:
                results.append(
                    {
                        "type": "chain_break",
                        "conclusion": f"推导链断裂: '{title[:30]}'引用了未定义的'{ref}'",
                        "derived_from": [ref],
                        "confidence": 0.99,
                        "method": "rule_engine",
                    }
                )
    # 检测推导深度
    depths: dict[Any, Any] = {}
    for title in inferences:
        calc_depth(engine, title, inferences, depths, set())
    max_depth = max(depths.values()) if depths else 0
    if max_depth <= 1 and len(inferences) >= 3:
        results.append(
            {
                "type": "shallow_chain",
                "conclusion": f"推导链深度仅{max_depth}，{len(inferences)}个推论间缺少递进关系",
                "derived_from": [],
                "confidence": 0.70,
                "method": "rule_engine",
            }
        )
    return results
