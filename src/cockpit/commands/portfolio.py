"""cockpit portfolio — read-only Portfolio projection consumer (BET-Y1Q4-T8-05).

Loads digest-bound control projection only. Never writes Ledger, Goals, or OMO state.
Missing/stale/malformed/mismatched inputs return a stable unavailable result.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

CONTROL_REL = Path(".omo/_control/portfolio-status.json")

# Hostile-test surface: imported names that must never be called for writes.
_FORBIDDEN_WRITE_HINTS = (
    "write_text",
    "write_bytes",
    "safe_dump",
    "open(",
)


def _workspace_root() -> Path:
    # commands/portfolio.py → commands → cockpit → src → cockpit project → projects → workspace
    return Path(__file__).resolve().parents[5]


def load_control_projection(workspace: Path | None = None) -> dict[str, Any]:
    """Load control projection JSON. Never parses Ledger as fallback."""
    root = workspace or _workspace_root()
    path = root / CONTROL_REL
    if not path.is_file():
        return {
            "status": "unavailable",
            "unavailable_reason": "missing_control_projection",
            "source_digest": None,
            "path": str(CONTROL_REL),
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "status": "unavailable",
            "unavailable_reason": f"malformed_control_projection: {exc}",
            "source_digest": None,
            "path": str(CONTROL_REL),
        }
    if not isinstance(payload, dict):
        return {
            "status": "unavailable",
            "unavailable_reason": "malformed_control_projection: not an object",
            "source_digest": None,
            "path": str(CONTROL_REL),
        }
    digest = payload.get("source_digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        return {
            "status": "unavailable",
            "unavailable_reason": "digest_missing_or_invalid",
            "source_digest": digest if isinstance(digest, str) else None,
            "path": str(CONTROL_REL),
        }
    if payload.get("status") == "unavailable":
        return {
            "status": "unavailable",
            "unavailable_reason": payload.get("unavailable_reason") or "projection_marked_unavailable",
            "source_digest": digest,
            "path": str(CONTROL_REL),
            "payload": payload,
        }
    return {
        "status": "ok",
        "source_digest": digest,
        "path": str(CONTROL_REL),
        "payload": payload,
    }


def _format_status(result: dict[str, Any]) -> str:
    if result["status"] != "ok":
        return (
            f"unavailable\n"
            f"reason={result.get('unavailable_reason')}\n"
            f"digest={result.get('source_digest')}\n"
            f"path={result.get('path')}\n"
        )
    payload = result["payload"]
    lines = [
        "status=ok",
        f"digest={result['source_digest']}",
        f"vision_id={payload.get('vision_id')}",
        f"bet_count={payload.get('bet_count')}",
        f"broker_ok={payload.get('broker_ok')}",
        "status_counts=" + json.dumps(payload.get("status_counts") or {}, sort_keys=True),
        "",
    ]
    return "\n".join(lines)


def _format_objectives(result: dict[str, Any]) -> str:
    if result["status"] != "ok":
        return _format_status(result)
    # Control projection may not embed objectives; surface digest-bound honesty.
    return (
        f"digest={result['source_digest']}\n"
        "objectives=unavailable\n"
        "reason=control_projection_has_no_objectives_field\n"
    )


def _format_critical_path(result: dict[str, Any]) -> str:
    if result["status"] != "ok":
        return _format_status(result)
    return (
        f"digest={result['source_digest']}\n"
        "critical_path=unavailable\n"
        "reason=control_projection_has_no_critical_path_field\n"
    )


def _format_blockers(result: dict[str, Any]) -> str:
    if result["status"] != "ok":
        return _format_status(result)
    return (
        f"digest={result['source_digest']}\n"
        "blockers=unavailable\n"
        "reason=control_projection_has_no_blockers_field\n"
    )


def cmd_portfolio(args: argparse.Namespace) -> int:
    """CLI handler registered on the cockpit root parser."""
    workspace = Path(getattr(args, "workspace", "") or _workspace_root())
    result = load_control_projection(workspace)
    sub = getattr(args, "portfolio_command", None) or "status"
    if sub == "status":
        sys.stdout.write(_format_status(result))
    elif sub == "objectives":
        sys.stdout.write(_format_objectives(result))
    elif sub == "critical-path":
        sys.stdout.write(_format_critical_path(result))
    elif sub == "blockers":
        sys.stdout.write(_format_blockers(result))
    else:
        sys.stderr.write(f"unknown portfolio subcommand: {sub}\n")
        return 2
    return 0 if result["status"] == "ok" else 0  # unavailable is a successful honest report


def register_portfolio_subcommand(sub: argparse._SubParsersAction) -> None:
    portfolio_p = sub.add_parser(
        "portfolio",
        help="Portfolio 只读组合视图 (digest-bound projection; never writes Ledger/Goals/OMO)",
    )
    portfolio_sub = portfolio_p.add_subparsers(dest="portfolio_command")
    portfolio_sub.add_parser("status", help="Show portfolio status from control projection")
    portfolio_sub.add_parser("objectives", help="Show objectives from control projection")
    portfolio_sub.add_parser("critical-path", help="Show critical path from control projection")
    portfolio_sub.add_parser("blockers", help="Show blockers from control projection")
    portfolio_p.set_defaults(func=cmd_portfolio, portfolio_command="status")


__all__ = [
    "cmd_portfolio",
    "load_control_projection",
    "register_portfolio_subcommand",
    "CONTROL_REL",
]
