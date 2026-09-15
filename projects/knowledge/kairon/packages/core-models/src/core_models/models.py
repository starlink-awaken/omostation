"""Core data models — Entity, Relation, Provenance, KnowledgeGraph."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from urllib.parse import quote

logger = logging.getLogger(__name__)

ENTITY_TYPES = {
    "Module",
    "Function",
    "Class",
    "Method",
    "Variable",
    "Interface",
    "Type",
    "File",
    "Package",
    "Document",
    "Policy",
    "Regulation",
    "Standard",
    "Organization",
    "Person",
    "Project",
    "Event",
    "Platform",
    "University",
    "Government_Agency",
    "Concept",
    "Term",
    "Category",
    "Domain",
    "SourceFile",
    "Analyzer",
    "ProvenanceRecord",
}

RELATION_TYPES = {
    "IMPORTS": {"label": "导入", "domain": "代码", "desc": "A imports B"},
    "CALLS": {"label": "调用", "domain": "代码", "desc": "A calls B"},
    "INHERITS": {"label": "继承", "domain": "代码", "desc": "A extends B"},
    "IMPLEMENTS": {"label": "实现", "domain": "代码", "desc": "A implements B"},
    "REFERENCES": {"label": "引用", "domain": "文档", "desc": "A引用B"},
    "SUPERSEDES": {"label": "取代", "domain": "文档", "desc": "v2取代v1"},
    "CITES": {"label": "引述", "domain": "文档", "desc": "A引述B内容"},
    "AMENDS": {"label": "修订", "domain": "文档", "desc": "A修订B"},
    "BELONGS_TO": {"label": "隶属", "domain": "业务", "desc": "A隶属于B"},
    "MANAGES": {"label": "管理", "domain": "业务", "desc": "A管理B"},
    "PARTICIPATES_IN": {"label": "参与", "domain": "业务", "desc": "A参与B"},
    "COLLABORATES_WITH": {"label": "合作", "domain": "业务", "desc": "A与B合作"},
    "SAME_AS": {"label": "等同", "domain": "业务", "desc": "实体对齐"},
    "IS_A": {"label": "属于", "domain": "语义", "desc": "A is a B"},
    "RELATED_TO": {"label": "相关", "domain": "语义", "desc": "A与B相关"},
    "CONTAINS": {"label": "包含", "domain": "语义", "desc": "A包含B"},
    "PRECEDES": {"label": "前置", "domain": "语义", "desc": "A先于B"},
    "EXTRACTED_FROM": {"label": "提取自", "domain": "溯源", "desc": "从源文件提取"},
    "GENERATED_BY": {"label": "生成自", "domain": "溯源", "desc": "由分析器生成"},
    "VERIFIED_BY": {"label": "已验证", "domain": "溯源", "desc": "已人工确认"},
    "EXTRACTED": {"label": "确定", "domain": "元", "desc": "明确提取"},
    "INFERRED": {"label": "推断", "domain": "元", "desc": "语义推断"},
    "AMBIGUOUS": {"label": "模糊", "domain": "元", "desc": "置信度低"},
}


@dataclass
class Provenance:
    source_file: str = ""
    analyzer: str = ""
    method: str = ""
    confidence: float = 1.0
    extracted_at: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.extracted_at:
            self.extracted_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Entity:
    id: str
    name: str
    type: str
    source: str
    domain: str = "通用"
    confidence: float = 1.0
    properties: dict = field(default_factory=dict)
    provenance: Provenance | None = None
    source_path: str = ""
    source_line: int = 0
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.provenance:
            d["provenance"] = self.provenance.to_dict()
        else:
            d["provenance"] = {
                "source_file": self.source_path,
                "analyzer": self.source,
                "method": "unknown",
                "confidence": self.confidence,
            }
        return d

    def to_json_ld(self, graph_url: str = "") -> dict:
        b = graph_url or "https://codeanalyze.local/kg"
        p = self.provenance
        r = {
            "@context": {},
            "@id": quote(f"{b}/entity/{self.id}", safe=":/-"),
            "@type": ["schema:Thing", f"codeanalyze:{self.type}"],
            "codeanalyze:name": self.name,
        }
        if p:
            r["prov:wasGeneratedBy"] = {
                "@type": "prov:Activity",
                "prov:used": p.source_file or "unknown",
                "prov:wasAssociatedWith": p.analyzer,
            }
        return r


@dataclass
class Relation:
    source_id: str
    target_id: str
    type: str
    confidence: str = "EXTRACTED"
    weight: float = 1.0
    provenance: Provenance | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "source": self.source_id,
            "target": self.target_id,
            "type": self.type,
            "type_label": RELATION_TYPES.get(self.type, {}).get("label", self.type),
            "domain": RELATION_TYPES.get(self.type, {}).get("domain", ""),
            "confidence": self.confidence,
            "weight": self.weight,
            "metadata": self.metadata,
        }
        if self.provenance:
            d["provenance"] = self.provenance.to_dict()
        return d

    def to_json_ld(self, graph_url: str = "") -> dict:
        b = graph_url or "https://codeanalyze.local/kg"
        rel = RELATION_TYPES.get(self.type, {})
        return {
            "@context": {"schema": "https://schema.org/", "codeanalyze": f"{b}/ontology/"},
            "@id": quote(f"{b}/relation/{self.source_id}--{self.type}--{self.target_id}", safe=":/-"),
            "@type": ["schema:Relationship", f"codeanalyze:{self.type}"],
            "schema:name": rel.get("label", self.type),
            "codeanalyze:domain": rel.get("domain", ""),
            "codeanalyze:confidence": self.confidence,
            "schema:about": {"@id": quote(f"{b}/entity/{self.source_id}", safe=":/-")},
            "schema:relatedTo": {"@id": quote(f"{b}/entity/{self.target_id}", safe=":/-")},
        }


@dataclass
class KnowledgeGraph:
    entities: dict[str, Entity] = field(default_factory=dict)
    relations: list[Relation] = field(default_factory=list)
    source_files: dict[str, dict] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def add_entity(self, entity: Entity, source_file: str = "") -> None:
        self.entities[entity.id] = entity
        src = source_file or entity.source_path or (entity.provenance.source_file if entity.provenance else "")
        if src:
            sf_id = f"file-{src[-60:]}"
            if sf_id not in self.entities:
                self.entities[sf_id] = Entity(
                    id=sf_id,
                    name=src.split("/")[-1],
                    type="SourceFile",
                    source=entity.source,
                    properties={"path": src},
                    provenance=Provenance(source_file=src, analyzer="filesystem", method="stat"),
                )
                self.source_files[src] = {"id": sf_id, "analyzer": entity.source}
            self.relations.append(
                Relation(
                    source_id=entity.id,
                    target_id=sf_id,
                    type="EXTRACTED_FROM",
                    provenance=Provenance(source_file=src, analyzer=entity.source, method="filesystem"),
                )
            )

    def add_relation(self, relation: Relation) -> None:
        self.relations.append(relation)

    def merge(self, other: KnowledgeGraph) -> None:
        for eid, entity in other.entities.items():
            if eid not in self.entities:
                self.entities[eid] = entity
        self.relations.extend(other.relations)
        self.source_files.update(other.source_files)

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    @property
    def relation_count(self) -> int:
        return len(self.relations)

    def to_dict(self) -> dict:
        return {
            "metadata": {
                **self.metadata,
                "entity_count": len(self.entities),
                "relation_count": len(self.relations),
                "source_files": len(self.source_files),
            },
            "entities": [e.to_dict() for e in self.entities.values()],
            "relations": [r.to_dict() for r in self.relations],
        }

    def to_json(self, indent: int = 2, ensure_ascii: bool = False) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent)

    def to_json_ld(self, graph_url: str = "") -> dict:
        b = graph_url or "https://codeanalyze.local/kg"
        return {
            "@context": {
                "schema": "https://schema.org/",
                "codeanalyze": f"{b}/ontology/",
                "prov": "http://www.w3.org/ns/prov#",
            },
            "@graph": [e.to_json_ld(b) for e in self.entities.values()] + [r.to_json_ld(b) for r in self.relations],
        }

    def to_cypher(self, label_field: str = "name") -> str:
        def _esc(v: str) -> str:
            return v.replace("\\", "\\\\").replace("'", "\\'")

        def _label(v: str) -> str:
            return v.replace("'", "").replace(":", "_")

        lines = [
            "// Cypher import — generated by codeanalyze",
            f"// {self.entity_count} entities, {self.relation_count} relations, {len(self.source_files)} source files",
            "",
        ]
        for i, e in enumerate(self.entities.values()):
            props_json = json.dumps(e.properties, ensure_ascii=False) if e.properties else "{}"
            prov_json = json.dumps(e.provenance.to_dict() if e.provenance else {}, ensure_ascii=False)
            safe_id = _esc(e.id)
            safe_name = _esc(e.name)
            safe_domain = _esc(e.domain)
            safe_type = _label(e.type)
            lines.append(
                f"MERGE (n{i}:{safe_type} {{id: '{safe_id}'}}) "
                f"SET n{i}.name = '{safe_name}', n{i}.domain = '{safe_domain}', "
                f"n{i}.confidence = {e.confidence}, "
                f"n{i}.properties = '{props_json}', "
                f"n{i}.provenance = '{prov_json}';"
            )
        lines.append("")
        for r in self.relations:
            prov_str = f"provenance: '{r.provenance.analyzer if r.provenance else ''}'"
            safe_src = _esc(r.source_id)
            safe_tgt = _esc(r.target_id)
            safe_type = _label(r.type)
            lines.append(
                f"MATCH (a {{id: '{safe_src}'}}), (b {{id: '{safe_tgt}'}}) "
                f"MERGE (a)-[:{safe_type} {{confidence: '{r.confidence}', "
                f"weight: {r.weight}, {prov_str}}}]->(b);"
            )
        return "\n".join(lines)
