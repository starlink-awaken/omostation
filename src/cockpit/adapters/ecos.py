"""Anti-corruption adapter for projects/ecos (L0).

Re-exports the ecos workflow / governance symbols used by cockpit MCP server
and dashboard API routes.
"""

from ecos.cli.workflow_runs import _load_all_runs as load_all_workflow_runs  # type: ignore[import-not-found]
from ecos.l0.governance import GovernanceRegistry  # type: ignore[import-not-found]
from ecos.workflow import (  # type: ignore[import-not-found]
    execute_m1_workflow,
    list_backends,
    list_workflows,
    load_workflow,
)
from ecos.workflow.actions import list_actions  # type: ignore[import-not-found]
from ecos.workflow.executor import test_workflow  # type: ignore[import-not-found]
from ecos.workflow.validator import validate_workflow  # type: ignore[import-not-found]

__all__ = [
    "GovernanceRegistry",
    "execute_m1_workflow",
    "list_actions",
    "list_backends",
    "list_workflows",
    "load_all_workflow_runs",
    "load_workflow",
    "test_workflow",
    "validate_workflow",
]
