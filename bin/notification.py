#!/usr/bin/env python3
"""HITL Proposal Notification — multi-channel principal notification stub.

For HITL v1.1 (BET-Y1Q4-HITL-02). Sends principal notifications when a
proposal is created. Channels are opt-in via config and configured in
.omo/_truth/registry/notification-config.yaml.

This is a STUB implementation:
- "log" channel: writes to $HITL_PROPOSALS_DIR/.notifications.log; the variable
  must be declared (absolute path) — without it every write face is refused
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

# ADR-0456 第四类根（BET-Y2Q4-T10-288, spec §5 AC-02）—— 治理 SSOT 配置的**读**落点必须跟随
# 被加载的那份检出。修前 `Path(".omo/_truth/registry/notification-config.yaml")` 随进程 CWD 解析：
# 与同文件的提案面同形，只是它是读面。
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from repo_root import code_root  # noqa: E402

PROPOSALS_DIR_ENV = "HITL_PROPOSALS_DIR"
CONFIG_RELATIVE = ".omo/_truth/registry/notification-config.yaml"

_UNANCHORED_WRITE = (
    f"{PROPOSALS_DIR_ENV} 未声明：默认值 .omo/_knowledge/hitl-proposals 是仓内相对锚，"
    "落点随进程 CWD（ADR-0456 第四类根 / BET-Y2Q4-T10-288）。"
    "写 HITL 提案面需要显式声明该变量为绝对路径。"
)


def _anchored_proposals_dir() -> Path | None:
    """提案面的**写**落点：只有显式声明的 env 才算锚定，未声明即拒写而不是跟着 CWD 走。"""
    declared = os.environ.get(PROPOSALS_DIR_ENV)
    return Path(declared) if declared else None


def _config_path() -> Path:
    """通知配置的**读**落点：在调用时刻经 `code_root()` 解析，不在 import 时冻住。"""
    return code_root() / CONFIG_RELATIVE


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_proposal(proposal_id: str, proposals_dir: Path) -> dict | None:
    """Find proposal by ID (prefix match supported)."""
    if not proposals_dir.exists():
        return None
    exact = proposals_dir / f"{proposal_id}.yaml"
    if exact.exists():
        with open(exact) as f:
            return yaml.safe_load(f) or {}
    matches = list(proposals_dir.glob(f"{proposal_id}*.yaml"))
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


def _log_to_file(proposals_dir: Path, proposal_id: str, channels: list[str], status: str) -> None:
    """Append notification event to log file."""
    proposals_dir.mkdir(parents=True, exist_ok=True)
    line = f"{_now()}\t{proposal_id}\t{','.join(channels)}\t{status}\n"
    with open(proposals_dir / ".notifications.log", "a") as f:
        f.write(line)


def notify_log_channel(proposal_id: str, proposal: dict, proposals_dir: Path) -> bool:
    """Log channel: always succeeds, writes to log file."""
    try:
        _log_to_file(proposals_dir, proposal_id, ["log"], "ok")
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
    config_path = _config_path()
    if not config_path.exists():
        return {}
    try:
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return {}


def cmd_notify(args: argparse.Namespace) -> int:
    proposals_dir = _anchored_proposals_dir()
    if proposals_dir is None:
        print(_UNANCHORED_WRITE, file=sys.stderr)
        return 1
    proposal = _load_proposal(args.proposal_id, proposals_dir)
    if proposal is None:
        print(f"Proposal not found: {args.proposal_id}", file=sys.stderr)
        return 1

    config = load_config()
    channels = args.channels.split(",") if args.channels else ["log", "stdout"]

    results: dict[str, bool] = {}
    for ch in channels:
        if ch == "log":
            results[ch] = notify_log_channel(args.proposal_id, proposal, proposals_dir)
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
    path = proposals_dir / f"{proposal['proposal_id']}.yaml"
    successful = [ch for ch, ok in results.items() if ok]
    if successful:
        _save_notification(proposal, path, successful)

    print(f"notify result: {results}")
    return 0 if any(results.values()) else 1


def cmd_status(args: argparse.Namespace) -> int:
    """Show notification log (audit trail)."""
    proposals_dir = _anchored_proposals_dir()
    if proposals_dir is None:
        print(_UNANCHORED_WRITE, file=sys.stderr)
        return 1
    log_path = proposals_dir / ".notifications.log"
    if not log_path.exists():
        print("No notifications yet")
        return 0
    with open(log_path) as f:
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
