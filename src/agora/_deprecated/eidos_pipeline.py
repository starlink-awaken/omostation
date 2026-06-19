"""Backward-compat shim — delegates to agora.pipelines.eidos_pipeline."""

from agora.pipelines.eidos_pipeline import (  # noqa: F401
    EIDOS_PIPELINE_SERVICE,
    execute,
    route,
)
