"""system.yaml 的写面跟随 profile 声明的 state 根，读面同相对路径优先 state 根。

契约: `.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md` (D1/D3/D4)
BET: BET-Y2Q4-T10-220

判据分三层，缺一层就会留下"测试绿着但写面断裂"的缝:
- **落点**: 声明 profile 后写者真正落在 state 根，且检出的跟踪快照逐字节未变
  (C1/C3/C4)。只断言"解析结果等于某路径"不够 —— 那测的是字符串，不是写面。
- **兜底**: 未声明 profile 时路径与历史布局逐字节相同 (D1 不变量)。
- **边界**: 检出根拼法的残留点必须是一份**看过眼**的清单，不能靠记忆 (C8)。
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
STATE_REL = ".omo/state/system.yaml"
CHECKOUT_SNAPSHOT = ROOT / STATE_REL
STATE_ROOT_ENV = "OMOSTATION_STATE_ROOT"


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def repo_root():
    return _load("write_plane_repo_root", "bin/lib/repo_root.py")


@pytest.fixture
def declared_state_root(tmp_path, monkeypatch):
    """声明一个与检出分离的 state 根，并在其中备好一份完整镜像。

    镜像必须是**完整**的一份: 实测所有写者对 state 根缺失的文件都是跳过或抛错
    (compass_radar / harness-bridge / self-evolution / evidence-smoke 跳过,
    cmd_state_set 报错, write_system_projection_fields 抛 FileNotFoundError),
    所以 state 根那份一旦出现就是全集, 读者按文件级偏好读它是安全的。
    """
    state_root = tmp_path / "state"
    target = state_root / STATE_REL
    target.parent.mkdir(parents=True)
    target.write_text(
        yaml.dump({"health_score": 10, "harness": {"total_runs": 1}}, allow_unicode=True),
        encoding="utf-8",
    )
    monkeypatch.setenv(STATE_ROOT_ENV, str(state_root))
    monkeypatch.delenv("OMOSTATION_ROOT", raising=False)
    return state_root


@pytest.fixture
def undeclared(monkeypatch):
    monkeypatch.delenv(STATE_ROOT_ENV, raising=False)
    monkeypatch.delenv("OMOSTATION_ROOT", raising=False)


# ── state_file_read: 相对路径解析器的三态 ──────────────────────────────


def test_state_file_read_without_profile_stays_at_checkout(repo_root, tmp_path, undeclared):
    got = repo_root.state_file_read(STATE_REL, root=tmp_path)
    assert got == tmp_path / STATE_REL


def test_state_file_read_prefers_state_root_copy_then_falls_back(repo_root, declared_state_root, tmp_path):
    checkout = tmp_path / "checkout"
    (checkout / Path(STATE_REL).parent).mkdir(parents=True)
    (checkout / STATE_REL).write_text("checkout", encoding="utf-8")

    mirror = declared_state_root / STATE_REL
    assert repo_root.state_file_read(STATE_REL, root=checkout) == mirror

    mirror.unlink()
    assert repo_root.state_file_read(STATE_REL, root=checkout) == checkout / STATE_REL


def test_state_file_read_never_hijacks_a_foreign_checkout(repo_root, tmp_path, undeclared):
    """未声明 profile 时，即使 host state 根真的存在同名文件也不得劫持 tmp 检出。

    这是 `state_file_read` 只在 env 显式声明时才去探 state 根的全部理由 ——
    fixture 传的 tmp root 和 state_root()（真实检出）是两个不同目录。
    """
    assert (ROOT / STATE_REL).is_file()  # host 上确实有那份跟踪快照
    victim = tmp_path / "foreign"
    assert repo_root.state_file_read(STATE_REL, root=victim) == victim / STATE_REL


# ── 写者解析: 四个写点一律经 state 根 ─────────────────────────────────


WRITERS = [
    ("compass_radar", "bin/compass_radar.py"),
    ("harness_omo_bridge", "bin/gac/harness-omo-bridge.py"),
    ("self_evolution_loop", "bin/gac/self-evolution-loop.py"),
]

EVIDENCE_WRITER = ("evidence_smoke", "bin/gac/evidence-smoke.py")


@pytest.mark.parametrize("name,rel", WRITERS)
def test_writer_target_follows_declared_state_root(name, rel, declared_state_root, repo_root):
    module = _load(f"w_{name}", rel)
    assert module._system_yaml() == declared_state_root / STATE_REL


@pytest.mark.parametrize("name,rel", WRITERS)
def test_writer_target_is_byte_identical_to_legacy_layout_without_profile(
    name, rel, undeclared, repo_root
):
    module = _load(f"u_{name}", rel)
    assert module._system_yaml() == repo_root.code_root() / STATE_REL


def test_evidence_smoke_writer_shares_the_target(declared_state_root, repo_root):
    """evidence-smoke 是既有 state 根写者，新四写点必须与它同一个解析，不能平行第二套。"""
    name, rel = EVIDENCE_WRITER
    module = _load(f"e_{name}", rel)
    assert module._system_yaml() == declared_state_root / STATE_REL


# ── 真实落点: 写进行、检出不脏 ─────────────────────────────────────────


def test_compass_sync_lands_in_state_root_and_leaves_checkout_untouched(
    declared_state_root, monkeypatch
):
    module = _load("cr_landing", "bin/compass_radar.py")
    monkeypatch.setattr(
        module, "build_system_projection_updates", lambda _ws, _report: {"health_score": 77}
    )
    before = CHECKOUT_SNAPSHOT.read_bytes()

    module.sync_system_yaml(
        ws_root=ROOT,
        health_score=77,
        governance_anomaly_score=0,
        service_online_ratio=1.0,
        generated_at="2026-10-02T00:00:00Z",
    )

    data = yaml.safe_load((declared_state_root / STATE_REL).read_text(encoding="utf-8"))
    assert data["health_score"] == 77  # 正向落点断言，不是"检出里没有"
    assert CHECKOUT_SNAPSHOT.read_bytes() == before


def test_compass_skips_absent_mirror_without_fabricating_one(tmp_path, monkeypatch, undeclared):
    """state 根那份不存在时跳过: 凭空造一份缺字段镜像会让读者读到"新"状态。"""
    monkeypatch.setenv(STATE_ROOT_ENV, str(tmp_path / "empty-state"))
    module = _load("cr_skip", "bin/compass_radar.py")
    before = CHECKOUT_SNAPSHOT.read_bytes()

    module.sync_system_yaml(
        ws_root=ROOT,
        health_score=1,
        governance_anomaly_score=0,
        service_online_ratio=1.0,
        generated_at="2026-10-02T00:00:00Z",
    )

    assert not (tmp_path / "empty-state" / STATE_REL).exists()
    assert CHECKOUT_SNAPSHOT.read_bytes() == before


def test_harness_closeout_skips_absent_mirror(tmp_path, monkeypatch, undeclared):
    monkeypatch.setenv(STATE_ROOT_ENV, str(tmp_path / "empty-state"))
    module = _load("hob_skip", "bin/gac/harness-omo-bridge.py")
    monkeypatch.setattr(module, "OMO_GOVERNANCE_DATA", tmp_path / "gd.json")
    before = CHECKOUT_SNAPSHOT.read_bytes()

    _errors, warnings = module.sync_harness_closeout(run_id="r")

    assert any("system.yaml" in w for w in warnings)
    assert not (tmp_path / "empty-state" / STATE_REL).exists()
    assert CHECKOUT_SNAPSHOT.read_bytes() == before


def test_harness_closeout_lands_in_state_root(tmp_path, declared_state_root, monkeypatch):
    module = _load("hob_landing", "bin/gac/harness-omo-bridge.py")
    monkeypatch.setattr(module, "OMO_GOVERNANCE_DATA", tmp_path / "gd.json")
    before = CHECKOUT_SNAPSHOT.read_bytes()

    errors, _warnings = module.sync_harness_closeout(run_id="r")

    assert errors == []
    data = yaml.safe_load((declared_state_root / STATE_REL).read_text(encoding="utf-8"))
    assert data["harness"]["last_run"] == "r"
    assert CHECKOUT_SNAPSHOT.read_bytes() == before


# ── R-GOV-2 去同义反复: 证据键不再被复制 ───────────────────────────────


def test_compass_no_longer_copies_health_score_into_evidence_keys():
    """D2: `health_score_evidence = health_score` 是自证式指标，删。

    lint 侧 R-GOV-2 只 WARN，所以"诚实"不会把门禁跑红；这里用源码扫描钉住不回退，
    因为 monkeypatch 掉投影构造函数的那条路径根本不会碰到这三行。
    """
    source = (ROOT / "bin" / "compass_radar.py").read_text(encoding="utf-8")
    assert 'data["health_score_evidence"] = updates["health_score"]' not in source
    assert 'health_score_evidence (synced)"' not in source


# ── 读者偏好: 门禁读到运行态，不是上次提交快照 ─────────────────────────


def test_reader_prefers_the_state_root_copy(declared_state_root):
    (declared_state_root / STATE_REL).write_text(
        yaml.dump({"health_score": 91}, allow_unicode=True), encoding="utf-8"
    )
    module = _load("gcl_reader", "bin/gac/governance-convergence-lint.py")
    checkout_value = yaml.safe_load(CHECKOUT_SNAPSHOT.read_text(encoding="utf-8")).get("health_score")

    assert module._read_system_yaml()["health_score"] == 91
    assert checkout_value != 91  # 检出快照确实还是旧值 —— 读者若留在检出就会量到它


def test_reader_falls_back_to_checkout_snapshot(repo_root, declared_state_root, undeclared):
    module = _load("gcl_fallback", "bin/gac/governance-convergence-lint.py")
    assert module._read_system_yaml() == yaml.safe_load(CHECKOUT_SNAPSHOT.read_text(encoding="utf-8"))


# ── C8: 检出根拼法的残留面是一份看过眼的清单 ──────────────────────────

# 未接线/死码/归档 —— 本轮不扩面，但必须显式在册，防止"以为收敛了"。
CHECKOUT_PINNED_ALLOWLIST = {
    "bin/_archive/migrated_low_value/omo-health.py": "归档副本，不在调用面",
    "bin/_archive/omo-health.py": "归档副本，不在调用面",
    "bin/gac/architecture-check.py": "CORE_DOCS 常量零消费者（死码第三类，T10-220 已决定不为它造判据）",
}

STATE_ROOTED_ANCHORS = {"runtime_state_root", "state_root", "state_file_read", "STATE_ROOT"}
# 相对路径常量 (`Path(".omo") / "state" / "system.yaml`) 的锚点 —— 它不带根，
# 由调用方拼接, 所以不是检出根钉死。
RELATIVE_PATH_ANCHORS = {"Path"}


def _path_segments(node: ast.AST) -> list[ast.AST]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _path_segments(node.left) + _path_segments(node.right)
    return [node]


def _is_checkout_pinned_source(source: str) -> bool:
    """这份源码是否用检出根锚点拼出 system.yaml —— 判据内核, 供逐文件扫描与自证用例共用。

    两种形状都要抓, 缺一种就是假绿:
      * `ws / ".omo" / "state" / "system.yaml"` —— 完整相对面在字面量里
      * `OMO_DIR / "state" / "system.yaml"` —— 根变量已经含 `.omo`, 尾段只剩 `state/…`
        (T10-235 实测: `bin/ssot/ssot-guardian.py:44` 正是这一形, 旧的"整尾"匹配看不见它)
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
            continue
        segs = _path_segments(node)
        if len(segs) < 2 or not isinstance(segs[0], ast.Name | ast.Call):
            continue
        tail = " / ".join(
            str(s.value) for s in segs[1:] if isinstance(s, ast.Constant) and isinstance(s.value, str)
        )
        normalized = tail.replace(" ", "").strip("/")
        if not normalized.endswith("state/system.yaml"):
            continue
        anchor = segs[0]
        name = anchor.id if isinstance(anchor, ast.Name) else getattr(anchor.func, "id", "")
        if name in STATE_ROOTED_ANCHORS or any(m in name for m in STATE_ROOTED_ANCHORS):
            continue
        if name in RELATIVE_PATH_ANCHORS:
            continue
        return True
    return False


