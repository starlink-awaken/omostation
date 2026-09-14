#!/usr/bin/env python3
"""Mail/Calendar Ingress Daemon — poll for new signals and dispatch LECP events.

Usage:
    python bin/daemon/mail_ingress.py [--interval 60] [--once]

This daemon:
1. Polls configured email/calendar sources at a configurable interval
2. Parses new emails (.eml) and calendar events (.ics)
3. Triages them into LECP v3.0 entities
4. Dispatches events to bos://spine/ingress (via Spine broker)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Add workspace root to path for spine package
WS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS_ROOT / "projects" / "spine" / "src"))

from spine.ingress.parsers.email_parser import EmailParser
from spine.ingress.parsers.calendar_parser import CalendarParser
from spine.ingress.triage.lecp_triage import LeCPTriage


def run_daemon(*, interval: int = 60, once: bool = False) -> None:
    """Run the ingress daemon."""
    triage = LeCPTriage()
    email_parser = EmailParser()
    calendar_parser = CalendarParser()

    print(f"[mail_ingress] Starting daemon (interval={interval}s, once={once})")
    print(f"[mail_riage] LECP triage ready")

    # Minimal loop: in production this would connect to IMAP/CalDAV
    # For MVP, we demonstrate the triage pipeline is functional
    iteration = 0
    while True:
        iteration += 1
        print(f"[mail_ingress] Poll iteration #{iteration}")

        # TODO: Replace with actual IMAP/CalDAV polling
        # For now, just verify the pipeline is importable and functional
        _verify_pipeline(triage, email_parser, calendar_parser)

        if once:
            print("[mail_ingress] Single poll complete, exiting")
            break

        time.sleep(interval)


def _verify_pipeline(triage: LeCPTriage, email_parser: EmailParser, calendar_parser: CalendarParser) -> None:
    """Verify the pipeline components are functional."""
    # Quick self-check: parse a minimal email
    test_eml = b"From: test@example.com\nTo: user@example.com\nSubject: Test\nMessage-ID: <test@example.com>\n\nTest body"
    result = email_parser.parse_bytes(test_eml)
    entity = triage.triage_email(parsed=result)
    assert entity["status"] == "triaged"
    print(f"  [pipeline] Email triage OK: domain={entity['domain']}, privacy={entity['privacy_level']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mail/Calendar Ingress Daemon")
    parser.add_argument("--interval", type=int, default=60, help="Polling interval in seconds")
    parser.add_argument("--once", action="store_true", help="Run single poll and exit")
    args = parser.parse_args()

    run_daemon(interval=args.interval, once=args.once)


if __name__ == "__main__":
    main()
