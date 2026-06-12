"""Shared pattern-match helper — deduplicates _match() across backends.

R74 LOW fix: 6 backends all had an identical _match() static method.
Extracted here so the next backend doesn't reinvent.

Pattern syntax:
  - "*"       : catch-all (matches everything)
  - "x:*"     : prefix (matches any event_type starting with "x:")
  - "x:y"     : exact (matches only "x:y")

Used by: eventbus / asyncio / croniter / messagebus / sse / ws /
persistent_bus. (Realtime is special: it uses task_id as a literal
key, not a pattern — see realtime.py:59 for the divergence note.)
"""
from __future__ import annotations


def match_pattern(pattern: str, event_type: str) -> bool:
    """Return True if event_type matches the given pattern."""
    if pattern == "*":
        return True
    if pattern.endswith("*"):
        return event_type.startswith(pattern[:-1])
    return pattern == event_type
