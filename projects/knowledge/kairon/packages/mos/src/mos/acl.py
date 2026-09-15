"""Scope ACL filters for Memory OS hits (Phase 5).

Rules (deny if mismatch when scope key is set and hit has the field):
- principal_id
- agent_profile
- scene_id

Hits without a field are treated as shared/public for that dimension.
"""

from __future__ import annotations

from typing import Any


def hit_allowed(hit: dict[str, Any], scope: dict[str, Any] | None) -> bool:
    if not scope:
        return True
    for key in ("principal_id", "agent_profile", "scene_id"):
        wanted = scope.get(key)
        if not wanted:
            continue
        have = hit.get(key)
        if have is not None and have != "" and have != wanted:
            return False
    return True


def filter_hits(hits: list[dict[str, Any]], scope: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [h for h in hits if hit_allowed(h, scope)]


def scope_from_kwargs(**kwargs: Any) -> dict[str, Any] | None:
    scope = {k: kwargs[k] for k in ("principal_id", "agent_profile", "scene_id") if kwargs.get(k)}
    return scope or None
