"""ADR-0456 B1 残留: bin/ 的 profile 写面默认值必须在**调用时刻**解析, 不得在 import 时冻结.

契约: `.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md`
方案判据: `grep -rE "DEFAULT_(EVENT_)?LEDGER\\s*=" bin/` → 0 命中
BET: BET-Y2Q4-T10-232
spec: `docs/superpowers/specs/2026-10-05-b1-import-time-ledger-constants-call-time.md`

判据分四层, 缺一层就留下"测试绿着但写面冻结"的缝 (T10-203 的假绿正是缺第 4 层):
- **时机**: 模块在 profile 未声明时 import, 之后才声明 → 默认值必须跟到新根 (I5)。
  现有 profile 用例一律 setenv 之后才 exec_module, 恰好绕开冻结窗口。
- **等价**: 未声明 profile 时解析结果与历史布局逐字节相同 (I3)。
- **显式优先**: 显式传参时解析器一次都不被调用 (I2)。
- **自证**: 源码扫描按 **resolver** 匹配 (含 import 别名与 `repo_root.x()` 属性写法),
  resolver 集合由 repo_root 的**行为**导出而非手写名单, 且按合成违规样本证明它会点名
  文件+行+变量 (I4)。空绿不等于通过。
"""

from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bin" / "lib"))

import repo_root  # noqa: E402

STATE_ENV = "OMOSTATION_STATE_ROOT"
LEDGER_ENV = "OMO_EVENT_LEDGER_DB"
PROFILE_ENVS = ("OMOSTATION_ROOT", STATE_ENV, LEDGER_ENV, "OMOSTATION_PROFILE")
SENTINELS = {STATE_ENV: "/sentinel/state-root", LEDGER_ENV: "/sentinel/ledger.sqlite3"}

CHECKOUT = repo_root.code_root()

# (相对路径, 调用时刻解析器) —— 8 处 ledger + 5 处 state 根写面
LEDGER_ENTRIES = [
    ("bin/bc-os/north_star_meter_v2.py", "_default_ledger"),
    ("bin/bc-os/north_star_meter_v3.py", "_default_event_ledger"),
    ("bin/bc-os/weekly-value-report.py", "_default_event_ledger"),
    ("bin/gac/compound-attribution-report.py", "_default_ledger"),
    ("bin/gac/check-episode-pipeline.py", "_default_db"),
    ("bin/ssot/episode-source-aggregator.py", "_default_ledger"),
    ("bin/ssot/resident-orchestrator-daemon.py", "_default_ledger"),
    ("bin/ssot/system-health-check.py", "_default_ledger"),
]
STATE_ENTRIES = [
    ("bin/gac/evidence-smoke.py", "_output_dir"),
    ("bin/gac/task-inventory.py", "_snap_dir"),
    ("bin/gac/task-inventory.py", "_drifts_path"),
    ("bin/mof/generate-brief.py", "_system_yaml"),
    ("bin/gac/omo-state-write-guard.py", "_system_yaml"),
]

# 未声明 profile 时的历史布局 (逐字节判据, 与被测解析器的写法无关)
LEGACY_SUFFIXES = {
    ("bin/bc-os/north_star_meter_v2.py", "_default_ledger"): "runtime/omo/event-ledger.sqlite3",
    ("bin/bc-os/north_star_meter_v3.py", "_default_event_ledger"): "runtime/omo/event-ledger.sqlite3",
    ("bin/bc-os/weekly-value-report.py", "_default_event_ledger"): "runtime/omo/event-ledger.sqlite3",
    ("bin/gac/compound-attribution-report.py", "_default_ledger"): "runtime/omo/event-ledger.sqlite3",
    ("bin/gac/check-episode-pipeline.py", "_default_db"): "runtime/omo/event-ledger.sqlite3",
    ("bin/ssot/episode-source-aggregator.py", "_default_ledger"): "runtime/omo/event-ledger.sqlite3",
    ("bin/ssot/resident-orchestrator-daemon.py", "_default_ledger"): "runtime/omo/event-ledger.sqlite3",
    ("bin/ssot/system-health-check.py", "_default_ledger"): "runtime/omo/event-ledger.sqlite3",
    ("bin/gac/evidence-smoke.py", "_output_dir"): ".omo/_delivery/evidence-smoke",
    ("bin/gac/task-inventory.py", "_snap_dir"): "runtime/task-inventory/snapshots",
    ("bin/gac/task-inventory.py", "_drifts_path"): "runtime/task-inventory/drifts.jsonl",
    ("bin/mof/generate-brief.py", "_system_yaml"): ".omo/state/system.yaml",
    ("bin/gac/omo-state-write-guard.py", "_system_yaml"): ".omo/state/system.yaml",
}


