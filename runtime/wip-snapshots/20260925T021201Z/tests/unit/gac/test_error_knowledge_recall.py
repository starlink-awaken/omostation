"""The pitfall recall path must never drop an entry silently.

Regression guard for the 2026-09-24 retro finding: ``_load_all`` filtered on
``d.get("title")``, so ``PITFALL-CRD-001`` (legacy ``name:`` instead of ``title:``)
was invisible to ``lookup``/``stats``/escalation while ``check`` — which walked the
tree with its own copy of the loader — counted it. ``check`` reported 34, recall
reported 33, and nothing failed. Same roundtrip also wrote the loader's private
``_path`` (a host-absolute, already-deleted worktree path) into 6 committed files.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "error-knowledge.py"

LEGACY = """id: PITFALL-CRD-001
name: ADR 快速迭代导致治理管道不稳定
severity: high
description: gate 只验证格式不验证速率
root_cause: ADR 文件修改无速率限制
prevention: check-adr-iteration-rate gate
"""

CURRENT = """schema: agent-error/v1
id: PITFALL-GAT-900
category: gate
severity: medium
title: 召回路径静默丢条目
symptom: check 数到 34 而 lookup 数到 33
root_cause: _load_all 按 title 过滤
solution: 归一化 legacy 条目并让 check 复用同一 loader
prevention: ''
tags:
- recall
discovered_by: governance-agent
discovered_at: '2026-09-24'
times_encountered: 1
status: active
"""


def _load_module() -> object:
    spec = importlib.util.spec_from_file_location("error_knowledge", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _library(tmp_path: Path, *files: tuple[str, str]) -> Path:
    root = tmp_path / "pitfalls"
    for name, body in files:
        path = root / Path(name).parent / Path(name).name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def _by_id(entries: list[dict]) -> dict[str, dict]:
    return {e["id"]: e for e in entries}


def test_legacy_entry_is_recallable_with_normalized_fields(tmp_path: Path) -> None:
    module = _load_module()
    module.PITFALLS_DIR = _library(tmp_path, ("coordination/PITFALL-CRD-001.yaml", LEGACY))

    entries = module._load_all()

    assert len(entries) == 1
    entry = _by_id(entries)["PITFALL-CRD-001"]
    assert entry["title"] == "ADR 快速迭代导致治理管道不稳定"
    assert entry["category"] == "coordination"


def test_check_and_recall_report_the_same_total(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    module = _load_module()
    module.PITFALLS_DIR = _library(
        tmp_path,
        ("coordination/PITFALL-CRD-001.yaml", LEGACY),
        ("gate/PITFALL-GAT-900.yaml", CURRENT),
    )

    assert module.cmd_check(argparse.Namespace(json=True)) == 0
    reported = capsys.readouterr().out

    assert '"total": 2' in reported
    assert len(module._load_all()) == 2


def test_entry_without_title_or_name_is_reported_not_dropped(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    module = _load_module()
    module.PITFALLS_DIR = _library(tmp_path, ("gate/PITFALL-GAT-901.yaml", "id: PITFALL-GAT-901\nseverity: low\n"))

    issues: list[str] = []
    assert module._load_all(issues=issues) == []
    assert issues and "no title or name" in issues[0]

    assert module.cmd_check(argparse.Namespace(json=True)) == 1
    assert "no title or name" in capsys.readouterr().out


def test_unparseable_file_is_reported_not_swallowed(tmp_path: Path) -> None:
    module = _load_module()
    module.PITFALLS_DIR = _library(tmp_path, ("gate/PITFALL-GAT-902.yaml", "id: [unclosed\n"))

    issues: list[str] = []
    assert module._load_all(issues=issues) == []
    assert issues and "unparseable" in issues[0]


def test_save_entry_never_persists_loader_private_keys(tmp_path: Path) -> None:
    module = _load_module()
    module.PITFALLS_DIR = _library(tmp_path, ("gate/PITFALL-GAT-900.yaml", CURRENT))

    entry = module._load_all()[0]
    entry["times_encountered"] = 2
    module._save_entry(entry)

    written = (module.PITFALLS_DIR / "gate" / "PITFALL-GAT-900.yaml").read_text(encoding="utf-8")
    assert "_path:" not in written
    assert "_file:" not in written
    assert "/Users/" not in written
    assert "times_encountered: 2" in written


COORDINATION_SYMPTOM = (
    "the push was rejected by branch protection while the commit sat on local main"
)
SHALLOW_SYMPTOM = (
    "submit refuses the push because branch protection reports the pinned commit as unpushed"
)

COORDINATION = f"""schema: agent-error/v1
id: PITFALL-COO-901
category: coordination
severity: medium
title: 分支保护拒绝直推 main
symptom: {COORDINATION_SYMPTOM}
root_cause: 直接在 main 上提交
solution: 走 worktree + PR
prevention: ''
tags:
- push
discovered_by: governance-agent
discovered_at: '2026-09-24'
times_encountered: 1
status: active
"""

#: A genuinely different submodule defect that nonetheless shares ≥3 symptom words.
SHALLOW_EXISTING = """schema: agent-error/v1
id: PITFALL-SUB-901
category: submodule
severity: medium
title: 子模块指针回退 — 并发合并从陈旧 base 拉回旧指针
symptom: submit refuses the push and branch protection blocks the commit
root_cause: 陈旧 base
solution: rebase 后重推
prevention: ''
tags:
- pointer
discovered_by: governance-agent
discovered_at: '2026-09-24'
times_encountered: 1
status: active
"""


def _record(module: object, **overrides: object) -> int:
    args = {
        "category": "submodule",
        "severity": "high",
        "title": "浅历史子模块让未推送判定假阳性",
        "symptom": SHALLOW_SYMPTOM,
        "root_cause": "graft 边界压在 pin 上",
        "solution": "先测 --is-shallow-repository，再到全量 clone 复核",
        "prevention": "",
        "tags": "shallow",
        "agent": "governance-agent",
        "draft": False,
        "confirm_dup": None,
    }
    args.update(overrides)
    return module.cmd_record(argparse.Namespace(**args))


def test_dedup_does_not_swallow_a_distinct_pitfall_from_another_category(
    tmp_path: Path,
) -> None:
    """Three shared symptom tokens must not merge two unrelated root causes.

    Measured 2026-09-24: recording the shallow-submodule defect incremented
    ``PITFALL-COO-002`` (branch protection on ``chore(state)`` commits) and threw the
    new lesson away — ``cmd_record`` scanned every category and returned on its first
    fuzzy match. The inflated counter is also what drives rule escalation, so one
    loose match both loses knowledge and promotes an unrelated entry.
    """
    module = _load_module()
    # The test is only worth running while it still reproduces the trigger condition.
    assert module.symptom_overlap(SHALLOW_SYMPTOM, COORDINATION_SYMPTOM) >= 3

    module.PITFALLS_DIR = _library(tmp_path, ("coordination/PITFALL-COO-901.yaml", COORDINATION))

    assert _record(module) == 0
    created = sorted(p.name for p in (module.PITFALLS_DIR / "submodule").glob("*.yaml"))
    assert created == ["PITFALL-SUB-001.yaml"]
    neighbour = (module.PITFALLS_DIR / "coordination" / "PITFALL-COO-901.yaml").read_text(
        encoding="utf-8"
    )
    assert "times_encountered: 1" in neighbour


def test_same_category_lookalike_is_reported_not_merged(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Even inside one category, a fuzzy match warns instead of discarding the record."""
    module = _load_module()
    module.PITFALLS_DIR = _library(
        tmp_path, ("submodule/PITFALL-SUB-901.yaml", SHALLOW_EXISTING)
    )

    assert _record(module) == 0
    out = capsys.readouterr().out
    assert "DEDUP CANDIDATES" in out and "PITFALL-SUB-901" in out
    assert sorted(p.name for p in (module.PITFALLS_DIR / "submodule").glob("*.yaml")) == [
        "PITFALL-SUB-901.yaml",
        "PITFALL-SUB-902.yaml",
    ]
    existing = (module.PITFALLS_DIR / "submodule" / "PITFALL-SUB-901.yaml").read_text(
        encoding="utf-8"
    )
    assert "times_encountered: 1" in existing


def test_confirm_dup_increments_the_named_entry_only(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    module = _load_module()
    module.PITFALLS_DIR = _library(
        tmp_path, ("submodule/PITFALL-SUB-901.yaml", SHALLOW_EXISTING)
    )

    assert _record(module, confirm_dup="PITFALL-SUB-901") == 0
    assert "times_encountered: 2" in (
        module.PITFALLS_DIR / "submodule" / "PITFALL-SUB-901.yaml"
    ).read_text(encoding="utf-8")
    assert sorted(p.name for p in (module.PITFALLS_DIR / "submodule").glob("*.yaml")) == [
        "PITFALL-SUB-901.yaml"
    ]

    assert _record(module, confirm_dup="PITFALL-SUB-777") == 1
    assert "not a dedup candidate" in capsys.readouterr().err
