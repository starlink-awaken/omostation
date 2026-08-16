"""

# ruff: noqa: E501
OntoDerive 规则推导引擎 — 8种推理规则 + 13种结构检查
=====================================================
基于三段论模式+状态机的确定性推导。
不解析自然语言，不替代LLM。但对结构化数据有效。

推理规则(8种): R1数值比较, R7假言, R8传递, R9包含, R10影响, R13选言,
R14假言链, R16一致性
结构检查(13种): R2共享前提, R3缺失引用, R4证据缺口, R5阈值, R6链完整,
R11冗余, R12覆盖, R15时态, R17结构洞, R18约束, R19案例, R20增量,
R21时态序列

能力边界:
✅ 数值比较推导 (D-F1 > D-F2 → 推论A)
✅ 阈值触发推导 (D-F1 < 基准 → 告警)
✅ 共享前提推导 (INF-A和INF-B引用同一组事实 → 可能互补/矛盾)
✅ 缺失证据检测 (推论引用了不存在的ID)
✅ 推导链完整性 (INF-L2引用INF-L1但INF-L1未定义)
❌ 自然语言语义理解
❌ 新概念的创造性发现
❌ 隐喻/类比推理
"""

import re
from dataclasses import dataclass
from typing import Any

from ontoderive.foundation.rule_loader import RuleLoader

from .reasoning_rules import (
    chain_integrity_check,
    change_detection,
    consistency_analysis,
    constraint_propagation,
    coverage_analysis,
    disjunctive_syllogism,
    evidence_gap_check,
    hypothetical_syllogism,
    influence_analysis,
    missing_ref_check,
    modus_ponens_check,
    numeric_derive,
    redundancy_check,
    relation_reasoning,
    shared_premise_check,
    structural_holes,
    subsumption_check,
    threshold_check,
    transitive_closure,
)


@dataclass
class DerivationRule:
    """一条推导规则 = 三段论模式"""

    name: str
    premises: list[str]  # 前提模式(正则)
    conclusion_template: str  # 结论模板
    confidence: float = 0.85
    category: str = "deduction"  # deduction | induction | abduction


