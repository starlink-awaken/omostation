"""
OntoDerive 推理编排 — 选择器 + 范式化
======================================
解决两个核心问题:
1. 如何自动选择最合适的推理模式？（ReasoningSelector）
2. 是否需要将内容处理成范式再推理？（ContentCanonicalizer）

架构:
  ContentCanonicalizer → 事实/推论 → 标准化表示
  ReasoningSelector     → 分析数据特征 → 激活相关规则
  RuleReasoner          → 执行选中的规则 → 推导结果
"""

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class DataProfile:
    """数据特征画像 — 用于推理模式选择"""

    has_numeric: bool = False  # 是否包含数值事实
    has_timestamps: bool = False  # 是否包含时间戳
    has_inf_chains: bool = False  # 是否有INF→INF推导链
    has_policy_facts: bool = False  # 是否有政策事实(P-F)
    has_dichotomy: bool = False  # 是否有选言结构
    has_high_confidence: bool = False  # 是否所有推论置信度偏高
    fact_count: int = 0
    inf_count: int = 0
    avg_derives_from: float = 0.0  # 平均每个推论引用几个前提
    max_chain_depth: int = 0  # 最大推导链深度


class ContentCanonicalizer:
    """内容范式化器 — 将原始事实/推论转为标准化表示"""

    def __init__(self) -> None:
        self._numeric_cache: dict[Any, Any] = {}

    def canonicalize_facts(self, raw_facts: dict[str, dict]) -> dict[str, dict]:
        """
        范式化事实:
        - 提取数值到 structured_value 字段
        - 提取时间戳到 timestamp 字段
        - 标准化描述
        """
        canonical = {}
        for fid, info in raw_facts.items():
            entry = dict(info)
            # 数值提取
            value_str = str(info.get("value", ""))
            nums = re.findall(r"(\d+\.?\d*)", value_str)
            if nums:
                entry["structured_value"] = float(nums[0])
                entry["has_numeric"] = True
            else:
                entry["has_numeric"] = False

            # 时间戳提取
            text = f"{info.get('desc', '')} {value_str}"
            years = re.findall(r"(20\d{2})", text)
            months = re.findall(r"(20\d{2}-\d{2})", text)
            if months:
                entry["timestamp"] = months[0]
                entry["has_timestamp"] = True
            elif years:
                entry["timestamp"] = years[0]
                entry["has_timestamp"] = True
            else:
                entry["has_timestamp"] = False

            canonical[fid] = entry
        return canonical

    def canonicalize_inferences(self, raw_inferences: dict[str, dict]) -> dict[str, dict]:
        """
        范式化推论:
        - 标准化 derives_from 为统一格式
        - 提取置信度标签 → 数值
        - 提取结论句
        """
        conf_map = {"high": 0.92, "inference": 0.85, "medium": 0.70, "low": 0.45}
        canonical = {}
        for title, info in raw_inferences.items():
            entry = dict(info)
            # 标准化引用
            df = info.get("derives_from", [])
            entry["derives_from"] = list(set(df))
            entry["n_derives_from"] = len(entry["derives_from"])
            entry["has_inf_dependency"] = any(d.startswith("INF") for d in df)
            entry["has_fact_dependency"] = any(d.startswith(("D-F", "P-F")) for d in df)

            # 置信度标准化
            text = info.get("text", "")
            conf_match = re.search(r"confidence:\s*(\w+)", text)
            entry["confidence_value"] = conf_map.get(conf_match.group(1) if conf_match else "inference", 0.85)

            # 结论提取
            conclusions = re.findall(r"结论[：:]\s*(.+?)(?:。|\n|$)", text)
            entry["conclusion"] = conclusions[0].strip() if conclusions else ""

            canonical[title] = entry
        return canonical


