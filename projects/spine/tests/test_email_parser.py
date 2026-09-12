"""Tests for email parser."""

from spine.ingress.parsers.email_parser import EmailParser


def test_parse_basic_eml():
    raw = b"From: sender@github.com\nTo: user@example.com\nSubject: Test\nDate: Mon, 12 Sep 2026 10:00:00 +0000\nMessage-ID: <test@github.com>\n\nBody text"
    parser = EmailParser()
    result = parser.parse_bytes(raw)

    assert result["sender"] == "sender@github.com"
    assert result["sender_domain"] == "github.com"
    assert result["is_work_domain"] is True
    assert result["entity_id"].startswith("evt-")


def test_parse_personal_eml():
    raw = b"From: friend@personal.com\nTo: user@example.com\nSubject: Hi\nMessage-ID: <test@personal.com>\n\nHello"
    parser = EmailParser()
    result = parser.parse_bytes(raw)

    assert result["is_work_domain"] is False
    assert result["sender_domain"] == "personal.com"


def test_entity_id_format():
    raw = b"From: a@b.com\nTo: c@d.com\nSubject: Test\nMessage-ID: <unique-id@b.com>\n\nBody"
    parser = EmailParser()
    result = parser.parse_bytes(raw)

    assert result["entity_id"].startswith("evt-")
    parts = result["entity_id"].split("-")
    assert len(parts) == 3
    assert len(parts[1]) == 8  # YYYYMMDD
