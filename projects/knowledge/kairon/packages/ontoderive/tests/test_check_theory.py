"""Tests for check_theory — C-09~C-13 理论层规约检查"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.core.check_theory import (
    THEORY_CHECKS,
    check_bayesian,
    check_metrics,
    check_ontolang,
    check_pid,
    check_turing,
)


class TestTheoryRegistry:
    def test_registry_has_5_checks(self):
        assert len(THEORY_CHECKS) == 5

    def test_registry_contains_all(self):
        pids = [pid for pid, _, _ in THEORY_CHECKS]
        assert "C-09" in pids
        assert "C-10" in pids
        assert "C-11" in pids
        assert "C-12" in pids
        assert "C-13" in pids

    def test_registry_functions_are_callable(self):
        for _, _, fn in THEORY_CHECKS:
            assert callable(fn)


class TestCheckBayesian:
    def test_returns_dict(self, tmp_project):
        result = check_bayesian(tmp_project)
        assert isinstance(result, dict)
        assert "passed" in result
        assert "severity" in result
        assert "detail" in result

    def test_with_mock_project(self, tmp_project):
        """最小项目也能跑通"""
        result = check_bayesian(tmp_project)
        assert result["passed"] in (True, False)
        assert result["severity"] in ("PASS", "WARN", "ERROR", "BLOCKER")


class TestCheckMetrics:
    def test_returns_dict(self, tmp_project):
        result = check_metrics(tmp_project)
        assert isinstance(result, dict)
        assert "passed" in result
        assert "detail" in result

    def test_with_precomputed_confs(self, tmp_project):
        confs = {"D-F1": 0.8, "D-F2": 0.9, "INF-L1": 0.75}
        result = check_metrics(tmp_project, precomputed_confs=confs)
        assert isinstance(result, dict)
        assert "KQI" in result["detail"]


class TestCheckPID:
    def test_returns_dict(self, tmp_project):
        result = check_pid(tmp_project)
        assert isinstance(result, dict)
        assert "passed" in result


class TestCheckTuring:
    def test_returns_dict(self, tmp_project):
        result = check_turing(tmp_project)
        assert isinstance(result, dict)
        assert "passed" in result

    def test_turing_with_data(self, tmp_project):
        result = check_turing(tmp_project)
        assert "快照" in result["detail"] or "异常" in result["detail"]


class TestCheckOntolang:
    def test_returns_dict(self, tmp_project):
        result = check_ontolang(tmp_project)
        assert isinstance(result, dict)
        assert result["passed"] is True  # DEPRECATED always passes
        assert result["severity"] == "PASS"
