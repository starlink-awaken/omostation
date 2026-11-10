"""orchestrator 的 base 读取失败时必须自描述读侧/写侧路径。

缺陷（2026-11-10 实测，PANORAMA-GATE-DETAIL-UNRELIABLE）：读侧是
`state_root()/runtime/dashboard/data.json`，生产者写
`PANORAMA_ROOT/runtime/dashboard/data.json`；本机两者不同根 ⇒ 读侧
`FileNotFoundError` ⇒ 门禁 cohort 冻结 13 天。旧实现只报
`error: FileNotFoundError` 与上一份读到的 source，**下一个诊断者得重新推一遍
写侧在哪**（本轮实际花掉十余个回合）。

判据：失败诊断里带 `candidates`，含 reader/writer 两条路径与各自 exists。
本文件的用例用 AST 抽出该 helper（资产 import 链依赖 collectors/models/
runtime_paths，整模块加载在测试里不现实），并用 env 注入做 hermetic 断言。
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "bin" / "panorama" / "assets" / "host" / "orchestrator.py.asset"
# helper 内部 `from repo_root import state_root` —— 与 test_zhixing_source_health_mirror.py 同法
sys.path.insert(0, str(ROOT / "bin" / "lib"))


def _helper() -> callable:
    tree = ast.parse(ASSET.read_text(encoding="utf-8"), filename="orchestrator.py.asset")
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_panorama_base_candidates"
    )
    namespace = {"os": os, "Path": Path}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<orchestrator>", "exec"), namespace)
    return namespace["_panorama_base_candidates"]


def test_helper_is_present_in_the_asset() -> None:
    source = ASSET.read_text(encoding="utf-8")
    assert "def _panorama_base_candidates" in source, "helper 被改名或删除"


def test_candidates_describe_reader_and_writer(tmp_path, monkeypatch) -> None:
    state = tmp_path / "state"
    writer = tmp_path / "writer"
    (state / "runtime" / "dashboard").mkdir(parents=True)
    (writer / "runtime" / "dashboard").mkdir(parents=True)
    (writer / "runtime" / "dashboard" / "data.json").write_text("{}")
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(state))
    monkeypatch.setenv("PANORAMA_ROOT", str(writer))

    candidates = _helper()()

    roles = {entry["role"] for entry in candidates}
    assert roles == {"reader", "writer"}, f"缺 reader/writer 之一: {candidates}"
    by_role = {entry["role"]: entry for entry in candidates}
    assert by_role["reader"]["exists"] is False, "读侧路径不存在却未如实报出"
    assert by_role["writer"]["exists"] is True, "写侧路径存在却未如实报出"
    for entry in candidates:
        assert entry["path"].endswith("runtime/dashboard/data.json"), entry


def test_candidates_absent_writer_env_is_still_described(tmp_path, monkeypatch) -> None:
    """未声明 PANORAMA_ROOT 时只报读侧，不得抛异常。"""
    state = tmp_path / "state"
    (state / "runtime" / "dashboard").mkdir(parents=True)
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(state))
    monkeypatch.delenv("PANORAMA_ROOT", raising=False)

    candidates = _helper()()

    assert [entry["role"] for entry in candidates] == ["reader"]
    assert candidates[0]["exists"] is False
