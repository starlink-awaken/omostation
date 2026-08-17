"""Tests for minerva intent classification — extracted from SharedBrain D_Intelligence."""

from minerva.intent import ClassificationResult, ComplexityLevel, classify_intent


def test_simple_read_intent():
    result = classify_intent("read the file and show status")
    assert result.level == ComplexityLevel.SIMPLE
    assert result.confidence > 0.5


def test_complex_deploy_intent():
    result = classify_intent("deploy multi-step pipeline to production")
    assert result.level == ComplexityLevel.COMPLEX
    assert result.requires_swarm


def test_moderate_analyze_intent():
    result = classify_intent("analyze and search for patterns")
    assert result.level == ComplexityLevel.MODERATE


def test_unknown_intent_defaults_moderate():
    result = classify_intent("xyzzy foobar quux")
    assert result.level == ComplexityLevel.MODERATE
    assert result.confidence == 0.3


def test_mixed_intent_picks_best():
    result = classify_intent("read and deploy")
    assert result.level in (ComplexityLevel.SIMPLE, ComplexityLevel.COMPLEX)


def test_classification_result_trivial():
    r = ClassificationResult(level=ComplexityLevel.SIMPLE, confidence=0.9)
    assert r.is_trivial
    assert not r.requires_swarm


def test_swarm_size_defaults():
    r = ClassificationResult(level=ComplexityLevel.SIMPLE, confidence=0.8)
    assert r.suggested_swarm_size == 1


def test_enum_values():
    assert ComplexityLevel.SIMPLE.value == "SIMPLE"
    assert ComplexityLevel.COMPLEX.value == "COMPLEX"
