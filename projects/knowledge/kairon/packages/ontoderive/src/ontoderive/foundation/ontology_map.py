"""
本体映射 — OntoDerive类型 → 标准词汇表
========================================
支持导出: schema.org, PROV-O, Dublin Core, SKOS
"""

import json
from dataclasses import dataclass
from typing import Any

# ── 类型映射表 ──
TYPE_MAPPINGS = {
    # OntoDerive → [schema.org, PROV-O, Dublin Core]
    "DOMAIN:ORG": {
        "schema_org": "Organization",
        "prov_o": "prov:Agent",
        "dc": "dc:Agent",
        "description": "组织 — 机构/公司/政府部门",
    },
    "DOMAIN:ROL": {
        "schema_org": "Person",
        "prov_o": "prov:Agent",
        "dc": "dc:Agent",
        "description": "角色 — 个人/职位持有者",
    },
    "DOMAIN:PRJ": {
        "schema_org": "Project",
        "prov_o": "prov:Entity",
        "dc": "dc:Collection",
        "description": "项目 — 工程/计划/方案",
    },
    "FACT:DAT": {
        "schema_org": "QuantitativeValue",
        "prov_o": "prov:Entity",
        "dc": "dc:Dataset",
        "description": "数据事实 — 可量化的观测",
    },
    "FACT:POL": {
        "schema_org": "Legislation",
        "prov_o": "prov:Entity",
        "dc": "dc:Policy",
        "description": "政策事实 — 法规/公文/标准",
    },
    "INFERENCE": {
        "schema_org": "Claim",
        "prov_o": "prov:Entity",
        "dc": "dc:Statement",
        "description": "推论 — 从事实推导的结论",
    },
    "DOCUMENT:STD": {
        "schema_org": "Standard",
        "prov_o": "prov:Entity",
        "dc": "dc:Standard",
        "description": "标准 — ISO/GB/行业标准",
    },
}

# ── 关系映射表 ──
RELATION_MAPPINGS = {
    "cooperates_with": {
        "schema_org": "https://schema.org/colleague",
        "uri": "http://purl.org/dc/terms/relation",
    },
    "part_of": {
        "schema_org": "https://schema.org/isPartOf",
        "uri": "http://purl.org/dc/terms/isPartOf",
    },
    "employs": {
        "schema_org": "https://schema.org/employee",
        "uri": "http://xmlns.com/foaf/0.1/member",
    },
    "derives_from": {
        "schema_org": "https://schema.org/citation",
        "uri": "http://purl.org/dc/terms/source",
        "prov_uri": "http://www.w3.org/ns/prov#wasDerivedFrom",
    },
    "depends_on": {
        "schema_org": "https://schema.org/isBasedOn",
        "uri": "http://purl.org/dc/terms/requires",
    },
    "authored_by": {
        "schema_org": "https://schema.org/author",
        "uri": "http://purl.org/dc/terms/creator",
    },
    "influences": {
        "schema_org": "https://schema.org/about",
        "uri": "http://purl.org/dc/terms/subject",
    },
    "precedes": {
        "schema_org": "https://schema.org/before",
        "uri": "http://purl.org/dc/terms/temporal",
    },
}


@dataclass
class RDFTriple:
    """RDF三元组"""

    subject: str
    predicate: str
    object: str
    datatype: str = ""  # xsd:string, xsd:decimal, etc.


class OntologyMapper:
    """本体映射器 — 将OntoDerive知识导出为标准格式"""

    DEFAULT_BASE_URI = "https://ontoderive.org/ns/"
    DEFAULT_CONTEXT = {
        "@vocab": DEFAULT_BASE_URI,
        "schema": "https://schema.org/",
        "prov": "http://www.w3.org/ns/prov#",
        "dc": "http://purl.org/dc/terms/",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
    }

    def to_schema_org_type(self, onto_type: str) -> str:
        """OntoDerive类型→schema.org类型"""
        return TYPE_MAPPINGS.get(onto_type, {}).get("schema_org", "Thing")

    def to_prov_type(self, onto_type: str) -> str:
        """OntoDerive类型→PROV-O类型"""
        return TYPE_MAPPINGS.get(onto_type, {}).get("prov_o", "prov:Entity")

    def to_jsonld(self, knowledge: Any, base_uri: str = "") -> dict:
        """将FormalKnowledge导出为JSON-LD (schema.org context)"""
        uri = base_uri or self.DEFAULT_BASE_URI

        result: dict[str, Any] = {
            "@context": dict(self.DEFAULT_CONTEXT),
            "@graph": [],
        }

        # 实体 → schema:Thing
        for eid, edata in knowledge.abox.get("entities", {}).items():
            etype = edata.get("type", "")
            schema_type = self.to_schema_org_type(f"DOMAIN:{etype}")
            if not schema_type or schema_type == "Thing":
                schema_type = self.to_schema_org_type(f"DOCUMENT:{etype}")
            node = {
                "@id": f"{uri}{eid}",
                "@type": schema_type,
                "schema:name": edata.get("name", ""),
                "schema:description": edata.get("role", ""),
            }
            result["@graph"].append(node)

        # 事实 → schema:QuantitativeValue / prov:Entity
        for fid, fdata in knowledge.abox.get("facts", {}).items():
            result["@graph"].append(
                {
                    "@id": f"{uri}{fid}",
                    "@type": "schema:QuantitativeValue",
                    "schema:value": fdata.get("value", ""),
                    "schema:description": fdata.get("description", ""),
                }
            )

        # 推论 → schema:Claim (含prov:wasDerivedFrom)
        for inf in knowledge.inferences:
            claim = {
                "@id": f"{uri}{inf.id}",
                "@type": "schema:Claim",
                "schema:text": inf.conclusion or inf.title,
                "prov:wasDerivedFrom": [f"{uri}{d}" for d in inf.derives_from],
            }
            result["@graph"].append(claim)

        return result

    def to_turtle(self, knowledge: Any, base_uri: str = "") -> str:
        """导出Turtle格式 (最小实现)"""
        uri = base_uri or self.DEFAULT_BASE_URI
        lines = [
            f"@prefix onto: <{uri}> .",
            "@prefix schema: <https://schema.org/> .",
            "@prefix prov: <http://www.w3.org/ns/prov#> .",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n",
        ]
        # 实体
        for eid, edata in knowledge.abox.get("entities", {}).items():
            etype = edata.get("type", "ORG")
            lines.append(f"onto:{eid} a schema:{self.to_schema_org_type(f'DOMAIN:{etype}')} ;")
            lines.append(f'    schema:name "{edata.get("name", "")}" .\n')

        # 事实
        for fid, fdata in knowledge.abox.get("facts", {}).items():
            val = fdata.get("value", "").replace('"', '\\"')
            lines.append(f"onto:{fid} a schema:QuantitativeValue ;")
            lines.append(f'    schema:value "{val}" .\n')

        # 推论 + 推导链
        for inf in knowledge.inferences:
            lines.append(f"onto:{inf.id} a schema:Claim ;")
            lines.append(f'    schema:text "{inf.conclusion or inf.title}" .')
            for d in inf.derives_from:
                lines.append(f"onto:{inf.id} prov:wasDerivedFrom onto:{d} .")
            lines.append("")

        return "\n".join(lines)

    def export(self, knowledge: Any, fmt: Any = "jsonld", base_uri: Any = "") -> str:
        """统一导出入口"""
        if fmt == "turtle":
            return self.to_turtle(knowledge, base_uri)
        return json.dumps(self.to_jsonld(knowledge, base_uri), ensure_ascii=False, indent=2)
