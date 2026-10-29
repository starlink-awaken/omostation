"""resident-orchestrator 写面的读者必须按 profile 根解析 (ADR-0456 决策 2 / B1)。

背景: BET-Y2Q4-T10-233 把 omo.resident 的**写面**收敛到 state 根, 并把 bin/ 侧读者钉成
`tests/unit/test_resident_write_plane_split.py` 里的 SPLIT_* 登记表 —— 台账 circuit-breaker
当时明确「需要改 bin/ 读者 → 停下登记而不是扩大 PR」。本文件兑现该登记面里
`.omo/_delivery/resident-orchestrator/**` 四个族的**两个**读者:

- `bin/ssot/resident-orchestrator-daemon.py` — daemon.pid / daemon.log / watermarks/* (本批已转)
- `bin/ssot/system-health-check.py` — watermarks/* (本批已转)

第三个读者 `bin/gac/check-resident-status.py` (CI 门禁 R-RESIDENT 的取数点) **本批未改**:
它是 sgf-policy 登记的 gate 脚本, 落 `governance_code` lane, 与 `code` lane 不能同批交付
(`bin/change-lane-check.py` 的 `ALLOWED_COMBOS` 不含该组合, 且 `PUSH_RANGE` 聚合使「拆 commit
一次 push」同样失效)。由 `test_check_resident_status_still_registered_checkout` 钉住它在登记表里
**不许消失**, 防止本文件被读成「该族已全量收敛」。

`bin/ssot/log-rotate.py` **仍是检出根**并且故意留在 SPLIT_ANCESTOR 里 (它是目录级清理者,
改错方向的后果是 state 根日志永不清轮, 不属这一腿)。`test_log_rotate_stays_registered`
把这条钉住, 防止本文件被读成「该族已全量收敛」。

⚠️ 检测器盲区 (本轮实测, 决定本文件为什么必须存在):
`reader_pairs()` 只把 `/` 链**头锚点之后**的字面量尾巴拼成族名, 锚点自身的模块级字面量
前缀不展平。改造前 `bin/ssot/system-health-check.py` 写的是两级派生常量

    DELIVERY = WORKSPACE / ".omo" / "_delivery"
    DAEMON_WATERMARKS = DELIVERY / "resident-orchestrator" / "watermarks"

尾巴 `resident-orchestrator/watermarks` 不以 `.omo/` 开头 ⇒ 该读者在 SPLIT_* 里**从未出现过**,
而它和 check-resident-status 读的是同一个面。本轮不放宽匹配规则 (那会把别的族一次性扫红,
超出这一腿范围), 改用下面的**运行时**判据把这个改造前不可见的读者一并钉住 —— 改成访问器后
它反而被那把尺认成了 STATE (锚点 `state_root`, 家族 `.omo/_delivery/resident-orchestrator/watermarks/*`),
于是双向都有证据。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "bin"
SPLIT_TEST = ROOT / "tests" / "unit" / "test_resident_write_plane_split.py"
FAMILY = ".omo/_delivery/resident-orchestrator"
FAMILIES = {
    f"{FAMILY}/daemon.log",
    f"{FAMILY}/daemon.pid",
    f"{FAMILY}/receipts.jsonl",
    f"{FAMILY}/watermarks/*",
}

# (模块文件, 访问器名, 访问器参数, 落点尾巴, 该模块改造前用的检出根常量名)
ACCESSORS = [
    ("bin/ssot/resident-orchestrator-daemon.py", "_pid_file", (), f"{FAMILY}/daemon.pid", "WORKSPACE"),
    ("bin/ssot/resident-orchestrator-daemon.py", "_log_file", (), f"{FAMILY}/daemon.log", "WORKSPACE"),
    (
        "bin/ssot/resident-orchestrator-daemon.py",
        "_wm_path",
        ("resident-sub",),
        f"{FAMILY}/watermarks/resident-sub.json",
        "WORKSPACE",
    ),
    ("bin/ssot/system-health-check.py", "_daemon_watermarks", (), f"{FAMILY}/watermarks", "WORKSPACE"),
]


def _load(rel_path: str) -> object:
    name = rel_path.rsplit("/", 1)[-1].replace("-", "_").replace(".", "") + "_readerprobe"
    spec = importlib.util.spec_from_file_location(name, ROOT / rel_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def split_mod():
    """借用同仓那份尺 —— 判据必须与登记表用同一个 detector, 否则两边会各自塌。"""
    spec = importlib.util.spec_from_file_location("split尺", SPLIT_TEST)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["split尺"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _no_profile(monkeypatch):
    """未声明 profile 是本组用例的基线; 声明面由用例自己显式设置。"""
    for k in ("OMOSTATION_STATE_ROOT", "OMO_EVENT_LEDGER_DB"):
        monkeypatch.delenv(k, raising=False)


def test_accessor_follows_declared_state_root(tmp_path: Path, monkeypatch) -> None:
    """声明 profile 后, 五个访问器的落点必须整体搬到 state 根。"""
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(tmp_path))
    for rel, fn_name, args, tail, _const in ACCESSORS:
        got = getattr(_load(rel), fn_name)(*args)
        assert got == tmp_path / tail, f"{rel}::{fn_name} 没跟着 profile 根走: {got}"


def test_accessor_reproduces_checkout_path_when_profile_undeclared(tmp_path: Path) -> None:
    """未声明 profile 时必须逐字节复现改造前的检出落点 (ADR-0456 那条不变量)。

    参照对象是**各模块自己的检出根常量** (改造前的表达式就是它拼出来的), 不是再去调一次
    code_root() —— 否则断言与实现同源, 「同值所以恒绿」。
    """
    for rel, fn_name, args, tail, const in ACCESSORS:
        module = _load(rel)
        expected = getattr(module, const) / tail
        got = getattr(module, fn_name)(*args)
        assert got == expected, f"{rel}::{fn_name}: {got} != 改造前落点 {expected}"
        assert not str(got).startswith(str(tmp_path))


def test_converted_readers_are_state_classified_by_the_shared_detector(split_mod) -> None:
    """正面落点判据的**尺不共享失效**面: 由登记表那把尺确认这三个文件的锚点是 STATE。

    若有人把 `state_root()` 换回 `WORKSPACE` 或换一个检测器认不出的定位器, 这条当场红 ——
    前者会分类成 CHECKOUT, 后者会变成 DERIVED/CALLER, 都不再是 STATE。
    """
    converted = {
        "bin/ssot/resident-orchestrator-daemon.py",
        "bin/ssot/system-health-check.py",
    }
    rows = [r for r in split_mod.reader_pairs(BIN, FAMILIES) if r[2] in converted]
    assert rows, "三个读者在尺上完全不出现 —— 那是检测器没命中, 不是写面收敛了"
    by_file: dict[str, set[str]] = {}
    for _fam, _kind, rel, _line, _anchor, klass in rows:
        by_file.setdefault(rel, set()).add(klass)
    assert by_file == {f: {"STATE"} for f in converted}, f"仍有读者不在 state 根: {by_file}"


def test_log_rotate_stays_registered(split_mod) -> None:
    """log-rotate 仍按检出根清理, 且**必须**继续在 SPLIT_ANCESTOR 里 —— 不许顺手摘空。"""
    rows = split_mod.reader_pairs(BIN, FAMILIES)
    measured = {
        (fam, rel) for fam, kind, rel, _l, _a, klass in rows if kind == "ancestor" and klass != "STATE"
    }
    registered = {(fam, rel) for fam, pairs in split_mod.SPLIT_ANCESTOR.items() for rel, _k in pairs}
    for fam in sorted(FAMILIES):
        assert (fam, "bin/ssot/log-rotate.py") in measured, f"{fam} 的 log-rotate 读取点不见了"
        assert (fam, "bin/ssot/log-rotate.py") in registered, f"{fam} 的 log-rotate 登记被摘掉了"
def test_check_resident_status_still_registered_checkout(split_mod) -> None:
    """第三个读者 `check-resident-status.py` **故意**还留在检出根登记里 —— 别把它读成已收敛。

    它和 daemon 读的是同一个面, 所以这一族当前的读写同根是**部分**成立: writer 与两个读者在
    state 根, 这个 CI 门禁读者在检出根。它是 `sgf-policy.yaml` 登记的 gate 脚本 (lane =
    governance_code), 与本 code lane 腿不能进同一个 push range, 因此留下一批。本用例钉住
    "仍 measured 且仍 registered", 防止改道在无人签字的情况下悄悄发生或被登记面摘空。
    """
    fam = f"{FAMILY}/watermarks/*"
    rows = split_mod.reader_pairs(BIN, {fam})
    got = {(rel, klass) for _f, _k, rel, _l, _a, klass in rows if _k == "ancestor"}
    assert ("bin/gac/check-resident-status.py", "CHECKOUT") in got, got
    assert ("bin/gac/check-resident-status.py", "CHECKOUT") in {
        pair for pair in split_mod.SPLIT_ANCESTOR.get(fam, set())
    }, split_mod.SPLIT_ANCESTOR.get(fam)
