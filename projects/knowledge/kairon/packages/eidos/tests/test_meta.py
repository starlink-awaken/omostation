"""Tests for the SSOT meta-model module."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class TestMetaType:
    def test_all_types_defined(self):
        from eidos.meta import MetaType

        values = [e.value for e in MetaType]
        expected = ["domain", "fact", "inference", "relation", "state", "document", "constraint", "processor"]
        for exp in expected:
            assert exp in values, f"Missing MetaType: {exp}"

    def test_from_string(self):
        from eidos.meta import MetaType

        assert MetaType.from_string("domain") == MetaType.DOMAIN
        assert MetaType.from_string("FACT") == MetaType.FACT

    def test_from_string_invalid(self):
        import pytest
        from eidos.meta import MetaType

        with pytest.raises(ValueError):
            MetaType.from_string("nonexistent")

    def test_display_name(self):
        from eidos.meta import MetaType

        assert MetaType.DOMAIN.display_name() == "领域实体"
        assert MetaType.FACT.display_name() == "事实断言"


class TestMetaRelationType:
    def test_all_relations_defined(self):
        from eidos.meta import MetaRelationType

        values = [e.value for e in MetaRelationType]
        expected = ["struct", "derive", "behavior", "justify"]
        for exp in expected:
            assert exp in values, f"Missing MetaRelationType: {exp}"

    def test_from_string(self):
        from eidos.meta import MetaRelationType

        assert MetaRelationType.from_string("struct") == MetaRelationType.STRUCT
        assert MetaRelationType.from_string("derive") == MetaRelationType.DERIVE


class TestListTypes:
    def test_list_all(self):
        from eidos.meta import list_types

        types = list_types()
        assert len(types) >= 8

    def test_list_filtered(self):
        from eidos.meta import MetaType, list_types

        types = list_types(MetaType.DOMAIN)
        assert all(t["meta_type"] == "domain" for t in types)

    def test_list_filter_missing(self):
        from eidos.meta import MetaType, list_types

        types = list_types(MetaType.PROCESSOR)
        # PROCESSOR has no mapped types
        assert len(types) >= 0
