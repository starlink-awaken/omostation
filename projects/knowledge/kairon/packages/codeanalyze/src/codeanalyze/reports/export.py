"""知识图谱导出 — 跨引擎数据融合 + 溯源支持"""

import json
from pathlib import Path

from codeanalyze.core.results import (  # type: ignore[import-not-found]
    Entity,
    KnowledgeGraph,
    Provenance,
    Relation,
)
from codeanalyze.documents.official import PolicyGraph  # type: ignore[import-not-found]


def policy_graph_to_kg(pg: PolicyGraph, source: str = "official") -> KnowledgeGraph:
    """将 PolicyGraph 转为统一知识图谱（带溯源）。"""
    kg = KnowledgeGraph(
        metadata={
            "source": source,
            "generator": "codeanalyze documents",
        }
    )

    for doc in pg.documents:
        sf_path = str(doc.path)
        eid = f"doc-{doc.filename[:40]}"

        entity = Entity(
            id=eid,
            name=doc.title or doc.filename[:50],
            type="Document",
            source=source,
            domain="公文" if doc.level != "其他" else "文档",
            confidence=0.9 if doc.doc_number else 0.6,
            properties={
                "filename": doc.filename,
                "doc_number": doc.doc_number or "",
                "issuing_org": doc.issuing_org or "",
                "level": doc.level,
                "pub_date": doc.pub_date or "",
                "domain_name": doc.domain,
                "format": doc.path.suffix,
                "size_bytes": doc.byte_size,
            },
            provenance=Provenance(
                source_file=sf_path,
                analyzer=source,
                method="regex+pdftotext",
                confidence=0.9 if doc.doc_number or doc.content_preview else 0.5,
            ),
        )
        kg.add_entity(entity, source_file=sf_path)

        # 文号 → Policy 实体
        if doc.doc_number:
            num_id = f"docnum-{doc.doc_number}"
            kg.add_entity(
                Entity(
                    id=num_id,
                    name=doc.doc_number,
                    type="Policy",
                    source=source,
                    domain="政策",
                    confidence=0.95,
                    provenance=Provenance(source_file=sf_path, analyzer=source, method="regex"),
                ),
                source_file=sf_path,
            )
            kg.add_relation(
                Relation(
                    source_id=eid,
                    target_id=num_id,
                    type="REFERENCES",
                    confidence="EXTRACTED",
                    provenance=Provenance(source_file=sf_path, analyzer=source, method="regex_docnum"),
                )
            )

        # 发文机关 → Organization 实体
        if doc.issuing_org:
            org_id = f"org-{doc.issuing_org[:20]}"
            if org_id not in kg.entities:
                kg.add_entity(
                    Entity(
                        id=org_id,
                        name=doc.issuing_org,
                        type="Organization",
                        source=source,
                        domain="组织",
                        confidence=0.7,
                        provenance=Provenance(source_file=sf_path, analyzer=source, method="regex_org"),
                    ),
                    source_file=sf_path,
                )
            kg.add_relation(
                Relation(
                    source_id=eid,
                    target_id=org_id,
                    type="BELONGS_TO",
                    confidence="EXTRACTED",
                    provenance=Provenance(source_file=sf_path, analyzer=source, method="regex_org"),
                )
            )

    # 层级关系
    for level, docs in pg.level_groups.items():
        if level == "其他":
            continue
        level_id = f"level-{level}"
        if level_id not in kg.entities:
            kg.add_entity(
                Entity(
                    id=level_id,
                    name=level,
                    type="Category",
                    source=source,
                    domain="政策层级",
                    confidence=1.0,
                )
            )
        for doc in docs:
            eid = f"doc-{doc.filename[:40]}"
            if eid in kg.entities:
                kg.add_relation(
                    Relation(
                        source_id=eid,
                        target_id=level_id,
                        type="BELONGS_TO",
                        confidence="EXTRACTED",
                        provenance=Provenance(
                            source_file=str(doc.path),
                            analyzer=source,
                            method="directory_classification",
                        ),
                    )
                )

    # 领域关系
    for domain, docs in pg.domain_groups.items():
        domain_id = f"domain-{domain}"
        if domain_id not in kg.entities:
            kg.add_entity(
                Entity(
                    id=domain_id,
                    name=domain,
                    type="Domain",
                    source=source,
                    domain="业务领域",
                    confidence=0.9,
                )
            )
        for doc in docs:
            eid = f"doc-{doc.filename[:40]}"
            if eid in kg.entities:
                kg.add_relation(
                    Relation(
                        source_id=eid,
                        target_id=domain_id,
                        type="CONTAINS",
                        confidence="EXTRACTED",
                        provenance=Provenance(
                            source_file=str(doc.path),
                            analyzer=source,
                            method="path_domain_mapping",
                        ),
                    )
                )

    # 政策间引用关系
    for rel in pg.relationships:
        e1 = f"doc-{rel['source'][4:44]}" if rel["source"].startswith("doc-") else rel["source"]
        e2 = rel["target"]
        if isinstance(e2, str) and "号" in e2:
            e2 = f"docnum-{e2}"
        kg.add_relation(
            Relation(
                source_id=e1,
                target_id=e2,
                type=rel.get("type", "REFERENCES"),
                confidence="INFERRED",
                weight=0.5,
                provenance=Provenance(
                    analyzer="official",
                    method="cross_doc_reference",
                    confidence=0.5,
                ),
            )
        )

    return kg


