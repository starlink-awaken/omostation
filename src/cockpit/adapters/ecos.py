"""Anti-corruption adapter for projects/ecos (L0).

Re-exports the ecos workflow / governance symbols used by cockpit MCP server
and dashboard API routes.
"""

from ecos.cli.workflow_runs import _load_all_runs as load_all_workflow_runs
from ecos.l0.governance import GovernanceRegistry
from ecos.workflow import execute_m1_workflow, list_backends, list_workflows, load_workflow
from ecos.workflow.actions import list_actions
from ecos.workflow.executor import test_workflow
from ecos.workflow.validator import validate_workflow

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
