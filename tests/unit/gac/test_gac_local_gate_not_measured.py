"""门禁把「check 自报没测成」与「测了但有问题」分开。

契约来源：债条目 `GATE-CLEAN-CHECKOUT-NOISE` 的 (a) —— 门禁在干净检出上的
16 条红**全部**由缺输入引起，但它们与真缺陷同形。逐条定性不能靠门禁猜报错
文本（那是匹配拼写），只能由 **check 自己声明**：

    {"measured": false, "reason": "<kind>", ...}

`current-state-coherence` 是第一个按此契约实现的：输入
（`.omo/state/system.yaml`）缺失时输出 `{"measured": false,
"reason": "missing_input"}`，门禁据此归入 `not_measured`。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / "bin" / "gac" / "gac-local-gate.py"
COHERENCE = ROOT / "bin" / "ssot" / "current-state-coherence.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("gac_local_gate_not_measured", GATE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_coherence_declares_not_measured_when_input_missing(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(COHERENCE), "--json", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2  # 退出码语义不变
    payload = json.loads(proc.stdout)
    assert payload["measured"] is False
    assert payload["reason"] == "missing_input"
    assert payload["ok"] is False


def test_declared_not_measured_reads_marker() -> None:
    module = _load_gate()
    marked = {"name": "x", "stdout": json.dumps({"measured": False, "reason": "missing_input"})}
    assert module._declared_not_measured(marked) == "missing_input"

    assert module._declared_not_measured({"name": "y", "stdout": ""}) is None
    # 测了、且有结论 —— 不是 not_measured
    assert module._declared_not_measured({"name": "z", "stdout": '{"measured": true}'}) is None
    # 非 JSON 输出（纯文本报错）不猜
    assert module._declared_not_measured({"name": "w", "stdout": "can't open file ..."}) is None
    # 坏 JSON 不猜
    assert module._declared_not_measured({"name": "v", "stdout": "{not json"}) is None


def test_run_gate_collects_not_measured(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_gate()
    monkeypatch.setattr(
        module,
        "gate_checks",
        lambda *a, **k: (("current-state-coherence", ["bin/ssot/current-state-coherence.py", "--json"]),),
    )
    monkeypatch.setattr(
        module,
        "run_checks",
        lambda checks: [
            {
                "name": "current-state-coherence",
                "command": "bin/ssot/current-state-coherence.py --json",
                "ok": False,
                "returncode": 2,
                "skipped": False,
                "stdout": json.dumps({"measured": False, "reason": "missing_input"}),
                "stderr": "missing input: ...",
                "duration_ms": 1,
            }
        ],
    )
    monkeypatch.setattr(module, "change_lane_files_for_scope", lambda *a, **k: [])
    monkeypatch.setattr(module, "_read_state_fingerprint", lambda: {})
    monkeypatch.setattr(module, "_check_drift", lambda snap: None)
    monkeypatch.setattr(module, "_update_drift_topic", lambda report, drift: None)
    monkeypatch.setattr(module, "extract_finding_topics", lambda results: [])
    monkeypatch.setattr(module, "preflight_report", lambda: {"complete": True, "reasons": []})

    report = module.run_gate(scope="files", files=["README.md"], strict=True)

    assert report["not_measured"] == [
        {
            "name": "current-state-coherence",
            "reason": "missing_input",
            "command": "bin/ssot/current-state-coherence.py --json",
        }
    ]
    # 判定语义不变: 它是 soft check, 不翻转 gate
    assert report["ok"] is True


def test_print_human_lists_not_measured(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    module = _load_gate()
    base = {
        "ok": True,
        "scope": "files",
        "change_lane_files": [],
        "checks": [],
        "hard_fails": [],
        "soft_warns": [],
        "finding_topics": [],
        "preflight": {"complete": True, "reasons": []},
    }
    module.print_human(base)
    assert "没测成" not in capsys.readouterr().err

    module.print_human({**base, "not_measured": [{"name": "x", "reason": "missing_input"}]})
    err = capsys.readouterr().err
    assert "没测成" in err
    assert "x: missing_input" in err


def _failing(result_name: str = "x", stdout: str = "", entrypoint: str = "projects/ecos/x.py"):
    return {
        "name": result_name,
        "command": f"{entrypoint} --json",
        "ok": False,
        "returncode": 2,
        "skipped": False,
        "stdout": stdout,
        "stderr": "",
        "duration_ms": 1,
    }


def test_missing_entrypoint_flags_submodule_script(tmp_path: Path, monkeypatch) -> None:
    module = _load_gate()
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)  # 入口必然不在
    assert module._missing_entrypoint("mof-schema-validate", ["projects/ecos/x.py", "--json"], _failing()) == "projects/ecos/x.py"


def test_missing_entrypoint_silent_when_entry_exists(tmp_path: Path, monkeypatch) -> None:
    module = _load_gate()
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "x.py").write_text("# x\n", encoding="utf-8")
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)
    assert module._missing_entrypoint("x", ["bin/x.py", "--json"], _failing(entrypoint="bin/x.py")) is None


def test_missing_entrypoint_ignores_passing_and_self_reported(tmp_path: Path, monkeypatch) -> None:
    module = _load_gate()
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)
    passing = {**_failing(), "ok": True}
    assert module._missing_entrypoint("x", ["projects/ecos/x.py"], passing) is None
    self_reported = _failing(stdout=json.dumps({"measured": False, "reason": "missing_input"}))
    assert module._missing_entrypoint("x", ["projects/ecos/x.py"], self_reported) is None


def test_missing_entrypoint_ignores_absolute_and_bare_commands(tmp_path: Path, monkeypatch) -> None:
    module = _load_gate()
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)
    # 绝对路径不是入口（且它不会中断扫描: 后面那个缺失的相对入口仍要被认出）
    assert module._missing_entrypoint("x", ["/usr/bin/python3", "bin/x.py"], _failing(entrypoint="bin/x.py")) == "bin/x.py"
    # 纯裸命令没有入口可言
    assert module._missing_entrypoint("y", ["make", "test"], _failing(entrypoint="")) is None


def test_service_config_drift_is_machine_readable_and_declares_absence(module=None) -> None:
    """本机 plist 目录缺席时, service-config-drift 必须能自报没测成。

    债条目 OMO-DEBT-GATE-SERVICE-CONFIG-DRIFT-HOST-STATE-INPUT-NO-PROVENANCE：
    此前命令不带 --json, 门禁读不到 measured:false, 只能看到 ok:true —— 「缺席即绿」。
    """
    gate = _load_gate()
    # fallback 策略必须带 --json（齐备树生效的是 ecos 的 sgf-policy，由子模块侧决定）
    entry = next(g for g in gate.DEFAULT_POLICY["gates"] if g["id"] == "service-config-drift")
    assert "--json" in entry["command"]
    assert gate._declared_not_measured(
        {
            "name": "service-config-drift",
            "stdout": '{"ok": true, "measured": false, "reason": "launchd_observer_unavailable"}',
        }
    ) == "launchd_observer_unavailable"
    assert "launchd_observer_unavailable" in gate.KNOWN_NOT_MEASURED_REASONS
