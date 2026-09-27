"""引用口径: 只计整个字面量为 URI; agora 旧名别名 (目标已登记) 视为已覆盖。"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "xrepo_literal", WORKSPACE / "bin" / "ssot" / "check-cross-repo-consistency.py"
)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

SRC = '''
"""模块说明: 例如 bos://doc/example/action 这类写法。"""
# 注释里的 bos://comment/only/uri 不算
URI = "bos://real/svc/run"
WITH_QUERY = "bos://real/embed/call?model=bge-m3"
parser_help = "Capability URI (e.g. bos://mail/draft), repeatable"
'''


def test_only_whole_literals_count() -> None:
    assert mod._literal_uris(SRC) == {"bos://real/svc/run", "bos://real/embed/call"}


def test_alias_to_registered_target_is_covered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pending.yaml").write_text("pending_registrations: []\n", encoding="utf-8")
    monkeypatch.setattr(mod, "PENDING_REGISTRATIONS", tmp_path / "pending.yaml")
    monkeypatch.setattr(mod, "load_agora_registered_uris", lambda: {"bos://canon/svc/run": {}})
    monkeypatch.setattr(mod, "collect_referenced_uris", lambda: {"bos://old/svc/run", "bos://orphan/x/y"})
    monkeypatch.setattr(
        mod,
        "load_agora_aliases",
        lambda: {"bos://old/svc/run": "bos://canon/svc/run", "bos://orphan/x/y": "bos://nowhere/x/y"},
    )
    for name in ("load_ecos_ports", "load_protocols_ports"):
        monkeypatch.setattr(mod, name, lambda: {})
    monkeypatch.setattr(mod, "find_port_conflicts", lambda: [])
    monkeypatch.setattr(sys, "argv", ["x", "--json"])

    assert mod.main() == 1
    out = json.loads(capsys.readouterr().out)
    assert out["unregistered_new_list"] == ["bos://orphan/x/y"]  # 别名目标未登记则不算覆盖
