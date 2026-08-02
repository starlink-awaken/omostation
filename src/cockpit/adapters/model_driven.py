"""Anti-corruption adapter for projects/model-driven (M0).

Re-exports the model-driven lifecycle / toolchain symbols used by cockpit
commands.
"""

from model_driven.lifecycle.pipeline import (  # type: ignore[import-not-found]
    PipelinePhase,
    PipelineTracker,
)
from model_driven.lifecycle.tracking import LifecycleManager  # type: ignore[import-not-found]
from model_driven.lifecycle.transitions import TransitionEngine  # type: ignore[import-not-found]
from model_driven.management.okr import OKRManager  # type: ignore[import-not-found]
from model_driven.management.spec import SpecManager  # type: ignore[import-not-found]
from model_driven.mof.m3_extended import LifecycleStage  # type: ignore[import-not-found]
from model_driven.toolchain.derivation_engine import DerivationEngine  # type: ignore[import-not-found]
from model_driven.toolchain.mof_scan import load_m1_nodes  # type: ignore[import-not-found]
from model_driven.toolchain.tools import tool_validate  # type: ignore[import-not-found]

__all__ = [
    "DerivationEngine",
    "LifecycleManager",
    "LifecycleStage",
    "OKRManager",
    "PipelinePhase",
    "PipelineTracker",
    "SpecManager",
    "TransitionEngine",
    "load_m1_nodes",
    "tool_validate",
]
