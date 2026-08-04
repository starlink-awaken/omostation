"""test_governance_ratio - classification logic tests (防回归).

Validates the _classify() function in check-governance-ratio.py:
- Workflow-internal lock paths (.omo/_delivery/agent-workflows/locks/) do NOT
  cause a run to be classified as governance
- FLEX_OVERRIDE_WORKFLOWS (project-code-change, project-doc-change) classify as
  flex even when run by governance-agent profile
- Explicit track field takes precedence over all heuristics
- Governance profiles and workflows still classify correctly
- Non-governance locks (e.g. .omo/_truth/) still classify as governance
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "gac" / "check-governance-ratio.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_governance_ratio", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


class TestClassifyTrackOverride:
    """Explicit track field should always win."""

    def test_track_governance(self, mod):
        evt = {"track": "governance", "agent_profile": "engineering-agent", "workflow_id": "project-code-change"}
        assert mod._classify(evt) == "governance"

    def test_track_flex(self, mod):
        evt = {"track": "flex", "agent_profile": "governance-agent", "workflow_id": "governance-state-mutation"}
        assert mod._classify(evt) == "flex"

    def test_track_collaboration(self, mod):
        evt = {"track": "collaboration", "agent_profile": "engineering-agent"}
        assert mod._classify(evt) == "collaboration"


class TestFlexOverrideWorkflows:
    """project-code-change and project-doc-change should be flex even with governance-agent."""

    def test_governance_agent_project_code_change(self, mod):
        evt = {"agent_profile": "governance-agent", "workflow_id": "project-code-change"}
        assert mod._classify(evt) == "flex"

    def test_governance_agent_project_doc_change(self, mod):
        evt = {"agent_profile": "governance-agent", "workflow_id": "project-doc-change"}
        assert mod._classify(evt) == "flex"

    def test_engineering_agent_project_code_change(self, mod):
        evt = {"agent_profile": "engineering-agent", "workflow_id": "project-code-change"}
        assert mod._classify(evt) == "flex"


class TestGovernanceClassification:
    """Governance profiles and workflows should classify as governance."""

    def test_governance_agent_governance_state_mutation(self, mod):
        evt = {"agent_profile": "governance-agent", "workflow_id": "governance-state-mutation"}
        assert mod._classify(evt) == "governance"

    def test_release_agent_submodule_pointer_close(self, mod):
        evt = {"agent_profile": "release-agent", "workflow_id": "submodule-pointer-close"}
        assert mod._classify(evt) == "governance"

    def test_mof_agent_mof_model_change(self, mod):
        evt = {"agent_profile": "mof-agent", "workflow_id": "mof-model-change"}
        assert mod._classify(evt) == "governance"

    def test_engineering_agent_with_governance_workflow(self, mod):
        evt = {"agent_profile": "engineering-agent", "workflow_id": "state-sync"}
        assert mod._classify(evt) == "governance"


class TestWorkflowLockPrefixExclusion:
    """Locks under .omo/_delivery/agent-workflows/locks/ should NOT trigger governance."""

    def test_workflow_lock_prefix_excluded(self, mod):
        evt = {
            "agent_profile": "engineering-agent",
            "workflow_id": "project-code-change",
            "locks": [
                ".omo/_delivery/agent-workflows/locks/project.lock.yaml",
                ".omo/_delivery/agent-workflows/locks/root-gate.lock.yaml",
            ],
        }
        assert mod._classify(evt) == "flex"

    def test_non_workflow_omo_lock_still_governance(self, mod):
        evt = {
            "agent_profile": "engineering-agent",
            "workflow_id": "handoff-resume",
            "locks": [".omo/_truth/registry/governance-checks.yaml"],
        }
        assert mod._classify(evt) == "governance"

    def test_mixed_locks_workflow_and_non_workflow(self, mod):
        evt = {
            "agent_profile": "engineering-agent",
            "workflow_id": "handoff-resume",
            "locks": [
                ".omo/_delivery/agent-workflows/locks/project.lock.yaml",
                "bin/gac/gac-local-gate.py",
            ],
        }
        assert mod._classify(evt) == "governance"

    def test_no_locks_flex(self, mod):
        evt = {"agent_profile": "engineering-agent", "workflow_id": "project-code-change"}
        assert mod._classify(evt) == "flex"


class TestCollaborationObjective:
    """Objective containing 'collaboration' should classify as collaboration."""

    def test_collaboration_in_objective(self, mod):
        evt = {
            "agent_profile": "engineering-agent",
            "workflow_id": "handoff-resume",
            "objective": "cross-team collaboration on feature X",
        }
        assert mod._classify(evt) == "collaboration"

    def test_no_collaboration_in_objective(self, mod):
        evt = {
            "agent_profile": "engineering-agent",
            "workflow_id": "handoff-resume",
            "objective": "fix bug in module Y",
        }
        assert mod._classify(evt) == "flex"