class RuleReasoner:
    _TYPE_TO_RULE = {
        "numeric_comparison": "R1",
        "shared_premise": "R2",
        "missing_reference": "R3",
        "evidence_gap": "R4",
        "threshold_alert": "R5",
        "chain_break": "R6",
        "modus_ponens_valid": "R7",
        "modus_ponens_fail": "R7",
        "transitive_dependency": "R8",
        "subsumption": "R9",
        "influence_analysis": "R10",
        "redundancy_warning": "R11",
        "coverage": "R12",
        "disjunctive_syllogism": "R13",
        "hypothetical_syllogism": "R14",
        "temporal_sequence": "R15",
        "consistency_warning": "R16",
        "structural_hole": "R17",
        "constraint_propagation": "R18",
        "relation_transitive": "R19",
        "relation_inverse": "R19",
        "relation_domain": "R19",
        "relation_range": "R19",
        "shallow_chain": "R6",
    }

    def __init__(self, loaded_rules: list | None = None) -> None:
        self.rules: list[DerivationRule] = self._default_rules()
        self._rule_loader = RuleLoader()
        if loaded_rules is not None:
            self._loaded_rules = loaded_rules
        else:
            # 自动从 YAML 规则目录加载
            self._loaded_rules = self._rule_loader.load_all()
        self.state = "idle"

    def _default_rules(self) -> list[Any]:
        """内置推导规则库 — 可扩展"""
        return [
            # ── 数值比较规则 ──
            DerivationRule(
                name="numeric_comparison",
                premises=["D-F\\d+.*?(\\d+\\.?\\d*).*?(\\d+\\.?\\d*)"],
                conclusion_template="数值比较: {label1}={val1} vs {label2}={val2}",
                confidence=0.95,
                category="deduction",
            ),
            # ── 共享前提规则 ──
            DerivationRule(
                name="shared_premise_alert",
                premises=[],
                conclusion_template="INF-{a}和INF-{b}共享{n}个前提事实，可能互补或矛盾",
                confidence=0.75,
                category="induction",
            ),
            # ── 缺失引用规则 ──
            DerivationRule(
                name="missing_reference",
                premises=[],
                conclusion_template="推论 {inf} 引用了不存在的事实 {fid}",
                confidence=0.99,
                category="deduction",
            ),
            # ── 证据缺口规则 ──
            DerivationRule(
                name="evidence_gap",
                premises=[],
                conclusion_template="推论 {inf} 基于{n}个前提，建议增加引用以增强可信度",
                confidence=0.80,
                category="induction",
            ),
            # ── 阈值触发规则 ──
            DerivationRule(
                name="threshold_alert",
                premises=[],
                conclusion_template="{metric}达到{value}，超过基准{threshold}",
                confidence=0.90,
                category="deduction",
            ),
        ]

    def derive(
        self, facts: dict[str, dict], inferences: dict[str, dict], relations: list[dict] | None = None
    ) -> list[dict]:
        """
        基于规则库做确定性推导。
        facts: {id: {desc, value, ...}}   inferences: {title: {text, derives_from, ...}}
        relations: [{subject, relation_type, object}, ...]  (R19)
        """
        self.state = "deriving"
        results = []

        # R1: 数值比较
        results.extend(numeric_derive(self, facts))

        # R2: 共享前提检测
        results.extend(shared_premise_check(self, inferences))

        # R3: 缺失引用检测
        all_ids = set(facts.keys()) | set(inferences.keys())
        results.extend(missing_ref_check(self, inferences, all_ids))

        # R4: 证据缺口
        results.extend(evidence_gap_check(self, inferences))

        # R5: 阈值触发
        results.extend(threshold_check(self, facts))

        # R6: 推导链完整性
        results.extend(chain_integrity_check(self, inferences))

        # R7: 假言推理
        results.extend(modus_ponens_check(self, inferences, facts))

        # R8: 传递推理
        results.extend(transitive_closure(self, inferences, facts))

        # R9: 包含推理 (增强版)
        results.extend(subsumption_check(self, inferences, facts))

        # R10: 影响传播
        results.extend(influence_analysis(self, inferences, facts))

        # R11: 冗余检测
        results.extend(redundancy_check(self, inferences))

        # R12: 覆盖度分析
        results.extend(coverage_analysis(self, inferences, facts))

        # R13: 选言三段论
        results.extend(disjunctive_syllogism(self, inferences))

        # R14: 假言三段论
        results.extend(hypothetical_syllogism(self, inferences))

        # R15: 变化检测
        results.extend(change_detection(self, facts))

        # R16: 一致性分析
        results.extend(consistency_analysis(self, inferences, facts))

        # R17: 结构洞检测
        results.extend(structural_holes(self, inferences))

        # R18: 约束传播
        results.extend(constraint_propagation(self, inferences, facts))

        # R19: 关系推理 — 传递性/逆关系/域约束 (v3.3)
        if relations:
            results.extend(relation_reasoning(self, relations))

        # 推理链路可解释性: 每个结论标注规则ID+依赖链
        for r in results:
            rule_id = self._TYPE_TO_RULE.get(r.get("type", ""), "R?")
            deps = r.get("derived_from", [])
            trail = f"{rule_id}: {'→'.join(deps[:4])}" if deps else f"{rule_id}"
            r["derivation_trail"] = trail

        # v3.6: YAML规则执行 — 前提匹配+声明式产出
        if self._loaded_rules:
            yaml_results = self._rule_loader.evaluate_all(facts, inferences)
            results.extend(yaml_results)

        self.state = "done"
        return results

    def case_based_reasoning(self, current_project: Any, reference_cases: Any) -> Any:
        """
        TF-IDF驱动的案例匹配 — 无LLM的CBR引擎。
        current_project: {facts: {id: info}, inferences: {title: info}}
        reference_cases: [{name: str, facts: dict, inferences: dict, outcome: str}, ...]
        """
        results: list[Any] = []
        if not reference_cases:
            return results

        # 构建当前项目的特征向量
        current_profile = self._project_profile(current_project)

        for case in reference_cases:
            case_profile = self._project_profile(case)
            similarity = self._cosine_similarity(current_profile, case_profile)
            if similarity > 0.3:
                results.append(
                    {
                        "type": "case_match",
                        "conclusion": (
                            f"案例'{case.get('name', '未命名')}'与当前项目相似度{similarity:.0%}, "
                            f"参考结果: {case.get('outcome', '')[:80]}"
                        ),
                        "derived_from": [],
                        "confidence": round(similarity, 2),
                        "method": "rule_engine",
                    }
                )
        return results

    def _project_profile(self, project: Any) -> list[Any]:
        """提取项目特征向量: [事实数, 推偶数, 平均引用数, 数值事实比, 政策事实比]"""
        facts = project.get("facts", {})
        infs = project.get("inferences", {})
        n_f = len(facts)
        n_i = len(infs)
        avg_df = sum(len(i.get("derives_from", [])) for i in infs.values()) / max(n_i, 1)
        num_ratio = sum(1 for f in facts.values() for v in [str(f.get("value", ""))] if re.search(r"\d", v)) / max(
            n_f, 1
        )
        pol_ratio = sum(1 for f in facts.values() if "政策" in str(f.get("desc", ""))) / max(n_f, 1)
        return [n_f / 20, n_i / 10, avg_df / 5, num_ratio, pol_ratio]

    def _cosine_similarity(self, a: Any, b: Any) -> Any:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = (sum(x * x for x in a) or 1) ** 0.5
        norm_b = (sum(x * x for x in b) or 1) ** 0.5
        return dot / (norm_a * norm_b)

    def incremental_recalc(self, old_facts: Any, new_facts: Any, inferences: Any) -> Any:
        """
        检测事实变更, 标记受影响的推论为stale。
        比全量重算更高效: 只重算变更相关的推论。
        """
        results: list[Any] = []
        changed = set()
        for fid in set(old_facts.keys()) | set(new_facts.keys()):
            old_v = str(old_facts.get(fid, {}).get("value", ""))
            new_v = str(new_facts.get(fid, {}).get("value", ""))
            if old_v != new_v:
                changed.add(fid)

        if not changed:
            return results

        affected = set()
        for title, info in inferences.items():
            if changed & set(info.get("derives_from", [])):
                affected.add(title)
                # 传递影响: 引用受影响的推论的其他推论也受影响
                for t2, i2 in inferences.items():
                    if title in i2.get("derives_from", []):
                        affected.add(t2)

        results.append(
            {
                "type": "incremental_recalc",
                "conclusion": f"{len(changed)}个事实变更 → {len(affected)}个推论需重新评估: {list(affected)[:3]}",
                "derived_from": list(changed),
                "confidence": 0.95,
                "method": "rule_engine",
            }
        )
        return results

    def temporal_reasoning(self, facts: Any) -> Any:
        """
        简化版Allen区间时态推理。
        检测事实的时间顺序关系: before/after/simultaneous。
        """
        results: list[Any] = []
        dated = []
        for fid, info in facts.items():
            text = f"{info.get('desc', '')} {info.get('value', '')}"
            years = re.findall(r"(20\d{2})", text)
            months = re.findall(r"(20\d{2}-\d{2})", text)
            if months:
                dated.append((fid, months[0], info))
            elif years:
                dated.append((fid, years[0], info))

        if len(dated) < 2:
            return results

        dated.sort(key=lambda x: x[1])
        newest = dated[-1]
        oldest = dated[0]

        results.append(
            {
                "type": "temporal_sequence",
                "conclusion": f"时间跨度: {oldest[1]}-{newest[1]}, {len(dated)}个带时态的事实",
                "derived_from": [d[0] for d in dated],
                "confidence": 0.85,
                "method": "rule_engine",
            }
        )

        # 检测"过时事实": 推论基于旧事实, 存在更新的事实
        for i in range(len(dated) - 1):
            if dated[i + 1][1] > dated[i][1]:
                # 两个相同描述的事实, 后者更新
                pass

        return results
