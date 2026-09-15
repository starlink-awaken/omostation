"""卫生政策相关性分析 — 过滤出与 omostation 场景 A 相关的政策。

场景 A 关键词：基层医疗、药品集采、医保支付、分级诊疗、基本药物、门诊共济。
"""

from __future__ import annotations

from minerva.policy_tracker.types import PolicyItem

# 场景 A 关键词权重
_KEYWORDS: dict[str, float] = {
    # 基层医疗（高权重）
    "基层": 1.0,
    "基层医疗": 1.2,
    "基层卫生": 1.2,
    "primary care": 1.0,
    "社区卫生": 0.9,
    "乡镇卫生院": 0.9,
    "村卫生室": 0.8,
    # 药品集采（高权重）
    "药品集中采购": 1.2,
    "药品集采": 1.2,
    "带量采购": 1.1,
    "集采中选": 1.0,
    "drug procurement": 1.0,
    "volume-based procurement": 1.0,
    "vbp": 0.8,
    # 医保支付
    "医保支付": 1.0,
    "医保基金": 0.9,
    "医保报销": 0.8,
    "drg": 0.9,
    "dip": 0.9,
    "medical insurance": 0.9,
    "基本医保": 0.9,
    "门诊共济": 1.0,
    "门诊保障": 0.8,
    # 分级诊疗
    "分级诊疗": 1.0,
    "双向转诊": 0.9,
    "hierarchical diagnosis": 0.9,
    "分级医疗": 0.8,
    "上下联动": 0.7,
    # 基本药物
    "基本药物": 1.0,
    "基本药物制度": 1.0,
    "essential medicine": 1.0,
    "零差率": 0.7,
    "国家基本药物目录": 1.0,
    # 医改
    "医改": 0.7,
    "医药卫生体制改革": 0.8,
    "公立医院改革": 0.8,
    "三医联动": 0.9,
    # 公共卫生
    "公共卫生": 0.6,
    "家庭医生": 0.7,
    "签约服务": 0.6,
}

# 噪音词（命中降分）
_NOISE_WORDS = {"化妆品", "兽药", "动物诊疗", "渔业"}


def score_item(item: PolicyItem) -> float:
    """对单条政策计算 omostation 场景 A 相关度 [0.0, 1.0]。"""
    text = (item.title + " " + item.summary + " " + " ".join(item.tags)).lower()

    score = 0.0
    matched: set[str] = set()
    for kw, weight in _KEYWORDS.items():
        if kw.lower() in text and kw not in matched:
            score += weight
            matched.add(kw)

    # 噪音惩罚
    for noise in _NOISE_WORDS:
        if noise in text:
            score *= 0.5

    # 归一化到 [0, 1]，上限 = 6 分
    return min(round(score / 6.0, 3), 1.0)


def analyze_items(items: list[PolicyItem], threshold: float = 0.15) -> list[PolicyItem]:
    """批量评分，过滤低相关度条目。

    Returns: 按 relevance_score 降序排列的过滤后条目。
    """
    scored: list[PolicyItem] = []
    for item in items:
        item.relevance_score = score_item(item)
        if item.relevance_score >= threshold:
            scored.append(item)

    scored.sort(key=lambda x: x.relevance_score, reverse=True)
    return scored
