"""`.omo/state/system.yaml` 创建者的四条硬约束 (I1–I4) + 摘库后的落点与接线。

契约: `.omo/superpowers` 侧 spec
      `docs/superpowers/specs/2026-10-07-system-yaml-materializer-untrack.md`
BET: BET-Y2Q4-T10-235

判据形状与 AGENTS.md §7 的四条纪律对齐:
- **树相对**: 派生计数断言「== 同一棵树上 `current-state-coherence.py:_task_counts` 的读数」,
  绝不写死某棵树的具体数字 —— 任务面部分被 gitignore, 抄绝对值就是 host 炸弹。
- **检测器自证**: I1 的键集合相等除了对真实检出跑一次, 还注入合成违规, 证明它不是空绿。
- **正向落点**: 每条「把写目标移走」的契约配一条「新落点确实出现」的断言, 不用否定式当验收。
- **去时钟依赖**: fixture 不写绝对时间戳, 时间类断言一律相对 now。
"""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

STATE_REL = ".omo/state/system.yaml"
WRITE_OWNERS_REL = ".omo/_truth/registry/write-owners.yaml"
STATE_ROOT_ENV = "OMOSTATION_STATE_ROOT"


def _load(name: str, rel: str, root: Path):
    path = root / rel
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def repo_root():
    return _load("materializer_repo_root", "bin/lib/repo_root.py", Path(__file__).resolve().parents[2])


@pytest.fixture(scope="module")
def materializer(repo_root):
    return _load("materialize_system_state", "bin/gac/materialize-system-state.py", repo_root.code_root())


@pytest.fixture(scope="module")
def coherence(repo_root):
    return _load(
        "current_state_coherence_for_materializer",
        "bin/ssot/current-state-coherence.py",
        repo_root.code_root(),
    )


@pytest.fixture
def quiet_state_root(tmp_path, monkeypatch):
    """把 profile 显式声明到一个空目录 —— 没有它, 未声明时写面就是真实检出本身。"""
    state_root = tmp_path / "state"
    monkeypatch.setenv(STATE_ROOT_ENV, str(state_root))
    return state_root


def _checkout_fixture(root: Path, *, counts=(2, 1, 0, 3, 1), declared: set[str] | None = None) -> Path:
    """造一棵最小检出: goals 是双文档 YAML, tasks 面按 counts 铺文件。"""
    active, planned, blocked, done, archived = counts
    omo = root / ".omo"
    for sub, n in (("active", active), ("planned", planned), ("blocked", blocked), ("done", done)):
        d = omo / "tasks" / sub
        d.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            (d / f"task-{sub}-{i}.yaml").write_text(
                f"id: task-{sub}-{i}\ntitle: Title {sub} {i}\n", encoding="utf-8"
            )
    if archived:
        d = omo / "tasks" / "archived" / "done"
        d.mkdir(parents=True, exist_ok=True)
        for i in range(archived):
            (d / f"archived-{i}.yaml").write_text(f"id: archived-{i}\ntitle: Archived {i}\n", encoding="utf-8")
    (omo / "goals").mkdir(parents=True, exist_ok=True)
    (omo / "goals" / "current.yaml").write_text(
        "---\ntype: ssot\n---\nphase: 41\ncurrent_wave: W7\nexecution_mode: rolling\n", encoding="utf-8"
    )
    owners = root / WRITE_OWNERS_REL
    owners.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted(declared if declared is not None else _real_declared_keys())
    owners.write_text(
        yaml.dump({"fields": {STATE_REL: {k: {"owner": "script:test"} for k in keys}}}, allow_unicode=True),
        encoding="utf-8",
    )
    return root


def _real_declared_keys() -> set[str]:
    owners = yaml.safe_load((Path(__file__).resolve().parents[2] / WRITE_OWNERS_REL).read_text(encoding="utf-8"))
    return set(owners["fields"][STATE_REL])


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ── I1: 键集合钉成集合相等 ──────────────────────────────────────────────────────────