def merge_code_kg(kg: KnowledgeGraph, repo_path: str) -> KnowledgeGraph:
    """尝试从代码分析器（Graphify/GitNexus）提取实体并合并。"""
    from codeanalyze.analyzers import graphify as gfa  # type: ignore[import-not-found]

    g_result = gfa.analyze(repo_path)
    if g_result.get("error"):
        kg.metadata["code_engine_error"] = g_result["error"]
        return kg

    for ent in g_result.get("entities", []):
        eid = f"code-{ent.get('name', '')}-{ent.get('type', 'Module')}"
        if eid not in kg.entities:
            ent_name = ent.get("name", "")
            ent_type = ent.get("type", "Module")
            ent_path = ent.get("properties", {}).get("path", "")
            kg.add_entity(
                Entity(
                    id=eid,
                    name=ent_name,
                    type=ent_type,
                    source="graphify",
                    domain="代码",
                    confidence=0.85,
                    properties={"path": ent_path, "language": ent.get("properties", {}).get("language", "")},
                    provenance=Provenance(
                        source_file=ent_path,
                        analyzer="graphify",
                        method="tree-sitter_ast",
                    ),
                ),
                source_file=ent_path,
            )

    # 代码关系
    for rel in g_result.get("relations", []):
        src = f"code-{rel.get('source', '')}"
        tgt = f"code-{rel.get('target', '')}"
        kg.add_relation(
            Relation(
                source_id=src,
                target_id=tgt,
                type=rel.get("type", "IMPORTS"),
                confidence=rel.get("confidence", "EXTRACTED"),
                provenance=Provenance(
                    analyzer="graphify",
                    method="ast_extraction",
                ),
            )
        )

    return kg


def export_graph(
    path: str,
    output_format: str = "json",
    include_code: bool = False,
) -> str:
    """全流程导出：分析 → 建图 → 序列化。"""
    from codeanalyze.documents.official import analyze_policy_directory

    root = Path(path).resolve()
    pg = analyze_policy_directory(str(root))
    kg = policy_graph_to_kg(pg)

    if include_code:
        kg = merge_code_kg(kg, str(root))

    suffix_map = {"json": ".json", "json-ld": ".jsonld", "cypher": ".cypher", "md": ".md"}
    serializers = {
        "json": lambda: kg.to_json(),
        "json-ld": lambda: json.dumps(kg.to_json_ld(), ensure_ascii=False, indent=2),
        "cypher": lambda: kg.to_cypher(),
        "md": lambda: _md_summary(kg),
    }

    content = serializers[output_format]()
    suffix = suffix_map[output_format]
    target = root / f"codeanalyze-export{suffix}"
    target.write_text(content, encoding="utf-8")

    return str(target)


def _md_summary(kg: KnowledgeGraph) -> str:
    lines = [
        "# 知识图谱导出报告",
        "## 概览",
        f"- 实体: {kg.entity_count} 个",
        f"- 关系: {kg.relation_count} 条",
        f"- 来源文件: {len(kg.source_files)} 个",
        "",
        "## 实体列表",
    ]
    for e in kg.entities.values():
        lines.append(f"- [{e.type}] **{e.name}** (领域: {e.domain}, 置信度: {e.confidence})")
    lines.extend(["", "## 关系列表"])
    for r in kg.relations[:50]:
        src = kg.entities.get(r.source_id)
        tgt = kg.entities.get(r.target_id)
        sn = src.name if src else r.source_id
        tn = tgt.name if tgt else r.target_id
        label = r.type
        if "RELATION_TYPES" in globals():
            label = globals()["RELATION_TYPES"].get(r.type, {}).get("label", r.type)
        lines.append(f"- {sn} --[{label}]--> {tn}")
    if len(kg.relations) > 50:
        lines.append(f"  ... 还有 {len(kg.relations) - 50} 条关系")
    lines.extend(["", "## 来源文件"])
    for sf_path, info in kg.source_files.items():
        name = sf_path.split("/")[-1]
        lines.append(f"- {name} ({info['analyzer']})")
    return "\n".join(lines)
