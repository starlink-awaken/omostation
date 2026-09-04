"""Tests for Typo Correction & Fuzzy Matching Engine (BET-Y1Q4-T8-16 / Phase 2)."""

import json
import pytest

from cockpit.cli import main
from cockpit.domain.exit_codes import ExitCode
from cockpit.domain.fuzzy_matcher import find_closest_commands, levenshtein_distance, similarity_ratio


def test_fuzzy_matcher_math():
    assert levenshtein_distance("status", "statsu") == 2
    assert similarity_ratio("status", "status") == 1.0
    assert similarity_ratio("dashboard", "dasbhoard") > 0.7


def test_find_closest_commands():
    res = find_closest_commands("statsu")
    assert "status" in res

    res2 = find_closest_commands("dasbhoard")
    assert "dashboard" in res2

    res3 = find_closest_commands("gacc")
    assert "gac" in res3


def test_cli_typo_json_suggestions(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--json", "statsu"])

    assert exc_info.value.code == ExitCode.USAGE_ERROR

    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert data["ok"] is False
    assert "suggestions" in data
    assert "status" in data["suggestions"]


def test_cli_typo_tty_suggestions(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["dasbhoard"])

    assert exc_info.value.code == ExitCode.USAGE_ERROR

    captured = capsys.readouterr()
    assert "您是不是想输入以下命令之一？" in captured.out
    assert "cockpit dashboard" in captured.out
