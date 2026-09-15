"""类型系统测试"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.foundation.typesystem import META_TYPES, PREFIX_TO_META, TypeValidator


def test_meta_types_defined():
    assert len(META_TYPES) == 7
    assert "DOMAIN" in META_TYPES
    assert "FACT" in META_TYPES
    assert "INFERENCE" in META_TYPES


def test_prefix_mapping():
    assert PREFIX_TO_META["D-F"] == "FACT"
    assert PREFIX_TO_META["ORG-"] == "DOMAIN"
    assert PREFIX_TO_META["INF-"] == "INFERENCE"


def test_valid_id():
    tv = TypeValidator()
    r = tv.check_id("D-F1")
    assert r.is_valid
    assert r.expected_type == "FACT"


def test_valid_entity():
    tv = TypeValidator()
    r = tv.check_id("ORG-国转中心")
    assert r.is_valid
    assert r.expected_type == "DOMAIN"


def test_valid_inference():
    tv = TypeValidator()
    r = tv.check_id("INF-L1")
    assert r.is_valid
    assert r.expected_type == "INFERENCE"


def test_invalid_prefix():
    tv = TypeValidator()
    r = tv.check_id("BAD-xxx")
    assert not r.is_valid


def test_type_mismatch():
    tv = TypeValidator()
    r = tv.check_id("D-F1", "DOMAIN")
    assert not r.is_valid
    assert any("DOMAIN" in e for e in r.errors)


def test_batch_check():
    tv = TypeValidator()
    items = [
        {"id": "ORG-国转中心", "type": "DOMAIN"},
        {"id": "D-F1", "type": "FACT"},
        {"id": "INF-L1", "type": "INFERENCE"},
        {"id": "BAD", "type": "DOMAIN"},
    ]
    results = tv.check_batch(items)
    assert len(results) == 4
    assert results[0].is_valid
    assert not results[3].is_valid


def test_has_errors():
    tv = TypeValidator()
    tv.check_id("D-F1")
    assert not tv.has_errors()
    tv.check_id("BAD")
    assert tv.has_errors()


def test_summary():
    tv = TypeValidator()
    tv.check_id("D-F1", "FACT")
    tv.check_id("D-F2", "FACT")
    s = tv.summary()
    assert s["total"] == 2
    assert s["valid"] == 2


def test_v2_prefixes():
    tv = TypeValidator()
    assert tv._infer_type("INF-V2-001") == "INFERENCE"
    assert tv._infer_type("DCH-001") == "DOCUMENT"
