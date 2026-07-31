"""Anti-corruption adapter for projects/model-driven (M0).

Re-exports the model-driven lifecycle / toolchain symbols used by cockpit
commands.
"""

from model_driven.lifecycle.pipeline import PipelinePhase, PipelineTracker
from model_driven.lifecycle.tracking import LifecycleManager
from model_driven.lifecycle.transitions import TransitionEngine
from model_driven.management.okr import OKRManager
from model_driven.management.spec import SpecManager
from model_driven.mof.m3_extended import LifecycleStage
from model_driven.toolchain.derivation_engine import DerivationEngine
from model_driven.toolchain.mof_scan import load_m1_nodes
from model_driven.toolchain.tools import tool_validate

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