def _checkout_pinned_sites() -> set[str]:
    """bin/**/*.py 里以检出根锚点拼出 .omo/state/system.yaml 的文件。"""
    found: set[str] = set()
    for path in sorted((ROOT / "bin").rglob("*.py")):
        rel = str(path.relative_to(ROOT))
        if rel == "bin/lib/repo_root.py":  # 解析器自身
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        try:
            if _is_checkout_pinned_source(source):
                found.add(rel)
        except SyntaxError:
            continue
    return found


def test_checkout_pinned_detector_fires_on_both_pinned_shapes():
    """检测器须自证: 空绿会让判据在写者没改完时就变绿 (#4606 同族纪律)。"""
    assert _is_checkout_pinned_source('p = ws / ".omo" / "state" / "system.yaml"')
    assert _is_checkout_pinned_source('p = OMO_DIR / "state" / "system.yaml"')
    assert _is_checkout_pinned_source('p = CODE_ROOT / ".omo/state/system.yaml"')


def test_checkout_pinned_detector_does_not_fire_on_seam_or_relative_constant():
    assert not _is_checkout_pinned_source('p = state_file_read(".omo/state/system.yaml", root=ws)')
    assert not _is_checkout_pinned_source('p = state_root() / ".omo" / "state" / "system.yaml"')
    assert not _is_checkout_pinned_source('p = runtime_state_root() / ".omo" / "state" / "system.yaml"')
    assert not _is_checkout_pinned_source('SYSTEM_YAML_REL = Path(".omo") / "state" / "system.yaml"')


