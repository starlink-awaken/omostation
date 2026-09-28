"""orphan 语义: 未被代码字面量引用 ≠ 僵尸; 只有非 active 且无引用的列为清理候选; 旧名引用覆盖规范目标。"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "xrepo_orphan", WORKSPACE / "bin" / "ssot" / "check-cross-repo-consistency.py"
)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def test_cleanup_candidates_only_non_active(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pending.yaml").write_text("pending_registrations: []\n", encoding="utf-8")
    monkeypatch.setattr(mod, "PENDING_REGISTRATIONS", tmp_path / "pending.yaml")
    monkeypatch.setattr(
        mod,
        "load_agora_registered_uris",
        lambda: {
            "bos://a/live/svc": {"status": "active"},
            "bos://a/canon/svc": {"status": "active"},
            "bos://a/old/svc": {"status": "deprecated"},
            "bos://a/stub/svc": {"status": "unimplemented"},
            "bos://a/used/stub": {"status": "unimplemented"},
        },
    )
    monkeypatch.setattr(mod, "collect_referenced_uris", lambda: {"bos://legacy/name/x", "bos://a/used/stub"})
    monkeypatch.setattr(mod, "load_agora_aliases", lambda: {"bos://legacy/name/x": "bos://a/canon/svc"})
    for name in ("load_ecos_ports", "load_protocols_ports"):
        monkeypatch.setattr(mod, name, lambda: {})
    monkeypatch.setattr(mod, "find_port_conflicts", lambda: [])
    monkeypatch.setattr(sys, "argv", ["x", "--json"])

    assert mod.main() == 0
    out = json.loads(capsys.readouterr().out)
    # active 未引用只计数; 别名目标 canon 视为已引用; 被引用的 stub 不是候选
    assert out["orphan"] == 3  # live / old / stub
    assert out["orphan_cleanup_candidates"] == ["bos://a/old/svc", "bos://a/stub/svc"]
