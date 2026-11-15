"""`governance-convergence-lint.py --rule <未知>` 必须报错，不能空跑报 ok。

契约来源：2026-11-15 —— `lint(rule_filter)` 的循环体是
`if rule_filter and rule_filter != name: continue`，于是过滤器匹配不到任何 check 时
**一次都不执行**，errors/warnings 全空 ⇒ `ok:true` + exit 0。
`governance-checks.yaml` 的 `CR-L0-SSOT-PATH-NORM` 描述正好写着
「实现: … --rule ssot-path-norm」—— 那个名字不存在，这条「实现」指路指向一次空跑。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "governance-convergence-lint.py"

KNOWN_RULES = ["registration", "score", "loop", "rules-count", "matrix"]


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        cwd=ROOT,
    )


def test_unknown_rule_is_an_error() -> None:
    result = _run("--rule", "ssot-path-norm", "--json")
    assert result.returncode != 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert any("UNKNOWN_RULE" in e for e in payload["errors"]), payload


def test_unknown_rule_without_json_also_fails() -> None:
    result = _run("--rule", "definitely-not-a-rule")
    assert result.returncode != 0, result.stdout + result.stderr
    assert "UNKNOWN_RULE" in (result.stdout + result.stderr)


def test_every_known_rule_name_is_accepted() -> None:
    """反证：五个合法名字一个都不能被当成未知。"""
    for name in KNOWN_RULES:
        result = _run("--rule", name, "--json")
        payload = json.loads(result.stdout)
        assert not any("UNKNOWN_RULE" in e for e in payload["errors"]), (name, payload)


def test_no_filter_still_runs_all() -> None:
    """不带 --rule 是正常用法，不该触发 UNKNOWN_RULE。"""
    result = _run("--json")
    payload = json.loads(result.stdout)
    assert not any("UNKNOWN_RULE" in e for e in payload["errors"]), payload
