"""GaC #38 field-ownership check (ADR-0456 B5 / BET-Y2Q4-T10-219).

Hermetic: every case builds a tmp checkout + tmp state root and patches the
guard's module-level targets, so no case reads the host's real system.yaml.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
GUARD_MOD = ROOT / "bin/gac/omo-state-write-guard.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(name="guard")
def fixture_guard():
    return _load(GUARD_MOD, "omo_state_write_guard_under_test")


@pytest.fixture(name="checkout")
def fixture_checkout(tmp_path):
    """A tmp code_root holding one real writer script + the registry."""
    code = tmp_path / "checkout"
    (code / "bin/gac").mkdir(parents=True)
    (code / ".omo/_truth/registry").mkdir(parents=True)
    (code / "bin/gac/writer.py").write_text("x = 1\n", encoding="utf-8")
    (code / "bin/gac/other.py").write_text("x = 1\n", encoding="utf-8")
    state = tmp_path / "state"
    (state / ".omo/state").mkdir(parents=True)
    return code, state


def _wire(guard, monkeypatch, checkout, system_yaml_text=None, owners=None):
    code, state = checkout
    registry = state / ".omo/state/system.yaml"
    if system_yaml_text is not None:
        registry.write_text(system_yaml_text, encoding="utf-8")
    owners_file = code / ".omo/_truth/registry/write-owners.yaml"
    owners_file.write_text(
        yaml.safe_dump({"fields": {".omo/state/system.yaml": owners or {}}}, allow_unicode=True),
        encoding="utf-8",
    )
    monkeypatch.setattr(guard, "_system_yaml", lambda: registry)
    monkeypatch.setattr(guard, "WRITE_OWNERS_YAML", owners_file)
    monkeypatch.setattr(guard, "WORKSPACE", code)
    monkeypatch.setattr(guard, "code_root", lambda: code)
    return registry, owners_file


def test_fully_declared_keys_pass(guard, checkout, monkeypatch):
    _wire(
        guard,
        monkeypatch,
        checkout,
        "health_score: 95\nupdated_at: now\n",
        {
            "health_score": ["script:bin/gac/writer.py", "script:bin/gac/other.py"],
            "updated_at": "anyone",
        },
    )
    assert guard.check_field_ownership() == []


def test_multi_writer_list_and_anyone_are_accepted(guard, checkout, monkeypatch):
    _wire(
        guard,
        monkeypatch,
        checkout,
        "health_score: 95\n",
        {"health_score": ["script:bin/gac/writer.py", "daemon:compass-radar", "anyone"]},
    )
    assert guard.check_field_ownership() == []


def test_undeclared_key_is_flagged(guard, checkout, monkeypatch):
    _wire(
        guard,
        monkeypatch,
        checkout,
        "health_score: 95\nprobe_undeclared_key: 1\n",
        {"health_score": "anyone"},
    )
    findings = guard.check_field_ownership()
    assert [f["key"] for f in findings] == ["probe_undeclared_key"]
    assert findings[0]["check"] == "undeclared-key"


def test_list_items_with_colon_are_not_misread_as_keys(guard, checkout, monkeypatch):
    """List items (``- ...``) are values, not mapping keys.

    A list item containing ``:`` (e.g. a task description) must NOT be
    misinterpreted as a top-level key — else the guard emits false
    undeclared-key positives on every such system.yaml.
    """
    _wire(
        guard,
        monkeypatch,
        checkout,
        "next_planned_tasks:\n"
        "- 'TASK-9BFD0422 (R4 回归泄漏: 高负载降级路径绕过沙箱台账重定向)'\n"
        "- 'TASK-B7086225 (断言分层改造: 21 场景断言按业务谓词分类重写)'\n"
        "health_score: 95\n",
        {"next_planned_tasks": "script:bin/gac/writer.py", "health_score": "anyone"},
    )
    assert guard.check_field_ownership() == []


def test_ghost_declaration_is_flagged(guard, checkout, monkeypatch):
    _wire(
        guard,
        monkeypatch,
        checkout,
        "health_score: 95\n",
        {"health_score": "anyone", "phase41_status": "anyone"},
    )
    findings = guard.check_field_ownership()
    assert [f["check"] for f in findings] == ["ghost-declaration"]
    assert findings[0]["key"] == "phase41_status"


def test_missing_script_owner_is_unresolvable(guard, checkout, monkeypatch):
    _wire(
        guard,
        monkeypatch,
        checkout,
        "health_score: 95\n",
        {"health_score": "script:bin/gac/does-not-exist.py"},
    )
    findings = guard.check_field_ownership()
    assert [f["check"] for f in findings] == ["unresolvable-owner"]
    assert "does-not-exist.py" in findings[0]["message"]


def test_owner_without_lexicon_prefix_is_unresolvable(guard, checkout, monkeypatch):
    _wire(guard, monkeypatch, checkout, "health_score: 95\n", {"health_score": "omo-debt"})
    findings = guard.check_field_ownership()
    assert [f["check"] for f in findings] == ["unresolvable-owner"]


def test_absolute_or_escaping_script_path_is_rejected(guard, checkout, monkeypatch):
    _wire(
        guard,
        monkeypatch,
        checkout,
        "health_score: 95\n",
        {"health_score": ["script:/etc/passwd", "script:../outside.py"]},
    )
    findings = guard.check_field_ownership()
    assert len(findings) == 2
    assert {f["check"] for f in findings} == {"unresolvable-owner"}


def test_missing_system_yaml_skips(guard, checkout, monkeypatch):
    """Absent write plane (fresh dev state root) is inert, not a false ghost storm."""
    _wire(guard, monkeypatch, checkout, None, {"health_score": "anyone"})
    assert guard.check_field_ownership() == []


def test_main_json_reports_two_roots_and_counts(guard, checkout, monkeypatch, capsys):
    registry, owners_file = _wire(
        guard,
        monkeypatch,
        checkout,
        "health_score: 95\nprobe_undeclared_key: 1\n",
        {"health_score": "anyone"},
    )
    assert guard.main(["--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["targets"] == {
        "system_yaml": str(registry),
        "write_owners_yaml": str(owners_file),
    }
    assert payload["declared"] == 1
    assert payload["present"] == 2
    assert payload["ownership"] == {
        "undeclared-key": 1,
        "ghost-declaration": 0,
        "unresolvable-owner": 0,
    }


def test_main_json_exits_zero_when_clean(guard, checkout, monkeypatch, capsys):
    _wire(guard, monkeypatch, checkout, "health_score: 95\n", {"health_score": "anyone"})
    assert guard.main(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["findings"] == []


def test_duplicate_key_check_still_runs(guard, checkout, monkeypatch):
    """The two pre-existing checks keep their behaviour after the root split."""
    registry, _ = _wire(guard, monkeypatch, checkout, "a: 1\nb: 2\na: 3\n", {"a": "anyone", "b": "anyone"})
    findings = guard.check_duplicate_keys()
    assert [f["key"] for f in findings] == ["a"]
    assert guard.check_unauthorized_writes() == []
    assert registry.parent.is_dir()
