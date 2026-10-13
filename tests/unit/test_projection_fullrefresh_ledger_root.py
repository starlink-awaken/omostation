"""BET-Y2Q4-T10-247 — projection-full-refresh 的 ledger 根在**调用时刻**解析.

契约: `docs/superpowers/specs/2026-10-12-projection-fullrefresh-ledger-root-seam.md` §3
- ISC-1 落点: 未声明 profile → canonical 检出, 而不是 driver 所在的那个 publisher 克隆。
- ISC-2 声明优先: `OMO_EVENT_LEDGER_DB` / `OMOSTATION_STATE_ROOT` 逐字采用, 与
  `repo_root.event_ledger_path()` 同读数。
- ISC-3 无 import 时冻结: 模块级不存在由 `__file__` 导出的常量 (含传递导出)。
- ISC-4 检测器自证: 合成违规逐个点名, 且「改前 = 2 / 改后 = 0」由同一个扫描器产出。
- ISC-5 子进程同读数: 注入给 publisher 的 `OMO_EVENT_LEDGER_DB` == 解析函数返回值, 且**在声明
  了 profile 的面上**比 —— 未声明时两侧读数与 `__file__` 反推逐字节相同, 那样子写会假绿。
"""

from __future__ import annotations

import ast
import contextlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bin" / "lib"))

import repo_root  # noqa: E402

CHECKOUT = repo_root.code_root()
DRIVER_REL = "bin/panorama/projection-full-refresh.py"
LEDGER_ENV = "OMO_EVENT_LEDGER_DB"
STATE_ENV = "OMOSTATION_STATE_ROOT"
ROOT_ENV = "OMOSTATION_ROOT"
PROFILE_ENVS = (ROOT_ENV, STATE_ENV, LEDGER_ENV, "OMOSTATION_PROFILE",
                "OMOSTATION_PUBLISHER_CHECKOUT", "ZHIXING_DASHBOARD_STATE_ROOT")
LEDGER_SUFFIX = Path("runtime") / "omo" / "event-ledger.sqlite3"

# 改前两行 (origin/main 5895db390 的 :41-:42, 本轮 06:51Z 逐字节核对)。第二行是第一行的
# **传递**导出 —— 直串判定看不见它, 所以「改前 = 2」必须由同一个扫描器数出来。
PRE_FIX_TEXT = (
    'WORKSPACE_ROOT = Path(__file__).resolve().parents[2]\n'
    'EVENT_LEDGER_DB = WORKSPACE_ROOT / "runtime" / "omo" / "event-ledger.sqlite3"\n'
)

# ── seams ─────────────────────────────────────────────────────────────────


@pytest.fixture
def spy(monkeypatch):
    """`subprocess.run` 的替身: 记录调用, 永不真跑 git, 永不联网。"""
    seen: list[tuple[list[str], dict]] = []

    def fake_run(cmd, *args, **kwargs):
        seen.append((list(cmd), kwargs))
        return subprocess.CompletedProcess(list(cmd), 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return seen


def _module_from(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, path
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def _detached_repo_root():
    """让被测模块 import 到**它自己旁边**那份 repo_root, 而不是测试进程已绑定的这份。"""
    saved = sys.modules.pop("repo_root", None)
    try:
        yield
    finally:
        sys.modules["repo_root"] = saved


def _load(name: str, driver_path: Path, monkeypatch, tmp_path: Path, *, detached: bool = False):
    """在 profile **未声明**的窗口里 import, 再把落点全部改指到 tmp。"""
    for env in PROFILE_ENVS:
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "absent-home"))
    monkeypatch.setenv(ROOT_ENV, str(CHECKOUT))
    if detached:
        with _detached_repo_root():
            module = _module_from(name, driver_path)
    else:
        module = _module_from(name, driver_path)
    module.LOCK_PATH = tmp_path / "run" / ".fullrefresh.lock"
    module.LOG_PATH = tmp_path / "run" / "log.jsonl"
    module.CHECKOUT = tmp_path / "clone"
    module.DEPLOY_DIR = tmp_path / "deploy"
    return module


@pytest.fixture
def driver(monkeypatch, tmp_path):
    return _load("t247_driver", CHECKOUT / DRIVER_REL, monkeypatch, tmp_path)


