"""CR-CHANGE-LANE-RANGE 的合同测试: CI 侧 lane 隔离判据 (per-commit 粒度)。

缺陷背景 (2026-10-30 实锤): lane 隔离规则在**三条路径上全部空转** ——
- `sgf-policy.yaml` 把 `change-lane-check` 登记为 `--staged`, CI 干净检出里
  没有 staged 文件 => 读到空集 => 恒 PASS;
- `change-lane-check.py` 的 `PUSH_RANGE` 分支在 `.githooks/` 无导出点 => 从未触发;
- 本地 `pre-commit` / `pre-push` 的检查清单里也没有它 => 从未触发。

本测试锁住三件事:
1. **判据粒度是 per-commit**, 不是整段合并成一个集合 (规则原文「每 commit 单 lane」,
   ADR-0122 §46 / ADR-0456 §验收) —— 一段范围里多个不同 lane 的 commit 是合规的;
2. **判据有牙齿**: 单个 commit 内混 lane 必须被报出 (不是被「范围为空」悄悄放过);
3. **空范围不误报**: 无可比基线时必须显式 skip, 而不是假装通过或假装失败。
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RANGE_SCRIPT = ROOT / "bin" / "gac" / "check-change-lane-range.py"
LANE_SCRIPT = ROOT / "bin" / "change-lane-check.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    return repo


def _commit(repo: Path, files: dict, message: str) -> str:
    for rel, content in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _run_range_check(repo: Path, base: str, head: str, extra_args=None) -> dict:
    """跑 range 判据并读回 JSON 报告。"""
    module = _load(RANGE_SCRIPT, "check_change_lane_range")
    module.CHANGE_LANE_CHECK = LANE_SCRIPT
    # git 查询必须发生在被测的临时仓里 (默认是本仓 WORKSPACE)
    module.WORKSPACE = repo
    argv = ["--json", "--base", base, "--head", head]
    argv.extend(extra_args or [])
    original = sys.argv
    sys.argv = ["check-change-lane-range.py", *argv]
    try:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = module.main()
    finally:
        sys.argv = original
    return {"exit": code, "report": json.loads(buffer.getvalue())}


def test_per_commit_judgement_separates_commits_within_one_range(tmp_path):
    """一段范围里两个不同 lane 的 commit => 合规 (per-commit 粒度的核心语义)。

    若把整段合并成一个集合去判, 这会得到 {docs, submodule_pointer} 的假违规。
    """
    repo = _make_repo(tmp_path)
    base = _commit(repo, {"README.md": "base\n"}, "base")
    # docs 档: docs/ 下的 md => docs lane
    _commit(repo, {"docs/plan.md": "plan\n"}, "docs change")
    # config 面: .github/workflows/ 下的 yml => config lane
    head = _commit(repo, {".github/workflows/ci.yml": "name: x\n"}, "workflow change")

    result = _run_range_check(repo, base, head)
    report = result["report"]
    assert report["ok"], report
    assert report["commits"] == 2
    assert report["violations"] == 0


def test_single_commit_with_mixed_lanes_is_reported(tmp_path):
    """单个 commit 内混 lane => 必须报出 (判据有牙齿)。"""
    repo = _make_repo(tmp_path)
    base = _commit(repo, {"README.md": "base\n"}, "base")
    # 机制面 (代码) + 治理面 (.omo/) => 仍须判违规
    # (注: docs + governance_state 已于 2026-10-30 放宽为合法组合, 见
    #  test_governance_state_may_share_a_commit_with_docs_lane)
    head = _commit(
        repo,
        {
            "bin/plan/tool.py": "# tool\n",
            ".omo/_knowledge/decisions/0001-x.md": "# decision\n",
        },
        "mixed change",
    )

    result = _run_range_check(repo, base, head)
    report = result["report"]
    assert not report["ok"], report
    assert report["violations"] == 1
    violation = report["per_commit"][0]
    assert set(violation["lanes"]) == {"code", "governance_state"}


def test_default_is_advisory_but_fail_on_violation_blocks(tmp_path):
    """默认 advisory (exit 0, 信号可见); --fail-on-violation 才阻断。

    默认不断阻是刻意的: 实测 40 个已合并 PR 中 13 个 (32.5%) 在此判据下违规,
    这是该规则从未生效留下的历史欠账, 直接阻断会炸掉约 1/3 的 PR。
    """
    repo = _make_repo(tmp_path)
    base = _commit(repo, {"README.md": "base\n"}, "base")
    head = _commit(
        repo,
        {
            "bin/plan/tool.py": "# tool\n",
            ".omo/_knowledge/decisions/0001-x.md": "# decision\n",
        },
        "mixed change",
    )

    advisory = _run_range_check(repo, base, head)
    assert advisory["exit"] == 0
    assert advisory["report"]["violations"] == 1
    assert advisory["report"]["severity"] == "advisory"

    blocking = _run_range_check(repo, base, head, ["--fail-on-violation"])
    assert blocking["exit"] == 1


def test_empty_range_is_skipped_not_passed(tmp_path):
    """无可解析 commit => 显式 skip, 既不假装通过也不假装失败。"""
    repo = _make_repo(tmp_path)
    head = _commit(repo, {"README.md": "x\n"}, "only")

    result = _run_range_check(repo, head, head)
    report = result["report"]
    assert result["exit"] == 0
    assert report["skipped"] is True
    assert report["ok"] is True
    assert "no commits resolvable" in report["reason"]


def test_commit_paths_in_range_returns_commit_file_sets(tmp_path):
    """change-lane-check.commit_paths_in_range: 按 commit 逐个返回改动文件。"""
    repo = _make_repo(tmp_path)
    base = _commit(repo, {"README.md": "base\n"}, "base")
    _commit(repo, {"docs/a.md": "a\n"}, "first")
    head = _commit(repo, {"docs/b.md": "b\n"}, "second")

    module = _load(LANE_SCRIPT, "change_lane_check_range")
    commits = module.commit_paths_in_range(base + ".." + head, cwd=repo)
    assert len(commits) == 2
    assert commits[0][1] == ["docs/a.md"]
    assert commits[1][1] == ["docs/b.md"]

def test_script_registry_entries_share_the_governance_lane(tmp_path):
    """bin/_registry/ 下的登记条目与被登记脚本同属 governance_code lane。

    归类依据同 ADR-0129 §2.1: 分类应反映语义单元而非路径字面。若注册表条目落到
    后缀兜底 (yaml => code), 则「改脚本 + 改它的登记条目」这个原子变更必然被判成
    code + governance_code 混 lane (该组合不在 ALLOWED_COMBOS 内) => 治理面自带的
    原子性被路径前缀破坏。
    """
    module = _load(LANE_SCRIPT, "change_lane_check_registry_lane")
    registry_entry = "bin/_registry/scripts/governance/check-change-lane-range.yaml"
    script = "bin/gac/check-change-lane-range.py"

    assert module.classify(registry_entry, submodules=set()) == "governance_code"
    assert module.classify(script, submodules=set()) == "governance_code"

    # 二者同 lane => 「改脚本 + 改登记条目」是单 lane 的原子变更
    lanes = {module.classify(registry_entry, submodules=set()), module.classify(script, submodules=set())}
    assert module.allowed_for(lanes, set()) is True

def test_governance_state_may_share_a_commit_with_docs_lane(tmp_path):
    """治理面 + 文档面可以同交 (2026-10-30 放宽)。

    这是仓内最常见的收口形态 (retro + 台账 + 报告一起交)。实测近 120 个 commit 里,
    该组合占全部违规的 27% —— 规则**从未生效**期间积累的主流模式。
    """
    module = _load(LANE_SCRIPT, "change_lane_check_relaxed")
    lanes = {"docs", "docs_data", "governance_state"}
    assert module.allowed_for(lanes, allowed_lanes=set()) is True


def test_governance_state_still_isolated_from_code_lanes(tmp_path):
    """治理面与**机制面** (code / governance_code / config) 仍必须分开提交。

    放宽只针对文档面 —— 代码变更与治理登记混在一个 commit 仍被判违规 (那才是真该拆的)。
    """
    module = _load(LANE_SCRIPT, "change_lane_check_isolation")
    for extra in ("code", "governance_code", "config"):
        lanes = {"governance_state", extra}
        assert module.allowed_for(lanes, allowed_lanes=set()) is False, lanes


def test_runtime_snapshot_isolation_is_unchanged(tmp_path):
    """runtime_snapshot 的硬隔离不受本次放宽影响 (ADR-0129 §11.3.2 的硬规则)。"""
    module = _load(LANE_SCRIPT, "change_lane_check_runtime")
    assert module.allowed_for({"runtime_snapshot", "docs"}, allowed_lanes=set()) is False
    assert module.allowed_for({"runtime_snapshot", "governance_state"}, allowed_lanes=set()) is False


def test_hook_runner_wires_lane_check_into_pre_commit(tmp_path):
    """pre-commit hook 必须真的调这道尺 (它是 ADR-0122 §46 指定的执行点)。

    2026-10-30 实锤: hook-runner 的 pre-commit 清单里**没有** change-lane-check
    ⇒ 这道尺在本地路径上从未触发 ⇒ 规则从未真正生效过。
    """
    hook_runner = ROOT / "bin" / "gac" / "hook-runner.sh"
    text = hook_runner.read_text(encoding="utf-8")
    assert "change-lane-check" in text, "pre-commit 未接线 lane 尺"
    # 必须带 --staged (判据输入 = 本次提交实际要带上的文件集合)
    assert "bin/change-lane-check.py --staged" in text
    # 必须是 blocking (run_check 第 3 参 = true)
    assert 'run_check "change-lane-check"' in text
    assert '"$py run --profile pyyaml -- bin/change-lane-check.py --staged" true' in text