def test_checkout_pinned_system_yaml_sites_are_the_reviewed_list():
    """新增检出根拼法 = 让 state 根写面在无人察觉处断裂，必须红在这里。"""
    assert _checkout_pinned_sites() == set(CHECKOUT_PINNED_ALLOWLIST)


def test_allowlist_reasons_point_at_real_files():
    for rel in CHECKOUT_PINNED_ALLOWLIST:
        assert (ROOT / rel).is_file(), rel


def test_state_rooted_writers_are_present_in_bin():
    """反向核对: 判据不能只对残留生效 —— 走 state 根的写者要在册。"""
    rooted = set()
    for path in sorted((ROOT / "bin").rglob("*.py")):
        source = path.read_text(encoding="utf-8", errors="ignore")
        if "runtime_state_root() /" in source or "state_file_read(" in source:
            rooted.add(str(path.relative_to(ROOT)))
    for rel in {
        "bin/compass_radar.py",
        "bin/gac/harness-omo-bridge.py",
        "bin/gac/self-evolution-loop.py",
        "bin/gac/evidence-smoke.py",
        "bin/mof/generate-brief.py",
        "bin/gac/unified-health-score.py",
    }:
        assert rel in rooted, rel


@pytest.mark.parametrize("name,rel", WRITERS)
def test_module_load_is_side_effect_free(name, rel, declared_state_root):
    """import 写者不得创建/改写任何 system.yaml（env 冻在 import 的旧坑）。"""
    state_target = declared_state_root / STATE_REL
    before_bytes = state_target.read_bytes()
    checkout_bytes = CHECKOUT_SNAPSHOT.read_bytes()

    _load(f"side_{name}", rel)

    assert state_target.read_bytes() == before_bytes
    assert CHECKOUT_SNAPSHOT.read_bytes() == checkout_bytes