def _log_events(module) -> list[dict]:
    if not module.LOG_PATH.exists():
        return []
    return [json.loads(line) for line in
            module.LOG_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def _clone_tree(tmp_path: Path) -> Path:
    """一棵只有 driver 和它身旁 repo_root 的假克隆 —— spec §0 形状的复刻。"""
    clone = tmp_path / "pub"
    (clone / "bin" / "lib").mkdir(parents=True)
    (clone / "bin" / "panorama").mkdir(parents=True)
    for src in (CHECKOUT / "bin" / "lib" / "repo_root.py", CHECKOUT / DRIVER_REL):
        dest = clone / src.relative_to(CHECKOUT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
    return clone


# ── ISC-1 落点 ────────────────────────────────────────────────────────────


def test_unresolved_profile_resolves_to_canonical_checkout(driver, spy):
    assert repo_root.canonical_root() == CHECKOUT
    assert driver.ledger_db_path() == CHECKOUT / LEDGER_SUFFIX


def test_root_does_not_follow_the_publisher_clone(monkeypatch, tmp_path, spy):
    """ISC-1 的否证形状: 根落在克隆内 = 改前行为 (那份每轮 `git clean -fdx`)。"""
    clone = _clone_tree(tmp_path)
    mod = _load("t247_clone_driver", clone / DRIVER_REL, monkeypatch, tmp_path, detached=True)
    clone_repo_root = _module_from("t247_clone_repo_root", clone / "bin" / "lib" / "repo_root.py")
    got = mod.ledger_db_path()
    assert clone not in got.parents, got
    assert got != clone / LEDGER_SUFFIX
    # 同一时刻, 克隆旁那份 repo_root 的 event_ledger_path() 确实给出克隆内读数 ——
    # 这是 spec §2「为什么不调 event_ledger_path()」的实测依据, 不是叙述。
    assert clone_repo_root.event_ledger_path() == clone / LEDGER_SUFFIX
    assert clone_repo_root.event_ledger_path() != got


# ── ISC-2 声明优先, 逐字采用 ──────────────────────────────────────────────


def test_ledger_env_override_is_verbatim(driver, spy, monkeypatch, tmp_path):
    declared = tmp_path / "elsewhere" / "ledger.sqlite3"
    monkeypatch.setenv(LEDGER_ENV, str(declared))
    assert driver.ledger_db_path() == declared
    assert driver.ledger_db_path() == repo_root.event_ledger_path()


def test_state_root_declaration_beats_canonical(driver, spy, monkeypatch, tmp_path):
    state = tmp_path / "state"
    monkeypatch.setenv(STATE_ENV, str(state))
    got = driver.ledger_db_path()
    assert got == repo_root.state_root() / LEDGER_SUFFIX
    assert got == repo_root.event_ledger_path()
    assert got != CHECKOUT / LEDGER_SUFFIX


# ── ISC-3 / ISC-4 冻结面与检测器自证 ──────────────────────────────────────


def _file_derived_names(source: str) -> set[str]:
    """模块级 `NAME = <expr>` 中由 `__file__` 导出的名字, 含传递导出 (fixpoint)。"""
    assigns: dict[str, ast.expr] = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        else:
            continue
        if node.value is not None:
            for name in names:
                assigns[name] = node.value

    def tainted(expr, seen: frozenset[str]) -> bool:
        for sub in ast.walk(expr):
            if isinstance(sub, ast.Name) and sub.id == "__file__":
                return True
            if isinstance(sub, ast.Attribute) and sub.attr == "__file__":
                return True
            if isinstance(sub, ast.Name) and sub.id in assigns and sub.id not in seen:
                if tainted(assigns[sub.id], seen | {sub.id}):
                    return True
        return False

    return {n for n, v in assigns.items() if tainted(v, frozenset({n}))}


def _naive_literal_count(source: str) -> int:
    """被否证的对照判据: 只认 `ast.unparse` 后含字面 `runtime/` 的模块级赋值。"""
    return sum(1 for node in ast.parse(source).body
               if isinstance(node, ast.Assign) and "runtime/" in ast.unparse(node.value))


SYNTHETIC_VIOLATIONS = {
    "ROOT = Path(__file__)\n": ("ROOT",),
    "ROOT = Path(__file__)\nFOO = Path(ROOT)\n": ("ROOT", "FOO"),
    'ROOT = Path(__file__)\nFOO = Path(ROOT)\nLEDGER = FOO / "runtime" / "x.sqlite3"\n': (
        "ROOT", "FOO", "LEDGER",
    ),
}


def test_scanner_names_each_synthetic_violation():
    """检测器自证: 三件合成样本逐个点名 (AGENTS.md §7 ② —— 空绿不等于通过)。"""
    for source, expected in SYNTHETIC_VIOLATIONS.items():
        found = _file_derived_names(source)
        for name in expected:
            assert name in found, (source, name, sorted(found))


def test_pre_and_post_counted_by_one_scanner_run():
    """ISC-3 + ISC-4: 「改后 = 0」与「改前 = 2」由同一个扫描器同一次测试产出。"""
    post = _file_derived_names((CHECKOUT / DRIVER_REL).read_text(encoding="utf-8"))
    pre = _file_derived_names(PRE_FIX_TEXT)
    assert post == set(), sorted(post)
    assert pre == {"WORKSPACE_ROOT", "EVENT_LEDGER_DB"}, sorted(pre)


def test_naive_substring_detector_would_have_missed_the_pre_fix_text():
    """为什么是 fixpoint: 直串判据对**同一份**改前文本报 0 (06:20:51Z 实录)。"""
    assert _naive_literal_count(PRE_FIX_TEXT) == 0
    assert _file_derived_names(PRE_FIX_TEXT) == {"WORKSPACE_ROOT", "EVENT_LEDGER_DB"}


def test_resolution_happens_at_call_time_not_import_time(monkeypatch, tmp_path, spy):
    """时机判据: import 时根可解析, **之后**才把它变成不可解析 → 调用必须当场抛。

    若根被冻结在 import 时, 这里会读到旧值而不抛, 下一条 fail-closed 用例也随之假绿。
    """
    mod = _load("t247_timing_driver", CHECKOUT / DRIVER_REL, monkeypatch, tmp_path)
    assert mod.ledger_db_path() == CHECKOUT / LEDGER_SUFFIX
    monkeypatch.setenv(ROOT_ENV, str(tmp_path / "no-marker-here"))
    monkeypatch.setenv("HOME", str(tmp_path / "no-marker-home"))
    with pytest.raises(RuntimeError):
        mod.ledger_db_path()


# ── fail-closed 顺序 ─────────────────────────────────────────────────────


def test_fail_closed_before_any_git_action(monkeypatch, tmp_path, spy):
    """定位不到根 → 一条 JSON failed 行 + 非零退出, 且**一次 subprocess 都没发生**。"""
    mod = _load("t247_fail_driver", CHECKOUT / DRIVER_REL, monkeypatch, tmp_path)
    monkeypatch.setenv(ROOT_ENV, str(tmp_path / "no-marker-here"))
    monkeypatch.setenv("HOME", str(tmp_path / "no-marker-home"))
    assert mod.main() == 1
    assert spy == [], spy
    events = _log_events(mod)
    assert events[-1]["event"] == "failed", events
    assert events[-1]["step"] == "ledger_root", events
    assert not mod.CHECKOUT.exists()


# ── ISC-5 子进程同读数 ────────────────────────────────────────────────────


def _run_to_child(monkeypatch, tmp_path, spy, mod) -> dict:
    """把 main() 跑到注入点, 返回注入给子进程的那份 env。替身永不真跑 git。"""
    (mod.CHECKOUT / ".git").mkdir(parents=True, exist_ok=True)

    def responder(cmd, *args, **kwargs):  # 检出已存在 → remote 卫生检查必须放行
        out = mod.CLONE_URL + "\n" if "get-url" in cmd else ""
        spy.append((list(cmd), kwargs))
        return subprocess.CompletedProcess(list(cmd), 0, stdout=out, stderr="")

    monkeypatch.setattr(subprocess, "run", responder)
    assert mod.main() == 0, _log_events(mod)
    children = [kw for cmd, kw in spy if any("panorama-collect.py" in c for c in cmd)]
    assert len(children) == 1, spy
    return children[0]["env"]


def test_child_env_injection_equals_resolver_value(monkeypatch, tmp_path, spy):
    """ISC-5: 注入值 == 解析函数返回值, 且比较发生在**声明了 profile 的面**上。

    本轮变异实测（07:03Z）: 未声明 profile 时把注入点写成 `__file__` 反推, 10 条用例全绿 ——
    两侧按构造读到同一个路径, 判据没有牙齿。因此这里 import 后声明 `OMOSTATION_STATE_ROOT`
    （顺带再压一遍 ISC-3 的时机面): 解析器给 state 根读数, 任何自行重算的注入点当场分叉。
    """
    mod = _load("t247_child_driver", CHECKOUT / DRIVER_REL, monkeypatch, tmp_path)
    state = tmp_path / "state"
    monkeypatch.setenv(STATE_ENV, str(state))
    expected = str(mod.ledger_db_path())
    env = _run_to_child(monkeypatch, tmp_path, spy, mod)
    assert env[LEDGER_ENV] == expected
    assert Path(expected) == state / LEDGER_SUFFIX
    # 判别自证 (AGENTS.md §7 ③): 绿不得来自「两侧本来就读不出差别」
    assert expected != str(Path(mod.__file__).resolve().parents[2] / LEDGER_SUFFIX)
    assert expected != str(CHECKOUT / LEDGER_SUFFIX)
    assert expected != str(mod.CHECKOUT / LEDGER_SUFFIX)
    resolved = [e["path"] for e in _log_events(mod) if e["event"] == "ledger_root_resolved"]
    assert resolved == [expected], resolved  # 操作者看到的落点与注入值是同一个读数


def test_injection_point_does_not_follow_the_publisher_clone(monkeypatch, tmp_path, spy):
    """ISC-5 在 spec §0 那个常驻位置上的否证形状: 根从克隆反推 → 子进程读到克隆内 ledger。"""
    clone = _clone_tree(tmp_path)
    mod = _load("t247_clone_child", clone / DRIVER_REL, monkeypatch, tmp_path, detached=True)
    env = _run_to_child(monkeypatch, tmp_path, spy, mod)
    assert env[LEDGER_ENV] == str(CHECKOUT / LEDGER_SUFFIX)
    assert env[LEDGER_ENV] != str(clone / LEDGER_SUFFIX)
