"""Path resolution for OMO state projections.

Canonical paths live in .omo/state/runtime/.
Legacy paths are supported for backward compatibility during migration.

Usage:
    from omo.paths import projection_path
    health = projection_path("health")  # -> .omo/state/runtime/health.yaml
"""
from __future__ import annotations

from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[4]
CANONICAL_ROOT = WORKSPACE / ".omo" / "state" / "runtime"

# Canonical name -> (filename, legacy_path_relative_to_workspace)
_PROJECTIONS: dict[str, tuple[str, str | None]] = {
    "health": ("health.yaml", ".omo/state/health.yaml"),
    "system_health": ("system_health.yaml", ".omo/state/system_health.yaml"),
    "governance_data": ("governance-data.json", ".omo/_control/governance-data.json"),
    "brief": ("brief.md", "BRIEF.md"),
}


def projection_path(name: str, *, canonical_only: bool = False) -> Path:
    """Return the path for a named projection.

    Args:
        name: Projection name (health, system_health, governance_data, brief).
        canonical_only: If True, always return canonical path even if legacy exists.

    Returns:
        Path to the projection file.
    """
    if name not in _PROJECTIONS:
        raise ValueError(f"Unknown projection: {name}. Known: {list(_PROJECTIONS)}")

    filename, legacy_rel = _PROJECTIONS[name]
    canonical = CANONICAL_ROOT / filename

    if canonical_only or not legacy_rel:
        return canonical

    legacy = WORKSPACE / legacy_rel

    # Prefer canonical if it exists
    if canonical.exists():
        return canonical

    # Fallback to legacy
    return legacy


def projection_paths() -> dict[str, dict[str, str | bool]]:
    """Return all projection paths and their status (for debugging/audit)."""
    result = {}
    for name, (filename, legacy_rel) in _PROJECTIONS.items():
        canonical = CANONICAL_ROOT / filename
        legacy = WORKSPACE / legacy_rel if legacy_rel else None
        result[name] = {
            "canonical": str(canonical),
            "canonical_exists": canonical.exists(),
            "legacy": str(legacy) if legacy else None,
            "legacy_exists": legacy.exists() if legacy else False,
            "active_path": str(projection_path(name)),
        }
    return result
