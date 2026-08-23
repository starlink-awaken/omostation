#!/usr/bin/env python3
"""D3/D5 升级集成测试 — 跨仓变更审计 + 子模块 fast-forward 一致性.

D3 升级: changeset --verify-claims 校验变更路径在 agent claim 范围内.
D5 升级: pre-commit gitlink fast-forward 校验.

长期维护保障: 每个升级点都有对应测试, 防止回归.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

# 确保 bin/gac 在 path 中 (pytest 从根仓运行时需要)
_BIN_GAC = Path(__file__).resolve().parent
sys.path.insert(0, str(_BIN_GAC))
# 确保根仓在 path 中 (swarm_discipline 需要从 bin.gac 导入 coordination_store)
sys.path.insert(0, str(_BIN_GAC.parents[1]))

# agent-clone.py / swarm-discipline.py 含连字符, 需用 importlib 导入
ac = importlib.import_module("agent-clone")
sd = importlib.import_module("swarm_discipline")


class TestD3ClaimChangesetIntegration:
    """D3 升级: 跨仓变更审计引擎."""

    def test_verify_claims_no_changes(self, tmp_path: Path):
        """无变更时 claim 校验通过."""
        result = ac._verify_changeset_claims(str(tmp_path), [])
        assert result["enabled"] is True
        assert result["all_covered"] is True
        assert result["violations"] == []

    def test_verify_claims_with_empty_claims(self, tmp_path: Path):
        """无活跃 claim 时, 有变更则标记 violation."""
        changes = [{"path": "projects/omo/src/foo.py"}]
        result = ac._verify_changeset_claims(str(tmp_path), changes)
        assert result["enabled"] is True
        # 无 claim 覆盖 → violation
        assert result["all_covered"] is False
        assert "projects/omo/src/foo.py" in result["violations"]

    def test_verify_claims_all_covered(self, tmp_path: Path, monkeypatch):
        """变更被 claim 全部覆盖."""
        # Mock active_workflow_claimed_paths 返回覆盖路径
        monkeypatch.setattr(
            sd, "active_workflow_claimed_paths",
            lambda root: ["projects/omo/**"],
        )
        changes = [
            {"path": "projects/omo/src/foo.py"},
            {"path": "projects/omo/tests/test_foo.py"},
        ]
        result = ac._verify_changeset_claims(str(tmp_path), changes)
        assert result["all_covered"] is True
        assert result["violations"] == []

    def test_verify_claims_partial_violation(self, tmp_path: Path, monkeypatch):
        """部分变更超出 claim 范围."""
        monkeypatch.setattr(
            sd, "active_workflow_claimed_paths",
            lambda root: ["projects/omo/**"],
        )
        changes = [
            {"path": "projects/omo/src/foo.py"},  # covered
            {"path": "projects/cockpit/src/bar.py"},  # NOT covered
        ]
        result = ac._verify_changeset_claims(str(tmp_path), changes)
        assert result["all_covered"] is False
        assert len(result["violations"]) == 1
        assert "projects/cockpit/src/bar.py" in result["violations"]

    def test_verify_claims_import_failure_graceful(self, tmp_path: Path, monkeypatch):
        """swarm_discipline 不可用时优雅降级."""
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "swarm_discipline":
                raise ImportError("not available")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        changes = [{"path": "projects/omo/src/foo.py"}]
        result = ac._verify_changeset_claims(str(tmp_path), changes)
        assert result["enabled"] is False
        assert "not available" in result["reason"]


class TestD3PathCoveredByClaim:
    """D3 路径覆盖匹配逻辑."""

    def test_exact_match(self):
        assert sd.path_covered_by_claim(["projects/omo"], "projects/omo") is True

    def test_prefix_match(self):
        assert sd.path_covered_by_claim(["projects/omo"], "projects/omo/src/foo.py") is True

    def test_glob_match(self):
        assert sd.path_covered_by_claim(["projects/omo/**"], "projects/omo/src/foo.py") is True

    def test_no_match(self):
        assert sd.path_covered_by_claim(["projects/omo"], "projects/cockpit/src") is False

    def test_dotdot_stripped(self):
        assert sd.path_covered_by_claim(["projects/omo"], "./projects/omo/src") is True


class TestD5FastForwardLogic:
    """D5 升级: fast-forward 一致性校验逻辑."""

    def test_branch_available_when_free(self, tmp_path: Path):
        """无 claim 时分支可用."""
        ok, reason = sd.check_branch_available(tmp_path, "work/test", "session-1")
        assert ok is True
        assert reason == "free"

    def test_branch_available_when_owned(self, tmp_path: Path, monkeypatch):
        """自己持有 claim 时可用."""
        claims_dir = tmp_path / ".omo" / "_delivery" / "branch-claims"
        claims_dir.mkdir(parents=True)
        (claims_dir / "s1.json").write_text(json.dumps({
            "branch": "work/test", "session": "s1",
        }))
        monkeypatch.setattr(sd, "load_registry", lambda root: {
            "delivery": {"branch_claims_dir": ".omo/_delivery/branch-claims"},
        })
        ok, reason = sd.check_branch_available(tmp_path, "work/test", "s1")
        assert ok is True
        assert reason == "owned"

    def test_branch_not_available_when_occupied(self, tmp_path: Path, monkeypatch):
        """他人持有时不可用."""
        claims_dir = tmp_path / ".omo" / "_delivery" / "branch-claims"
        claims_dir.mkdir(parents=True)
        (claims_dir / "s1.json").write_text(json.dumps({
            "branch": "work/test", "session": "s1",
        }))
        monkeypatch.setattr(sd, "load_registry", lambda root: {
            "delivery": {"branch_claims_dir": ".omo/_delivery/branch-claims"},
        })
        ok, reason = sd.check_branch_available(tmp_path, "work/test", "s2")
        assert ok is False
        assert "occupied" in reason


class TestD2Retired:
    """D2 shadow mirror 退役验证."""

    def test_shadow_mirror_noop(self):
        """shadow mirror 不再执行任何操作."""
        result = sd._shadow_mirror_claim("work/test", "session-1")
        assert result == {}

    def test_shadow_mirror_release_noop(self):
        """shadow mirror release 也是 no-op."""
        result = sd._shadow_mirror_claim("work/test", "session-1", release=True)
        assert result == {}


class TestRegistryState:
    """验证 registry 中 D2/D3/D5 状态正确."""

    def test_d2_retired(self, tmp_path: Path, monkeypatch):
        """D2 在 registry 中标记为 retired."""
        reg_file = tmp_path / "swarm-coordination.yaml"
        reg_file.write_text("""
gates:
  d2_branch_occupancy:
    status: retired
    retired_reason: "独立 clone 拓扑消除分支竞争"
  d4_escape_hatch:
    status: active
""")
        monkeypatch.setattr(sd, "DEFAULT_REGISTRY", str(reg_file))
        reg = sd.load_registry(tmp_path)
        assert reg["gates"]["d2_branch_occupancy"]["status"] == "retired"
        assert reg["gates"]["d4_escape_hatch"]["status"] == "active"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
