"""Integration test pipeline for spine ingress.

Run with: uv run python -m spine.ingress.test_pipeline
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from spine.ingress.parsers.email_parser import EmailParser
from spine.ingress.parsers.calendar_parser import CalendarParser
from spine.ingress.triage.lecp_triage import LeCPTriage


SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "spine_ingress" / "samples"


def _build_sample_eml() -> bytes:
    """Build a sample .eml for testing without external files."""
    return b"""From: sender@github.com
To: user@example.com
Subject: PR Review Request: Fix ingress pipeline
Date: Mon, 12 Sep 2026 10:00:00 +0000
Message-ID: <test-ingress-001@github.com>
Content-Type: text/plain; charset="utf-8"

Please review the attached PR for the ingress pipeline fix.
"""


def _build_sample_ics() -> bytes:
    """Build a sample .ics for testing without external files."""
    return b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:test-event-001@example.com
SUMMARY:Team Standup
DTSTART:20260912T090000Z
DTEND:20260912T093000Z
LOCATION:Zoom
ATTENDEE:person1@example.com
ATTENDEE:person2@example.com
DESCRIPTION:Daily team sync meeting
END:VEVENT
END:VCALENDAR
"""


def test_email_parser() -> None:
    """Test email parsing."""
    parser = EmailParser()
    result = parser.parse_bytes(_build_sample_eml())

    assert result["subject"] == "PR Review Request: Fix ingress pipeline"
    assert result["sender"] == "sender@github.com"
    assert result["sender_domain"] == "github.com"
    assert result["is_work_domain"] is True
    assert result["entity_id"].startswith("evt-20260912-")
    print("  [PASS] email_parser: basic parsing")


def test_email_triage() -> None:
    """Test email triage to LECP."""
    triage = LeCPTriage()
    entity = triage.triage_email(raw=_build_sample_eml())

    assert entity["domain"] == "p0_work"
    assert entity["privacy_level"] == "internal"
    assert entity["status"] == "triaged"
    assert entity["source"] == "email"
    assert "payload" in entity
    print("  [PASS] email_triage: work domain classification")


def test_calendar_parser() -> None:
    """Test calendar parsing."""
    parser = CalendarParser()
    events = parser.parse_bytes(_build_sample_ics())

    assert len(events) == 1
    event = events[0]
    assert event["summary"] == "Team Standup"
    assert event["is_multi_attendee"] is True
    assert event["attendee_count"] == 2
    print("  [PASS] calendar_parser: basic parsing")


def test_calendar_triage() -> None:
    """Test calendar triage to LECP."""
    triage = LeCPTriage()
    entities = triage.triage_calendar(raw=_build_sample_ics())

    assert len(entities) == 1
    entity = entities[0]
    assert entity["domain"] == "p0_work"
    assert entity["privacy_level"] == "internal"
    assert entity["status"] == "triaged"
    assert entity["source"] == "calendar"
    print("  [PASS] calendar_triage: multi-attendee work classification")


def test_personal_email_triage() -> None:
    """Test personal email triage."""
    raw = b"""From: friend@personal.com
To: user@example.com
Subject: Dinner this weekend?
Date: Mon, 12 Sep 2026 10:00:00 +0000
Message-ID: <test-personal-001@personal.com>
Content-Type: text/plain; charset="utf-8"

Hey, want to grab dinner this weekend?
"""
    triage = LeCPTriage()
    entity = triage.triage_email(raw=raw)

    assert entity["domain"] == "p3_mind"
    assert entity["privacy_level"] == "secret"
    print("  [PASS] personal_email_triage: mind domain classification")


def test_health_calendar_triage() -> None:
    """Test health-related calendar event triage."""
    raw = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:test-health-001@example.com
SUMMARY:Annual Physical Exam
DTSTART:20260915T140000Z
DTEND:20260915T150000Z
LOCATION:City Hospital
DESCRIPTION:Yearly health checkup with doctor
END:VEVENT
END:VCALENDAR
"""
    triage = LeCPTriage()
    entities = triage.triage_calendar(raw=raw)

    assert len(entities) == 1
    entity = entities[0]
    assert entity["domain"] == "p1_health"
    assert entity["privacy_level"] == "secret"
    print("  [PASS] health_calendar_triage: health domain classification")


def run_all() -> int:
    """Run all tests. Returns exit code."""
    tests = [
        test_email_parser,
        test_email_triage,
        test_calendar_parser,
        test_calendar_triage,
        test_personal_email_triage,
        test_health_calendar_triage,
    ]

    passed = 0
    failed = 0

    print("Spine Ingress Test Pipeline")
    print("=" * 40)

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as exc:
            failed += 1
            print(f"  [FAIL] {test_fn.__name__}: {exc}")
            traceback.print_exc()

    print("=" * 40)
    print(f"Results: {passed} passed, {failed} failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all())