def test_materialized_key_set_equals_committed_write_owners(materializer, repo_root, monkeypatch):
    """真实检出上跑一次: 物化器键集合 == write-owners 声明集合 (两边来源不同, 故非按构造绿)。"""
    monkeypatch.delenv(STATE_ROOT_ENV, raising=False)
    report = materializer.build_report(repo_root.code_root())
    assert report["key_set_equals_declared"] is True
    assert report["undeclared"] == []
    assert report["ghost"] == []
    assert report["key_count"] == report["declared_count"] == len(_real_declared_keys())


def test_i1_detector_fires_on_synthetic_violation(materializer, tmp_path, quiet_state_root):
    """检测器自证: 声明面多一个键 ⇒ ghost + rc 1；少一个键 ⇒ undeclared + rc 1。

    没有这一条, 上一句的绿可能只是装置压根没命中 (AGENTS.md §7「空绿代价」)。
    """
    declared = _real_declared_keys()

    over = _checkout_fixture(tmp_path / "over", declared=declared | {"totally_unknown_key"})
    assert materializer.main(["--root", str(over), "--dry-run", "--json"]) == 1

    under = _checkout_fixture(tmp_path / "under", declared=declared - {"self_evolution"})
    assert materializer.main(["--root", str(under), "--dry-run", "--json"]) == 1


def test_missing_committed_truth_is_a_real_error(materializer, tmp_path, quiet_state_root, capsys):
    """摘库后的世界里「文件缺失」必须是真错误, 不能被物化器猜掉 (spec §5 第 2 条的动机)。"""
    root = _checkout_fixture(tmp_path / "tree")
    (root / ".omo" / "goals" / "current.yaml").unlink()
    assert materializer.main(["--root", str(root), "--dry-run", "--json"]) == 1
    assert "missing input" in capsys.readouterr().err

    broken = _checkout_fixture(tmp_path / "broken")
    (broken / ".omo" / "goals" / "current.yaml").write_text("---\ntype: ssot\n", encoding="utf-8")
    assert materializer.main(["--root", str(broken), "--dry-run", "--json"]) == 1


# ── 树相对派生 ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("counts", [(2, 1, 0, 3, 1), (0, 0, 0, 0, 0), (1, 4, 2, 0, 5)])
def test_derived_counts_equal_same_tree_coherence_reading(materializer, coherence, tmp_path, quiet_state_root, counts):
    root = _checkout_fixture(tmp_path / f"tree-{counts}", counts=counts)
    derived = materializer.build_report(root)["derived"]
    theirs = coherence._task_counts(root / ".omo")
    assert derived["active_tasks"] == theirs["active"]
    assert derived["planned_tasks"] == theirs["planned"]
    assert derived["blocked_tasks"] == theirs["blocked"]
    assert derived["completed_tasks"] == theirs["done"]
    assert derived["total_tasks"] == theirs["active"] + theirs["planned"] + theirs["blocked"] + theirs["done"]


def test_derived_counts_match_coherence_on_the_checked_out_tree(materializer, coherence, repo_root, monkeypatch):
    """同一判据在真实检出上再跑一次 —— 该树因 gitignore 差异会与本机活运行态数出不同组数。"""
    monkeypatch.delenv(STATE_ROOT_ENV, raising=False)
    root = repo_root.code_root()
    derived = materializer.build_report(root)["derived"]
    theirs = coherence._task_counts(root / ".omo")
    assert (derived["active_tasks"], derived["planned_tasks"], derived["blocked_tasks"]) == (
        theirs["active"],
        theirs["planned"],
        theirs["blocked"],
    )
    assert derived["completed_tasks"] == theirs["done"]


def test_phase_and_wave_come_from_the_second_yaml_document(materializer, tmp_path, quiet_state_root):
    """goals/current.yaml 是双文档: 值在第二个文档里, safe_load 单文档口径会当场绊倒。"""
    root = _checkout_fixture(tmp_path / "goals")
    derived = materializer.build_report(root)["derived"]
    assert derived["current_phase"] == 41
    assert derived["current_wave"] == "W7"


