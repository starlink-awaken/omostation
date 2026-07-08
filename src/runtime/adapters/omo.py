"""Anti-corruption adapter for projects/omo (L2).

Re-exports the OMO governance symbols used by runtime scheduler.
"""

from omo.omo_gc import archive_resolved_debt_items
from omo.omo_state_schema import summarize_system_health_snapshot

__all__ = [
    "archive_resolved_debt_items",
    "summarize_system_health_snapshot",
]
