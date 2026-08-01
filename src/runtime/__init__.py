"""eCOS Runtime Layer — L1 infrastructure management."""

__version__ = "0.1.0"

from .board_engine import (
    BoardConsensusEngine,
    BoardMode,
    PersonaRole,
    PersonaRouter,
    dispatch_board_command,
)

__all__ = [
    "BoardConsensusEngine",
    "BoardMode",
    "PersonaRole",
    "PersonaRouter",
    "dispatch_board_command",
]