# ── I2: 落点在调用时刻的 state 根 (正向落点断言) ────────────────────────────────────


def test_undeclared_profile_write_target_is_the_checkout_path(materializer, repo_root, monkeypatch):
    """D1 不变量: 未声明 profile 时逐字节复现历史布局 (纯路径判据, 不落盘)。"""
    monkeypatch.delenv(STATE_ROOT_ENV, raising=False)
    assert materializer.write_target() == repo_root.code_root() / Path(STATE_REL)


def test_write_lands_inside_declared_state_root(materializer, tmp_path, quiet_state_root, repo_root):
    """正向落点: 声明 profile 后文件真的出现在 state 根, 且检出的跟踪快照零改动。"""
    root = _checkout_fixture(tmp_path / "checkout")
    assert materializer.main(["--root", str(root), "--json"]) == 0

    landed = quiet_state_root / STATE_REL
    assert landed.is_file(), "I2: 物化产物必须出现在调用时刻的 state 根"
    doc = yaml.safe_load(landed.read_text(encoding="utf-8"))
    assert set(doc) == _real_declared_keys()

    snapshot = repo_root.code_root() / STATE_REL
    before = _sha(snapshot) if snapshot.is_file() else None
    assert materializer.main(["--root", str(root), "--json"]) == 0
    after = _sha(snapshot) if snapshot.is_file() else None
    assert before == after, "写面泄漏到检出: state 根已声明却动了这份跟踪快照"


def test_write_target_resolves_at_call_time_not_import_time(materializer, tmp_path, monkeypatch):
    """模块导入发生在 env 声明之前 —— 若路径被冻在模块级常量, 这一条会红。"""
    late = tmp_path / "declared-late"
    monkeypatch.setenv(STATE_ROOT_ENV, str(late))
    assert materializer.write_target() == late / Path(STATE_REL)
    assert materializer.main(["--root", str(_checkout_fixture(tmp_path / "late-tree")), "--json"]) == 0
    assert (late / STATE_REL).is_file()


# ── I3: 幂等且不覆盖 ──────────────────────────────────────────────────────────────


def test_second_run_skips_and_preserves_bytes_and_mtime(materializer, tmp_path, quiet_state_root):
    root = _checkout_fixture(tmp_path / "idem")
    target = quiet_state_root / STATE_REL
    assert materializer.main(["--root", str(root), "--json"]) == 0

    sentinel = "written_by: a live producer\nhealth_score: 88\n"
    target.write_text(sentinel, encoding="utf-8")
    digest, mtime = _sha(target), target.stat().st_mtime_ns

    assert materializer.main(["--root", str(root), "--json"]) == 0
    assert target.read_text(encoding="utf-8") == sentinel, "I3: 已存在的活运行态被物化器改写了"
    assert (_sha(target), target.stat().st_mtime_ns) == (digest, mtime)

    assert materializer.main(["--root", str(root), "--force", "--json"]) == 0
    assert sentinel not in target.read_text(encoding="utf-8"), "--force 必须真的重写"


