"""Cross-project data adapters — ontoderive → Eidos schema conversion.

遵循 AGENTS.md 约定：跨项目通信优先 MCP > REST > CLI subprocess > pip import。
此处提供纯数据转换，不直接依赖 Eidos 运行时。
"""

from typing import Any

# ontoderive category → 默认 subject 映射
_CATEGORY_SUBJECT_MAP: dict[str, str] = {
    "data": "系统",
    "policy": "政策",
}


def to_eidos_fact(
    fact: Any,
    *,
    default_subject: str | None = None,
    source_card_id: str = "",
    derived_from: str = "",
) -> dict[str, Any]:
    """将 ontoderive SymbolicFact 转换为 Eidos Fact 兼容的 dict。

    Args:
        fact: SymbolicFact 实例（或具有 id/description/value/source/confidence/category 属性的对象）。
        default_subject: 可选，覆盖自动派生的 subject 值。
        source_card_id: 可选，源卡片 ID。
        derived_from: 可选，推导来源。

    Returns:
        可通过 Fact.validate() 的 dict。
    """
    # 派生 subject
    if default_subject is not None:
        subject = default_subject
    else:
        category = getattr(fact, "category", "data")
        subject = _CATEGORY_SUBJECT_MAP.get(category, "未知实体")

    return {
        "id": fact.id,
        "subject": subject,
        "predicate": fact.description,
        "object": fact.value,
        "confidence": getattr(fact, "confidence", 1.0),
        "source_card_id": source_card_id,
        "derived_from": derived_from,
    }


def to_eidos_fact_from_dict(
    fact_dict: dict[str, Any],
    *,
    default_subject: str | None = None,
    source_card_id: str = "",
    derived_from: str = "",
) -> dict[str, Any]:
    """将 ontoderive SymbolicFact 的 dict 表示转换为 Eidos Fact 兼容的 dict。

    适用于已知 field names 但无法导入 SymbolicFact 类的场景。
    """
    if default_subject is not None:
        subject = default_subject
    else:
        category = fact_dict.get("category", "data")
        subject = _CATEGORY_SUBJECT_MAP.get(category, "未知实体")

    return {
        "id": fact_dict["id"],
        "subject": subject,
        "predicate": fact_dict.get("description", ""),
        "object": fact_dict.get("value", ""),
        "confidence": fact_dict.get("confidence", 1.0),
        "source_card_id": source_card_id,
        "derived_from": derived_from,
    }
