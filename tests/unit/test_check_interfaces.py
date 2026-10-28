"""bin/ssot/check-interfaces.py —— 接口契约表结构检查器的规则与自证。

自证原则（AGENTS.md §7）：检测器必须能被合成违规样本触发，否则「绿」可能只是
检测器压根没命中。每条规则都有对应的反例用例。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "check_interfaces",
    Path(__file__).resolve().parents[2] / "bin" / "ssot" / "check-interfaces.py",
)
assert _SPEC and _SPEC.loader
guard = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(guard)

GOOD = """# Interface Contract

## Model: TaskObject

| Field | Type | Description |
|---|---|---|
| id | string | task id |
| status | string | lifecycle |

## Model: AgentMessage

| Field | Type | Description |
|---|---|---|
| source | string | sender |
| payload | dict | body |
"""


def _errors(text: str) -> list[str]:
    _, errors = guard.parse_models(text)
    return errors


# ── 正例 ────────────────────────────────────────────────────────────


def test_well_formed_contract_has_no_errors():
    assert _errors(GOOD) == []


def test_all_known_types_are_accepted():
    body = "\n".join(f"| f{i} | {t} | d |" for i, t in enumerate(sorted(guard.KNOWN_TYPES)))
    text = "## Model: M\n\n| Field | Type | Description |\n|---|---|---|\n" + body + "\n"
    assert _errors(text) == []


# ── 反例：每条规则一个触发用例 ──────────────────────────────────────


def test_empty_document_is_an_error():
    assert any("未声明任何" in e for e in _errors("# nothing here\n"))


def test_missing_table_after_model_is_an_error():
    errors = _errors("## Model: M\n\njust prose, no table\n")
    assert any("没有 markdown 表" in e for e in errors)


def test_wrong_header_is_an_error():
    text = GOOD.replace("| Field | Type | Description |", "| Name | Kind | Note |", 1)
    assert any("表头应为" in e for e in _errors(text))


def test_missing_separator_is_an_error():
    text = GOOD.replace("|---|---|---|", "", 1)
    assert any("缺少分隔行" in e for e in _errors(text))


def test_wrong_column_count_is_an_error():
    text = GOOD.replace("| id | string | task id |", "| id | string |", 1)
    assert any("3 列" in e for e in _errors(text))


def test_unknown_type_is_an_error():
    text = GOOD.replace("| id | string | task id |", "| id | uuid | task id |", 1)
    assert any("Type `uuid`" in e for e in _errors(text))


def test_duplicate_field_in_one_model_is_an_error():
    text = GOOD.replace("| status | string | lifecycle |", "| id | string | dup |", 1)
    assert any("重复" in e for e in _errors(text))


def test_duplicate_model_name_is_an_error():
    text = GOOD + "\n## Model: TaskObject\n\n| Field | Type | Description |\n|---|---|---|\n| x | string | y |\n"
    assert any("模型名重复" in e for e in _errors(text))


# ── 自证：规则真的被命中（不是"空绿"）──────────────────────────────


def test_detector_is_not_a_no_op():
    """注入一条违规后必须变红 —— 证明检测器确实在读内容。"""
    assert _errors(GOOD) == []
    assert _errors(GOOD.replace("| id | string | task id |", "| id | nope | task id |")) != []


def test_check_parse_flags_empty_model():
    models, _ = guard.parse_models("## Model: Empty\n\n| Field | Type | Description |\n|---|---|---|\n")
    assert guard.check_parse(models) != []
    models_ok, _ = guard.parse_models(GOOD)
    assert guard.check_parse(models_ok) == []


def test_cli_exits_nonzero_on_violation(tmp_path, capsys):
    bad = tmp_path / "contract.md"
    bad.write_text(GOOD.replace("| id | string | task id |", "| id | uuid | task id |"), encoding="utf-8")
    rc = guard.main(["--path", str(bad)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "uuid" in captured.err


def test_cli_exits_nonzero_when_document_missing(tmp_path):
    assert guard.main(["--path", str(tmp_path / "nope.md")]) == 1


@pytest.mark.parametrize("flag", ["--json", "--check-parse"])
def test_cli_flags_run_without_crashing(tmp_path, capsys, flag):
    good = tmp_path / "contract.md"
    good.write_text(GOOD, encoding="utf-8")
    assert guard.main(["--path", str(good), flag]) == 0
    capsys.readouterr()
