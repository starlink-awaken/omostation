"""Tests for eidos.output_reshaper."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false


class TestEstimateTokens:
    """Test estimate_tokens utility function."""

    def test_import(self):
        from eidos.output_reshaper import estimate_tokens

        assert estimate_tokens is not None

    def test_empty_text(self):
        from eidos.output_reshaper import estimate_tokens

        assert estimate_tokens("") == 0
        assert estimate_tokens("", method="character") == 0
        assert estimate_tokens("", method="word") == 0

    def test_approximation_method(self):
        from eidos.output_reshaper import estimate_tokens

        # All ASCII
        tokens = estimate_tokens("hello world")
        assert tokens >= 1

        # Mix CJK and ASCII
        tokens = estimate_tokens("你好 world")
        assert tokens >= 1

    def test_character_method(self):
        from eidos.output_reshaper import estimate_tokens

        result = estimate_tokens("abcd", method="character")
        assert result == 1

        result = estimate_tokens("abcdefgh", method="character")
        assert result == 2

    def test_word_method(self):
        from eidos.output_reshaper import estimate_tokens

        result = estimate_tokens("one two three", method="word")
        assert result == 3  # 3 words * 1.3 = 3.9 -> int(3.9) = 3

    def test_unknown_method_falls_back(self):
        from eidos.output_reshaper import estimate_tokens

        result = estimate_tokens("hello", method="unknown")
        assert result >= 1


class TestStrategyEnum:
    """Test Strategy enum."""

    def test_enum_values(self):
        from eidos.output_reshaper import Strategy

        assert Strategy.PASSTHROUGH.value == "passthrough"
        assert Strategy.LLM_COMPRESSION.value == "llm_compression"
        assert Strategy.SMART_TRUNCATE.value == "smart_truncate"

    def test_enum_uniqueness(self):
        from eidos.output_reshaper import Strategy

        values = [s.value for s in Strategy]
        assert len(values) == len(set(values))


class TestReshapeResult:
    """Test ReshapeResult dataclass."""

    def test_default_creation(self):
        from eidos.output_reshaper import ReshapeResult, Strategy

        result = ReshapeResult(
            compressed_output="hello",
            strategy_used=Strategy.PASSTHROUGH,
            confidence=1.0,
        )
        assert result.compressed_output == "hello"
        assert result.strategy_used == Strategy.PASSTHROUGH
        assert result.confidence == 1.0
        assert result.original_tokens == 0
        assert result.compressed_tokens == 0
        assert result.metadata == {}


class TestOutputReshaper:
    """Test OutputReshaper class."""

    def test_import(self):
        from eidos.output_reshaper import OutputReshaper

        assert OutputReshaper is not None

    def test_default_initialization(self):
        from eidos.output_reshaper import OutputReshaper

        reshaper = OutputReshaper()
        assert reshaper.status == "ACTIVE"
        assert reshaper.token_threshold == 2000
        assert reshaper.truncate_threshold == 5000
        assert reshaper.max_output_tokens == 500
        assert reshaper.llm_timeout == 0.5
        assert reshaper._initialized is True

    def test_shape_passthrough_short_text(self):
        from eidos.output_reshaper import OutputReshaper, Strategy

        reshaper = OutputReshaper()
        result = reshaper.reshape("short text")
        assert result.strategy_used == Strategy.PASSTHROUGH
        assert result.compressed_output == "short text"
        assert result.confidence == 1.0

    def test_shape_long_text_truncates(self):
        from eidos.output_reshaper import OutputReshaper, Strategy

        reshaper = OutputReshaper(
            token_threshold=10,
            truncate_threshold=20,
        )
        # Force smart truncate by exceeding truncate_threshold
        long_text = "\n".join([f"line {i}" for i in range(100)])
        result = reshaper.reshape(long_text)
        assert result.strategy_used == Strategy.SMART_TRUNCATE
        assert "[OUTPUT TRUNCATED" in result.compressed_output

    def test_force_strategy(self):
        from eidos.output_reshaper import OutputReshaper, Strategy

        reshaper = OutputReshaper()
        result = reshaper.reshape(
            "some text",
            force_strategy=Strategy.SMART_TRUNCATE,
        )
        assert result.strategy_used == Strategy.SMART_TRUNCATE

    def test_initialize_and_shutdown(self):
        from eidos.output_reshaper import OutputReshaper

        reshaper = OutputReshaper()
        assert reshaper.status == "ACTIVE"
        assert reshaper._initialized is True

        reshaper.shutdown()
        assert reshaper.status == "SHUTDOWN"
        assert reshaper._initialized is False

        reshaper.initialize()
        assert reshaper.status == "ACTIVE"
        assert reshaper._initialized is True

    def test_get_metrics_initial(self):
        from eidos.output_reshaper import OutputReshaper

        reshaper = OutputReshaper()
        metrics = reshaper.get_metrics()
        assert metrics["total_calls"] == 0
        assert metrics["passthrough_ratio"] == 0

    def test_metrics_after_reshape(self):
        from eidos.output_reshaper import OutputReshaper

        reshaper = OutputReshaper()
        reshaper.reshape("hello")
        metrics = reshaper.get_metrics()
        assert metrics["total_calls"] == 1
        assert metrics["passthrough_count"] == 1

    def test_reset_metrics(self):
        from eidos.output_reshaper import OutputReshaper

        reshaper = OutputReshaper()
        reshaper.reshape("hello")
        assert reshaper.get_metrics()["total_calls"] == 1

        reshaper.reset_metrics()
        assert reshaper.get_metrics()["total_calls"] == 0

    def test_update_thresholds(self):
        from eidos.output_reshaper import OutputReshaper

        reshaper = OutputReshaper()
        reshaper.update_thresholds(
            token_threshold=100,
            truncate_threshold=200,
            max_output_tokens=50,
            llm_timeout=1.0,
        )
        assert reshaper.token_threshold == 100
        assert reshaper.truncate_threshold == 200
        assert reshaper.max_output_tokens == 50
        assert reshaper.llm_timeout == 1.0

    def test_set_llm_provider(self):
        from eidos.output_reshaper import OutputReshaper

        reshaper = OutputReshaper()
        assert reshaper.llm_provider is None

        reshaper.set_llm_provider(lambda x: "compressed")
        assert reshaper.llm_provider is not None
        assert reshaper.llm_provider("test") == "compressed"

    def test_llm_compression_with_provider(self):
        from eidos.output_reshaper import OutputReshaper, Strategy

        def mock_provider(prompt: str) -> str:
            return "compressed result"

        reshaper = OutputReshaper(
            llm_provider=mock_provider,
            token_threshold=10,
            truncate_threshold=5000,
        )
        # Use enough words to exceed token_threshold but stay below truncate_threshold
        # ~2600 tokens estimated
        text = "hello world " * 1000
        result = reshaper.reshape(text)
        assert result.strategy_used == Strategy.LLM_COMPRESSION
        assert result.compressed_output == "compressed result"

    def test_llm_timeout_fallback(self):
        from eidos.output_reshaper import OutputReshaper

        def slow_provider(prompt: str) -> str:
            import time

            time.sleep(10)
            return "too late"

        reshaper = OutputReshaper(
            llm_provider=slow_provider,
            token_threshold=10,
            truncate_threshold=5000,
            llm_timeout=0.01,
        )
        text = "hello world " * 1000
        result = reshaper.reshape(text)
        # Should fallback to smart truncate on timeout
        assert result.metadata.get("fallback_reason") is not None

    def test_llm_fallback_when_no_provider(self):
        from eidos.output_reshaper import OutputReshaper, Strategy

        reshaper = OutputReshaper(
            llm_provider=None,
            token_threshold=10,
            truncate_threshold=5000,
        )
        # Use text with enough tokens to exceed token_threshold
        text = "hello world " * 2000
        result = reshaper.reshape(text)
        # No LLM provider available, should fallback to smart truncate
        assert result.strategy_used == Strategy.SMART_TRUNCATE

    def test_reshape_error_fallback(self):
        from eidos.output_reshaper import OutputReshaper, Strategy

        def broken_provider(prompt: str) -> str:
            raise RuntimeError("LLM crashed")

        reshaper = OutputReshaper(
            llm_provider=broken_provider,
            token_threshold=10,
            truncate_threshold=5000,
        )
        text = "hello world " * 2000
        result = reshaper.reshape(text)
        # Should fallback to smart truncate on error
        assert result.strategy_used == Strategy.SMART_TRUNCATE

    def test_reshape_output_helper(self):
        from eidos.output_reshaper import Strategy, reshape_output

        result = reshape_output("short text")
        assert result.strategy_used == Strategy.PASSTHROUGH

    def test_get_reshaper_singleton(self):
        from eidos.output_reshaper import get_reshaper

        r1 = get_reshaper()
        r2 = get_reshaper()
        assert r1 is r2

    def test_disable_metrics(self):
        from eidos.output_reshaper import OutputReshaper

        reshaper = OutputReshaper(enable_metrics=False)
        reshaper.reshape("hello")
        metrics = reshaper.get_metrics()
        assert metrics["total_calls"] == 0

    def test_smart_truncate_few_lines(self):
        from eidos.output_reshaper import OutputReshaper, Strategy

        reshaper = OutputReshaper(
            token_threshold=10,
            truncate_threshold=20,
        )
        # Many lines with enough words to exceed thresholds
        text = "\n".join([f"line {i} content" for i in range(5)])
        result = reshaper.reshape(text, force_strategy=Strategy.SMART_TRUNCATE)
        assert result.strategy_used == Strategy.SMART_TRUNCATE

    def test_smart_truncate_single_long_line(self):
        from eidos.output_reshaper import OutputReshaper, Strategy

        reshaper = OutputReshaper(
            token_threshold=10,
            truncate_threshold=20,
            max_output_tokens=1,
        )
        text = "x" * 200  # Single long line
        result = reshaper.reshape(text, force_strategy=Strategy.SMART_TRUNCATE)
        assert result.strategy_used == Strategy.SMART_TRUNCATE
