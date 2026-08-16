"""
测试 foundation/ontology_map.py - 本体映射与格式导出
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import json

from ontoderive.foundation.ontology_map import (  # type: ignore[import-not-found]
    RELATION_MAPPINGS,
    TYPE_MAPPINGS,
    OntologyMapper,
    RDFTriple,
)


class MockKnowledge:
    """模拟 FormalKnowledge 对象供测试"""

    def __init__(self, entities=None, facts=None, inferences=None):
        self.abox = {
            "entities": entities or {},
            "facts": facts or {},
        }
        self.inferences = inferences or []


class MockInference:
    def __init__(self, id, conclusion="", title="", derives_from=None):
        self.id = id
        self.conclusion = conclusion
        self.title = title
        self.derives_from = derives_from or []


class TestOntologyMapper:
    """OntologyMapper - 类型映射与格式导出"""

    def setup_method(self):
        self.mapper = OntologyMapper()

    def test_to_schema_org_type_known(self):
        assert self.mapper.to_schema_org_type("DOMAIN:ORG") == "Organization"
        assert self.mapper.to_schema_org_type("DOMAIN:ROL") == "Person"
        assert self.mapper.to_schema_org_type("FACT:DAT") == "QuantitativeValue"

    def test_to_schema_org_type_unknown_defaults_to_thing(self):
        assert self.mapper.to_schema_org_type("UNKNOWN") == "Thing"

    def test_to_prov_type_known(self):
        assert self.mapper.to_prov_type("DOMAIN:ORG") == "prov:Agent"
        assert self.mapper.to_prov_type("FACT:POL") == "prov:Entity"

    def test_to_prov_type_unknown_defaults_to_entity(self):
        assert self.mapper.to_prov_type("BOGUS") == "prov:Entity"

    def test_to_jsonld_empty_knowledge(self):
        kn = MockKnowledge()
        result = self.mapper.to_jsonld(kn)
        assert "@context" in result
        assert "@graph" in result
        assert len(result["@graph"]) == 0

    def test_to_jsonld_with_entities_and_facts(self):
        kn = MockKnowledge(
            entities={
                "E1": {"type": "ORG", "name": "测试组织", "role": "监管"},
                "E2": {"type": "ROL", "name": "张三", "role": "负责人"},
            },
            facts={
                "F1": {"value": "100", "description": "测试数据"},
            },
            inferences=[
                MockInference("INF-1", conclusion="结论一", derives_from=["F1"]),
            ],
        )
        result = self.mapper.to_jsonld(kn)
        graph = result["@graph"]
        # 2 entities + 1 fact + 1 inference = 4 nodes
        assert len(graph) == 4

        entities = [n for n in graph if n["@type"] in ("Organization", "Person")]
        facts = [n for n in graph if n["@type"] == "schema:QuantitativeValue"]
        claims = [n for n in graph if n["@type"] == "schema:Claim"]

        assert len(entities) == 2
        assert len(facts) == 1
        assert len(claims) == 1
        assert claims[0]["schema:text"] == "结论一"
        assert "prov:wasDerivedFrom" in claims[0]

    def test_to_turtle_renders_prefixes_and_triples(self):
        kn = MockKnowledge(
            entities={"E1": {"type": "ORG", "name": "Alpha"}},
            facts={"F1": {"value": "200"}},
            inferences=[MockInference("I1", conclusion="inf", derives_from=["F1"])],
        )
        turtle = self.mapper.to_turtle(kn)
        assert "@prefix onto:" in turtle
        assert "@prefix schema:" in turtle
        assert "onto:E1" in turtle
        assert "schema:name" in turtle
        assert "onto:F1" in turtle
        assert "onto:I1" in turtle
        assert "prov:wasDerivedFrom" in turtle

    def test_to_turtle_empty_knowledge(self):
        kn = MockKnowledge()
        turtle = self.mapper.to_turtle(kn)
        assert turtle.startswith("@prefix")
        # 只有前缀行(4行) + 空行
        assert turtle.count("\n") >= 3

    def test_export_jsonld_returns_json_string(self):
        kn = MockKnowledge()
        result = self.mapper.export(kn, fmt="jsonld")
        parsed = json.loads(result)
        assert "@graph" in parsed

    def test_export_turtle_returns_turtle_string(self):
        kn = MockKnowledge(
            entities={"E1": {"type": "ORG", "name": "X"}},
        )
        result = self.mapper.export(kn, fmt="turtle")
        assert isinstance(result, str)
        assert "onto:E1" in result


class TestRDFTriple:
    """RDFTriple - 数据类"""

    def test_default_datatype_is_empty_string(self):
        t = RDFTriple(subject="s", predicate="p", object="o")
        assert t.datatype == ""

    def test_full_construction(self):
        t = RDFTriple(subject="s1", predicate="p1", object="o1", datatype="xsd:string")
        assert t.subject == "s1"
        assert t.predicate == "p1"
        assert t.object == "o1"
        assert t.datatype == "xsd:string"


class TestTypeMappings:
    """类型映射表完整性"""

    def test_all_entries_have_required_keys(self):
        for key, mapping in TYPE_MAPPINGS.items():
            assert "schema_org" in mapping
            assert "prov_o" in mapping
            assert "description" in mapping

    def test_relation_mappings_have_uris(self):
        for key, mapping in RELATION_MAPPINGS.items():
            assert "schema_org" in mapping
            assert "uri" in mapping
