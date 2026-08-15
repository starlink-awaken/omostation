"""Adapter inventory high-water comparison. Count-only; no model names."""

from __future__ import annotations

# Cliff is a drop strictly greater than 30%: current < 70% of baseline.
INVENTORY_DROP_REMAINING_NUMERATOR = 7
INVENTORY_DROP_REMAINING_DENOMINATOR = 10
INVENTORY_DROP_CODE = "inventory_drop"


def is_inventory_cliff(baseline: int, current: int) -> bool:
    """Return True when a healthy inventory count has fallen more than 30%."""
    if baseline < 0 or current < 0:
        raise ValueError("inventory counts must be non-negative")
    if baseline == 0:
        return False
    return (
        current * INVENTORY_DROP_REMAINING_DENOMINATOR
        < baseline * INVENTORY_DROP_REMAINING_NUMERATOR
    )


def inventory_count(model_ids: object) -> int:
    """Count unique adapter list_models() IDs, including unloaded library entries."""
    unique: set[str] = set()
    for item in model_ids:  # type: ignore[union-attr]
        model_id = getattr(item, "id", item)
        if isinstance(model_id, str) and model_id:
            unique.add(model_id)
    return len(unique)


def inventory_drop_warning(
    *,
    node_id: str,
    backend_id: str,
    baseline: int,
    current: int,
) -> dict[str, object]:
    return {
        "code": INVENTORY_DROP_CODE,
        "node_id": node_id,
        "backend_id": backend_id,
        "baseline": baseline,
        "current": current,
    }