class ReasoningSelector:
    """推理模式选择器 — 基于数据特征自动选择合适的推理规则"""

    RULE_DEPENDENCIES = {
        # rule_name → required features
        "numeric_comparison": {"has_numeric"},
        "modus_ponens": {"inf_count"},  # 有推论就可用
        "transitive_closure": {"has_inf_chains"},
        "hypothetical_syllogism": {"has_inf_chains"},
        "disjunctive_syllogism": {"has_dichotomy"},
        "subsumption": {"fact_count"},  # 有事实就可用
        "influence_analysis": {"inf_count", "fact_count"},
        "structural_holes": {"inf_count"},
        "coverage_analysis": {"fact_count"},
        "redundancy_check": {"inf_count"},
        "consistency_analysis": {"has_high_confidence"},
        "constraint_propagation": {"inf_count"},
        "change_detection": {"has_timestamps"},
        "missing_reference": {"inf_count"},
        "evidence_gap": {"inf_count"},
        "chain_integrity": {"has_inf_chains"},
    }

    def profile(self, facts: dict[str, dict], inferences: dict[str, dict]) -> DataProfile:
        """分析数据特征, 生成画像"""
        profile = DataProfile()
        profile.fact_count = len(facts)
        profile.inf_count = len(inferences)

        # 检测数值
        for info in facts.values():
            if info.get("has_numeric", False):
                profile.has_numeric = True
            if info.get("has_timestamp", False):
                profile.has_timestamps = True
            if "政策" in str(info.get("desc", "")) or info.get("value", "").startswith("P-F"):
                profile.has_policy_facts = True

        # 检测推导链
        total_df = 0
        for info in inferences.values():
            df = info.get("derives_from", [])
            total_df += len(df)
            if any(d.startswith("INF") for d in df):
                profile.has_inf_chains = True

        profile.avg_derives_from = total_df / len(inferences) if inferences else 0

        # 检测选言结构
        inf_list = list(inferences.items())
        for i in range(len(inf_list)):
            for j in range(i + 1, len(inf_list)):
                shared = set(inf_list[i][1].get("derives_from", [])) & set(inf_list[j][1].get("derives_from", []))
                if len(shared) >= 2:
                    a_text, b_text = inf_list[i][1].get("text", ""), inf_list[j][1].get("text", "")
                    for w1, w2 in [("研发", "营销"), ("增加", "控制"), ("优先", "推迟")]:
                        if (w1 in a_text and w2 in b_text) or (w2 in a_text and w1 in b_text):
                            profile.has_dichotomy = True
                            break

        # 检测过度自信
        confs = []
        for info in inferences.values():
            m = re.search(r"confidence:\s*(\w+)", info.get("text", ""))
            conf_map = {"high": 0.92, "inference": 0.85, "medium": 0.70}
            confs.append(conf_map.get(m.group(1) if m else "inference", 0.85))
        if confs and all(c >= 0.85 for c in confs):
            profile.has_high_confidence = True

        # 计算链深度
        profile.max_chain_depth = self._calc_max_depth(inferences)

        return profile

    def _calc_max_depth(self, inferences: Any) -> Any:
        depths = {}
        visited = set()

        def dfs(node: Any) -> Any:
            if node not in inferences:
                return 0
            visited.add(node)
            max_d = 0
            for parent in inferences[node].get("derives_from", []):
                if parent.startswith("INF") and parent not in visited:
                    max_d = max(max_d, dfs(parent))
            return max_d + 1

        for title in inferences:
            if title not in visited:
                depths[title] = dfs(title)
        return max(depths.values()) if depths else 0

    def select_rules(self, profile: DataProfile) -> list[str]:
        """基于数据特征选择合适的推理规则"""
        features = set()
        if profile.has_numeric:
            features.add("has_numeric")
        if profile.has_timestamps:
            features.add("has_timestamps")
        if profile.has_inf_chains:
            features.add("has_inf_chains")
        if profile.has_dichotomy:
            features.add("has_dichotomy")
        if profile.has_high_confidence:
            features.add("has_high_confidence")
        if profile.fact_count > 0:
            features.add("fact_count")
        if profile.inf_count > 0:
            features.add("inf_count")

        selected = []
        skipped = []
        for rule_name, required in self.RULE_DEPENDENCIES.items():
            if required.issubset(features):
                selected.append(rule_name)
            else:
                skipped.append((rule_name, required - features))

        return selected

    def explain_selection(self, profile: DataProfile) -> str:
        """解释为何选择/跳过某些规则"""
        selected = self.select_rules(profile)
        lines = [
            f"数据画像: {profile.fact_count}事实/{profile.inf_count}推论, "
            f"数值={profile.has_numeric}, 时态={profile.has_timestamps}, "
            f"推导链={profile.has_inf_chains}, 选言={profile.has_dichotomy}",
            f"激活规则: {len(selected)}种 — {', '.join(selected[:8])}",
        ]
        return "\n".join(lines)