def _undeclare(monkeypatch) -> None:
    for name in PROFILE_ENVS:
        monkeypatch.delenv(name, raising=False)


def _load(rel: str, name: str, monkeypatch):
    """在 profile **未声明**时 import —— 正是冻结常量能存活的那个窗口。"""
    _undeclare(monkeypatch)
    spec = importlib.util.spec_from_file_location(name, CHECKOUT / rel)
    assert spec and spec.loader, rel
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# ── I4: 检测器 (按 resolver 匹配, 别名感知, 含传递闭包) ────────────────


def _restore(saved: dict[str, str | None]) -> None:
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _profile_resolvers() -> set[str]:
    """从 repo_root 的**行为**导出 profile 解析器集合, 不手写名单。

    手写名单正是 T10-203 假绿的形状: 判据与被检对象共享同一个失效方式 (变量名 /
    连字符-下划线拼写), 于是改名或漏一个就静默变绿。

    ⚠️ 探测不得依赖 host 状态: `canonical_root()` 在没有 `~/Workspace` 的机器 (CI
    干净检出) 上抛 RuntimeError —— 实测让本文件 5 个用例在 `governance-verify` 里红
    而本地 42 全绿。两侧都把规范检出钉成**被测检出** (它按构造含 MARKER), 于是
    canonical_root 同值不入集合, 而 profile 声明面的位移仍由 SENTINELS 观测。
    """
    probed = (*SENTINELS, "OMOSTATION_ROOT")
    saved = {key: os.environ.get(key) for key in probed}
    resolvers: set[str] = set()
    try:
        for name in repo_root.__all__:
            fn = getattr(repo_root, name, None)
            if not callable(fn):
                continue
            os.environ["OMOSTATION_ROOT"] = str(CHECKOUT)
            os.environ.update(SENTINELS)
            try:
                declared = fn()
            except TypeError:
                continue  # 需要参数的 API 不参与零参探测
            _restore(saved)
            os.environ["OMOSTATION_ROOT"] = str(CHECKOUT)
            try:
                undeclared = fn()
            except TypeError:
                continue
            if isinstance(declared, Path) and declared != undeclared:
                resolvers.add(name)
    finally:
        _restore(saved)
    return resolvers


def _aliases(tree: ast.Module) -> dict[str, str]:
    """`from repo_root import state_root as runtime_state_root` → {别名: 真名}。"""
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("repo_root"):
            for alias in node.names:
                out[alias.asname or alias.name] = alias.name
    return out


def _called_names(node: ast.AST) -> set[str]:
    """被调用的名字, 含 `repo_root.state_root()` 的属性写法。"""
    names: set[str] = set()
    for call in (c for c in ast.walk(node) if isinstance(c, ast.Call)):
        if isinstance(call.func, ast.Name):
            names.add(call.func.id)
        elif isinstance(call.func, ast.Attribute):
            names.add(call.func.attr)
    return names


def _referenced_names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _frozen_write_targets(scan_root: Path, resolvers: set[str]) -> set[str]:
    """模块级赋值若在 import 时经 profile resolver 求值 (直接或间接), 返回 file:line:name。"""
    hits: set[str] = set()
    for path in sorted(scan_root.rglob("*.py")):
        rel = str(path.relative_to(scan_root))
        if rel.endswith("repo_root.py"):  # 解析器自身
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        alias = _aliases(tree)
        frozen: set[str] = set()
        for _ in range(6):  # 传递闭包: 引用已冻结常量的赋值同样冻结
            grew = False
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if not targets or any(t in frozen for t in targets):
                    continue
                called = {alias.get(n, n) for n in _called_names(node.value)}
                direct = bool(called & resolvers)
                transitive = bool(_referenced_names(node.value) & frozen)
                if direct or transitive:
                    for target in targets:
                        frozen.add(target)
                        hits.add(f"{rel}:{node.lineno}:{target}")
                        grew = True
            if not grew:
                break
    return hits


