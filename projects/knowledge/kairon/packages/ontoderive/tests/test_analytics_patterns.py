"""Unit tests for analytics_patterns module-level functions"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

# detect/analyze functions take `engine` but don't use it — expected pattern

import pytest
from ontoderive.theories.analytics_patterns import (
    _extract_num,
    _find_entity_for_fact,
    _is_dict,
    _iter_facts,
    analyze_capacity,
    analyze_market_structure,
    detect_capacity_constraint,
    detect_market_structure,
)

# ============================================================
# Mock engine — detect/analyze functions accept `self` as first
# param but never use it.  A plain object suffices.
# ============================================================


class _MockEngine:
    patterns: list[str] = []
    enhancer = None
    matcher = None


@pytest.fixture
def engine():
    return _MockEngine()


# ============================================================
# _is_dict
# ============================================================


class TestIsDict:
    def test_dict_returns_true(self):
        assert _is_dict({}) is True
        assert _is_dict({"a": 1}) is True

    def test_none_returns_false(self):
        assert _is_dict(None) is False

    def test_list_returns_false(self):
        assert _is_dict([]) is False
        assert _is_dict([1, 2]) is False

    def test_string_returns_false(self):
        assert _is_dict("") is False
        assert _is_dict("hello") is False

    def test_int_returns_false(self):
        assert _is_dict(0) is False
        assert _is_dict(42) is False

    def test_float_returns_false(self):
        assert _is_dict(3.14) is False

    def test_bool_returns_false(self):
        # bool is a subclass of int, not dict
        assert _is_dict(True) is False
        assert _is_dict(False) is False

    def test_tuple_returns_false(self):
        assert _is_dict(()) is False


# ============================================================
# _iter_facts — additional edge cases beyond test_analytics
# ============================================================


class TestIterFacts:
    def test_yields_fid_and_info(self):
        facts = {"D-F1": {"desc": "a"}}
        results = list(_iter_facts(facts))
        assert results == [("D-F1", {"desc": "a"})]

    def test_skips_non_dict_values_but_yields_dict_ones(self):
        facts = {
            "D-F1": {"desc": "valid"},
            "D-F2": "string",
            "D-F3": {"desc": "also valid"},
        }
        results = list(_iter_facts(facts))
        assert len(results) == 2
        assert ("D-F1", {"desc": "valid"}) in results
        assert ("D-F3", {"desc": "also valid"}) in results

    def test_fact_with_missing_desc(self):
        """dict values without 'desc' key should still be yielded"""
        facts = {"D-F1": {"value": "100"}}
        results = list(_iter_facts(facts))
        assert len(results) == 1

    def test_generator_lazy(self):
        """_iter_facts returns a generator, not a list"""
        facts = {"D-F1": {"desc": "a"}}
        gen = _iter_facts(facts)
        assert hasattr(gen, "__next__")

    def test_non_string_keys(self):
        facts = {1: {"desc": "int key"}, (): {"desc": "tuple key"}}
        results = list(_iter_facts(facts))
        assert len(results) == 2


# ============================================================
# _extract_num — additional edge cases beyond test_analytics
# ============================================================


class TestExtractNum:
    def test_int(self):
        assert _extract_num(42) == 42.0

    def test_float(self):
        assert _extract_num(3.14) == 3.14

    def test_zero(self):
        assert _extract_num(0) == 0.0

    def test_zero_float(self):
        assert _extract_num(0.0) == 0.0

    def test_none(self):
        """None should be converted to string 'None' and yield 0.0"""
        assert _extract_num(None) == 0.0

    def test_negative_number_string(self):
        assert _extract_num("-42") == 42.0

    def test_whitespace_string(self):
        assert _extract_num("  ") == 0.0

    def test_string_with_leading_trailing_spaces(self):
        assert _extract_num("  94%  ") == 94.0

    def test_very_long_string(self):
        long_str = "数字" * 1000 + "42" + "数据" * 1000
        assert _extract_num(long_str) == 42.0

    def test_percentage_with_decimal(self):
        assert _extract_num("12.5%") == 12.5

    def test_string_with_units(self):
        assert _extract_num("1286万辆") == 1286.0
        assert _extract_num("5.3亿元") == 5.3

    def test_multiple_numbers_uses_first(self):
        assert _extract_num("50到100亿元") == 50.0

    def test_bool_false_returns_zero(self):
        # bool is handled as int before re check, so isinstance(val, bool) is True
        # -> returns 0.0 per source code
        assert _extract_num(False) == 0.0

    def test_empty_string(self):
        assert _extract_num("") == 0.0

    def test_no_digits(self):
        assert _extract_num("无数据") == 0.0

    def test_chinese_number_large(self):
        assert _extract_num("999999.99") == 999999.99


# ============================================================
# _find_entity_for_fact — additional edge cases
# ============================================================


class TestFindEntityForFact:
    def test_string_match_returns_correct_eid(self):
        entities = {
            "E-ORG-A": {"name": "企业A"},
            "E-ORG-B": {"name": "企业B"},
        }
        fid = _find_entity_for_fact("D-F1", "企业A营收增长", entities)
        assert fid == "E-ORG-A"

    def test_partial_name_in_desc(self):
        """entity name appears as substring in desc"""
        entities = {"E-1": {"name": "北京"}}
        fid = _find_entity_for_fact("D-F1", "北京公司营收", entities)
        assert fid == "E-1"

    def test_no_match_returns_fid(self):
        entities = {"E-1": {"name": "企业A"}}
        fid = _find_entity_for_fact("D-F1", "无关描述", entities)
        assert fid == "D-F1"

    def test_non_dict_entities_returns_fid(self):
        fid = _find_entity_for_fact("D-F1", "desc", ["not", "a", "dict"])
        assert fid == "D-F1"

    def test_empty_entities(self):
        fid = _find_entity_for_fact("D-F1", "desc", {})
        assert fid == "D-F1"

    def test_none_entities(self):
        fid = _find_entity_for_fact("D-F1", "desc", None)
        assert fid == "D-F1"

    def test_entities_with_missing_name_key(self):
        """entity without 'name' — desc does not contain '' so no match => fid"""
        entities = {"E-1": {"other": "data"}}
        # info.get("name", "") returns "" and "" in desc is always True for any str,
        # so E-1 matches. Use a desc that doesn't contain empty string... impossible.
        # Instead verify the actual behavior: empty string is "in" any string, so
        # the entity without name will still match any desc.
        fid = _find_entity_for_fact("D-F1", "other", entities)
        assert fid == "E-1"  # "" in "other" is True in Python

    def test_entities_mixed_dict_and_non_dict(self):
        entities = {
            "E-1": {"name": "企业A"},
            "E-2": "not a dict",
            "E-3": {"name": "企业B"},
        }
        fid = _find_entity_for_fact("D-F1", "企业B产出", entities)
        assert fid == "E-3"

    def test_first_matching_entity_returned(self):
        """when multiple entities have same name in desc, first iterated wins"""
        entities = {
            "E-ORG-A": {"name": "企业A"},
            "E-ORG-B": {"name": "企业A"},
        }
        fid = _find_entity_for_fact("D-F1", "企业A营收", entities)
        assert fid == "E-ORG-A"


# ============================================================
# Fixtures for detect_x / analyze_x tests
# ============================================================


@pytest.fixture
def empty_facts():
    return {}


@pytest.fixture
def empty_entities():
    return {}


@pytest.fixture
def empty_relations():
    return []


@pytest.fixture
def high_util_facts():
    return {"D-F1": {"desc": "产能利用率", "value": "94%"}}


@pytest.fixture
def normal_util_facts():
    return {"D-F1": {"desc": "产能利用率", "value": "75%"}}


@pytest.fixture
def low_stock_facts():
    return {
        "D-F1": {"desc": "库存天数", "value": "12天"},
        "D-F2": {"desc": "安全库存基准", "value": "30天"},
    }


@pytest.fixture
def market_facts():
    return {
        "D-F1": {"desc": "企业A市场份额", "value": "50"},
        "D-F2": {"desc": "企业B市场份额", "value": "30"},
        "D-F3": {"desc": "企业C市场份额", "value": "20"},
    }


@pytest.fixture
def three_entities():
    return {"E-A": {"name": "企业A"}, "E-B": {"name": "企业B"}, "E-C": {"name": "企业C"}}


# ============================================================
# detect_capacity_constraint — 2+ tests (True / False)
# ============================================================


class TestDetectCapacityConstraint:
    def test_true_high_utilization(self, engine, high_util_facts):
        assert detect_capacity_constraint(engine, high_util_facts, {}, []) is True

    def test_true_low_stock_below_safety(self, engine, low_stock_facts):
        assert detect_capacity_constraint(engine, low_stock_facts, {}, []) is True

    def test_true_excess_capacity(self, engine):
        facts = {"D-F1": {"desc": "产能利用率", "value": "56%"}}
        assert detect_capacity_constraint(engine, facts, {}, []) is True

    def test_false_normal_utilization(self, engine, normal_util_facts):
        assert detect_capacity_constraint(engine, normal_util_facts, {}, []) is False

    def test_false_empty_facts(self, engine, empty_facts):
        assert detect_capacity_constraint(engine, empty_facts, {}, []) is False

    def test_false_unrelated_facts(self, engine):
        facts = {"D-F1": {"desc": "营收", "value": "100亿"}}
        assert detect_capacity_constraint(engine, facts, {}, []) is False

    def test_false_utilization_90_exact(self, engine):
        """90% is not > 90, so should not trigger"""
        facts = {"D-F1": {"desc": "产能利用率", "value": "90%"}}
        assert detect_capacity_constraint(engine, facts, {}, []) is False

    def test_false_utilization_60_exact(self, engine):
        """60% is not < 60, so should not trigger"""
        facts = {"D-F1": {"desc": "产能利用率", "value": "60%"}}
        assert detect_capacity_constraint(engine, facts, {}, []) is False

    def test_false_non_dict_facts(self, engine):
        assert detect_capacity_constraint(engine, "not a dict", {}, []) is False

    def test_true_uses_description_field(self, engine):
        """description field should work the same as desc"""
        facts = {"D-F1": {"description": "产能利用率", "value": "93%"}}
        assert detect_capacity_constraint(engine, facts, {}, []) is True


# ============================================================
# detect_market_structure — 2+ tests (True / False)
# ============================================================


class TestDetectMarketStructure:
    def test_true_three_entities(self, engine, three_entities):
        assert detect_market_structure(engine, {}, three_entities, []) is True

    def test_true_market_keyword_in_fact(self, engine, market_facts, empty_entities):
        assert detect_market_structure(engine, market_facts, empty_entities, []) is True

    def test_true_market_keyword_matches_kw_list(self, engine):
        """single entity + fact with market keyword should trigger"""
        facts = {"D-F1": {"desc": "市场集中度数据", "value": "0.4"}}
        assert detect_market_structure(engine, facts, {"E-A": {}}, []) is True

    def test_false_two_entities_no_keyword(self, engine):
        entities = {"E-A": {}, "E-B": {}}
        assert detect_market_structure(engine, {}, entities, []) is False

    def test_false_empty_facts_empty_entities(self, engine, empty_facts, empty_entities):
        assert detect_market_structure(engine, empty_facts, empty_entities, []) is False

    def test_false_no_market_kw(self, engine):
        entities = {"E-A": {}}
        facts = {"D-F1": {"desc": "营收数据", "value": "100"}}
        assert detect_market_structure(engine, facts, entities, []) is False


# ============================================================
# analyze_capacity — verify list[dict] with expected keys
# ============================================================


class TestAnalyzeCapacity:
    def test_returns_list_of_dicts(self, engine, high_util_facts):
        results = analyze_capacity(engine, high_util_facts, {}, [], None)
        assert isinstance(results, list)
        assert all(isinstance(r, dict) for r in results)

    def test_result_has_expected_keys(self, engine, high_util_facts):
        results = analyze_capacity(engine, high_util_facts, {}, [], None)
        for r in results:
            assert "type" in r
            assert "conclusion" in r
            assert "derives_from" in r
            assert "confidence" in r
            assert r["type"] == "analytics"
            assert isinstance(r["derives_from"], list)
            assert isinstance(r["confidence"], (int, float))

    def test_supply_elasticity_conclusion(self, engine, high_util_facts):
        """94% utilization -> supply elasticity ~0.06"""
        results = analyze_capacity(engine, high_util_facts, {}, [], None)
        assert any("供给弹性" in r["conclusion"] for r in results)

    def test_excess_capacity_conclusion(self, engine):
        facts = {"D-F1": {"desc": "产能利用率", "value": "56%"}}
        results = analyze_capacity(engine, facts, {}, [], None)
        assert any("产能过剩" in r["conclusion"] for r in results)

    def test_inventory_gap_conclusion(self, engine, low_stock_facts):
        results = analyze_capacity(engine, low_stock_facts, {}, [], None)
        assert any("库存缺口" in r["conclusion"] for r in results)

    def test_empty_facts_returns_empty_list(self, engine, empty_facts):
        assert analyze_capacity(engine, empty_facts, {}, [], None) == []

    def test_unrelated_facts_returns_empty_list(self, engine):
        facts = {"D-F1": {"desc": "营收", "value": "100亿"}}
        assert analyze_capacity(engine, facts, {}, [], None) == []

    def test_non_dict_facts(self, engine):
        assert analyze_capacity(engine, "bad", {}, [], None) == []

    def test_multiple_results_possible(self, engine):
        """both utilization and inventory issues -> multiple results"""
        facts = {
            "D-F1": {"desc": "产能利用率", "value": "94%"},
            "D-F2": {"desc": "库存天数", "value": "12天"},
            "D-F3": {"desc": "安全库存基准", "value": "30天"},
        }
        results = analyze_capacity(engine, facts, {}, [], None)
        assert len(results) >= 2


# ============================================================
# analyze_market_structure — verify list[dict] with expected keys
# ============================================================


class TestAnalyzeMarketStructure:
    def test_returns_list_of_dicts(self, engine, market_facts, empty_entities):
        results = analyze_market_structure(engine, market_facts, empty_entities, [], None)
        assert isinstance(results, list)
        assert all(isinstance(r, dict) for r in results)

    def test_result_has_expected_keys(self, engine, market_facts, empty_entities):
        results = analyze_market_structure(engine, market_facts, empty_entities, [], None)
        for r in results:
            assert "type" in r
            assert "conclusion" in r
            assert "derives_from" in r
            assert "confidence" in r
            assert r["type"] == "analytics"
            assert isinstance(r["derives_from"], list)
            assert isinstance(r["confidence"], (int, float))

    def test_monopoly_detected(self, engine):
        """single share > 50 -> HHI > 2500 -> 垄断"""
        facts = {"D-F1": {"desc": "市场份额", "value": "60"}}
        results = analyze_market_structure(engine, facts, {"E-A": {}}, [], None)
        assert any("垄断" in r["conclusion"] for r in results)

    def test_hhi_calculation(self, engine):
        """two shares 50/50 -> HHI = 5000"""
        facts = {
            "D-F1": {"desc": "市场份额", "value": "50"},
            "D-F2": {"desc": "市场份额", "value": "50"},
        }
        results = analyze_market_structure(engine, facts, {"E-A": {}, "E-B": {}}, [], None)
        hhi_line = next(r for r in results if "HHI" in r["conclusion"])
        # 2500 + 2500 = 5000
        assert "HHI=5000" in hhi_line["conclusion"]

    def test_cr3_with_less_than_3_shares(self, engine):
        """fewer than 3 share facts -> CR3 = 100%"""
        facts = {"D-F1": {"desc": "份额", "value": "50"}}
        results = analyze_market_structure(engine, facts, {"E-A": {}}, [], None)
        assert any("CR3=100%" in r["conclusion"] for r in results)

    def test_empty_shares_no_results(self, engine):
        """no market-keyword facts -> empty results"""
        facts = {"D-F1": {"desc": "一般数据", "value": "50"}}
        results = analyze_market_structure(engine, facts, {}, [], None)
        assert results == []

    def test_multiple_entities_counted(self, engine, market_facts, three_entities):
        results = analyze_market_structure(engine, market_facts, three_entities, [], None)
        assert any("3个参与者" in r["conclusion"] for r in results)

    def test_non_dict_facts(self, engine):
        assert analyze_market_structure(engine, "bad", {}, [], None) == []
