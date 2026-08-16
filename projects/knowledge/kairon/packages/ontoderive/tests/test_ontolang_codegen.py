"""Tests for OntoLang code generator"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.ontolang.ast import AST, EntityDef
from ontoderive.ontolang.codegen import to_json, to_legacy_ast, to_markdown


def test_to_markdown_empty():
    result = to_markdown(AST())
    assert isinstance(result, str)


def test_to_markdown_with_entity():
    ast = AST(entities=[EntityDef(id="ORG-Test", entity_type="organization")])
    result = to_markdown(ast)
    assert "ORG-Test" in result
    assert "organization" in result


def test_to_json():
    ast = AST(entities=[EntityDef(id="ORG-Test", entity_type="organization")])
    result = to_json(ast)
    assert isinstance(result, dict)
    assert "entities" in result


def test_to_legacy_ast():
    ast = AST(entities=[EntityDef(id="ORG-Test", entity_type="organization")])
    result = to_legacy_ast(ast)
    assert isinstance(result, dict)
    assert "entities" in result
    assert result["entities"][0]["id"] == "ORG-Test"
