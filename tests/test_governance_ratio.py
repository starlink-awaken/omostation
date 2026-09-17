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
        evt = {
            "track": "governance",
            "agent_profile": "engineering-agent",
            "workflow_id": "project-code-change",
        }
        assert mod._classify(evt) == "governance"

    def test_track_flex(self, mod):
        evt = {
            "track": "flex",
            "agent_profile": "governance-agent",
            "workflow_id": "governance-state-mutation",
        }
        assert mod._classify(evt) == "flex"

    def test_track_collaboration(self, mod):
        evt = {"track": "collaboration", "agent_profile": "engineering-agent"}
        assert mod._classify(evt) == "collaboration"


class TestFlexOverrideWorkflows:
    """project-code-change and project-doc-change should be flex even with governance-agent."""

    def test_governance_agent_project_code_change(self, mod):
        evt = {
            "agent_profile": "governance-agent",
            "workflow_id": "project-code-change",
        }
        assert mod._classify(evt) == "flex"

    def test_governance_agent_project_doc_change(self, mod):
        evt = {"agent_profile": "governance-agent", "workflow_id": "project-doc-change"}
        assert mod._classify(evt) == "flex"

    def test_engineering_agent_project_code_change(self, mod):
        evt = {
            "agent_profile": "engineering-agent",
            "workflow_id": "project-code-change",
        }
        assert mod._classify(evt) == "flex"


class TestGovernanceClassification:
    """Governance profiles and workflows should classify as governance."""

    def test_governance_agent_governance_state_mutation(self, mod):
        evt = {
            "agent_profile": "governance-agent",
            "workflow_id": "governance-state-mutation",
        }
        assert mod._classify(evt) == "governance"

    def test_release_agent_submodule_pointer_close(self, mod):
        evt = {
            "agent_profile": "release-agent",
            "workflow_id": "submodule-pointer-close",
        }
        assert mod._classify(evt) == "flex"

    def test_gov_agent_submodule_pointer_close_is_flex(self, mod):
        evt = {
            "agent_profile": "governance-agent",
            "workflow_id": "submodule-pointer-close",
        }
        assert mod._classify(evt) == "flex"

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
        """governance=true when lock path matches GOVERNANCE_PATHS (e.g. .omo/_truth/).

        As of 2026-09-17 PITFALL-COO-006 fix: bin/gac/ bin/ssot/ removed from
        GOVERNANCE_PATHS (tool-fix land, not governance-rule rewrite), so
        the test uses .omo/_truth/governance/ which is the canonical governance
        write surface.
        """
        evt = {
            "agent_profile": "engineering-agent",
            "workflow_id": "handoff-resume",
            "locks": [
                ".omo/_delivery/agent-workflows/locks/project.lock.yaml",
                ".omo/_truth/governance/governance-state.yaml",
            ],
        }
        assert mod._classify(evt) == "governance"

    def test_no_locks_flex(self, mod):
        evt = {
            "agent_profile": "engineering-agent",
            "workflow_id": "project-code-change",
        }
        assert mod._classify(evt) == "flex"


class TestWaiverActive:
    """Waiver 机制: env GITHUB_PR_NUMBER 命中 waiver 列表 → 返 active waiver.

    4019+ fix: PITFALL-COO-006 加固. waiver 文件 .omo/_truth/governance-evidence/waiver-*.md
    frontmatter 含 pr_numbers 列表.
    """

    def test_waiver_load_no_env(self, mod, monkeypatch):
        monkeypatch.delenv("GITHUB_PR_NUMBER", raising=False)
        assert mod._active_waivers() == []

    def test_waiver_load_invalid_env(self, mod, monkeypatch):
        monkeypatch.setenv("GITHUB_PR_NUMBER", "not-a-number")
        assert mod._active_waivers() == []

    def test_waiver_load_match(self, mod, monkeypatch, tmp_path):
        """Setup: 写一个 waiver 含 pr_numbers=[1234], 跑 _active_waivers with PR=1234 → 命中."""
        # 改 WAIVERS_DIR 临时指向 tmp
        import os
        import yaml
        # WAIVERS_DIR 实际是 WORKSPACE/.omo/_truth/governance-evidence. 改不了 (模块级常量).
        # 改用 monkey-patch 模块属性
        waivers_subdir = tmp_path / "waivers_test"
        waivers_subdir.mkdir()
        w = waivers_subdir / "waiver-test-001.md"
        w.write_text(
            "---\n"
            "schema_version: governance-waiver/v1\n"
            "status: active\n"
            "lifecycle: history\n"
            "type: governance-ratio-waiver\n"
            "owner: governance-team\n"
            "created: 2026-09-17\n"
            "last-reviewed: 2026-09-17\n"
            "pr_numbers:\n"
            "  - 1234\n"
            "  - 5678\n"
            "---\n"
            "\n# test waiver\n"
        )
        # 用 monkey-patch WAIVERS_DIR 临时指向 tmp/waivers_test
        # 但要确保其他 .md 不被 scan
        # 简单方案: copy 现有 waivers 旁路 (不扫原 dir)
        monkeypatch.setattr(mod, "WAIVERS_DIR", waivers_subdir)
        monkeypatch.setenv("GITHUB_PR_NUMBER", "1234")
        hits = mod._active_waivers()
        assert "waiver-test-001" in hits
        # 5678 单独跑
        monkeypatch.setenv("GITHUB_PR_NUMBER", "5678")
        hits = mod._active_waivers()
        assert "waiver-test-001" in hits
        # 9999 不命中
        monkeypatch.setenv("GITHUB_PR_NUMBER", "9999")
        assert mod._active_waivers() == []


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
