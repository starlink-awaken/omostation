"""Anti-corruption adapter for projects/l4-kernel (L4).

Re-exports the l4-kernel symbols used by cockpit MCP server and health command.
"""

from l4_kernel import DomainRegistry
from l4_kernel.config_loader import load_overrides_from_config
from l4_kernel.health import DomainHealth
from l4_kernel.kems import CardsPlane, KemsPlane

__all__ = [
    "CardsPlane",
    "DomainHealth",
    "DomainRegistry",
    "KemsPlane",
    "load_overrides_from_config",
]
