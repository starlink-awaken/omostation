"""`gac-healthcheck` 的 M1 实例 drift 项：工具没跑起来时**不得**报 ✅ 全 0。

契约来源：2026-11-15 —— 原判据是 `ok = m1_drift == 0`，**不看退出码**。
于是工具失败时 diff 为空 ⇒ drift=0 ⇒ 报 `✅ registry=0 M1=0`。

实测同一个仓的两种检出：

| 检出 | 读数 |
|---|---|
| 子模块齐全 | `❌ registry=86 M1=136 缺=18 多余=68 过期=5` |
| **缺 ecos 子模块** | `gac-m1-sync` 输出人类可读报错（非 JSON）⇒ 旧代码 `✅ registry=0 M1=0` |

**同一条检查、相反结论** —— 而绿的那次是错的。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "gac-healthcheck.py"


def _load():
    spec = importlib.util.spec_from_file_location("gac_healthcheck_m1_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["gac_healthcheck_m1_under_test"] = module
    spec.loader.exec_module(module)
    return module


def test_non_json_output_is_not_vacuous_green(monkeypatch) -> None:
    """工具输出人类可读报错（缺子模块时的真实形态）⇒ 必须 ❌ 且带原因。"""
    module = _load()
    monkeypatch.setattr(module, "run_tool", lambda script, args: (1, "❌ M3 元元模型缺失: .../m3.yaml\n"))
    result = module.probe_m1_instance_drift()
    assert result["ok"] is False, result
    assert result["tool_error"], result
    assert result["registry_rules"] is None
    assert result["m1_instances"] is None


def test_failed_exit_code_alone_blocks_ok(monkeypatch) -> None:
    """输出是合法 JSON 但退出码非 0 ⇒ 仍不得报 ✅。"""
    module = _load()
    payload = json.dumps({"registry_rules": 86, "m1_instances": 136, "diff": {}})
    monkeypatch.setattr(module, "run_tool", lambda script, args: (1, payload))
    result = module.probe_m1_instance_drift()
    assert result["ok"] is False, result


def test_clean_run_is_green(monkeypatch) -> None:
    module = _load()
    payload = json.dumps({"registry_rules": 86, "m1_instances": 86, "diff": {}})
    monkeypatch.setattr(module, "run_tool", lambda script, args: (0, payload))
    result = module.probe_m1_instance_drift()
    assert result["ok"] is True, result
    assert result["tool_error"] is None
    assert result["registry_rules"] == 86


def test_real_drift_is_red_with_counts(monkeypatch) -> None:
    """有漂移 ⇒ ❌ 且计数保留（不是「读数不可用」）。"""
    module = _load()
    payload = json.dumps(
        {
            "registry_rules": 86,
            "m1_instances": 136,
            "diff": {"missing_in_m1": ["A"], "orphan_in_m1": ["B", "C"], "stale": []},
        }
    )
    monkeypatch.setattr(module, "run_tool", lambda script, args: (0, payload))
    result = module.probe_m1_instance_drift()
    assert result["ok"] is False, result
    assert result["tool_error"] is None
    assert result["missing_in_m1"] == 1
    assert result["orphan_in_m1"] == 2


def test_missing_script_is_reported(monkeypatch) -> None:
    """脚本文件缺失 ⇒ run_tool 返回 (127, "")，同样不得空绿。"""
    module = _load()
    monkeypatch.setattr(module, "WORKSPACE", Path("/nonexistent-workspace"))
    result = module.probe_m1_instance_drift()
    assert result["ok"] is False, result
    assert result["tool_error"] == "empty output"


def test_parse_json_output_rejects_non_dict() -> None:
    module = _load()
    data, error = module.parse_json_output("[1, 2, 3]")
    assert data is None and error is None  # 合法 JSON 但不是 mapping ⇒ (None, None)
    data, error = module.parse_json_output("not json at all")
    assert data is None and error is not None
    data, error = module.parse_json_output("")
    assert data is None and error == "empty output"
