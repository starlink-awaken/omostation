"""统一实体/关系建模 — 全领域数据模型

为所有分析器提供统一的实体-关系-图谱模型。
两个原则：
  1. Agent 可直接消费（JSON 序列化 + 显式 schema）
  2. 可用于本体建模（typed relations + 实体链接）

v2 新增：溯源追踪 — 每个实体和关系都能追溯到来源文件、提取方式、置信度。
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from urllib.parse import quote

logger = logging.getLogger(__name__)


# ── 实体类型 Taxonomy ──
ENTITY_TYPES = {
    # 代码分析层
    "Module",
    "Function",
    "Class",
    "Method",
    "Variable",
    "Interface",
    "Type",
    "File",
    "Package",
    # 文档分析层
    "Document",
    "Policy",
    "Regulation",
    "Standard",
    # 业务实体层
    "Organization",
    "Person",
    "Project",
    "Event",
    "Platform",
    "University",
    "Government_Agency",
    # 知识层
    "Concept",
    "Term",
    "Category",
    "Domain",
    # 溯源层
    "SourceFile",
    "Analyzer",
    "ProvenanceRecord",
}

# ── 关系类型 Taxonomy ──
RELATION_TYPES = {
    # 代码关系
    "IMPORTS": {"label": "导入", "domain": "代码", "desc": "A imports B"},
    "CALLS": {"label": "调用", "domain": "代码", "desc": "A calls B"},
    "INHERITS": {"label": "继承", "domain": "代码", "desc": "A extends B"},
    "IMPLEMENTS": {"label": "实现", "domain": "代码", "desc": "A implements B"},
    # 文档关系
    "REFERENCES": {"label": "引用", "domain": "文档", "desc": "A 引用 B"},
    "SUPERSEDES": {"label": "取代", "domain": "文档", "desc": "v2 取代 v1"},
    "CITES": {"label": "引述", "domain": "文档", "desc": "A 引述 B 内容"},
    "AMENDS": {"label": "修订", "domain": "文档", "desc": "A 修订 B"},
    # 业务关系
    "BELONGS_TO": {"label": "隶属", "domain": "业务", "desc": "A 隶属于 B"},
    "MANAGES": {"label": "管理", "domain": "业务", "desc": "A 管理 B"},
    "PARTICIPATES_IN": {"label": "参与", "domain": "业务", "desc": "A 参与 B"},
    "COLLABORATES_WITH": {"label": "合作", "domain": "业务", "desc": "A 与 B 合作"},
    "SAME_AS": {"label": "等同", "domain": "业务", "desc": "实体对齐: A ≡ B"},
    # 语义关系
    "IS_A": {"label": "属于", "domain": "语义", "desc": "A is a B"},
    "RELATED_TO": {"label": "相关", "domain": "语义", "desc": "A 与 B 相关"},
    "CONTAINS": {"label": "包含", "domain": "语义", "desc": "A 包含 B"},
    "PRECEDES": {"label": "前置", "domain": "语义", "desc": "A 先于 B"},
    # 溯源关系
    "EXTRACTED_FROM": {"label": "提取自", "domain": "溯源", "desc": "实体从源文件提取而来"},
    "GENERATED_BY": {"label": "生成自", "domain": "溯源", "desc": "实体由分析器生成"},
    "VERIFIED_BY": {"label": "已验证", "domain": "溯源", "desc": "实体已人工确认"},
    # 抽取置信度标签
    "EXTRACTED": {"label": "确定", "domain": "元", "desc": "从源明确提取"},
    "INFERRED": {"label": "推断", "domain": "元", "desc": "通过语义推断"},
    "AMBIGUOUS": {"label": "模糊", "domain": "元", "desc": "置信度低"},
}


# ── 溯源模型 ──


@dataclass
class Provenance:
    """溯源信息 — 每一个实体从哪来、怎么来的。"""

    source_file: str = ""  # 来源文件绝对路径
    analyzer: str = ""  # 提取工具: graphify/gitnexus/pdftotext
    method: str = ""  # 提取方式: ast/regex/llm/ocr/lsp
    confidence: float = 1.0  # 本条提取的置信度
    extracted_at: str = ""  # 提取时间戳
    notes: str = ""  # 备注（如人工复核记录）

    def __post_init__(self) -> None:
        if not self.extracted_at:
            self.extracted_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Entity:
    """统一实体模型 — 代码/文档/业务实体共用"""

    id: str  # 全局唯一 ID
    name: str  # 实体显示名
    type: str  # 实体类型（ENTITY_TYPES 之一）
    source: str  # 来源分析器
    domain: str = "通用"  # 业务域
    confidence: float = 1.0  # 总体置信度 0.0-1.0
    properties: dict = field(default_factory=dict)  # 领域属性
    provenance: Provenance | None = None  # 溯源信息
    source_path: str = ""  # 兼容旧字段
    source_line: int = 0
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        d = asdict(self)
        # provenance 序列化
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
        base = graph_url or "https://codeanalyze.local/kg"
        prov = self.provenance
        result = {
            "@context": {
                "schema": "https://schema.org/",
                "codeanalyze": f"{base}/ontology/",
                "prov": "http://www.w3.org/ns/prov#",
            },
            "@id": quote(f"{base}/entity/{self.id}", safe=":/-"),
            "@type": ["schema:Thing", f"codeanalyze:{self.type}"],
            "codeanalyze:name": self.name,
            "codeanalyze:domain": self.domain,
            "codeanalyze:confidence": self.confidence,
        }
        if prov:
            result["prov:wasGeneratedBy"] = {
                "@type": "prov:Activity",
                "prov:used": prov.source_file or "unknown",
                "prov:wasAssociatedWith": prov.analyzer,
                "codeanalyze:method": prov.method,
            }
        return result


@dataclass
class Relation:
    """统一关系模型 — 两个实体之间的语义边，带溯源"""

    source_id: str
    target_id: str
    type: str
    confidence: str = "EXTRACTED"  # EXTRACTED / INFERRED / AMBIGUOUS
    weight: float = 1.0
    provenance: Provenance | None = None  # 关系级别的溯源
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
        base = graph_url or "https://codeanalyze.local/kg"
        rel = RELATION_TYPES.get(self.type, {})
        return {
            "@context": {"schema": "https://schema.org/", "codeanalyze": f"{base}/ontology/"},
            "@id": quote(f"{base}/relation/{self.source_id}--{self.type}--{self.target_id}", safe=":/-"),
            "@type": ["schema:Relationship", f"codeanalyze:{self.type}"],
            "schema:name": rel.get("label", self.type),
            "codeanalyze:domain": rel.get("domain", ""),
            "codeanalyze:confidence": self.confidence,
            "schema:about": {"@id": quote(f"{base}/entity/{self.source_id}", safe=":/-")},
            "schema:relatedTo": {"@id": quote(f"{base}/entity/{self.target_id}", safe=":/-")},
        }


@dataclass
class KnowledgeGraph:
    """完整知识图谱 — 实体 + 关系 + 元数据 + 溯源"""

    entities: dict[str, Entity] = field(default_factory=dict)
    relations: list[Relation] = field(default_factory=list)
    source_files: dict[str, dict] = field(default_factory=dict)  # path → {size, type, analyzer}
    metadata: dict = field(default_factory=dict)

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    @property
    def relation_count(self) -> int:
        return len(self.relations)

    def add_entity(self, entity: Entity, source_file: str = "") -> None:
        self.entities[entity.id] = entity
        # 自动添加溯源关系：实体 → 来源文件
        src = source_file or entity.source_path or (entity.provenance.source_file if entity.provenance else "")
        if src:
            sf_id = f"file-{src[-60:]}"
            if sf_id not in self.entities:
                self.entities[sf_id] = Entity(
                    id=sf_id,
                    name=src.split("/")[-1],
                    type="SourceFile",
                    source=entity.source,
                    domain="溯源",
                    properties={"path": src},
                    provenance=Provenance(source_file=src, analyzer="filesystem", method="stat"),
                )
                self.source_files[src] = {"id": sf_id, "analyzer": entity.source}
            self.relations.append(
                Relation(
                    source_id=entity.id,
                    target_id=sf_id,
                    type="EXTRACTED_FROM",
                    confidence="EXTRACTED",
                    provenance=Provenance(source_file=src, analyzer=entity.source, method="filesystem"),
                )
            )

    def add_relation(self, relation: Relation) -> None:
        self.relations.append(relation)

    def merge(self, other: KnowledgeGraph) -> None:
        """合并另一个图谱，自动建立跨域实体链接。"""
        # 先合并实体（去重）
        for eid, entity in other.entities.items():
            if eid not in self.entities:
                self.entities[eid] = entity
            else:
                # 同ID实体来自不同分析器 → 建立 SAME_AS 关系去重
                existing = self.entities[eid]
                if existing.source != entity.source and eid not in {r.source_id for r in self.relations}:
                    self.relations.append(
                        Relation(
                            source_id=eid,
                            target_id=eid,
                            type="SAME_AS",
                            confidence="INFERRED",
                            provenance=Provenance(
                                analyzer="merge",
                                method="entity_resolution",
                                confidence=0.7,
                            ),
                        )
                    )
        # 合并关系
        self.relations.extend(other.relations)
        # 合并 source_files
        self.source_files.update(other.source_files)

    def to_dict(self) -> dict:
        return {
            "metadata": {
                **self.metadata,
                "entity_count": self.entity_count,
                "relation_count": self.relation_count,
                "source_files": len(self.source_files),
            },
            "entities": [e.to_dict() for e in self.entities.values()],
            "relations": [r.to_dict() for r in self.relations],
        }

    def to_json(self, indent: int = 2, ensure_ascii: bool = False) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent)

    def to_json_ld(self, graph_url: str = "") -> dict:
        base = graph_url or "https://codeanalyze.local/kg"
        return {
            "@context": {
                "schema": "https://schema.org/",
                "codeanalyze": f"{base}/ontology/",
                "prov": "http://www.w3.org/ns/prov#",
            },
            "@graph": (
                [e.to_json_ld(base) for e in self.entities.values()] + [r.to_json_ld(base) for r in self.relations]
            ),
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
            # escape single quotes for Cypher safety
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


# ── 领域适配器 ──


class DomainAdapter:
    """每个分析器继承此类，实现 to_kg() 方法。"""

    def to_kg(self) -> KnowledgeGraph:
        raise NotImplementedError