def test_status_reports_dry_run_materialized_and_skipped(materializer, tmp_path, quiet_state_root, capsys):
    root = _checkout_fixture(tmp_path / "status")
    target = quiet_state_root / STATE_REL

    assert materializer.main(["--root", str(root), "--dry-run", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "dry_run"
    assert not target.exists(), "--dry-run 不得落盘"

    assert materializer.main(["--root", str(root), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "materialized"

    assert materializer.main(["--root", str(root), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "skipped"


# ── I4: 原子写入 ──────────────────────────────────────────────────────────────────


def test_atomic_write_leaves_no_temp_and_survives_replace_failure(materializer, tmp_path, quiet_state_root, monkeypatch):
    root = _checkout_fixture(tmp_path / "atomic")
    assert materializer.main(["--root", str(root), "--json"]) == 0
    target = quiet_state_root / STATE_REL
    keep = _sha(target)
    assert list(target.parent.glob(".system.yaml.*")) == [], "I4: 临时文件残留"

    def boom(*_a, **_k):
        raise OSError("replace interrupted")

    monkeypatch.setattr(materializer.os, "replace", boom)
    with pytest.raises(OSError):
        materializer.main(["--root", str(root), "--force", "--json"])
    assert _sha(target) == keep, "半份写入污染了读者可见的文件"
    assert list(target.parent.glob(".system.yaml.*")) == [], "I4: 失败路径未清理临时文件"


# ── 空形取值 (§7.1) ───────────────────────────────────────────────────────────────


def test_generator_owned_keys_get_empty_shape_not_zero(materializer, repo_root, monkeypatch):
    """`null` 而不是 `0`: 一个从未测量被记成一个分数, 健康度门禁会把它读成零分。"""
    monkeypatch.delenv(STATE_ROOT_ENV, raising=False)
    doc = materializer.build_report(repo_root.code_root())["document"]
    for key in materializer.EMPTY_SCALAR_KEYS:
        assert doc[key] is None, f"{key} 不得被物化器写成测量值"
    for key in materializer.EMPTY_MAPPING_KEYS:
        assert doc[key] == {}


def test_updated_at_is_now_utc_not_a_frozen_timestamp(materializer, repo_root, monkeypatch):
    monkeypatch.delenv(STATE_ROOT_ENV, raising=False)
    stamp = materializer.build_report(repo_root.code_root())["document"]["updated_at"]
    parsed = dt.datetime.strptime(str(stamp), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    assert abs((dt.datetime.now(dt.timezone.utc) - parsed).total_seconds()) < 300, (
        "updated_at 必须是物化时刻 —— fixture 写绝对时间戳 × 断言用相对窗口即刻画了时钟炸弹"
    )


# ── §5 第 6 条: 接线可见性 (CI 不点名 = 本地全绿不算交付) ──────────────────────────


def test_unit_suite_is_named_by_ci(repo_root):
    """指认命令的测试化: `git grep -n test_system_yaml_materializer -- .github/workflows/`。"""
    text = (repo_root.code_root() / ".github" / "workflows" / "governance-check.yml").read_text(encoding="utf-8")
    assert "tests/unit/test_system_yaml_materializer.py" in text, (
        "tests/unit/** 不在任何 CI 白名单里, 未点名即本文件只是本地证据"
    )


def test_enforce_workflow_materializes_before_the_check(repo_root):
    """摘库的前置: state-goals-enforce.yml 必须在 coherence 之前物化一次, 否则 rc 2。"""
    lines = (repo_root.code_root() / ".github" / "workflows" / "state-goals-enforce.yml").read_text(
        encoding="utf-8"
    ).splitlines()
    # 只认真正的 `run:` 步骤行 —— 文件头注释也提到 coherence 脚本, 按首次命中会把它当成步骤。
    def step_line(script: str) -> int | None:
        return next(
            (i for i, l in enumerate(lines) if script in l and l.strip().startswith(("- run:", "run:"))),
            None,
        )

    materialize_at = step_line("materialize-system-state.py")
    coherence_at = step_line("current-state-coherence.py")
    assert materialize_at is not None, "摘库后 CI 里没有创建者 → 干净检出必 rc 2"
    assert coherence_at is not None and materialize_at < coherence_at


# ── §5 第 4 条: 仍钉检出根的读者接入 state_file_read 后的落点 ──────────────────────

READER_SENTINEL = """health_score: 88
health_score_ref: runtime/health-sentinel.json
service_online_ratio: 0.77
phase_verdict:
  verdict: sentinel
runtime:
  daemons:
    a: {online: true}
    b: {online: false}
"""


@pytest.fixture
def state_only_tree(tmp_path, monkeypatch):
    """检出侧**没有** system.yaml, 现值只在 state 根 —— 摘库后的真实形状。

    判据必须是正向的: 读者命中 state 根会交出哨兵值, 留在检出根则交不出任何东西。
    用「检出不含该文件」当验收是否定式, 一次物化就会让它假绿 (§7 正向落点纪律)。
    """
    checkout = tmp_path / "checkout"
    state = tmp_path / "state"
    for root in (checkout, state):
        (root / ".omo" / "state").mkdir(parents=True)
    (state / STATE_REL).write_text(READER_SENTINEL, encoding="utf-8")
    monkeypatch.setenv(STATE_ROOT_ENV, str(state))
    assert not (checkout / STATE_REL).exists()
    return checkout, state


def test_guardian_resolves_system_yaml_at_call_time(state_only_tree, repo_root):
    checkout, state = state_only_tree
    code = _load("b5r_guardian", "bin/ssot/ssot-guardian.py", repo_root.code_root())
    assert not hasattr(code, "SYSTEM_YAML")  # 模块级常量会让 profile 冻结在 import 时刻
    assert code.system_yaml_path() == state / STATE_REL
    assert code._load_system_value("health_score") == "88"


def test_meta_compass_radar_write_target_is_the_state_root(state_only_tree, repo_root):
    code = _load("b5r_meta_compass", "bin/meta/compass_radar.py", repo_root.code_root())
    assert code._system_yaml() == state_only_tree[1] / STATE_REL


def test_arch_health_meter_reads_the_state_root_copy(state_only_tree, repo_root, monkeypatch):
    checkout, _ = state_only_tree
    code = _load("b5r_arch_meter", "bin/arch-health-meter.py", repo_root.code_root())
    monkeypatch.setattr(code, "WS", checkout)
    assert code.dim_operations() == {"online": 1, "total": 2, "ratio": 0.5}


def test_check_health_ssot_reads_the_state_root_copy(state_only_tree, repo_root, monkeypatch, capsys):
    checkout, _ = state_only_tree
    code = _load("b5r_check_health", "bin/check_health_ssot.py", repo_root.code_root())
    monkeypatch.setattr(sys, "argv", ["check_health_ssot.py", "--workspace", str(checkout)])
    code.main()
    out = capsys.readouterr()
    joined = out.out + out.err
    assert "system.yaml 不存在" not in joined, "读面仍钉检出 ⇒ 摘库后该检查器对活机器直接报缺失"
    assert "health-sentinel.json" in joined, "health_score_ref 只能来自 state 根那份"


def test_session_recovery_lists_the_state_root_copy(state_only_tree, repo_root, monkeypatch):
    checkout, state = state_only_tree
    code = _load("b5r_session_recovery", "bin/gac/session-recovery.py", repo_root.code_root())
    monkeypatch.setattr(code, "REPO_ROOT", checkout)
    reported = {item["file"] for item in code.get_state_changes()["files"]}
    assert STATE_REL in reported


def test_ssot_watcher_tracks_the_state_root_copy(state_only_tree, repo_root, monkeypatch):
    checkout, state = state_only_tree
    code = _load("b5r_ssot_watcher", "bin/ssot-watcher.py", repo_root.code_root())
    monkeypatch.setattr(code, "WORKSPACE_ROOT", checkout)
    tracked = code.SSOTFile("system_state", STATE_REL)
    assert tracked.path == state / STATE_REL
    assert tracked.exists()


def test_m1_closeout_reads_ratio_from_the_state_root(state_only_tree, repo_root):
    checkout, _ = state_only_tree
    code = _load("b5r_m1_closeout", "bin/gac/m1-closeout-report.py", repo_root.code_root())
    verdict = code.check_g_conv_2_daemon(checkout)
    assert verdict["detail"]["source_fields"]["system.yaml"] == 0.77


def test_panorama_collect_reads_the_state_root_copy(state_only_tree, repo_root, monkeypatch):
    checkout, _ = state_only_tree
    code = _load("b5r_panorama", "bin/panorama/panorama-collect.py", repo_root.code_root())
    monkeypatch.setattr(code, "CODE_ROOT", checkout)
    assert code.collect_phase_verdict() == {"verdict": "sentinel"}
