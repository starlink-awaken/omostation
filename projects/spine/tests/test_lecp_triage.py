"""Tests for LECP triage."""

from spine.ingress.triage.lecp_triage import (
    DOMAIN_MIND,
    DOMAIN_WORK,
    PRIVACY_INTERNAL,
    PRIVACY_SECRET,
    LeCPTriage,
)


def test_work_email_triage():
    triage = LeCPTriage()
    raw = b"From: bot@github.com\nTo: user@example.com\nSubject: PR\nMessage-id: <pr@github.com>\n\nPlease review"
    entity = triage.triage_email(raw=raw)

    assert entity["domain"] == DOMAIN_WORK
    assert entity["privacy_level"] == PRIVACY_INTERNAL
    assert entity["source"] == "email"


def test_personal_email_triage():
    triage = LeCPTriage()
    raw = b"From: friend@personal.com\nTo: user@example.com\nSubject: Hi\nMessage-id: <hi@personal.com>\n\nHello"
    entity = triage.triage_email(raw=raw)

    assert entity["domain"] == DOMAIN_MIND
    assert entity["privacy_level"] == PRIVACY_SECRET


def test_multi_attendee_calendar_triage():
    triage = LeCPTriage()
    raw = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:meeting-001@test.com
SUMMARY:Team Meeting
DTSTART:20260912T090000Z
DTEND:20260912T100000Z
ATTENDEE:person1@test.com
ATTENDEE:person2@test.com
END:VEVENT
END:VCALENDAR
"""
    entities = triage.triage_calendar(raw=raw)
    assert len(entities) == 1
    assert entities[0]["domain"] == DOMAIN_WORK
    assert entities[0]["privacy_level"] == PRIVACY_INTERNAL
