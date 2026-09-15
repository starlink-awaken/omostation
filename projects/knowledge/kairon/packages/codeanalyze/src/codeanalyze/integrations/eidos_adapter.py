"""Eidos 集成适配器 — 将 codeanalyze 知识图谱转换为 Eidos 兼容格式

Eidos 是 Workspace 的 schema 定义与校验层。
集成线路: codeanalyze export → Eidos validate (单向导出，KOS/OntoDerive 需手动执行)

架构位置:
  codeanalyze (分析抽取) → Eidos (schema校验) → KOS/OntoDerive (手动执行)
"""

from datetime import datetime

from codeanalyze.core.results import RELATION_TYPES, Entity, KnowledgeGraph  # type: ignore[import-not-found]

# ── 元关系映射 (codeanalyze → Eidos MetaRelationType) ──
_RELATION_TO_META = {
    # 结构组成 → STRUCT
    "IMPORTS": "struct",
    "INHERITS": "struct",
    "IMPLEMENTS": "struct",
    "BELONGS_TO": "struct",
    "CONTAINS": "struct",
    "IS_A": "struct",
    "SUPERSEDES": "struct",
    # 推导派生 → DERIVE
    "CALLS": "derive",
    "INFERRED": "derive",
    "PRECEDES": "derive",
    # 行为状态 → BEHAVIOR
    "MANAGES": "behavior",
    "PARTICIPATES_IN": "behavior",
    "COLLABORATES_WITH": "behavior",
    # 归因溯源 → JUSTIFY
    "REFERENCES": "justify",
    "CITES": "justify",
    "EXTRACTED_FROM": "justify",
    "SAME_AS": "justify",
    "VERIFIED_BY": "justify",
    # 默认
    "DEFAULT": "struct",
}

# ── 域映射 (codeanalyze domain → Eidos MetaType) ──
_DOMAIN_TO_META_TYPE = {
    "代码": "domain",
    "代码语义": "domain",
    "代码依赖": "relation",
    "代码符号": "processor",
    "公文": "document",
    "文档": "document",
    "政策": "fact",
    "政策层级": "constraint",
    "业务领域": "domain",
    "组织": "domain",
    "溯源": "constraint",
}


def _meta_relation(rel_type: str) -> str:
    """映射 codeanalyze 关系类型到 Eidos MetaRelationType。"""
    return _RELATION_TO_META.get(rel_type, _RELATION_TO_META["DEFAULT"])


def _meta_type(domain: str) -> str:
    """映射 codeanalyze 域到 Eidos MetaType。"""
    return _DOMAIN_TO_META_TYPE.get(domain, "document")


def kg_to_eidos_nodes(kg: KnowledgeGraph) -> list[dict]:
    """将 KG 实体转为 Eidos OntologyNode 兼容格式。"""
    nodes = []
    for e in kg.entities.values():
        node = {
            "id": e.id,
            "name": e.name,
            "node_type": e.type,
            "parent": e.properties.get("level", "") if isinstance(e.properties, dict) else "",
            "properties": {
                **(e.properties if isinstance(e.properties, dict) else {}),
                "source": e.source,
                "domain": e.domain,
                "confidence": e.confidence,
            },
            "aliases": [e.name],
            "description": _build_description(e),
        }
        nodes.append(node)
    return nodes


def _build_description(e: Entity) -> str:
    """从实体属性生成人类可读的描述。"""
    parts = [f"类型: {e.type}", f"领域: {e.domain}"]
    if e.provenance:
        parts.append(f"来源: {e.provenance.source_file.split('/')[-1] if e.provenance.source_file else e.source}")
        parts.append(f"方法: {e.provenance.method}")
    return " | ".join(parts)


def kg_to_eidos_relations(kg: KnowledgeGraph) -> list[dict]:
    """将 KG 关系转为 Eidos Relation 兼容格式。"""
    relations = []
    for i, r in enumerate(kg.relations):
        meta = _meta_relation(r.type)
        rel_label = RELATION_TYPES.get(r.type, {}).get("label", r.type)
        relations.append(
            {
                "id": f"rel-{i}",
                "source_id": r.source_id,
                "target_id": r.target_id,
                "relation_type": r.type,
                "meta_relation": meta,
                "weight": r.weight,
                "properties": {
                    "confidence": r.confidence,
                    "label": rel_label,
                    "domain": RELATION_TYPES.get(r.type, {}).get("domain", ""),
                    "provenance_analyzer": r.provenance.analyzer if r.provenance else "",
                },
            }
        )
    return relations