def test_profile_resolver_list_is_derived_from_repo_root_behaviour():
    resolvers = _profile_resolvers()
    assert {"state_root", "event_ledger_path"} <= resolvers, resolvers
    # 读根跟随当前检出是 ADR-0456 的规则, 不是缺陷 ⇒ 检测器只许盯 profile 根
    for code_face in ("code_root", "canonical_root", "install_root"):
        assert code_face not in resolvers, code_face


def test_resolver_probe_survives_a_machine_without_canonical_checkout(
    tmp_path, monkeypatch
):
    """探测不得依赖 host 状态: CI 干净检出没有 `~/Workspace`。

    实证 (PR #4651, `governance-verify`): 本文件本地 42 全绿、CI 5 红, 根因是探测
    调 `canonical_root()` 而它抛 `RuntimeError`。这类"本地绿/CI 红"若只靠改窄断言或
    给 CI 步骤加特例处置, 门禁就退化成对某台机器的记忆。
    """
    baseline = _profile_resolvers()
    for key in PROFILE_ENVS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert not (Path.home() / repo_root.MARKER).is_file(), "fixture 没造出 CI 那台机器"
    assert _profile_resolvers() == baseline
    for key in PROFILE_ENVS:
        assert os.environ.get(key) is None, (key, "探测结束必须把环境还原干净")


def test_resolver_probe_notifies_when_a_code_face_root_starts_reading_profile(monkeypatch):
    """变异对照: 钉住 `OMOSTATION_ROOT` 不得把探测变成"按构造就绿"。

    若有人把 `canonical_root()` 翻成读 profile 写根 (正是 B4b 要避免的静默改道),
    探测仍要点名它 —— 否则"读根不入集合"这条断言只是构造出来的绿。
    """
    monkeypatch.setattr(repo_root, "canonical_root", lambda: repo_root.state_root() / "moved")
    assert "canonical_root" in _profile_resolvers()


