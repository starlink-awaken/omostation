"""Basic unit tests for cockpit helper functions."""

from __future__ import annotations

import time

from cockpit.commands.base import (
    _derive_import_title,
    _fmt_time,
    _looks_like_url,
    _normalize_import_content,
    _panel,
    _short,
    _status_services,
    _strip_html,
    _strip_thinking,
    _topic_text,
)


def test_short_truncates_long_text():
    result = _short("x" * 200, limit=10)
    assert len(result) == 10  # limit chars + …
    assert result.endswith("…")


def test_short_keeps_short_text():
    result = _short("hello world")
    assert result == "hello world"


def test_short_strips_whitespace():
    result = _short("  hello  ")
    assert result == "hello"


def test_short_empty():
    assert _short(None) == ""
    assert _short("") == ""
    assert _short("   ") == ""


def test_topic_text_joins_list():
    assert _topic_text(["hello", "world"]) == "hello world"


def test_topic_text_passes_string():
    assert _topic_text("hello") == "hello"


def test_looks_like_url_http():
    assert _looks_like_url("http://example.com") is True


def test_looks_like_url_https():
    assert _looks_like_url("https://example.com") is True


def test_looks_like_url_other():
    assert _looks_like_url("ftp://example.com") is False
    assert _looks_like_url("not a url") is False
    assert _looks_like_url("") is False


def test_strip_html_removes_tags():
    assert _strip_html("<p>hello</p>") == "hello"


def test_strip_html_removes_script():
    assert _strip_html("<script>alert(1)</script>text") == "text"


def test_strip_html_removes_style():
    assert _strip_html("<style>.cls{}</style>text") == "text"


def test_strip_html_unescapes():
    assert _strip_html("&amp;") == "&"


def test_fmt_time():
    ts = time.mktime(time.strptime("2025-01-15 10:30:00", "%Y-%m-%d %H:%M:%S"))
    result = _fmt_time(ts)
    assert "2025" in result
    assert "01" in result or "1" in result


def test_panel_returns_panel():
    p = _panel("hello")
    assert "hello" in str(p.renderable)


def test_panel_with_title():
    p = _panel("hello", title="Title")
    assert p.title is not None


def test_derive_import_title_from_html_title():
    html = "<html><head><title>My Page</title></head><body></body></html>"
    result = _derive_import_title("http://example.com", html)
    assert "My Page" in result


def test_derive_import_title_from_markdown():
    md = "# Hello World\nSome text"
    result = _derive_import_title("file.md", md)
    assert "Hello World" in result


def test_derive_import_title_falls_back_to_first_line():
    text = "just plain text\nno title here"
    result = _derive_import_title("http://example.com/page", text)
    assert "just plain text" in result


def test_derive_import_title_falls_back_to_filename():
    text = "   "
    result = _derive_import_title("some/path/file.txt", text)
    assert result == "file"


def test_normalize_import_content_extracts_html():
    title, body = _normalize_import_content("http://x.com", "<html><body><p>Hello</p></body></html>")
    assert "Hello" in body
    assert title


def test_normalize_import_content_plain_text():
    title, body = _normalize_import_content("note.txt", "Just some text")
    assert body == "Just some text"
    assert title


def test_strip_thinking_no_tags():
    result = _strip_thinking("hello world")
    assert result == "hello world"


def test_strip_thinking_with_closed_think():
    result = _strip_thinking("<think>思考过程</think>最终答案")
    assert "思考过程" not in result
    assert "最终答案" in result


def test_strip_thinking_empty():
    assert _strip_thinking("") == ""
    assert _strip_thinking("   ") == ""


def test_status_services_returns_list():
    services = _status_services()
    assert isinstance(services, list)
    assert len(services) > 0
    assert all(len(svc) == 5 for svc in services)
    assert any("Agora" in svc[0] for svc in services)
