#!/usr/bin/env python3
"""HITL Proposal Notification — multi-channel principal notification stub.

For HITL v1.1 (BET-Y1Q4-HITL-02). Sends principal notifications when a
proposal is created. Channels are opt-in via config and configured in
.omo/_truth/registry/notification-config.yaml.

This is a STUB implementation:
- "log" channel: always available, writes to .omo/_knowledge/hitl-proposals/.notifications.log
- "stdout" channel: always available, prints to console
- "slack" / "email" channels: require explicit config (URL/webhook) to enable;
  without config, logs a warning and marks channel as "configured: false"

The intent is to provide the integration point + observability without
shipping a production-ready Slack/email client (which would require
per-environment secrets management).

Backward-compat: existing v1.0 proposals without notified_at are
treated as "not notified" (notified_at=None). Calling notify on them
is safe and updates the field.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

PROPOSALS_DIR = Path(os.environ.get("HITL_PROPOSALS_DIR", ".omo/_knowledge/hitl-proposals"))
NOTIFICATION_LOG = PROPOSALS_DIR / ".notifications.log"
DEFAULT_CONFIG_PATH = Path(".omo/_truth/registry/notification-config.yaml")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_proposal(proposal_id: str) -> dict | None:
    """Find proposal by ID (prefix match supported)."""
    if not PROPOSALS_DIR.exists():
        return None
    exact = PROPOSALS_DIR / f"{proposal_id}.yaml"
    if exact.exists():
        with open(exact) as f:
            return yaml.safe_load(f) or {}
    matches = list(PROPOSALS_DIR.glob(f"{proposal_id}*.yaml"))
    if len(matches) == 1:
        with open(matches[0]) as f:
            return yaml.safe_load(f) or {}
    return None


def _atomic_write_proposal(proposal: dict, path: Path) -> None:
    """Write proposal back atomically."""
    import tempfile
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(proposal, f, default_flow_style=False, sort_keys=False)
        os.rename(tmp, str(path))
    except BaseException:
        os.unlink(tmp)
        raise


def _save_notification(proposal: dict, path: Path, channels: list[str]) -> None:
    """Update proposal's notified_at and notification_channels fields."""
    proposal["notified_at"] = _now()
    proposal["notification_channels"] = list(set(proposal.get("notification_channels", []) + channels))
    _atomic_write_proposal(proposal, path)


def _log_to_file(proposal_id: str, channels: list[str], status: str) -> None:
    """Append notification event to log file."""
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{_now()}\t{proposal_id}\t{','.join(channels)}\t{status}\n"
    with open(NOTIFICATION_LOG, "a") as f:
        f.write(line)


def notify_log_channel(proposal_id: str, proposal: dict) -> bool:
    """Log channel: always succeeds, writes to log file."""
    try:
        _log_to_file(proposal_id, ["log"], "ok")
        return True
    except OSError:
        return False


def notify_stdout_channel(proposal_id: str, proposal: dict) -> bool:
    """Stdout channel: always succeeds, prints to console."""
    title = proposal.get("title", "(no title)")
    bet_id = proposal.get("bet_id", "?")
    print(f"[HITL notify] {proposal_id} bet={bet_id} title={title}", file=sys.stderr)
    return True


def notify_slack_channel(proposal_id: str, proposal: dict, config: dict) -> bool:
    """Slack channel: requires webhook URL in config. Without config, no-op + warning."""
    webhook = config.get("slack", {}).get("webhook_url")
    if not webhook:
        print(f"[HITL notify] slack channel not configured for {proposal_id} (skipped)", file=sys.stderr)
        return False
    # STUB: real implementation would POST to webhook
    print(f"[HITL notify] slack stub: would POST to {webhook[:30]}... for {proposal_id}", file=sys.stderr)
    return True


def notify_email_channel(proposal_id: str, proposal: dict, config: dict) -> bool:
    """Email channel: requires SMTP config. Without config, no-op + warning."""
    smtp = config.get("email", {}).get("smtp_server")
    if not smtp:
        print(f"[HITL notify] email channel not configured for {proposal_id} (skipped)", file=sys.stderr)
        return False
    # STUB: real implementation would send email
    print(f"[HITL notify] email stub: would send via {smtp} for {proposal_id}", file=sys.stderr)
    return True


def load_config() -> dict:
    """Load notification config (returns empty dict if not present)."""
    if not DEFAULT_CONFIG_PATH.exists():
        return {}
    try:
        with open(DEFAULT_CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return {}


def cmd_notify(args: argparse.Namespace) -> int:
    proposal = _load_proposal(args.proposal_id)
    if proposal is None:
        print(f"Proposal not found: {args.proposal_id}", file=sys.stderr)
        return 1

    config = load_config()
    channels = args.channels.split(",") if args.channels else ["log", "stdout"]

    results: dict[str, bool] = {}
    for ch in channels:
        if ch == "log":
            results[ch] = notify_log_channel(args.proposal_id, proposal)
        elif ch == "stdout":
            results[ch] = notify_stdout_channel(args.proposal_id, proposal)
        elif ch == "slack":
            results[ch] = notify_slack_channel(args.proposal_id, proposal, config)
        elif ch == "email":
            results[ch] = notify_email_channel(args.proposal_id, proposal, config)
        else:
            print(f"Unknown channel: {ch}", file=sys.stderr)
            results[ch] = False

    # Update proposal
    path = PROPOSALS_DIR / f"{proposal['proposal_id']}.yaml"
    successful = [ch for ch, ok in results.items() if ok]
    if successful:
        _save_notification(proposal, path, successful)

    print(f"notify result: {results}")
    return 0 if any(results.values()) else 1


def cmd_status(args: argparse.Namespace) -> int:
    """Show notification log (audit trail)."""
    if not NOTIFICATION_LOG.exists():
        print("No notifications yet")
        return 0
    with open(NOTIFICATION_LOG) as f:
        print(f.read())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hitl-notify",
        description="HITL proposal notification (v1.1)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_notify = sub.add_parser("notify", help="Notify principal of pending proposal")
    p_notify.add_argument("proposal_id")
    p_notify.add_argument("--channels", default="log,stdout",
                          help="Comma-separated channels: log,stdout,slack,email (default: log,stdout)")
    p_notify.set_defaults(func=cmd_notify)

    p_status = sub.add_parser("status", help="Show notification audit log")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
