"""Tests for bin/gac/check-silent-workflows.py

Covers:
  - exit code 0 when no silent workflows (current state)
  - exit code 1 when warn_count > 0 (synthetic silent workflow)
  - exit code 2 on missing registry
  - JSON output shape
  - --list-silent output
  - Synthetic events/runs wiring

All tests use isolated tmp_path fixtures with stub registry + events.
The omo.workflow import is pre-loaded via the projects/omo venv sys.path
since the script adds that path itself on import.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

WORKSPACE = Path(__file__).resolve().parents[1]
OMO_SRC = WORKSPACE / "projects" / "omo" / "src"
SCRIPT = WORKSPACE / "bin" / "gac" / "check-silent-workflows.py"
_MODULE = "_check_silent_workflows_test"


def _load_script_module():
    # Pre-add omo src to sys.path so the script's own sys.path.insert finds
    # the package (it's the same path; this is just defensive against an
    # order-dependent sys.path state).
    if str(OMO_SRC) not in sys.path:
        sys.path.insert(0, str(OMO_SRC))
    spec = importlib.util.spec_from_file_location(_MODULE, SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def script_mod():
    return _load_script_module()


def _run_main(mod, *args: str) -> int:
    """Invoke main() with a controlled argv, restoring afterwards."""
    old = sys.argv
    sys.argv = [str(SCRIPT), *args]
    try:
        return mod.main()
    finally:
        sys.argv = old


@pytest.fixture
def fake_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a synthetic workspace with stub registry + ledger."""
    ws = tmp_path
    monkeypatch.setattr(sys.modules[_MODULE], "WORKSPACE", ws)
    monkeypatch.setattr(
        sys.modules[_MODULE], "REGISTRY_PATH",
        ws / ".omo/_truth/registry/agent-workflows",
    )
    monkeypatch.setattr(
        sys.modules[_MODULE], "EVENTS_PATH",
        ws / ".omo/_delivery/agent-workflows/events.jsonl",
    )
    monkeypatch.setattr(
        sys.modules[_MODULE], "RUNS_DIR",
        ws / ".omo/_delivery/agent-workflows/runs",
    )
    return ws


def _write_registry(ws: Path, workflows: list[dict], diff_checks: list[dict] | None = None) -> None:
    reg = ws / ".omo/_truth/registry/agent-workflows"
    reg.mkdir(parents=True, exist_ok=True)
    payload = {
        "workflows": workflows,
        "diff_checks": diff_checks or [],
        "doctor_checks": [],
        "silent_workflow_policy": {
            "warn_after_days": 30,
            "warn_after_days_by_frequency": {
                "on_demand": 30,
                "periodic": 7,
                "continuous": 1,
            },
        },
    }
    (reg / "_root.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _write_events(ws: Path, events: list[dict]) -> None:
    p = ws / ".omo/_delivery/agent-workflows"
    p.mkdir(parents=True, exist_ok=True)
    (p / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )


def test_exit_zero_when_no_silent_workflows(script_mod, fake_workspace):
    """Workflow with diff_check coverage → not silent → exit 0."""
    _write_registry(
        fake_workspace,
        workflows=[
            {
                "id": "wf-active",
                "run_frequency": "on_demand",
                "surfaces": {"write": ["docs/"]},
            }
        ],
        diff_checks=[{"paths": ["docs/"]}],
    )
    assert _run_main(script_mod) == 0


def test_exit_zero_when_recent_run(script_mod, fake_workspace):
    """Workflow with no diff_check but a recent run → not silent."""
    from datetime import datetime, UTC, timedelta

    _write_registry(
        fake_workspace,
        workflows=[
            {
                "id": "wf-by-run",
                "run_frequency": "on_demand",
                "surfaces": {"write": ["bin/"]},
            }
        ],
    )
    recent = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_events(
        fake_workspace,
        [{"event": "agent_workflow_start", "workflow_id": "wf-by-run", "ts": recent}],
    )
    assert _run_main(script_mod) == 0


def test_exit_one_when_silent_workflow(script_mod, fake_workspace, capsys):
    """Workflow with no coverage and no recent run → warn_count > 0 → exit 1."""
    _write_registry(
        fake_workspace,
        workflows=[
            {
                "id": "wf-silent",
                "run_frequency": "on_demand",
                "surfaces": {"write": ["x/"]},
            }
        ],
    )
    assert _run_main(script_mod) == 1
    captured = capsys.readouterr()
    assert "wf-silent" in captured.out


def test_exit_two_on_missing_registry(script_mod, tmp_path, monkeypatch):
    """Empty workspace (no registry dir) → exit 2."""
    monkeypatch.setattr(sys.modules[_MODULE], "WORKSPACE", tmp_path)
    monkeypatch.setattr(
        sys.modules[_MODULE], "REGISTRY_PATH",
        tmp_path / ".omo/_truth/registry/agent-workflows",
    )
    monkeypatch.setattr(
        sys.modules[_MODULE], "EVENTS_PATH",
        tmp_path / ".omo/_delivery/agent-workflows/events.jsonl",
    )
    monkeypatch.setattr(
        sys.modules[_MODULE], "RUNS_DIR",
        tmp_path / ".omo/_delivery/agent-workflows/runs",
    )
    assert _run_main(script_mod) == 2


def test_json_output_shape(script_mod, fake_workspace, capsys):
    """--json emits warn_count, silent_workflows, registry_workflows."""
    _write_registry(
        fake_workspace,
        workflows=[
            {
                "id": "wf-a",
                "run_frequency": "on_demand",
                "surfaces": {"write": ["docs/"]},
            }
        ],
        diff_checks=[{"paths": ["docs/"]}],  # coverage → not silent
    )
    assert _run_main(script_mod, "--json") == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "warn_count" in data
    assert "silent_workflows" in data
    assert "registry_workflows" in data
    assert data["registry_workflows"] == 1
    assert data["warn_count"] == 0
    assert data["silent_workflows"] == []


def test_list_silent_flag(script_mod, fake_workspace, capsys):
    """--list-silent prints only the silent workflow IDs."""
    _write_registry(
        fake_workspace,
        workflows=[
            {
                "id": "wf-silent-1",
                "run_frequency": "on_demand",
                "surfaces": {"write": ["x/"]},
            },
            {
                "id": "wf-active",
                "run_frequency": "on_demand",
                "surfaces": {"write": ["docs/"]},
            },
        ],
        diff_checks=[{"paths": ["docs/"]}],
    )
    assert _run_main(script_mod, "--list-silent") == 1
    captured = capsys.readouterr()
    assert "wf-silent-1" in captured.out
    assert "wf-active" not in captured.out