def kg_to_eidos_facts(kg: KnowledgeGraph) -> list[dict]:
    """将 KG 关系转为 Eidos Fact 格式（SPO 三元组）。"""
    facts = []
    for i, r in enumerate(kg.relations):
        src = kg.entities.get(r.source_id)
        tgt = kg.entities.get(r.target_id)
        if not src or not tgt:
            continue
        facts.append(
            {
                "id": f"fact-{i}",
                "subject": src.name,
                "predicate": RELATION_TYPES.get(r.type, {}).get("label", r.type),
                "object": tgt.name,
                "confidence": 1.0 if r.confidence == "EXTRACTED" else 0.5,
                "source_card_id": f"card-{r.source_id}",
                "derived_from": r.provenance.analyzer if r.provenance else "codeanalyze",
            }
        )
    return facts


def kg_to_eidos_cards(kg: KnowledgeGraph) -> list[dict]:
    """将 Document 类型实体转为 Eidos KnowledgeCard 格式。"""
    cards = []
    for e in kg.entities.values():
        if e.type != "Document" and e.type != "Policy":
            continue
        props = e.properties if isinstance(e.properties, dict) else {}
        source_file = e.provenance.source_file if e.provenance else e.source_path
        cards.append(
            {
                "id": f"card-{e.id}",
                "title": e.name,
                "content": _build_description(e),
                "source": source_file.split("/")[-1] if source_file else e.source,
                "source_type": e.type,
                "schema_type": "Document",
                "tags": [props.get("level", ""), e.domain, e.type],
                "relations": [r.type for r in kg.relations if r.source_id == e.id][:5],
                "created_at": e.created_at or datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
        )
    return cards


def convert_kg(kg: KnowledgeGraph) -> dict:
    """全量转换: KnowledgeGraph → Eidos 兼容数据集"""
    return {
        "meta": {
            "generated_by": "codeanalyze",
            "generated_at": datetime.now().isoformat(),
            "entity_count": kg.entity_count,
            "relation_count": kg.relation_count,
            "source_files": len(kg.source_files),
        },
        "ontology_nodes": kg_to_eidos_nodes(kg),
        "relations": kg_to_eidos_relations(kg),
        "facts": kg_to_eidos_facts(kg),
        "cards": kg_to_eidos_cards(kg),
    }


def try_eidos_validate(data: dict) -> dict:
    """尝试用 Eidos 校验输出。如果 Eidos 未安装则优雅降级。"""
    try:
        from eidos.registry import create_registry

        registry = create_registry()
        results: dict = {"schema_checks": {}}

        # 校验 ontology_nodes
        for node in data.get("ontology_nodes", [])[:3]:
            result = registry.validate("OntologyNode", node, strict=False)
            results["schema_checks"][node["id"]] = {
                "type": "OntologyNode",
                "valid": result.is_valid if hasattr(result, "is_valid") else result,
            }

        # 校验 cards
        for card in data.get("cards", [])[:3]:
            result = registry.validate("KnowledgeCard", card, strict=False)
            results["schema_checks"][card["id"]] = {
                "type": "KnowledgeCard",
                "valid": result.is_valid if hasattr(result, "is_valid") else result,
            }

        results["available"] = True
        return results

    except ImportError:
        return {"available": False, "note": _eidos_install_hint()}
    except Exception as e:
        return {"available": False, "error": str(e)}


def _eidos_install_hint() -> str:
    """动态检测 Eidos 安装路径，避免硬编码。"""
    from pathlib import Path

    candidates = [
        Path.home() / "Workspace" / "eidos",
        Path.cwd() / ".." / "eidos",
    ]
    for candidate in candidates:
        if (candidate / "pyproject.toml").exists():
            return f"Eidos not installed. pip install -e {candidate}"
    return "Eidos not installed. pip install eidos (或从本地 eidos 目录 pip install -e .)"
