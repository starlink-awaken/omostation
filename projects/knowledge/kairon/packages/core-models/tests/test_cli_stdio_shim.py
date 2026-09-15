"""A2 回归测试: core_models.cli stdio shim 可解析.

锁定 bos://persona/core-models/{schema,validate} 的 resolve 断层修复 (2026-07-13)。
shim 协议: argv 取 action, stdin 读 {"args","kwargs"}, stdout 打印一行 JSON。
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import json
import subprocess
import sys

import pytest


@pytest.mark.parametrize("action", ["schema", "validate"])
def test_core_models_cli_resolves(action: str) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "core_models.cli", action],
        input='{"args":[],"kwargs":{}}\n',
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    line = proc.stdout.strip().splitlines()[0]
    payload = json.loads(line)  # 必须是合法 JSON (非 ModuleNotFoundError)
    assert payload.get("action_dispatched") == action
    assert payload.get("_reachability") == "ok"
