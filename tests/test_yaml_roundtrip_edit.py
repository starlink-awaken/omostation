"""yaml-roundtrip-edit 工具测试。"""
from pathlib import Path
import importlib.util

import yaml

_SPEC = importlib.util.spec_from_file_location(
    "yaml_roundtrip_edit",
    Path(__file__).resolve().parents[1] / "lib" / "yaml_ssot_edit.py",
)
assert _SPEC and _SPEC.loader
_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_mod)
roundtrip_edit = _mod.roundtrip_edit


def test_roundtrip_insert_and_preserve_unicode(tmp_path: Path) -> None:
    p = tmp_path / "r.yaml"
    p.write_text("families:\n  - id: 中文域\n    items:\n      - scope: a\n        n: 1\n", encoding="utf-8")

    def edit(data):
        fam = next(f for f in data["families"] if f["id"] == "中文域")
        fam.setdefault("transactions", []).append({"scope": "新事务", "n": 2})
        return data

    roundtrip_edit(p, edit)
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert d["families"][0]["transactions"][-1]["scope"] == "新事务"
    assert d["families"][0]["items"][0]["n"] == 1
    assert "中文域" in p.read_text(encoding="utf-8")  # allow_unicode 生效


def test_roundtrip_no_change_is_idempotent(tmp_path: Path) -> None:
    p = tmp_path / "r.yaml"
    before = p.write_text("a: 1\nb: 中文\n", encoding="utf-8")
    roundtrip_edit(p, lambda d: d)
    assert p.read_text(encoding="utf-8") == "a: 1\nb: 中文\n"  # 无变化不重写
