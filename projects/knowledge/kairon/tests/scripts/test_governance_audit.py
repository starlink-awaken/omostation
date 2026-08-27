"""P29-W0-GOVERNANCE-AUDIT — 单元测试.

目标:
  - 验证 5 项检查在受控 workspace 下行为正确
  - 验证 compute_grade / build_watchlist / build_recommendations / to_markdown
  - 用 tmp_path 模拟工作区布局, 避免污染真实仓库
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 把 scripts 目录加进 sys.path, 让 `import governance_audit` 可用
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import governance_audit as ga  # type: ignore[reportMissingImports]

# ── 公共 fixture ──────────────────────────────────────────────


@pytest.fixture
def fake_workspace(tmp_path: Path) -> Path:
    """构造一个最小化工作区布局, 用于单元测试.

    包含:
      - projects/kairon/packages/{pkg_a, pkg_b}
        - pkg_a: 有 tests/test_smoke.py
        - pkg_b: 无 tests/ (缺失)
      - .omo/debt/items/GOOD.yaml (resolved + resolution_evidence)
      - .omo/debt/items/BAD.yaml (resolved 无 evidence)
      - .omo/_knowledge/decisions/INDEX.md (引用 0001 + 0099 死链)
      - .omo/_knowledge/decisions/0001-test-adr.md (存在)
      - .omo/tasks/planned/COMPLETE_OK.yaml (deliverables 全存在)
      - .omo/tasks/planned/COMPLETE_BAD.yaml (deliverables 缺失)
    """
    ws = tmp_path
    # packages
    pkgs = ws / "projects" / "kairon" / "packages"
    pkg_a = pkgs / "pkg_a"
    pkg_a.mkdir(parents=True)
    (pkg_a / "tests").mkdir()
    (pkg_a / "tests" / "test_smoke.py").write_text("def test_x(): assert True\n", encoding="utf-8")
    pkg_b = pkgs / "pkg_b"
    pkg_b.mkdir(parents=True)
    # pkg_b 无 tests/

    # debt items
    debt = ws / ".omo" / "debt" / "items"
    debt.mkdir(parents=True)
    (debt / "GOOD.yaml").write_text(
        "id: GOOD\nlifecycle_state: resolved\nresolution_evidence: '>= 20 chars of valid evidence here, no problem.'\n",
        encoding="utf-8",
    )
    (debt / "BAD.yaml").write_text(
        "id: BAD\nlifecycle_state: resolved\n",
        encoding="utf-8",
    )
    (debt / "OPEN.yaml").write_text(
        "id: OPEN\nlifecycle_state: open\n",
        encoding="utf-8",
    )

    # decisions
    dec = ws / ".omo" / "_knowledge" / "decisions"
    dec.mkdir(parents=True)
    (dec / "INDEX.md").write_text(
        "# ADR Index\n\n- 0001-test-adr.md\n- 0099-ghost-adr.md\n",  # 0099 不存在 → 死链
        encoding="utf-8",
    )
    (dec / "0001-test-adr.md").write_text("# 0001\n", encoding="utf-8")
    # 0002-orphan.md 存在但 INDEX 未列 → orphan

    # tasks
    tasks = ws / ".omo" / "tasks" / "planned"
    tasks.mkdir(parents=True)
    (tasks / "COMPLETE_OK.yaml").write_text(
        "id: COMPLETE_OK\n"
        "status: completed\n"
        "deliverables:\n"
        "  - .omo/tasks/planned/COMPLETE_OK.yaml\n",  # 指向自己, 存在
        encoding="utf-8",
    )
    (tasks / "COMPLETE_BAD.yaml").write_text(
        "id: COMPLETE_BAD\nstatus: completed\ndeliverables:\n  - .omo/_delivery/this-file-does-not-exist.md\n",
        encoding="utf-8",
    )
    (tasks / "IN_PROGRESS.yaml").write_text(
        "id: IN_PROGRESS\nstatus: in_progress\ndeliverables:\n  - nonexistent-but-ok-because-not-completed.md\n",
        encoding="utf-8",
    )
    return ws


# ── 单元测试 ──────────────────────────────────────────────────


class TestComputeGrade:
    """compute_grade 等级阈值."""

    def test_compute_grade_a_plus(self) -> None:
        assert ga.compute_grade(100.0) == "A+"

    def test_compute_grade_a(self) -> None:
        assert ga.compute_grade(95.0) == "A"

    def test_compute_grade_b(self) -> None:
        assert ga.compute_grade(85.0) == "B"

    def test_compute_grade_c(self) -> None:
        assert ga.compute_grade(75.0) == "C"

    def test_compute_grade_d(self) -> None:
        assert ga.compute_grade(65.0) == "D"

    def test_compute_grade_f(self) -> None:
        assert ga.compute_grade(50.0) == "F"

    def test_compute_grade_boundary_98(self) -> None:
        """98 是 A+ 边界."""
        assert ga.compute_grade(98.0) == "A+"
        assert ga.compute_grade(97.9) == "A"


class TestCheckAdrLinkIntegrity:
    """ADR 链接完整性."""

    def test_check_adr_link_integrity_broken_link(self, fake_workspace: Path) -> None:
        """INDEX.md 引用 0099 但文件不存在 → 记为 broken."""
        result = ga.check_adr_link_integrity()
        # 跑之前先把全局路径切到 fake_workspace
        ga.OMO_ROOT = fake_workspace / ".omo"
        ga.WORKSPACE_ROOT = fake_workspace
        result = ga.check_adr_link_integrity()
        assert result.severity in ("warn", "fail")
        # 至少有一个 broken (0099-ghost-adr.md)
        assert any("0099" in d for d in result.details)

    def test_check_adr_link_integrity_orphan(self, fake_workspace: Path) -> None:
        """存在的 ADR 没在 INDEX 列出 → 记为 orphan (但不算 broken)."""
        # 注: fake_workspace 不含 0002-orphan.md, 这里用 monkey-patch 验证逻辑
        ga.OMO_ROOT = fake_workspace / ".omo"
        ga.WORKSPACE_ROOT = fake_workspace
        # 加一个未列出的孤儿
        (fake_workspace / ".omo" / "_knowledge" / "decisions" / "0002-orphan.md").write_text(
            "# 0002\n", encoding="utf-8"
        )
        result = ga.check_adr_link_integrity()
        # orphan 不算 broken, 但会出现在 details
        assert any("0002-orphan.md" in d for d in result.details)

    def test_check_adr_link_integrity_clean(self, tmp_path: Path) -> None:
        """完全干净的状态 → ok + 满分."""
        dec = tmp_path / ".omo" / "_knowledge" / "decisions"
        dec.mkdir(parents=True)
        (dec / "INDEX.md").write_text("- 0001-only.md\n", encoding="utf-8")
        (dec / "0001-only.md").write_text("# 1\n", encoding="utf-8")
        ga.OMO_ROOT = tmp_path / ".omo"
        ga.WORKSPACE_ROOT = tmp_path
        result = ga.check_adr_link_integrity()
        assert result.severity == "ok"
        assert result.score == 100.0


class TestCheckTaskYamlConsistency:
    """任务 YAML 一致性."""

    def test_check_task_yaml_consistency_missing_deliverable(self, fake_workspace: Path) -> None:
        """status=completed 但 deliverable 缺失 → warn."""
        ga.OMO_ROOT = fake_workspace / ".omo"
        ga.WORKSPACE_ROOT = fake_workspace
        result = ga.check_task_yaml_consistency()
        assert result.severity == "warn"
        assert any("COMPLETE_BAD" in d for d in result.details)

    def test_check_task_yaml_consistency_ignores_in_progress(self, fake_workspace: Path) -> None:
        """status=in_progress 的任务即使 deliverable 缺失也不报错."""
        ga.OMO_ROOT = fake_workspace / ".omo"
        ga.WORKSPACE_ROOT = fake_workspace
        result = ga.check_task_yaml_consistency()
        # IN_PROGRESS 不应在 details 中
        assert not any("IN_PROGRESS" in d for d in result.details)


class TestBuildWatchlist:
    """watchlist 提炼."""

    def test_build_watchlist_extracts_from_warn_fail(self) -> None:
        """只从 warn/fail 检查里提炼细节."""
        checks = [
            ga.CheckResult("lint", "lint", "ok", 100, "ok"),
            ga.CheckResult("tests", "tests", "warn", 80, "1 missing", ["pkg_b: 无 tests/"]),
            ga.CheckResult("debt", "debt", "fail", 50, "broken", ["BAD.yaml: no evidence"]),
        ]
        wl = ga.build_watchlist(checks)
        # ok 检查不出现在 watchlist
        assert not any("[lint]" in w for w in wl)
        # warn 与 fail 都提炼
        assert any("[tests]" in w for w in wl)
        assert any("[debt]" in w for w in wl)
        assert len(wl) == 2

    def test_build_watchlist_caps_per_check(self) -> None:
        """每个检查最多 5 条."""
        checks = [
            ga.CheckResult(
                "x",
                "lint",
                "warn",
                50,
                "many",
                [f"detail {i}" for i in range(20)],
            ),
        ]
        wl = ga.build_watchlist(checks)
        assert len(wl) == 5


class TestBuildRecommendations:
    """修复建议生成."""

    def test_build_recommendations_per_category(self) -> None:
        """每个 warn/fail 类别都生成对应建议."""
        checks = [
            ga.CheckResult("lint", "lint", "ok", 100, "ok"),
            ga.CheckResult("tests", "tests", "warn", 80, "1 missing", ["pkg_b"]),
            ga.CheckResult("debt", "debt", "warn", 95, "1 missing", ["BAD"]),
            ga.CheckResult("knowledge", "knowledge", "fail", 50, "broken", ["X"]),
            ga.CheckResult("tasks", "tasks", "warn", 90, "1 missing", ["Y"]),
        ]
        recs = ga.build_recommendations(checks)
        # ok 检查不出建议
        assert not any("ruff 错误" in r and "lint" in r for r in recs)
        # 每个 warn 类别有建议
        assert any("test" in r.lower() or "smoke" in r.lower() for r in recs)
        assert any("resolution_evidence" in r for r in recs)
        assert any("ADR" in r or "INDEX" in r for r in recs)
        assert any("deliverable" in r.lower() for r in recs)

    def test_build_recommendations_empty_when_all_ok(self) -> None:
        """全部 ok → 空建议."""
        checks = [ga.CheckResult("x", "lint", "ok", 100, "ok")]
        assert ga.build_recommendations(checks) == []


class TestAuditReportMarkdown:
    """报告 Markdown 渲染."""

    def test_audit_report_to_markdown_structure(self) -> None:
        """to_markdown 包含必备 section."""
        report = ga.AuditReport(
            date="2026-06-05",
            total_score=85.0,
            grade="B",
            checks=[
                ga.CheckResult("lint", "lint", "ok", 100, "ok"),
                ga.CheckResult(
                    "tests",
                    "tests",
                    "warn",
                    80,
                    "1 missing",
                    ["pkg_b: 无 tests/"],
                ),
                ga.CheckResult("debt", "debt", "ok", 100, "ok"),
                ga.CheckResult("adr", "knowledge", "ok", 100, "ok"),
                ga.CheckResult("tasks", "tasks", "ok", 100, "ok"),
            ],
            watchlist=["[tests] pkg_b: 无 tests/"],
            recommendations=["为 pkg_b 等包添加 1 个 smoke test"],
        )
        md = report.to_markdown()
        # 必备
        assert "# omostation 治理巡检报告 — 2026-06-05" in md
        assert "**总分: 85.0 (B)**" in md
        assert "## 1. 检查结果" in md
        assert "## 2. 检查细节" in md
        assert "## 3. 新发现潜在债务" in md
        assert "## 4. 修复建议" in md
        assert "## 5. 评分方法" in md
        # watchlist 内容
        assert "pkg_b" in md
        # 推荐内容
        assert "smoke test" in md

    def test_audit_report_to_markdown_no_watchlist(self) -> None:
        """全 ok 时 watchlist 段输出 (无)."""
        report = ga.AuditReport(
            date="2026-06-05",
            total_score=100.0,
            grade="A+",
            checks=[ga.CheckResult("x", "lint", "ok", 100, "ok")] * 5,
            watchlist=[],
            recommendations=[],
        )
        md = report.to_markdown()
        assert "_(无)_" in md


class TestRunAudit:
    """run_audit 端到端(在 fake_workspace 上)."""

    def test_run_audit_aggregates(self, fake_workspace: Path) -> None:
        """fake_workspace 应该有 warn(check_task, check_adr) 但不崩."""
        # 把全局路径切到 fake_workspace
        ga.OMO_ROOT = fake_workspace / ".omo"
        ga.KAIRON_DIR = fake_workspace / "projects" / "kairon"
        ga.WORKSPACE_ROOT = fake_workspace
        # 用 monkeypatch 子进程调用, 避免真实跑 ruff
        import unittest.mock as mock

        with mock.patch.object(ga, "check_lint", return_value=ga.CheckResult("lint", "lint", "ok", 100, "ok")):
            report = ga.run_audit()
        assert isinstance(report.total_score, float)
        assert 0 <= report.total_score <= 100
        # fake_workspace 至少一个 warn, 总分 < 100
        assert report.total_score < 100
        assert report.grade in ("A+", "A", "B", "C", "D", "F")
        # 至少 watchlist 有内容
        assert len(report.watchlist) >= 1


class TestCLI:
    """CLI smoke test."""

    def test_main_runs_and_emits_markdown(self, capsys) -> None:
        """main() 跑通, 输出含总分."""
        rc = ga.main([])
        captured = capsys.readouterr()
        assert rc == 0
        assert "总分" in captured.out
        assert "omostation 治理巡检报告" in captured.out

    def test_main_with_output_writes_file(self, tmp_path: Path) -> None:
        """--output 写入文件."""
        out = tmp_path / "report.md"
        rc = ga.main(["--output", str(out)])
        assert rc == 0
        assert out.exists()
        text = out.read_text(encoding="utf-8")
        assert "omostation 治理巡检报告" in text