def test_freeze_detector_names_file_line_and_variable_on_synthetic_violation(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text(
        "from repo_root import state_root\n"
        "\n"
        'FROZEN = state_root() / "a"\n'
        'DERIVED = FROZEN / "b"\n'
        "MERELY_REFERENCED = state_root  # 引用而非调用, 不在 import 时求值\n",
        encoding="utf-8",
    )
    found = _frozen_write_targets(tmp_path, {"state_root"})
    assert any(h.endswith("bad.py:3:FROZEN") for h in found), found
    assert any(h.endswith("bad.py:4:DERIVED") for h in found), found  # 传递闭包
    assert len(found) == 2, found


def test_freeze_detector_follows_import_aliases(tmp_path):
    """bin/ 实际写法是 `state_root as runtime_state_root` —— 只按真名匹配会静默漏掉。"""
    aliased = tmp_path / "aliased.py"
    aliased.write_text(
        "from repo_root import state_root as runtime_state_root\n"
        "\n"
        'OUTPUT_DIR = runtime_state_root() / ".omo" / "_delivery" / "x"\n',
        encoding="utf-8",
    )
    found = _frozen_write_targets(tmp_path, _profile_resolvers())
    assert any(h.endswith("aliased.py:3:OUTPUT_DIR") for h in found), found


def test_freeze_detector_does_not_flag_code_face_constants(tmp_path):
    """反向断言: 检测器过宽同样会假绿 (把 20 个读根常量全塞进允许清单)。"""
    good = tmp_path / "good.py"
    good.write_text(
        "from repo_root import code_root\n"
        "\n"
        "WORKSPACE = code_root()\n"
        'REGISTRY = WORKSPACE / ".omo" / "state" / "task-registry.yaml"\n',
        encoding="utf-8",
    )
    assert _frozen_write_targets(tmp_path, _profile_resolvers()) == set()


def test_no_module_level_profile_root_constant_left_in_bin():
    assert _frozen_write_targets(CHECKOUT / "bin", _profile_resolvers()) == set()


# 改前基线的**逐字**模块级赋值 (2026-10-05 由 `git show origin/main:<f>` 抽出并计数:
# 13 处直接调用 profile resolver + 1 处传递依赖 = 14)。I4-③ 要求"本轮基线读数为 14"是一条
# 断言, 不是记忆里的一个数字 —— 检测器若少认一种形状 (别名、传递、`LEDGER` 这种不规则命名),
# 计数当场不等于 14, 而"修复后为 0"照样绿。
PREFIX_BASELINE = [
    (
        "bin/bc-os/north_star_meter_v2.py",
        "from repo_root import event_ledger_path\n\nDEFAULT_LEDGER = event_ledger_path()\n",
    ),
    (
        "bin/bc-os/north_star_meter_v3.py",
        "from repo_root import event_ledger_path\n\nDEFAULT_EVENT_LEDGER = event_ledger_path()\n",
    ),
    (
        "bin/bc-os/weekly-value-report.py",
        "from repo_root import event_ledger_path\n\nDEFAULT_EVENT_LEDGER = event_ledger_path()\n",
    ),
    (
        "bin/gac/compound-attribution-report.py",
        "from repo_root import event_ledger_path\n\nDEFAULT_LEDGER = event_ledger_path()\n",
    ),
    (
        "bin/gac/check-episode-pipeline.py",
        "from repo_root import event_ledger_path\n\nDEFAULT_DB = event_ledger_path()\n",
    ),
    (
        "bin/ssot/resident-orchestrator-daemon.py",
        "from repo_root import event_ledger_path\n\nDEFAULT_LEDGER = event_ledger_path()\n",
    ),
    (
        "bin/ssot/episode-source-aggregator.py",
        "from repo_root import event_ledger_path\n\nDEFAULT_LEDGER = event_ledger_path()\n",
    ),
    (
        "bin/ssot/system-health-check.py",
        "from repo_root import event_ledger_path\n\nLEDGER = event_ledger_path()\n",
    ),
    (
        "bin/gac/evidence-smoke.py",
        "from repo_root import state_root as runtime_state_root\n\n"
        'OUTPUT_DIR = runtime_state_root() / ".omo" / "_delivery" / "evidence-smoke"\n',
    ),
    (
        "bin/gac/task-inventory.py",
        "from repo_root import state_root as runtime_state_root\n\n"
        'SNAP_DIR = runtime_state_root() / "runtime" / "task-inventory" / "snapshots"\n'
        'DRIFTS = runtime_state_root() / "runtime" / "task-inventory" / "drifts.jsonl"\n',
    ),
    (
        "bin/mof/generate-brief.py",
        "from repo_root import state_root as runtime_state_root\n\n"
        'SYSTEM_YAML = runtime_state_root() / ".omo" / "state" / "system.yaml"\n',
    ),
    (
        # 传递形状: SYSTEM_YAML 的值不调用 resolver, 只引用同文件已冻结的 STATE_ROOT
        "bin/gac/omo-state-write-guard.py",
        "from repo_root import code_root, state_root\n\n"
        'SYSTEM_YAML_REL = ".omo/state/system.yaml"\n'
        "WORKSPACE = code_root()\n"
        "STATE_ROOT = state_root()\n"
        'SYSTEM_YAML = STATE_ROOT / ".omo" / "state" / "system.yaml"\n'
        "WRITE_OWNERS_YAML = WORKSPACE / '.omo' / '_truth' / 'registry' / 'write-owners.yaml'\n",
    ),
]


def test_detector_counts_the_14_prefix_baseline_violations(tmp_path):
    root = tmp_path / "prefix"
    for rel, source in PREFIX_BASELINE:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")

    found = _frozen_write_targets(root / "bin", _profile_resolvers())
    assert len(found) == 14, sorted(found)
    # 逐名核对: 计数对不等于认对了对象 (少认一个别名形状 + 多认一个 code 面也能凑成 14)
    assert {h.rsplit(":", 1)[1] for h in found} == {
        "DEFAULT_LEDGER", "DEFAULT_EVENT_LEDGER", "DEFAULT_DB", "LEDGER",
        "OUTPUT_DIR", "SNAP_DIR", "DRIFTS", "SYSTEM_YAML", "STATE_ROOT",
    }, sorted(found)
    # 同一棵树里的 code 面一行都不许被算进来
    assert not any("WRITE_OWNERS_YAML" in h or "WORKSPACE" in h for h in found), found

    # 基线 14 → 修复后 0, 两个读数都由同一次扫描产出
    assert _frozen_write_targets(CHECKOUT / "bin", _profile_resolvers()) == set()


def test_plan_criterion_literal_grep_zero_hits_and_pattern_is_not_inert():
    pattern = re.compile(r"DEFAULT_(EVENT_)?LEDGER\s*=")
    assert pattern.search("DEFAULT_LEDGER = event_ledger_path()"), "判据模式本身失效 (T10-203 形状)"
    hits = [
        f"{p.relative_to(CHECKOUT)}:{i}"
        for p in sorted((CHECKOUT / "bin").rglob("*.py"))
        for i, line in enumerate(p.read_text(errors="ignore").splitlines(), 1)
        if pattern.search(line)
    ]
    assert hits == []


# ── I5: 时机 —— profile 在 import 之后才声明 ──────────────────────────


@pytest.mark.parametrize("rel,resolver", LEDGER_ENTRIES)
def test_ledger_default_follows_db_declared_after_import(rel, resolver, tmp_path, monkeypatch):
    module = _load(rel, f"b1_ledger_{resolver}_{Path(rel).stem}".replace("-", "_"), monkeypatch)
    db = tmp_path / "declared-later.sqlite3"
    monkeypatch.setenv(LEDGER_ENV, str(db))
    assert getattr(module, resolver)() == db


@pytest.mark.parametrize("rel,resolver", STATE_ENTRIES)
def test_state_write_target_follows_profile_declared_after_import(rel, resolver, tmp_path, monkeypatch):
    module = _load(rel, f"b1_state_{resolver}_{Path(rel).stem}".replace("-", "_"), monkeypatch)
    state_root = tmp_path / "state"
    monkeypatch.setenv(STATE_ENV, str(state_root))
    assert getattr(module, resolver)().is_relative_to(state_root)


def test_code_face_bindings_stay_on_the_checkout(tmp_path, monkeypatch):
    """一个移 + 一个不移: 读面留在检出侧是 ADR-0456 的规则, 跟着移到 state 根就是回归。"""
    smoke = _load("bin/gac/evidence-smoke.py", "b1_codeface_smoke", monkeypatch)
    inventory = _load("bin/gac/task-inventory.py", "b1_codeface_inventory", monkeypatch)
    state_root = tmp_path / "state"
    monkeypatch.setenv(STATE_ENV, str(state_root))
    assert smoke.WORKSPACE == CHECKOUT
    assert smoke.GOV_LOG == CHECKOUT / ".omo" / "_knowledge" / "governance-history.jsonl"
    assert smoke.EVENTS_LOG == CHECKOUT / ".omo" / "_knowledge" / "omo-events.jsonl"
    assert inventory.REGISTRY == CHECKOUT / ".omo" / "state" / "task-registry.yaml"
    assert smoke._output_dir().is_relative_to(state_root)
    assert inventory._snap_dir().is_relative_to(state_root)


# ── I3: 等价 —— 未声明 profile 时逐字节等于历史布局 ────────────────────


@pytest.mark.parametrize("rel,resolver", LEDGER_ENTRIES + STATE_ENTRIES)
def test_undeclared_profile_keeps_the_legacy_path_string(rel, resolver, monkeypatch):
    module = _load(rel, f"b1_legacy_{resolver}_{Path(rel).stem}".replace("-", "_"), monkeypatch)
    expected = CHECKOUT / LEGACY_SUFFIXES[(rel, resolver)]
    assert str(getattr(module, resolver)()) == str(expected)


# ── I2: 显式优先 —— 传参时解析器一次都不被调用 ─────────────────────────


@pytest.mark.parametrize(
    ("rel", "entry", "kwargs"),
    [
        ("bin/bc-os/north_star_meter_v2.py", "measure_value_truth", {"principal_id": "sp-x"}),
        ("bin/bc-os/north_star_meter_v3.py", "measure_journey_completion", {}),
        ("bin/bc-os/north_star_meter_v3.py", "measure_revision_rate", {}),
    ],
)
def test_explicit_db_path_short_circuits_the_resolver(rel, entry, kwargs, tmp_path, monkeypatch):
    module = _load(rel, f"b1_explicit_{Path(rel).stem}", monkeypatch)
    calls: list[str] = []

    def _spy() -> Path:
        calls.append("called")
        return Path("/sentinel/must-not-be-used.sqlite3")

    for name in ("event_ledger_path", "state_root", "runtime_state_root"):
        if hasattr(module, name):
            monkeypatch.setattr(module, name, _spy)
    getattr(module, entry)(db_path=tmp_path / "explicit.sqlite3", **kwargs)
    assert calls == [], f"{entry} 在显式传参时仍调用了解析器: {calls}"


# ── I5: 真实运行落点 (断言由一次真实运行产出, 不是改窄用例) ────────────


def test_check_ledger_run_opens_the_db_declared_after_import(tmp_path, monkeypatch):
    """落点判据是「被打开的路径」本身, 不是消息文案 —— 0 字节文件是合法空库, 返回 ledger ok。"""
    health = _load("bin/ssot/system-health-check.py", "b1_run_health", monkeypatch)
    monkeypatch.setenv(LEDGER_ENV, str(tmp_path / "absent.sqlite3"))
    assert health._check_ledger() == (False, "event-ledger.sqlite3 missing")

    declared = tmp_path / "declared-after-import.sqlite3"
    declared.write_bytes(b"")
    monkeypatch.setenv(LEDGER_ENV, str(declared))

    sys.path.insert(0, str(health.WORKSPACE / "projects" / "omo" / "src"))
    from omo.event_ledger.broker import LedgerBroker

    opened: list[str] = []

    class _Stub:
        def verify_chain(self):
            return {"ok": True}

        def close(self):
            return None

    def _connect(path, *args, **kwargs):
        opened.append(str(path))
        return _Stub()

    monkeypatch.setattr(LedgerBroker, "connect", staticmethod(_connect))
    ok, msg = health._check_ledger()

    assert (ok, msg) == (True, "ledger ok"), msg
    # 冻结常量的形状: 它按声明前的根打开另一份台账, 这条逐路径断言当场红
    assert opened == [str(declared)], opened


def test_measure_value_truth_run_uses_the_db_declared_after_import(tmp_path, monkeypatch):
    v2 = _load("bin/bc-os/north_star_meter_v2.py", "b1_run_v2", monkeypatch)
    db = tmp_path / "late.sqlite3"
    db.write_bytes(b"")  # 存在但不是账本 ⇒ 只有真打开了它才会得到 not_ready
    monkeypatch.setenv(LEDGER_ENV, str(db))
    report = v2.measure_value_truth(principal_id="sp-x")
    assert report["status"] == "not_ready", report


def test_task_inventory_run_writes_artifacts_into_state_root_declared_after_import(tmp_path, monkeypatch):
    inventory = _load("bin/gac/task-inventory.py", "b1_run_inventory", monkeypatch)
    registry = tmp_path / "registry.yaml"
    registry.write_text("tasks:\n  - id: T1\n    title: demo\n    status: planned\n", encoding="utf-8")
    monkeypatch.setattr(inventory, "REGISTRY", registry)
    state_root = tmp_path / "state"
    monkeypatch.setenv(STATE_ENV, str(state_root))
    argv = list(sys.argv)
    sys.argv = ["task-inventory", "--json"]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            inventory.main()
    finally:
        sys.argv = argv
    snapshots = sorted((state_root / "runtime" / "task-inventory" / "snapshots").glob("*.json"))
    drifts = state_root / "runtime" / "task-inventory" / "drifts.jsonl"
    assert snapshots, "快照没落进 state 根"
    assert drifts.is_file() and drifts.read_text().strip(), "drifts 没落进 state 根"


def test_generate_brief_run_reads_system_yaml_from_state_root_declared_after_import(tmp_path, monkeypatch):
    brief = _load("bin/mof/generate-brief.py", "b1_run_brief", monkeypatch)
    state_root = tmp_path / "state"
    (state_root / ".omo" / "state").mkdir(parents=True)
    (state_root / ".omo" / "state" / "system.yaml").write_text(
        "health_score: 77\ngovernance_anomaly_score: 88\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(STATE_ENV, str(state_root))
    content = brief.generate_brief_content()
    assert "77" in content and "88" in content, content[:400]


def test_evidence_smoke_writer_targets_the_call_time_output_dir(monkeypatch):
    """run_smoke 的落盘目标经 _output_dir() 取, 模块级 OUTPUT_DIR 不复存在。"""
    source = (CHECKOUT / "bin/gac/evidence-smoke.py").read_text(encoding="utf-8")
    smoke = _load("bin/gac/evidence-smoke.py", "b1_smoke_writer", monkeypatch)
    assert not hasattr(smoke, "OUTPUT_DIR")
    body = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == "run_smoke"
    )
    assert any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_output_dir"
        for node in ast.walk(body)
    ), "run_smoke 不再经 _output_dir() 取写面 ⇒ 写面可能回到冻结常量"
