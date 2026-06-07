"""
SSOT Kernel — patterns/contradiction.py
矛盾推导模式 (R-INF-001)

从事实数据中检测结构性矛盾，产出推论。
泛化版本：不关心"双轨"是什么，只关心 pattern 匹配。
"""

from __future__ import annotations

import re

from ..meta_model import DomainConfig, Rule
from .base import BasePattern, CheckResult


class ContradictionPattern(BasePattern):
    """矛盾推导模式。

    泛化工作原理：
    - 读取 rule.premises 中的条件表达式
    - 条件可以是：
      a) entity_attr(entity_id, attr_name) == value     — 实体属性匹配
      b) fact_ratio(fact_id_A, fact_id_B) < threshold     — 事实比例
      c) text_entity_exists(prefix, keyword)              — 文本中存在某实体
    - 全部前提满足 → 产出推论
    """

    @property
    def pattern_name(self) -> str:
        return "contradiction"

    def evaluate(self, rule: Rule, domain: DomainConfig, context: dict | None = None) -> CheckResult:
        rule_id = rule.id
        rule_name = rule.name or rule_id

        if not rule.premises:
            return CheckResult(protocol_id=rule_id, name=rule_name, passed=True, details=["⚠️ 无前提条件，跳过"])

        triggered = []
        for premise in rule.premises:
            cond = premise.get("condition", "")
            matched = self._evaluate_condition(cond, domain)
            triggered.append({"condition": cond, "matched": matched})

        all_matched = all(t["matched"] for t in triggered)

        if all_matched:
            # 条件满足 → 产出推论
            conclusion = rule.logic
            params = rule.params or {}
            if params.get("template") and params.get("solutions"):
                template = params["template"]
                conclusion = template.format(
                    solutions="/".join(params["solutions"]),
                    red_zone=params.get("red_zone", "A"),
                    blue_zone=params.get("blue_zone", "B"),
                )

            # 检查是否已存在相同推论
            existing = [i for i in domain.inferences if i.id == rule_id]

            details = [f"⚡ 矛盾触发: {rule_name}"]
            for t in triggered:
                details.append(f"  ├─ {t['condition']} → {'⚠️ 匹配' if t['matched'] else '不匹配'}")
            details.append(f"  └─ 结论: {conclusion[:80]}...")

            return CheckResult(
                protocol_id=rule_id,
                name=rule_name,
                passed=True,
                severity="ERROR",
                details=details,
                meta={
                    "triggered": True,
                    "conclusion": conclusion,
                    "inference_id": rule_id,
                    "already_exists": len(existing) > 0,
                },
            )
        else:
            return CheckResult(
                protocol_id=rule_id,
                name=rule_name,
                passed=True,
                details=[f"⏹️ 前提未满足: {rule_name} - 跳过"],
                meta={"triggered": False},
            )

    def _evaluate_condition(self, condition: str, domain: DomainConfig) -> bool:
        """评估一条前提条件表达式。

        支持的条件语法（可扩展）：
        - entity_attr("ORG-X", "mechanism") == "双轨"
        - fact_ratio("DAT-D-F3", "DAT-D-F1") < 0.1
        - entity_exists("ORG-", "双轨")
        """
        condition = condition.strip()

        # entity_attr(id, attr) op value
        m = re.match(r'entity_attr\("([^"]+)",\s*"([^"]+)"\)\s*(==|!=|in)\s*(.+)$', condition)
        if m:
            eid, attr, op, val = m.group(1), m.group(2), m.group(3), m.group(4).strip().strip('"')
            entity = domain.find_entity(eid)
            if not entity:
                return False
            actual = str(entity.attributes.get(attr, ""))
            op_table = {
                "==": actual == val,
                "!=": actual != val,
                "in": val in actual,
            }
            if op in op_table:
                return op_table[op]

        # fact_ratio(id_a, id_b) op threshold
        m = re.match(r'fact_ratio\("([^"]+)",\s*"([^"]+)"\)\s*(<|<=|==|>|>=)\s*([\d.]+)$', condition)
        if m:
            fa_id, fb_id = m.group(1), m.group(2)
            op = m.group(3)
            threshold = float(m.group(4))
            fa = domain.find_fact(fa_id)
            fb = domain.find_fact(fb_id)
            if not fa or not fb:
                return False
            try:
                ratio = float(fa.value or 0) / float(fb.value or 1)
            except (ValueError, ZeroDivisionError):
                return False
            op_table = {
                "<": ratio < threshold,
                "<=": ratio <= threshold,
                ">": ratio > threshold,
                ">=": ratio >= threshold,
                "==": abs(ratio - threshold) < 0.001,
            }
            if op in op_table:
                return op_table[op]

        # entity_exists(prefix, keyword) — 实体中存在含关键词的
        m = re.match(r'entity_exists\("([^"]+)",\s*"([^"]+)"\)', condition)
        if m:
            prefix, keyword = m.group(1), m.group(2)
            for e in domain.entities:
                if e.id.startswith(prefix) and (keyword in str(e.attributes) or keyword in e.name):
                    return True
            return False

        return False
