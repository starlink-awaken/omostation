"""`bin/ssot/script-registry.py` 必须报重复登记，而不是把 id 收进 set 静默折叠。

契约来源：2026-11-14 —— 登记面里实测有 **3 组**同一脚本被两个 yaml 登记
（`bin/ssot/fix-remotes.py` / `bin/ssot/scene-card-review.py` /
`bin/gac/zhixing_host_sync.py`），其中 `scene-card-review` 那对**逐字节相同**，
另两对同名不同详细度。而 `validate()` 把 id 收进 set ⇒ 重复**静默折叠**、
校验照绿，于是「哪一份是权威」无人知道。

本文件钉三层：检测逻辑本身、合成样本自证、真实登记面无重复。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "ssot" / "script-registry.py"


def _load():
    spec = importlib.util.spec_from_file_location("script_registry_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["script_registry_under_test"] = module
    spec.loader.exec_module(module)
    return module


def _write_registry(root: Path, entries: dict[str, str]) -> Path:
    """entries: filename -> id"""
    d = root / "bin" / "_registry" / "scripts"
    d.mkdir(parents=True, exist_ok=True)
    for fname, sid in entries.items():
        (d / fname).write_text(
            f'schema: script-registry/v1\nid: {sid}\nname: {sid}\n', encoding="utf-8"
        )
    return d


def test_find_duplicates_empty_and_single() -> None:
    module = _load()
    assert module.find_duplicates({}) == {}
    assert module.find_duplicates({"a": ["x.yaml"]}) == {}


def test_find_duplicates_reports_multi_registration() -> None:
    module = _load()
    got = module.find_duplicates({"a": ["x.yaml", "y.yaml"], "b": ["z.yaml"]})
    assert got == {"a": ["x.yaml", "y.yaml"]}


def test_collect_registrations_detects_synthetic_duplicate(tmp_path: Path) -> None:
    """自证：合成一个重复登记，检测必须点名两个来源。"""
    module = _load()
    reg = _write_registry(
        tmp_path,
        {"one.yaml": "bin/x.py", "two.yaml": "bin/x.py", "three.yaml": "bin/y.py"},
    )
    registered, sources = module.collect_registrations(reg)
    assert registered == {"bin/x.py", "bin/y.py"}
    dups = module.find_duplicates(sources)
    assert set(dups) == {"bin/x.py"}
    assert len(dups["bin/x.py"]) == 2


def test_real_registry_has_no_duplicate_ids() -> None:
    """真实登记面当前无重复 —— 这条会把「再出现重复」当场变红。"""
    module = _load()
    _, sources = module.collect_registrations(ROOT / "bin" / "_registry" / "scripts")
    dups = module.find_duplicates(sources)
    assert dups == {}, f"登记面出现重复 id: {dups}"
