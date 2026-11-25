"""`check-severity-registry` 在参考面缺席时必须自报「没测成」。

参考面 `projects/ecos/src/ecos/ssot/mof/m1/governance/sgf-policy.yaml` 在**未检出的
子模块**里。旧实现把它当空基准 `{}`，于是每个 primary lock 都报 not declared：
`checked=0 passed=0 mismatched=3`（实测干净检出）。那是「缺基准 ⇒ 全红」，与
「缺输入 ⇒ PASS」是同一病根的两半。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "bin" / "gac" / "check-severity-registry.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("check_severity_registry_nm", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_absent_reference_declares_not_measured(mod, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(mod, "SGF_POLICY_YAML", tmp_path / "absent-sgf-policy.yaml")
    rc = mod.main(["--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0, "参考面缺席不是仓库缺陷，不该阻断"
    assert out["measured"] is False
    assert out["reason"] == "reference_absent"
    assert out["summary"]["mismatched"] == 0


def test_present_reference_is_measured(mod, monkeypatch, tmp_path, capsys):
    """反向判据：参考面在场就必须真比，不得恒报未测成。"""
    root = tmp_path / "ws"
    root.mkdir()
    ref = root / "sgf-policy.yaml"
    ref.write_text(
        "gates:\n"
        "  - {id: gac-drift, severity: blocking, command: [bin/gac/gac-drift.py]}\n"
        "  - {id: doc-claims-check, severity: warn, command: [bin/gac/doc-claims-check.py]}\n"
        "  - {id: layer-call-direction-check, severity: informational,"
        " command: [bin/gac/layer-call-direction-check.py]}\n",
        encoding="utf-8",
    )
    # 脚本会做 `SGF_POLICY_YAML.relative_to(WORKSPACE)`, 参考面必须在 WORKSPACE 内。
    monkeypatch.setattr(mod, "WORKSPACE", root)
    monkeypatch.setattr(mod, "SGF_POLICY_YAML", ref)

    rc = mod.main(["--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc in (0, 1)
    assert out["measured"] is True
    assert out["summary"]["checked"] == 3
