"""Tests for SSOT extractor module.

Covers: TextSource, ExtractionCandidate, ExtractionResult, ExtractionPipeline.
"""

from unittest.mock import patch

from sot_bridge.ssot_kernel.extractor import (
    Conflict,
    ExtractionCandidate,
    ExtractionPipeline,
    ExtractionResult,
    TextSource,
    ValidationResult,
)


class TestTextSource:
    def test_create(self):
        source = TextSource(raw_text="hello world", source_name="test.txt")
        assert source.raw_text == "hello world"
        assert source.source_name == "test.txt"

    def test_defaults(self):
        source = TextSource(raw_text="test")
        assert source.source_name == ""  # default
        assert source.metadata == {}


class TestExtractionCandidate:
    def test_create(self):
        cand = ExtractionCandidate(
            id="CAND-001",
            category="entity",
            content={"name": "Test"},
            confidence=0.9,
        )
        assert cand.id == "CAND-001"
        assert cand.category == "entity"
        assert cand.confidence == 0.9

    def test_defaults(self):
        cand = ExtractionCandidate(category="fact", content={"value": 1})
        assert cand.category == "fact"


class TestExtractionResult:
    def test_candidates_list(self):
        result = ExtractionResult(candidates=[])
        assert result.candidates == []

    def test_empty(self):
        result = ExtractionResult()
        assert result.candidates == []


class TestValidationResult:
    def test_passed(self):
        vr = ValidationResult(passed=True)
        assert vr.passed
        assert vr.conflicts == []

    def test_with_conflicts(self):
        vr = ValidationResult(passed=False, conflicts=[], suggestions=["Fix it"])
        assert not vr.passed
        assert vr.suggestions == ["Fix it"]


class TestConflict:
    def test_create(self):
        c = Conflict(field="name", existing_value="A", extracted_value="B")
        assert c.field == "name"
        assert c.existing_value == "A"
        assert c.extracted_value == "B"


class TestExtractionPipeline:
    def test_init(self):
        pipe = ExtractionPipeline()
        assert hasattr(pipe, "run")
        assert hasattr(pipe, "extractors")

    def test_run_with_empty_text(self):
        pipe = ExtractionPipeline()
        source = TextSource(raw_text="", source_name="empty.txt")
        result = pipe.run(source, auto_write=False)
        assert "result" in result

    def test_run_with_simple_text(self):
        pipe = ExtractionPipeline()
        source = TextSource(
            raw_text="Organization: TestCorp\nPolicy: Must comply with rule X",
            source_name="test.txt",
        )
        result = pipe.run(source, auto_write=False)
        assert "result" in result
        extraction = result["result"]
        assert hasattr(extraction, "candidates")

    def test_run_with_facts(self):
        pipe = ExtractionPipeline()
        source = TextSource(
            raw_text="Fact: DAT-001 with value 100km. Policy POL-001 says must.",
            source_name="facts.txt",
        )
        result = pipe.run(source, auto_write=False)
        assert "result" in result


def test_llm_extractor_uses_standard_litellm_env(monkeypatch):
    from sot_bridge.ssot_kernel.extractor.llm import LLMExtractor, OpenAIBackend

    monkeypatch.setenv("LLM_PROVIDER", "litellm")
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:4000/v1")
    monkeypatch.setenv("LLM_MODEL", "claude-3-5-sonnet")
    monkeypatch.setenv("LLM_API_KEY", "litellm-secret")
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with patch("urllib.request.urlopen", side_effect=OSError):
        extractor = LLMExtractor()

    assert extractor.backends
    backend = extractor.backends[0]
    assert isinstance(backend, OpenAIBackend)
    assert backend.base_url == "http://127.0.0.1:4000/v1"
    assert backend.model == "claude-3-5-sonnet"
