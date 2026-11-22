"""ADR-0466 法条 2 的宿主零污染守卫必须真的接在门禁上, 且缺席时如实报「没测成」。

背景: ADR-0466 §5 法条 2 明文要求 `bin/gac/check-test-host-hygiene.py`「纳入门禁
流水线」, 但它此前只登记在 `bin/_registry`, 没有任何执行入口 —— 一道被声明却不存在
的防线 (2026-11-22 接线)。

它读**宿主**目录 (`~/.local/share/omostation/`)。在 CI / 新克隆里那些目录不存在,
所以必须走门禁的 `{"measured": false, "reason": "missing_input"}` 契约: 缺席即
如实报「没测成」, 而不是报 PASS —— 后者是空绿。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "bin" / "gac" / "check-test-host-hygiene.py"
GATE = ROOT / "bin" / "gac" / "gac-local-gate.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _tool():
    return _load(TOOL, "test_host_hygiene")


def _plant_host(tmp_path: Path) -> tuple[Path, Path]:
    """把宿主侧输入指到临时目录 (cards/ 与 patrol/night-patrol-latest.json)。"""
    cards = tmp_path / "cards"
    cards.mkdir(exist_ok=True)
    patrol = tmp_path / "patrol" / "night-patrol-latest.json"
    patrol.parent.mkdir(exist_ok=True)
    patrol.write_text('{"power_status": "ok"}', encoding="utf-8")
    return cards, patrol


def test_absent_host_inputs_are_not_measured(tmp_path, monkeypatch, capsys):
    """宿主输入缺席 ⇒ measured=false + reason=missing_input, 且 exit 0 (不是通过)。"""
    mod = _tool()
    monkeypatch.setattr(mod, "HOST_OMOSTATION", tmp_path)
    monkeypatch.setattr(mod, "HOST_INPUTS", (tmp_path / "cards", tmp_path / "patrol" / "night-patrol-latest.json"))
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    rc = mod.main(["--json"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["measured"] is False, payload
    assert payload["reason"] == "missing_input"
    assert payload["ok"] is False, "没测成不得报 ok"
    assert rc == 0, "没测成不是发现, 不该让门禁红"
    assert "✅" not in out


def test_present_host_inputs_are_measured(tmp_path, monkeypatch, capsys):
    mod = _tool()
    cards, patrol = _plant_host(tmp_path)
    monkeypatch.setattr(mod, "HOST_OMOSTATION", tmp_path)
    monkeypatch.setattr(mod, "HOST_INPUTS", (cards, patrol))
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    rc = mod.main(["--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["measured"] is True
    assert payload["ok"] is True
    assert payload["violations"] == []
    assert rc == 0


def test_forged_production_card_is_a_violation(tmp_path, monkeypatch, capsys):
    """正控制: 宿主目录里真的长出伪造执行卡片时必须红。"""
    mod = _tool()
    cards, patrol = _plant_host(tmp_path)
    (cards / "fake.json").write_text(
        json.dumps({"type": "agora_task", "status": "ok", "patch_ready": True}),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "HOST_OMOSTATION", tmp_path)
    monkeypatch.setattr(mod, "HOST_INPUTS", (cards, patrol))
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    rc = mod.main(["--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["measured"] is True
    assert payload["ok"] is False
    assert rc == 1
    assert any("Forged execution card" in v for v in payload["violations"])


def test_human_output_never_claims_pass_when_unmeasured(tmp_path, monkeypatch, capsys):
    mod = _tool()
    monkeypatch.setattr(mod, "HOST_OMOSTATION", tmp_path)
    monkeypatch.setattr(
        mod, "HOST_INPUTS", (tmp_path / "cards", tmp_path / "patrol" / "night-patrol-latest.json")
    )
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    mod.main([])
    out = capsys.readouterr().out
    assert "未测成" in out and "✅" not in out


def test_gate_registers_the_check():
    """接线本身要钉住 —— 否则下次改动可以静默把这道防线拿掉。"""
    gate = _load(GATE, "gac_local_gate_hygiene")
    entries = [g for g in gate.GATES_LIST if g.get("id") == "test-host-hygiene"]
    assert len(entries) == 1, f"门禁里找不到 test-host-hygiene: {[g.get('id') for g in gate.GATES_LIST]}"
    assert entries[0]["command"] == ["bin/gac/check-test-host-hygiene.py", "--json"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
