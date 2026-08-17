"""Tests for harvest data models — extracted from SharedBrain D_Harvest."""

from minerva.harvest_models import HarvestFact, HarvestRecord


def test_harvest_fact_defaults():
    f = HarvestFact(subject="Python", predicate="requires", object="CPython")
    assert f.subject == "Python"
    assert f.predicate == "requires"
    assert f.harvested_at != ""


def test_harvest_fact_as_triple():
    f = HarvestFact(subject="A", predicate="B", object="C")
    assert f.as_triple() == ("A", "B", "C")


def test_harvest_fact_to_dict():
    f = HarvestFact(subject="X", predicate="Y", object="Z", source="http://example.com", confidence=0.9)
    d = f.to_dict()
    assert d["source"] == "http://example.com"
    assert d["confidence"] == 0.9


def test_harvest_record_fact_count():
    r = HarvestRecord(source_url="http://test.com")
    assert r.fact_count == 0
    r.facts.append(HarvestFact(subject="a", predicate="b", object="c"))
    assert r.fact_count == 1


def test_harvest_record_valid_facts():
    r = HarvestRecord(
        source_url="http://test.com",
        facts=[
            HarvestFact("a", "b", "c", confidence=0.9),
            HarvestFact("d", "e", "f", confidence=0.3),
            HarvestFact("g", "h", "i", confidence=0.7),
        ],
    )
    valid = r.valid_facts(min_confidence=0.5)
    assert len(valid) == 2


def test_harvest_record_to_dict():
    r = HarvestRecord(source_url="http://test.com", operation="harvest", duration_ms=150.0)
    r.facts.append(HarvestFact("a", "b", "c"))
    d = r.to_dict()
    assert d["fact_count"] == 1
    assert d["operation"] == "harvest"
