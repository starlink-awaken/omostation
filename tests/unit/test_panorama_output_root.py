"""采集器的输出根与代码支持根必须可分离 (PANORAMA_OUTPUT_ROOT)。

缺陷（2026-11-10 起, PANORAMA-GATE-DETAIL-UNRELIABLE）：`PANORAMA_ROOT` 在本机被同时
当作两个用途 —— 代码支持根（`ssot/` `lib/` 只存在于安装位）与输出根（`OUT_DIR`）。而 base
的消费者 `orchestrator.py::_read_panorama_base` 读 `state_root()/runtime/dashboard/data.json`。
同一个变量扛两个用途 ⇒ 必然错位一侧：本机 `panorama_base` 走 FileNotFoundError、
`personal_value_truth` 走 `managed_state_root_mismatch`，两条 cohort 自 2026-10-28 起冻结。

本文件钉住分离本身，而不是某个具体落点：
- 采集器：`PANORAMA_OUTPUT_ROOT` 缺省时 `OUT_DIR` 与改动前逐字节相同；
- 采集器：`PANORAMA_ROOT` 继续决定代码支持根（不得被输出根顶替）；
- 聚合器：`personal_value_truth` 的守卫比对的是**输出根**（`PANORAMA_OUTPUT_ROOT or
  PANORAMA_ROOT`），不是代码支持根；
- 采集器：不得再有绕过 `DATA_JSON` 的第二处 `ROOT / "runtime/dashboard/data.json"` 读点
  （半接线的缝没有任何测试会红）。
"""

from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COLLECTOR = ROOT / "bin" / "panorama" / "panorama-collect.py"
ORCHESTRATOR = ROOT / "bin" / "panorama" / "assets" / "host" / "orchestrator.py.asset"


def _load_collector(monkeypatch, **env: str | None):
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    spec = importlib.util.spec_from_file_location(
        "panorama_output_root_under_test", COLLECTOR
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_output_root_defaults_to_configured_root(monkeypatch, tmp_path) -> None:
    """未设 PANORAMA_OUTPUT_ROOT 时，输出落点必须与改动前一致（缺省即今日行为）。"""
    code = tmp_path / "code"
    code.mkdir()
    module = _load_collector(
        monkeypatch, PANORAMA_ROOT=str(code), PANORAMA_OUTPUT_ROOT=None
    )

    assert module.OUTPUT_ROOT == code.resolve()
    assert module.OUT_DIR == code.resolve() / "runtime" / "dashboard"
    assert module.DATA_JSON == module.OUT_DIR / "data.json"


def test_output_root_env_redirects_output_only(monkeypatch, tmp_path) -> None:
    """设了 PANORAMA_OUTPUT_ROOT 时，只有输出面跟着走，代码支持根不动。"""
    code = tmp_path / "code"
    out = tmp_path / "out"
    code.mkdir()
    out.mkdir()
    module = _load_collector(
        monkeypatch, PANORAMA_ROOT=str(code), PANORAMA_OUTPUT_ROOT=str(out)
    )

    assert module.OUT_DIR == out.resolve() / "runtime" / "dashboard"
    assert module.DATA_JSON == module.OUT_DIR / "data.json"
    assert module.AGENT_BRIEF_JSON == module.OUT_DIR / "agent-brief.json"
    assert module.INDEX_HTML == module.OUT_DIR / "index.html"
    # 代码支持根不得被输出根顶替：_host_support_dir 仍从 PANORAMA_ROOT 解析。
    assert module.ROOT == code.resolve()
    assert module._host_support_dir("definitely-absent-dir") == str(
        COLLECTOR.resolve().parents[1] / "definitely-absent-dir"
    )


def test_collector_has_no_second_hardcoded_output_read() -> None:
    """`collect_alerts` 曾直接读 `ROOT / "runtime/dashboard/data.json"`，绕过 OUT_DIR。

    这类第二读点没有任何测试会红，却会让「输出根分离」只做了一半。
    """
    source = COLLECTOR.read_text(encoding="utf-8")
    assert 'ROOT / "runtime/dashboard/data.json"' not in source, (
        "又出现绕过 DATA_JSON 的输出读点 —— 输出根分离会只做一半"
    )


def _configured_state_expression() -> ast.Expression:
    """从 `_run_collector` 里取出 `configured_state = ...` 的右值。"""
    tree = ast.parse(ORCHESTRATOR.read_text(encoding="utf-8"), filename="orchestrator")
    fn = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_run_collector"
    )
    assign = next(
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "configured_state"
            for target in node.targets
        )
    )
    return ast.Expression(assign.value)


def _eval_guard(env: dict[str, str]) -> str | None:
    expr = _configured_state_expression()
    fake_os = type("Os", (), {"environ": env})()
    return eval(  # noqa: S307 — 表达式取自本仓资产, 用于 hermetic 断言
        compile(expr, "<guard>", "eval"), {"os": fake_os, "Path": Path}, {}
    )


def test_guard_compares_output_root_not_code_root() -> None:
    """守卫比对的是输出根：设了 PANORAMA_OUTPUT_ROOT 就用它，否则回落 PANORAMA_ROOT。"""
    assert _eval_guard(
        {"PANORAMA_OUTPUT_ROOT": "/out", "PANORAMA_ROOT": "/code"}
    ) == "/out"
    assert _eval_guard({"PANORAMA_ROOT": "/code"}) == "/code"
    assert _eval_guard({}) is None


def test_guard_expression_is_not_the_old_bare_form() -> None:
    """反证：旧形态（只读 PANORAMA_ROOT）必须被本文件检出，否则上面两条可能空转。"""
    expr = _configured_state_expression()
    literals = [
        node.value
        for node in ast.walk(expr)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    assert "PANORAMA_OUTPUT_ROOT" in literals, "守卫不再读 PANORAMA_OUTPUT_ROOT"
    assert "PANORAMA_ROOT" in literals, "守卫丢了 PANORAMA_ROOT 回落"


def test_both_sides_are_real_files() -> None:
    assert COLLECTOR.is_file()
    assert ORCHESTRATOR.is_file()
    assert os.access(ORCHESTRATOR, os.R_OK)


def test_publish_base_snapshot_writes_atomic_data_json_for_orchestrator(
    monkeypatch, tmp_path
) -> None:
    """_publish_base_snapshot 必须在 PANORAMA_OUTPUT_ROOT 落盘包含四组 base 键的 data.json。"""
    import json
    from datetime import datetime

    code = tmp_path / "code"
    out = tmp_path / "out"
    code.mkdir()
    out.mkdir()
    module = _load_collector(
        monkeypatch, PANORAMA_ROOT=str(code), PANORAMA_OUTPUT_ROOT=str(out)
    )
    sample = {
        "observed_at": "2026-11-25T07:00:00+00:00",
        "bets": {"total": 600, "counts": {"done": 598, "in_progress": 1, "pending": 1}},
        "gates": [{"id": "A1", "verdict": "PASS", "detail": "ok warnings=2"}],
        "runtime": {"service_keeper": {"ok": True}},
        "code_root_health": {"verdict": "PASS"},
    }

    written = module._publish_base_snapshot(sample)
    expected = out.resolve() / "runtime" / "dashboard" / "data.json"
    assert written == expected
    assert expected.is_file()

    loaded = json.loads(expected.read_text(encoding="utf-8"))
    for key in ("bets", "gates", "runtime", "code_root_health"):
        assert loaded[key] == sample[key]
    assert loaded["observed_at"] == sample["observed_at"]
    parsed_clock = datetime.fromisoformat(loaded["generated_at"])
    assert parsed_clock.tzinfo is not None
