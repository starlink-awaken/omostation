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
import json
import subprocess
from datetime import UTC, datetime, timedelta
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


class TestNotMeasuredContract:
    """账本缺席时必须自报「没测成」，不能以 ratio=0.0 空绿。

    动机：`.omo/_delivery/**` 是 gitignore 面，CI 的干净检出里没有这份账本 ——
    旧实现在那里返回 `ok: true, ratio: 0.0`，一个阻断级门禁于是永远 PASS。
    """

    def test_missing_ledger_declares_not_measured(self, mod, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(mod, "LEDGER", tmp_path / "absent.jsonl")
        # 投影面必须一起隔离：真实仓库里 `.omo/_delivery/events/` 存在，
        # 只 patch LEDGER 的用例会在有投影的机器上假红。
        monkeypatch.setattr(mod, "PROJECTION_DIR", tmp_path / "no-projection")
        rc = mod.main(["--json"])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0, "缺输入不是仓库缺陷，不该阻断"
        assert out["measured"] is False
        assert out["reason"] == "no_ledger"

    def test_present_ledger_is_measured(self, mod, monkeypatch, tmp_path, capsys):
        ledger = tmp_path / "events.jsonl"
        recent = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ledger.write_text(
            json.dumps(
                {
                    "event": "agent_workflow_start",
                    "ts": recent,
                    "agent_profile": "governance-agent",
                    "workflow_id": "governance-state-mutation",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(mod, "LEDGER", ledger)
        rc = mod.main(["--json"])
        out = json.loads(capsys.readouterr().out)
        assert rc in (0, 1)
        assert out["measured"] is True


class TestProjectionInput:
    """CI 可读面：账本缺席但已提交投影存在时必须真测。

    动机：账本在 gitignore 面且 worktree 里是指向 state root 的符号链接，
    CI 干净检出结构性缺输入 ⇒ 40% 上限只在持有账本的机器上执法。
    `omo.workflow.governance_projection` 把 start 事件镜像成一条一文件的
    去机器化投影；本类钉住读侧行为与**分类等价性** —— 投影不得改变结论。
    """

    @staticmethod
    def _recent(days: int = 1) -> str:
        return (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    @pytest.fixture
    def isolated(self, mod, monkeypatch, tmp_path):
        monkeypatch.setattr(mod, "LEDGER", tmp_path / "absent.jsonl")
        proj = tmp_path / "delivery-runs"
        proj.mkdir()
        monkeypatch.setattr(mod, "PROJECTION_DIR", proj)
        return mod, proj

    def test_projection_only_is_measured(self, isolated, capsys):
        mod, proj = isolated
        rows = [
            {"run_id": "r-gov", "agent_profile": "governance-agent",
             "workflow_id": "governance-state-mutation"},
            {"run_id": "r-flex", "agent_profile": "engineering-agent",
             "workflow_id": "project-code-change"},
        ]
        for row in rows:
            payload = {
                "schema_version": "governance-ratio-event/v1",
                "event": "agent_workflow_start",
                "ts": self._recent(),
                "locks": [],
                "human_approval": False,
                "is_collaboration": False,
                **row,
            }
            (proj / f"{row['run_id']}.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        rc = mod.main(["--json"])
        out = json.loads(capsys.readouterr().out)
        assert out["measured"] is True
        assert out["input_source"] == "projection"
        assert out["total_runs"] == 2
        assert out["buckets"]["governance"] == 1
        assert rc in (0, 1)

    def test_classification_parity_between_inputs(self, mod, monkeypatch, tmp_path, capsys):
        """同一批 run 走账本与走投影，buckets 必须逐字相同。

        两侧唯一差异是分类输入的形状（objective 文本 + 绝对锁路径 vs 两个派生
        布尔 + 相对锁路径），所以这条同时钉住「投影没改变判据」。
        """
        ledger_rows = [
            {"event": "agent_workflow_start", "ts": self._recent(), "run_id": "p1",
             "agent_profile": "governance-agent", "workflow_id": "governance-state-mutation",
             "objective": "收敛治理状态",
             "locks": ["/Users/tester/Repo/.omo/_delivery/agent-workflows/locks/docs.lock.yaml"]},
            {"event": "agent_workflow_start", "ts": self._recent(), "run_id": "p2",
             "agent_profile": "engineering-agent", "workflow_id": "project-code-change",
             "objective": "ship feature", "locks": []},
            # 必须绕过 track/FLEX/profile/GOVERNANCE_WORKFLOWS/locks 五层才落到
            # collaboration 分支；用 project-doc-change 会在 :131 就返回 flex，
            # 这一行便成了钉不住判据的死重（变异对照实测过）。
            {"event": "agent_workflow_start", "ts": self._recent(), "run_id": "p3",
             "agent_profile": "engineering-agent", "workflow_id": "adhoc-review",
             "objective": "docs: collaboration journey", "locks": []},
            {"event": "agent_workflow_start", "ts": self._recent(), "run_id": "p4",
             "agent_profile": "engineering-agent", "workflow_id": "adhoc-ship",
             "objective": "[human] 授权收口", "locks": ["/Users/tester/Repo/.omo/_truth/x.yaml"]},
        ]
        ledger = tmp_path / "events.jsonl"
        ledger.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in ledger_rows) + "\n",
            encoding="utf-8")
        proj = tmp_path / "delivery-runs"
        proj.mkdir()
        for r in ledger_rows:
            projected = {
                "schema_version": "governance-ratio-event/v1",
                "event": "agent_workflow_start",
                "ts": r["ts"],
                "run_id": r["run_id"],
                "agent_profile": r["agent_profile"],
                "workflow_id": r["workflow_id"],
                "locks": [x.replace("/Users/tester/Repo/", "") for x in r["locks"]],
                "human_approval": r["objective"].startswith("[human]"),
                "is_collaboration": "collaboration" in r["objective"].lower(),
            }
            (proj / f"{r['run_id']}.json").write_text(
                json.dumps(projected, ensure_ascii=False), encoding="utf-8")

        monkeypatch.setattr(mod, "LEDGER", ledger)
        monkeypatch.setattr(mod, "PROJECTION_DIR", proj)
        rc_a = mod.main(["--json"])
        from_ledger = json.loads(capsys.readouterr().out)
        monkeypatch.setattr(mod, "LEDGER", tmp_path / "absent.jsonl")
        rc_b = mod.main(["--json"])
        from_projection = json.loads(capsys.readouterr().out)

        assert from_projection["input_source"] == "projection"
        assert from_ledger["buckets"] == from_projection["buckets"]
        assert from_ledger["ratio"] == from_projection["ratio"]
        assert from_ledger["has_human_approval"] is True
        assert from_ledger["has_human_approval"] == from_projection["has_human_approval"]
        assert rc_a == rc_b

    def test_malformed_projection_is_skipped(self, isolated, capsys):
        mod, proj = isolated
        (proj / "broken.json").write_text("{not json", encoding="utf-8")
        (proj / "good.json").write_text(
            json.dumps({"event": "agent_workflow_start", "ts": self._recent(),
                        "run_id": "g1", "agent_profile": "governance-agent",
                        "workflow_id": "governance-state-mutation", "locks": []}),
            encoding="utf-8")
        rc = mod.main(["--json"])
        out = json.loads(capsys.readouterr().out)
        assert out["measured"] is True
        assert out["total_runs"] == 1
        assert rc in (0, 1)

    def test_ledger_wins_when_both_present(self, mod, monkeypatch, tmp_path, capsys):
        ledger = tmp_path / "events.jsonl"
        ledger.write_text(
            json.dumps({"event": "agent_workflow_start", "ts": self._recent(),
                        "run_id": "only-ledger", "agent_profile": "governance-agent",
                        "workflow_id": "governance-state-mutation"}) + "\n",
            encoding="utf-8")
        proj = tmp_path / "delivery-runs"
        proj.mkdir()
        (proj / "only-proj.json").write_text(
            json.dumps({"event": "agent_workflow_start", "ts": self._recent(),
                        "run_id": "only-proj", "agent_profile": "engineering-agent",
                        "workflow_id": "project-code-change", "locks": []}),
            encoding="utf-8")
        monkeypatch.setattr(mod, "LEDGER", ledger)
        monkeypatch.setattr(mod, "PROJECTION_DIR", proj)
        mod.main(["--json"])
        out = json.loads(capsys.readouterr().out)
        assert out["input_source"] == "ledger"
        assert out["total_runs"] == 1
        assert out["projection_files"] == 1


class TestProjectionCoverage:
    """warn-only 覆盖面守卫：只有**已提交**的投影才算 CI 可读输入。

    动机：投影落在每个检出各自的真实目录里（只有 `agent-workflows` 走 symlink
    桥），`gac-worktree.sh release` 把未提交的投影连同 worktree 一起删（2026-11-26
    实测 15 份）⇒ 批 1 的管道可以静默绕过。本类钉「缺口按 tracked 计」，且
    仪器读不出时不得写成 0，读数不得改变任何判定字段。
    """

    @staticmethod
    def _git(root: Path, *args: str) -> None:
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)

    @staticmethod
    def _recent() -> str:
        return (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    @pytest.fixture
    def repo(self, tmp_path: Path) -> tuple[Path, Path]:
        root = tmp_path / "repo"
        proj = root / ".omo" / "_delivery" / "events" / "delivery-runs"
        proj.mkdir(parents=True)
        self._git(root, "init", "-q")
        self._git(root, "config", "user.email", "t@example.com")
        self._git(root, "config", "user.name", "t")
        return root, proj

    def test_only_committed_projection_counts_as_covered(self, mod, repo) -> None:
        """盘上 2 份、已提交 1 份、账本窗口 3 个 run ⇒ 缺口是 2，不是 1 也不是 0。"""
        root, proj = repo
        (proj / "r1.json").write_text("{}", encoding="utf-8")
        (proj / "r2.json").write_text("{}", encoding="utf-8")
        self._git(root, "add", ".omo/_delivery/events/delivery-runs/r1.json")
        self._git(root, "commit", "-qm", "一份投影入库")
        cov = mod._coverage(
            [{"run_id": "r1"}, {"run_id": "r2"}, {"run_id": "r3"}],
            2,
            "ledger",
            projection_dir=proj,
            root=root,
        )
        assert cov["basis"] == "git_ls_files"
        assert cov["tracked_projection_files"] == 1
        assert cov["untracked_projection_files"] == 1
        assert cov["window_runs"] == 3
        assert cov["unprojected_runs"] == 2, "未提交的 r2 与无投影的 r3 都要计进缺口"

    def test_instrument_absence_is_never_zero(self, mod, tmp_path: Path) -> None:
        """投影不在检出内 / 根不是 git 仓库 —— 两种仪器失效都得返 None。"""
        starts = [{"run_id": "r1"}, {"run_id": "r2"}]
        anchored = tmp_path / "anchored"
        anchored.mkdir()
        outside = mod._coverage(
            starts, 0, "ledger", projection_dir=tmp_path / "elsewhere", root=anchored
        )
        assert outside["basis"] == "projection_outside_checkout"
        plain = tmp_path / "plain"
        plain.mkdir()
        not_a_repo = mod._coverage(starts, 0, "ledger", projection_dir=plain / ".omo", root=plain)
        assert not_a_repo["basis"] == "git_ls_files_failed"
        for cov in (outside, not_a_repo):
            assert cov["tracked_projection_files"] is None, "读不出不得写成「零个已提交投影」"
            assert cov["unprojected_runs"] is None
            assert cov["untracked_projection_files"] is None

    def test_subprocess_failure_reports_unavailable_not_zero(self, mod, monkeypatch, repo) -> None:
        """git 根本调不起来（OSError）时，读数必须是 None + 专门 basis。

        这条钉的是 `_tracked_projection_run_ids` 的 except 分支：实仓里 git 总在，
        不注入故障就永远走不到 —— 而「返空集」在这个形状下与「零个已提交投影」
        长得一样，正是 §7 的假绿形状。
        """
        root, proj = repo
        calls: list[list[str]] = []

        def boom(argv, **kwargs):
            calls.append(argv)
            raise OSError("git: spawn failed")

        monkeypatch.setattr(mod.subprocess, "run", boom)
        cov = mod._coverage([{"run_id": "r1"}], 1, "ledger", projection_dir=proj, root=root)
        assert calls, "用例必须真的走到仪器调用，否则是在测桩"
        assert cov["basis"] == "git_ls_files_unavailable"
        assert cov["tracked_projection_files"] is None
        assert cov["unprojected_runs"] is None

    def test_projection_input_reports_no_gap_rather_than_zero(self, mod, repo) -> None:
        """投影自己当输入时每个 run 都命中自己的文件 —— 恒 0 是假齐，得返 None。"""
        root, proj = repo
        (proj / "p1.json").write_text("{}", encoding="utf-8")
        self._git(root, "add", "-A")
        self._git(root, "commit", "-qm", "投影入库")
        cov = mod._coverage([{"run_id": "p1"}], 1, "projection", projection_dir=proj, root=root)
        assert cov["tracked_projection_files"] == 1
        assert cov["unprojected_runs"] is None

    @pytest.mark.parametrize("governance", [False, True], ids=["ratio 0%", "ratio 100%"])
    def test_coverage_fields_never_change_the_verdict(
        self, mod, monkeypatch, repo, capsys, governance: bool
    ) -> None:
        """同一个账本，投影未提交 vs 已提交 —— 除 coverage 外逐字段相等。

        这是 warn-only 的**定义**：回填只让缺口可见，不把 CI 变成另一种结论。
        必须两种区间都跑 —— 变异验证发现「只在超额区间跑」时，`ok` 已经是 False，
        `False and 任何判据` 恒 False，覆盖面漏进判定的变异会被既有阻断掩盖掉。
        """
        root, proj = repo
        runs = [f"x{i}" for i in range(11)]
        profile, wf = (
            ("governance-agent", "governance-state-mutation")
            if governance
            else ("engineering-agent", "project-code-change")
        )
        payload = "".join(
            json.dumps(
                {
                    "event": "agent_workflow_start",
                    "ts": self._recent(),
                    "run_id": rid,
                    "agent_profile": profile,
                    "workflow_id": wf,
                }
            )
            + "\n"
            for rid in runs
        )
        (root / "events.jsonl").write_text(payload, encoding="utf-8")
        for rid in runs:
            (proj / f"{rid}.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(mod, "WORKSPACE", root)
        monkeypatch.setattr(mod, "LEDGER", root / "events.jsonl")
        monkeypatch.setattr(mod, "PROJECTION_DIR", proj)
        monkeypatch.delenv("GITHUB_PR_NUMBER", raising=False)

        rc_before = mod.main(["--json"])
        out_before = json.loads(capsys.readouterr().out)
        self._git(root, "add", "-A")
        self._git(root, "commit", "-qm", "投影入库")
        rc_after = mod.main(["--json"])
        out_after = json.loads(capsys.readouterr().out)

        assert out_before["coverage"]["unprojected_runs"] == 11
        assert out_after["coverage"]["unprojected_runs"] == 0
        # 装置本身得真的产出预期结论，否则「前后相等」是空断言
        assert out_after["level"] == ("blocking" if governance else "ok"), out_after["reason"]
        strip = lambda d: {k: v for k, v in d.items() if k != "coverage"}  # noqa: E731
        assert strip(out_before) == strip(out_after), "覆盖面读数不得改变判定字段"
        assert rc_before == rc_after
