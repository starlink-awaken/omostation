"""B4b 写者的根缝可达性自证 (BET-Y2Q4-T10-282).

scripts/tools/spine-daily-ingress.py 是 ADR-0456 里「写面落 state_root」的少数
仍在仓内的直接写者: 它往 .omo/state/{spine-diff,lora-replay}-buffer.jsonl 追加
人类署名样本。它原先把 repo_root 缝算成 `parents[1] / "lib"` = scripts/lib ——
该目录按构造不存在, 于是每次运行都走 `except ImportError` 的字面量兜底:
code_root 与 state_root 都钉死在某台机器的检出根。后果比尺更坏 —— 声明了
OMOSTATION_STATE_ROOT 的机器上, 署名样本仍写进检出根, profile 侧的池子永远为空,
而管线状态打印出来的 lora_replay_file 指向一个没人写的文件。

四条用例: 正向落点 (两个 resolver 来自 repo_root, 不是局部 def)、尺外判据不共享
失效模式 (源码无检出字面量)、缝改回 parents[1] 时守卫必须当场拒 (且去掉守卫后
那份红并非按构造就有)、以及最关键的「写面真的落 state_root」—— 按 done_when
要求实际跑一次写入路径, 而不是只读源码。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SPINE = REPO / "scripts" / "tools" / "spine-daily-ingress.py"
SEAM_LINE = '_LIB_DIR = Path(__file__).resolve().parents[2] / "bin" / "lib"'
GUARD_LINES = (
    'if not _LIB_DIR.is_dir():\n'
    '    raise SystemExit(f"repo_root 缝不可达: {_LIB_DIR} —— 写者不得静默兜底检出根")\n'
)
OLD_SEAM_LINE = '_LIB_DIR = Path(__file__).resolve().parents[1] / "lib"'


def _exec(path: Path, name: str) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def _load_spine(monkeypatch, source_path: Path, name: str) -> object:
    # 写者用例不得碰本机 profile 的既有 state 根: 环境逐次显式给定。
    monkeypatch.setenv("OMOSTATION_ROOT", str(REPO))
    monkeypatch.delenv("OMOSTATION_ROOT_OVERRIDE", raising=False)
    # 真实写者 exec 时会把 bin/lib 塞进 sys.path 并缓存 repo_root 模块; 兄弟尺的用例
    # 也会。不先清掉这份残留、「缝不可达去掉守卫」的变异就会侥幸 import 成功 ——
    # 用例 4 的红于是变成顺序依赖 (同类事故见 test_reporting_reads_ledger)。
    lib_str = str(REPO / "bin" / "lib")
    path_snapshot = list(sys.path)
    sys.path[:] = [p for p in path_snapshot if p != lib_str]
    sys.modules.pop("repo_root", None)
    try:
        return _exec(source_path, name)
    finally:
        sys.path[:] = path_snapshot
        sys.modules.pop("repo_root", None)


def test_spine_seam_resolves_to_the_real_repo_root(monkeypatch) -> None:
    """正向落点: code_root / state_root 必须来自 repo_root 模块, 不是写者的局部 def。"""
    module = _load_spine(monkeypatch, SPINE, "t282_spine_under_test")
    for name in ("code_root", "state_root"):
        fn = getattr(module, name)
        assert fn.__module__ == "repo_root", f"{name} 来自兜底局部函数 —— 缝又不可达了"
    assert Path(module.code_root()) == REPO


def test_spine_source_has_no_checkout_literal() -> None:
    """判据与读数不共享失效模式: 直接按写者源码文本查字面量与旧缝算式。"""
    text = SPINE.read_text(encoding="utf-8")
    assert 'Path("/Users' not in text, "写者内重新出现了硬编码检出根"
    assert 'parents[1] / "lib"' not in text, "缝又算回 scripts/lib"


def test_seam_depth_mutation_is_caught_by_the_guard(tmp_path: Path, monkeypatch) -> None:
    """合成违规自证: 缝改回 parents[1] 时守卫必须当场拒, 而不是静默降级。"""
    original = SPINE.read_text(encoding="utf-8")
    mutated = original.replace(SEAM_LINE, OLD_SEAM_LINE)
    assert mutated != original, "变异点未命中 —— 本用例的断言按构造不可信"
    bad = tmp_path / "scripts" / "tools" / "spine_mutated.py"
    bad.parent.mkdir(parents=True)
    bad.write_text(mutated, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _load_spine(monkeypatch, bad, "t282_spine_mutated")
    assert "缝不可达" in str(exc.value)


def test_the_guard_is_what_makes_that_red(tmp_path: Path, monkeypatch) -> None:
    """反证: 同一缝变异去掉守卫后拿不到 SystemExit(缝不可达) 契约 ——
    用例 3 的红来自守卫本身, 不是变异恰好撞上别的报错。"""
    mutated = (
        SPINE.read_text(encoding="utf-8")
        .replace(SEAM_LINE, OLD_SEAM_LINE)
        .replace(GUARD_LINES, "")
    )
    assert GUARD_LINES not in mutated and OLD_SEAM_LINE in mutated
    bad = tmp_path / "scripts" / "tools" / "spine_no_guard.py"
    bad.parent.mkdir(parents=True)
    bad.write_text(mutated, encoding="utf-8")
    with pytest.raises(ModuleNotFoundError):
        _load_spine(monkeypatch, bad, "t282_spine_no_guard")


def test_writer_lands_in_state_root_not_checkout_or_cwd(
    tmp_path: Path, monkeypatch
) -> None:
    """正向落点 (done_when 3): 声明 state 根后实际跑写入路径, 产物必须落在那里。

    只读源码证明不了这件事 —— 兜底版源码里 state_root() 同样「存在」, 但返回值
    是检出根字面量。这里断言三件事: 落进 <tmp>/.omo/state、不落 CWD、
    不新增也不改写检出根上的同名文件。
    """
    state = tmp_path / "state-root"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(state))
    module = _load_spine(monkeypatch, SPINE, "t282_spine_writer")
    # cockpit 是可选项, 但 hermetic 复跑不得真去调本机 CLI。
    monkeypatch.setattr(module.shutil, "which", lambda _cmd: None)

    checkout_buf = Path(module.code_root()) / ".omo" / "state" / "spine-diff-buffer.jsonl"
    before = checkout_buf.read_bytes() if checkout_buf.exists() else None

    res = module.record_signature("原始草稿\n第二行\n", "人工署名终稿\n改了一行\n")

    assert res["status"] == "RECORDED"
    written = state / ".omo" / "state" / "spine-diff-buffer.jsonl"
    assert written.is_file(), f"署名样本没落进声明的 state 根: {written}"
    assert written.read_text(encoding="utf-8").count("\n") == 1
    assert not (tmp_path / ".omo" / "state" / "spine-diff-buffer.jsonl").exists(), (
        "产物落到了 CWD —— 根是参数, 不是工作目录"
    )
    after = checkout_buf.read_bytes() if checkout_buf.exists() else None
    assert after == before, "检出根上的历史池被这次写入改动了"
