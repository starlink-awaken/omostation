#!/usr/bin/env python3
"""governance-orchestrator 的路径解析钉 (2026-11-12).

两处路径缺陷让 `compliance_check()` 的 `interface_check` 恒 false:

1. `REPO = Path(__file__).resolve().parents[1]` —— `__file__` 是
   `bin/gac/governance-orchestrator.py`, `parents[1]` 是 `<root>/bin` 而不是
   检出根, 于是模块里每条 `REPO / "bin/..."` 都指向 `<root>/bin/bin/...`
   (全部不存在)。两个同类编排器 (`unified-orchestrator` /
   `pipeline-orchestrator`) 用的都是 `parents[2]`。
2. `interface_check` 写的是 `bin/gac/check-interfaces.py` —— 真身是
   `bin/ssot/check-interfaces.py`。

本文件把「REPO 必须是检出根」与「模块里每条 `REPO / '<file>'` 都解析到真实文件」
钉住, 并实跑一次 compliance_check。
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "governance-orchestrator.py"


def _load():
    spec = importlib.util.spec_from_file_location("go_paths", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_repo_is_the_workspace_root() -> None:
    m = _load()
    assert m.REPO == ROOT, f"REPO 解析到 {m.REPO}, 应为检出根 {ROOT}"
    assert (m.REPO / "bin" / "gac" / "governance-orchestrator.py").is_file()


def test_every_repo_file_reference_resolves() -> None:
    src = SCRIPT.read_text(encoding="utf-8")
    refs = sorted(set(re.findall(r'REPO / "([^"]+)"', src)))
    assert refs, "前提不成立: 模块里没有 REPO / '<path>' 引用"
    missing = [rel for rel in refs if Path(rel).suffix and not (ROOT / rel).exists()]
    assert not missing, f"这些 REPO / '<file>' 引用指向不存在的文件: {missing}"


def test_compliance_check_reaches_all_five() -> None:
    m = _load()
    r = m.compliance_check()
    assert r["total"] == 5
    assert r["passed"] == r["total"], r
