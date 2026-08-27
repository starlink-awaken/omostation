from __future__ import annotations

import importlib.util
import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "gac-local-gate.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("gac_local_gate_purity", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("scope", "files", "run_id", "strict", "ci"),
    [
        ("staged", None, "", False, False),
        ("files", ["bin/gac/gac-local-gate.py"], "", False, False),
        ("run", None, "missing-run", False, False),
        ("staged", None, "", True, False),
        ("staged", None, "", True, True),
    ],
)
def test_automatic_gate_never_selects_explicit_ops(
    monkeypatch: pytest.MonkeyPatch,
    scope: str,
    files: list[str] | None,
    run_id: str,
    strict: bool,
    ci: bool,
) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "staged_files_git", lambda: [])
    monkeypatch.setattr(module, "_is_ci_env", lambda: ci)

    assert "install-watch-agent" in module.OPS_ONLY_CHECKS
    selected = module.gate_checks(scope, files, run_id, strict)

    assert "install-watch-agent" not in {name for name, _command in selected}


def test_human_output_emits_events_only_when_explicitly_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    emitted: list[tuple[bool, object, object]] = []
    monkeypatch.setattr(
        module,
        "_emit_gate_events",
        lambda ok, hard, soft: emitted.append((ok, hard, soft)),
    )
    report = {
        "ok": True,
        "scope": "files",
        "change_lane_files": [],
        "checks": [],
        "hard_fails": [],
        "soft_warns": [],
        "finding_topics": [],
    }

    module.print_human(report)
    assert emitted == []

    module.print_human(report, emit_events=True)
    assert emitted == [(True, [], [])]

    failed_report = {
        **report,
        "ok": False,
        "checks": [
            {
                "name": "example-check",
                "ok": False,
                "command": ["example-check"],
                "stdout": "",
                "stderr": "failed",
            }
        ],
        "hard_fails": [{"name": "example-check"}],
    }
    module.print_human(failed_report, verbose=True)
    assert emitted == [(True, [], [])]

    module.print_human(failed_report, verbose=True, emit_events=True)
    assert emitted[-1] == (False, [{"name": "example-check"}], [])


@pytest.mark.parametrize("json_mode", [False, True])
@pytest.mark.parametrize("emit_events", [False, True])
def test_cli_event_flag_is_independent_of_output_format(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    json_mode: bool,
    emit_events: bool,
) -> None:
    module = _load_module()
    report = {
        "ok": True,
        "scope": "files",
        "change_lane_files": [],
        "checks": [],
        "hard_fails": [],
        "soft_warns": [],
        "finding_topics": [],
    }
    emitted: list[tuple[bool, object, object]] = []
    monkeypatch.setattr(module, "run_gate", lambda *args, **kwargs: report)
    monkeypatch.setattr(
        module,
        "_emit_gate_events",
        lambda ok, hard, soft: emitted.append((ok, hard, soft)),
    )
    argv = [str(SCRIPT)]
    if json_mode:
        argv.append("--json")
    if emit_events:
        argv.append("--emit-events")
    monkeypatch.setattr(sys, "argv", argv)

    assert module.main() == 0
    output = capsys.readouterr().out
    if json_mode:
        assert json.loads(output)["ok"] is True
    expected = [(True, [], [])] if emit_events else []
    assert emitted == expected


def test_make_target_expands_to_read_only_gate_command() -> None:
    result = subprocess.run(
        ["make", "-n", "gac-local-gate"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    commands = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert len(commands) == 1
    tokens = shlex.split(commands[0])
    assert tokens[-1] == "bin/gac/gac-local-gate.py"
    assert "git" not in tokens
    assert all("submodule" not in token for token in tokens)


def test_conflict_marker_gate_scans_all_tracked_files() -> None:
    module = _load_module()
    commands = {gate["id"]: gate["command"] for gate in module.GATES_LIST}

    assert commands["check-conflict-markers"] == [
        "bin/gac/check-conflict-markers.py",
        "--all",
    ]
