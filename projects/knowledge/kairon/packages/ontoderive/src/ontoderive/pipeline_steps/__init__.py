"""Pipeline steps — scan, diff, report, govern, validate.

Extracted from SharedBrain D_Logos.
"""

from __future__ import annotations

from .base import PipelineStep
from .core_steps import DiffStep, ReportStep, ScanStep

__all__ = [
    "BatchValidateStep",
    "DiffStep",
    "EvolveStep",
    "PipelineStep",
    "ReportStep",
    "RootNamespaceStep",
    "ScanStep",
    "SectionIndexStep",
    "ValidateStep",
]


def __getattr__(name):
    """Lazy import to break circular: governance_steps/validation_steps
    import back from pipeline_steps.base, but we re-export their Step
    classes here on first attribute access.
    """
    if name == "RootNamespaceStep" or name == "SectionIndexStep":
        from ontoderive.governance_steps import (
            RootNamespaceStep,
            SectionIndexStep,
        )

        return {"RootNamespaceStep": RootNamespaceStep, "SectionIndexStep": SectionIndexStep}[name]
    if name in ("BatchValidateStep", "EvolveStep", "ValidateStep"):
        from ontoderive.validation_steps import (
            BatchValidateStep,
            EvolveStep,
            ValidateStep,
        )

        return {
            "BatchValidateStep": BatchValidateStep,
            "EvolveStep": EvolveStep,
            "ValidateStep": ValidateStep,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
