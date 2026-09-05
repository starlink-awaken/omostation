"""Tests for completion generators, typo suggestion, and CLI-REFERENCE (BET-Y1Q4-T8-16)."""

from __future__ import annotations

import json
from pathlib import Path

from cockpit.cli import main
from cockpit.commands.completion import (
    SUPPORTED_SHELLS,
    generate_bash_completion,
    generate_fish_completion,
    generate_zsh_completion,
    suggest_commands,
)
from cockpit.domain.exit_codes import ExitCode


def test_all_three_shell_scripts_generated():
    scripts = {
        "bash": generate_bash_completion(),
        "zsh": generate_zsh_completion(),
        "fish": generate_fish_completion(),
    }
    assert set(scripts) == set(SUPPORTED_SHELLS)
    assert "cockpit" in scripts["bash"] and "complete" in scripts["bash"]
    assert scripts["zsh"].startswith("#compdef cockpit")
    assert "_cockpit" in scripts["zsh"]
    assert "function" in scripts["fish"] or "complete" in scripts["fish"]


def test_suggest_commands_close_match():
    # 单字符换位/漏字 → 建议真实命令
    assert "telemetry" in suggest_commands("telemtry")
    assert "completion" in suggest_commands("completoin")
    for s in suggest_commands("totally-unknown-cmd-xyz"):
        assert isinstance(s, str)


def test_suggest_commands_distance_bound():
    # 完全无关的 token 不产生低质量建议
    assert suggest_commands("zzzzzzzzzzzz") == []
    # 距离上限: 空串无建议
    assert suggest_commands("") == []


def test_unknown_command_json_payload_carries_suggestions(capsys):
    """WorkspaceParser.error 的 did-you-mean: JSON 模式输出 suggestions 字段。"""
    import pytest

    from cockpit.domain.fuzzy_matcher import find_closest_commands

    assert "telemetry" in find_closest_commands("telemtry")
    with pytest.raises(SystemExit):
        main(["telemtry", "--json"])  # telemetry 的 typo, parser.error 拦截
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False
    assert "telemetry" in data["suggestions"]


def test_cli_reference_generated_scale():
    """生成物 ≥1400 行且结构完整 (done_when: 1400+ 行全量手册)。"""
    ws = Path(__file__).resolve().parents[3]
    ref = ws / "docs" / "CLI-REFERENCE.md"
    if not ref.exists():
        # worktree 之外的回退路径
        ref = Path("/Users/xiamingxing/Workspace/docs/CLI-REFERENCE.md")
    assert ref.exists(), "CLI-REFERENCE.md missing"
    lines = ref.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 1400, f"only {len(lines)} lines"
    text = "\n".join(lines)
    assert "## 全局 Flags" in text
    assert "## Shell 自动补全" in text
    assert "## MCP 工具映射" in text
    assert text.count("### `cockpit ") >= 100
