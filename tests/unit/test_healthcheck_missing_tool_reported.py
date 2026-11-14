"""`gac-healthcheck.py` 的 legacy-drift 项：工具缺失必须**显式报**，不能伪装成「扫了 0 个」。

契约来源：2026-11-14 —— `bin/gac/gac-ingest-legacy.py` 被 #1839 归档到
`bin/_archive/migrations/` 而引用没跟。于是 `run_tool` 拿不到输出、json={}
⇒ 读数全是 0、判 ❌。**「源=0 indexed=0 missing=0 ghost=0」与「真的没问题」
在输出里长得一样**，而真相是「工具根本没跑」。

本文件钉三种形态：工具缺失 / 工具正常 / 工具跑起来但失败。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "gac-healthcheck.py"


def _load():
    spec = importlib.util.spec_from_file_location("gac_healthcheck_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["gac_healthcheck_under_test"] = module
    spec.loader.exec_module(module)
    return module


def _make_tool(tmp_path: Path, name: str, body: str) -> None:
    d = tmp_path / "bin" / "gac"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body, encoding="utf-8")


def test_missing_tool_is_reported_not_zeroed(monkeypatch, tmp_path: Path) -> None:
    module = _load()
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)
    result = module.probe_legacy_drift("bin/gac/absent.py")
    assert result["tool_missing"] is True
    assert result["ok"] is False
    # 关键: 读数必须是 None, 不能是 0 —— 0 会被读成「扫了 0 个」。
    assert result["legacy_count"] is None
    assert result["indexed_count"] is None
    assert result["missing"] is None
    assert result["ghost"] is None


def test_present_tool_ok(monkeypatch, tmp_path: Path) -> None:
    module = _load()
    _make_tool(
        tmp_path,
        "ok.py",
        "#!/usr/bin/env python3\n"
        "import json\n"
        'print(json.dumps({"legacy_count": 3, "indexed_count": 2, "missing": ["a"], "ghost": []}))\n',
    )
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)
    result = module.probe_legacy_drift("bin/gac/ok.py")
    assert result["tool_missing"] is False
    assert result["ok"] is True
    assert result["legacy_count"] == 3
    assert result["indexed_count"] == 2
    assert result["missing"] == 1
    assert result["ghost"] == 0


def test_present_tool_that_fails_keeps_readings(monkeypatch, tmp_path: Path) -> None:
    """工具跑了但失败 ⇒ ok=False 且读数保留 —— 与「工具没跑」必须区分开。"""
    module = _load()
    _make_tool(
        tmp_path,
        "bad.py",
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        'print(json.dumps({"legacy_count": 9, "indexed_count": 1, "missing": ["x"], "ghost": ["y"]}))\n'
        "sys.exit(1)\n",
    )
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)
    result = module.probe_legacy_drift("bin/gac/bad.py")
    assert result["tool_missing"] is False
    assert result["ok"] is False
    assert result["legacy_count"] == 9
    assert result["missing"] == 1
    assert result["ghost"] == 1


def test_real_checkout_reports_the_archived_tool() -> None:
    """真实检出上, 那一条必须被判成 tool_missing —— 而不是全 0。"""
    module = _load()
    result = module.probe_legacy_drift()
    assert result["tool_missing"] is True, result
    assert result["legacy_count"] is None
