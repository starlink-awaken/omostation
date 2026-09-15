"""Operation Levels enforcement — L0/L1/L2/L3 deny paths for all MCP tools.

Usage:
    from kos.operation_level import deny_unconfirmed_l2, deny_unconfirmed_l3, require_level

    # L2 deny
    if not confirmed:
        return deny_unconfirmed_l2("full reindex")

    # L3 deny
    if not confirmed or cool_down_hours < 24:
        return deny_unconfirmed_l3("db_vacuum", cool_down_hours)

    # Decorator-style check
    require_level("delete_page", level=2, confirmed=confirmed)

Integration notes:
    - KOS MCP (server.py): Uses _deny_unconfirmed_l2/_deny_unconfirmed_l3 inline
      (search_knowledge=L0, run_indexer/incremental=L1, run_indexer/full=L2,
      db_vacuum=L3 with 24h cooldown)
    - gbrain (core/operations.ts:1016-1052): delete_page L2 deny path checks
      _confirmed param inline, throws OperationError('permission_denied')
      when unconfirmed. No block-level override needed — the op-level gate
      is sufficient (gbrain MCP tools are per-op, not block/suite).
    - All L2 operations require _confirmed=true in the caller params.
    - All L3 operations require _confirmed=true + cool_down_hours >= 24.
"""

from __future__ import annotations

from typing import Any


def deny_unconfirmed_l2(action: str) -> dict[str, Any]:
    """L2 deny path: requires _confirmed=true."""
    return {
        "status": "denied",
        "error": f"L2 operation requires explicit confirmation before {action}",
        "operation_level": "L2",
        "required_confirmation": True,
    }


def deny_unconfirmed_l3(action: str, cool_down_hours: int = 0) -> dict[str, Any]:
    """L3 deny path: requires _confirmed=true AND _cool_down_hours >= 24."""
    return {
        "status": "denied",
        "error": (f"L3 operation requires _confirmed=true AND _cool_down_hours>=24 before {action}"),
        "operation_level": "L3",
        "required_confirmation": True,
        "required_cooldown_hours": 24,
        "actual_cooldown_hours": cool_down_hours,
    }


def require_level(tool: str, level: int, confirmed: bool = False, cool_down_hours: int = 0) -> dict[str, Any] | None:
    """Check operation level and return deny dict if blocked; None if allowed.

    Args:
        tool: Tool name for error message.
        level: Required operation level (0-3).
        confirmed: Whether human confirmed.
        cool_down_hours: Hours since last similar operation (L3 only).

    Returns:
        Deny response dict if blocked, None if allowed.
    """
    if level == 0:
        return None  # L0 — always allowed
    if level == 1:
        return None  # L1 — always allowed (audit required but not enforced here)
    if level == 2 and not confirmed:
        return deny_unconfirmed_l2(tool)
    if level == 3 and (not confirmed or cool_down_hours < 24):
        return deny_unconfirmed_l3(tool, cool_down_hours)
    return None
