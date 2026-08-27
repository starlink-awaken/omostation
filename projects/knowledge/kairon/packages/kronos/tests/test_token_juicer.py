"""Tests for TokenJuicer — HTML/text token compression."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from kronos.compressors.token_juicer import TokenJuicer


class TestHTMLStripping:
    def test_strips_html_tags(self):
        tj = TokenJuicer()
        result = tj.compress("<html><body><p>Hello</p></body></html>")
        assert "Hello" in result["text"]
        assert "<html>" not in result["text"]

    def test_compression_ratio_with_html(self):
        tj = TokenJuicer()
        html = "<html>" + " ".join(f"<p>{i}</p>" for i in range(100)) + "</html>"
        result = tj.compress(html)
        assert result["saved_pct"] > 0
        assert result["compressed_len"] < result["original_len"]

    def test_preserves_non_html_content(self):
        tj = TokenJuicer()
        result = tj.compress("Hello world, this is plain text.")
        assert "Hello world" in result["text"]


class TestWhitespaceNormalization:
    def test_normalizes_multiple_spaces(self):
        tj = TokenJuicer()
        result = tj.compress("Hello    world")
        assert "  " not in result["text"]
        assert result["text"] == "Hello world"

    def test_strips_leading_trailing_whitespace(self):
        tj = TokenJuicer()
        result = tj.compress("   Hello world   ")
        assert result["text"] == "Hello world"

    def test_normalizes_newlines_to_spaces(self):
        tj = TokenJuicer()
        result = tj.compress("Hello\n\n\nworld")
        assert "\n" not in result["text"]


class TestCJKPreservation:
    def test_preserves_chinese_characters(self):
        tj = TokenJuicer()
        result = tj.compress("<p>你好世界</p>")
        assert "你好世界" in result["text"]

    def test_preserves_japanese(self):
        tj = TokenJuicer()
        result = tj.compress("<div>こんにちは世界</div>")
        assert "こんにちは世界" in result["text"]

    def test_preserves_korean(self):
        tj = TokenJuicer()
        result = tj.compress("<span>안녕하세요</span>")
        assert "안녕하세요" in result["text"]

    def test_mixed_cjk_and_latin(self):
        tj = TokenJuicer()
        result = tj.compress("<p>Hello 你好 こんにちは</p>")
        assert "Hello 你好 こんにちは" in result["text"]


class TestURLTrackingParamStripping:
    def test_strips_utm_source(self):
        tj = TokenJuicer()
        result = tj.compress("click https://example.com/page?utm_source=google")
        assert "utm_source" not in result["text"]

    def test_strips_multiple_utm_params(self):
        tj = TokenJuicer()
        text = "visit https://example.com/page?utm_source=google&utm_medium=cpc&utm_campaign=spring"
        result = tj.compress(text)
        assert "utm_" not in result["text"]

    def test_preserves_non_utm_params(self):
        tj = TokenJuicer()
        text = "check https://example.com/page?id=123&ref=abc"
        result = tj.compress(text)
        # Non-tracking params are inside the URL, which gets replaced by [URL]
        assert "[URL]" in result["text"]

    def test_urls_replaced_with_placeholder(self):
        tj = TokenJuicer()
        result = tj.compress("visit https://example.com/some-page")
        assert "[URL]" in result["text"]
        assert "https://" not in result["text"]


class TestDedup:
    def test_same_text_detected(self):
        tj = TokenJuicer()
        assert tj.dedup_check("hello world") is True
        assert tj.dedup_check("hello world") is False

    def test_different_text_unique(self):
        tj = TokenJuicer()
        assert tj.dedup_check("first") is True
        assert tj.dedup_check("second") is True

    def test_empty_text_detectable(self):
        tj = TokenJuicer()
        assert tj.dedup_check("") is True
        assert tj.dedup_check("") is False

    def test_dedup_stats(self):
        tj = TokenJuicer()
        assert tj.dedup_stats()["total_unique"] == 0
        tj.dedup_check("a")
        tj.dedup_check("b")
        assert tj.dedup_stats()["total_unique"] == 2

    def test_dedup_after_compress(self):
        tj = TokenJuicer()
        html = "<p>same content</p>"
        r1 = tj.compress(html)
        r2 = tj.compress(html)
        assert r1["text"] == r2["text"]
        assert tj.dedup_check(r1["text"]) is True
        assert tj.dedup_check(r2["text"]) is False


class TestReturnShape:
    def test_compress_returns_expected_keys(self):
        tj = TokenJuicer()
        result = tj.compress("hello")
        assert "original_len" in result
        assert "compressed_len" in result
        assert "saved_pct" in result
        assert "text" in result

    def test_empty_string_compression(self):
        tj = TokenJuicer()
        result = tj.compress("")
        assert result["original_len"] == 0
        assert result["compressed_len"] == 0
        # 100% saved because there's nothing to compress

    def test_no_html_returns_slightly_smaller_or_equal(self):
        tj = TokenJuicer()
        result = tj.compress("hello world  ")
        assert result["compressed_len"] <= result["original_len"]
