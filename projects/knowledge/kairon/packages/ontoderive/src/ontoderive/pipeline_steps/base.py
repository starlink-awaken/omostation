"""Pipeline step base class — abstract base for all pipeline steps."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from ..pipeline_models import ProgressInfo, StepResult


class PipelineStep(ABC):
    """Pipeline step base class.

    Subclass and implement ``execute()`` to create a custom pipeline step.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._result: StepResult | None = None
        self._progress_callback: Callable[[ProgressInfo], None] | None = None

    @abstractmethod
    def execute(self, context: dict, progress: ProgressInfo) -> StepResult:
        """Execute the step. Override in subclasses."""

    def set_progress_callback(self, callback: Callable[[ProgressInfo], None]) -> None:
        """Set progress callback for this step."""
        self._progress_callback = callback

    def _update_progress(self, progress: ProgressInfo) -> None:
        """Notify progress callback if set."""
        if self._progress_callback:
            self._progress_callback(progress)

    @property
    def result(self) -> StepResult | None:
        return self._result
