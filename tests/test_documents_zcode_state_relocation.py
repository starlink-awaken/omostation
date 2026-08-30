from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from lib import documents_zcode_state_relocation as relocation

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "documents-zcode-config.py"


@dataclass(frozen=True)
class Layout:
    source_base: Path
    target_base: Path
    settings: Path
    manifest: Path
    original_settings: bytes

    @property
    def source_root(self) -> Path:
        return self.source_base / ".zcode"

    @property
    def target_root(self) -> Path:
        return self.target_base / ".zcode"


def _layout(tmp_path: Path) -> Layout:
    source_base = tmp_path / "Documents" / "ZCode"
    source_root = source_base / ".zcode"
    state = source_root / "v2"
    for directory in (
        state / "sessions",
        state / "logs",
        state / "checkpoints",
        state / "crash",
        state / "certs",
        state / "agent-config",
        source_root / "workspace" / "default",
        source_root / "plugin-workspace",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    for name, content in (
        ("tasks-index.sqlite", b"sqlite"),
        ("tasks-index.sqlite-wal", b"wal"),
        ("tasks-index.sqlite-shm", b"shm"),
        ("config.json", b'{"provider": {}}\n'),
        ("credentials.json", b'{"token": "fixture"}\n'),
    ):
        (state / name).write_bytes(content)
    (state / "sessions" / "session.json").write_text("{}\n", encoding="utf-8")
    (state / "checkpoints" / "checkpoint.bin").write_bytes(b"checkpoint")

    settings = tmp_path / "home" / ".zcode" / "v2" / "setting.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(
        json.dumps(
            {
                "locale": "zh-CN",
                "dataBaseDir": str(source_base),
                "recentProjects": [str(tmp_path / "project")],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    settings.chmod(0o640)
    return Layout(
        source_base=source_base,
        target_base=tmp_path / "Workspace" / "runtime" / "clients" / "zcode-data",
        settings=settings,
        manifest=tmp_path / "Workspace" / "runtime" / "quarantine" / "zcode" / "manifest.json",
        original_settings=settings.read_bytes(),
    )


def _paths(layout: Layout) -> relocation.RelocationPaths:
    return relocation.RelocationPaths(
        source_base=layout.source_base,
        target_base=layout.target_base,
        settings=layout.settings,
        manifest=layout.manifest,
    )


def test_apply_rejects_active_zcode_without_mutation(tmp_path: Path) -> None:
    layout = _layout(tmp_path)

    with pytest.raises(relocation.RelocationError, match="ZCode must be quiescent"):
        relocation.apply_relocation(
            _paths(layout),
            active_processes=[{"pid": 42, "command": "ZCode"}],
            source_handles=[],
        )

    assert layout.source_root.is_dir()
    assert not layout.target_root.exists()
    assert layout.settings.read_bytes() == layout.original_settings


def test_apply_rejects_missing_sqlite_sidecar(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    (layout.source_root / "v2" / "tasks-index.sqlite-wal").unlink()

    with pytest.raises(relocation.RelocationError, match="critical state is incomplete"):
        relocation.apply_relocation(_paths(layout), active_processes=[], source_handles=[])


def test_apply_rejects_target_collision(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    layout.target_root.mkdir(parents=True)

    with pytest.raises(relocation.RelocationError, match="target already exists"):
        relocation.apply_relocation(_paths(layout), active_processes=[], source_handles=[])


def test_apply_accepts_preexisting_empty_recovery_parent(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    layout.manifest.parent.mkdir(parents=True)

    result = relocation.apply_relocation(_paths(layout), active_processes=[], source_handles=[])

    assert result["status"] == "applied"
    assert layout.source_root.exists()


def test_same_device_guard_fails_closed() -> None:
    with pytest.raises(relocation.RelocationError, match="same filesystem"):
        relocation.require_same_device(source_device=1, target_device=2)


def test_free_space_guard_fails_closed() -> None:
    with pytest.raises(relocation.RelocationError, match="insufficient target disk space"):
        relocation.require_free_space(required_bytes=2, available_bytes=1)


def test_process_parser_uses_executable_identity_not_shell_arguments() -> None:
    process_table = """\
  11   1 /bin/zsh
  12   1 zcode-cli
  13   1 /Applications/ZCode.app/Contents/Frameworks/ZCode Helper.app/Contents/MacOS/ZCode Helper
"""

    assert relocation._parse_process_table(process_table) == [  # noqa: SLF001
        {"pid": 12, "ppid": 1, "command": "zcode-cli"},
        {
            "pid": 13,
            "ppid": 1,
            "command": "/Applications/ZCode.app/Contents/Frameworks/ZCode Helper.app/Contents/MacOS/ZCode Helper",
        },
    ]


def test_manifest_must_stay_outside_source_and_target(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    paths = relocation.RelocationPaths(
        source_base=layout.source_base,
        target_base=layout.target_base,
        settings=layout.settings,
        manifest=layout.source_root / "manifest.json",
    )

    with pytest.raises(relocation.RelocationError, match="manifest must stay outside"):
        relocation.apply_relocation(paths, active_processes=[], source_handles=[])


def test_apply_copies_complete_tree_and_preserves_source_and_settings(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    before = json.loads(layout.settings.read_text(encoding="utf-8"))

    result = relocation.apply_relocation(_paths(layout), active_processes=[], source_handles=[])

    after = json.loads(layout.settings.read_text(encoding="utf-8"))
    assert result["status"] == "applied"
    assert layout.source_root.exists()
    assert (layout.target_root / "v2" / "tasks-index.sqlite").read_bytes() == b"sqlite"
    assert (layout.target_root / "v2" / "checkpoints" / "checkpoint.bin").read_bytes() == b"checkpoint"
    assert after["dataBaseDir"] == str(layout.target_base)
    assert {key: value for key, value in after.items() if key != "dataBaseDir"} == {
        key: value for key, value in before.items() if key != "dataBaseDir"
    }
    assert layout.settings.stat().st_mode & 0o777 == 0o640
    manifest = json.loads(layout.manifest.read_text(encoding="utf-8"))
    assert manifest["schema"] == "documents.zcode-state-relocation/v1"
    assert manifest["status"] == "applied"
    backup = layout.manifest.parent / manifest["settings_backup"]
    assert backup.read_bytes() == layout.original_settings


def test_verify_requires_restarted_process_and_target_handle(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    relocation.apply_relocation(_paths(layout), active_processes=[], source_handles=[])

    with pytest.raises(relocation.RelocationError, match="restarted ZCode process"):
        relocation.verify_relocation(
            _paths(layout), active_processes=[], source_handles=[], target_handles=[]
        )

    result = relocation.verify_relocation(
        _paths(layout),
        active_processes=[{"pid": 84, "command": "ZCode"}],
        source_handles=[],
        target_handles=[str(layout.target_root / "v2" / "tasks-index.sqlite")],
    )
    assert result["status"] == "relocated"
    assert result["source_present"] is True
    assert result["target_handle_count"] == 1


def test_verify_rejects_any_documents_source_handle(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    relocation.apply_relocation(_paths(layout), active_processes=[], source_handles=[])

    with pytest.raises(relocation.RelocationError, match="source handle remains"):
        relocation.verify_relocation(
            _paths(layout),
            active_processes=[{"pid": 84, "command": "ZCode"}],
            source_handles=[str(layout.source_root / "v2" / "tasks-index.sqlite")],
            target_handles=[str(layout.target_root / "v2" / "tasks-index.sqlite")],
        )


def test_verify_requires_target_database_handle(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    relocation.apply_relocation(_paths(layout), active_processes=[], source_handles=[])

    with pytest.raises(relocation.RelocationError, match="target database handle"):
        relocation.verify_relocation(
            _paths(layout),
            active_processes=[{"pid": 84, "command": "ZCode"}],
            source_handles=[],
            target_handles=[str(layout.target_root / "plugin-workspace")],
        )


def test_verify_allows_runtime_workspace_session_refresh(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    relocation.apply_relocation(_paths(layout), active_processes=[], source_handles=[])
    settings = json.loads(layout.settings.read_text(encoding="utf-8"))
    settings["lastWorkspaceSession"] = [{"kind": "local", "workspacePath": str(tmp_path / "project")}]
    layout.settings.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

    result = relocation.verify_relocation(
        _paths(layout),
        active_processes=[{"pid": 84, "command": "ZCode"}],
        source_handles=[],
        target_handles=[str(layout.target_root / "v2" / "tasks-index.sqlite")],
    )

    assert result["status"] == "relocated"


def test_verify_rejects_protected_setting_drift(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    relocation.apply_relocation(_paths(layout), active_processes=[], source_handles=[])
    settings = json.loads(layout.settings.read_text(encoding="utf-8"))
    settings["locale"] = "en-US"
    layout.settings.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(relocation.RelocationError, match="protected settings drifted"):
        relocation.verify_relocation(
            _paths(layout),
            active_processes=[{"pid": 84, "command": "ZCode"}],
            source_handles=[],
            target_handles=[str(layout.target_root / "v2" / "tasks-index.sqlite")],
        )


def test_rollback_restores_source_and_byte_identical_settings(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    relocation.apply_relocation(_paths(layout), active_processes=[], source_handles=[])

    result = relocation.rollback_relocation(
        _paths(layout), active_processes=[], target_handles=[]
    )

    assert result["status"] == "rolled_back"
    assert layout.source_root.is_dir()
    assert layout.target_root.exists()
    assert layout.settings.read_bytes() == layout.original_settings
    manifest = json.loads(layout.manifest.read_text(encoding="utf-8"))
    assert manifest["status"] == "rolled_back"


def test_finalize_moves_retained_source_to_durable_recovery(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    relocation.apply_relocation(_paths(layout), active_processes=[], source_handles=[])

    result = relocation.finalize_relocation(
        _paths(layout),
        active_processes=[{"pid": 84, "command": "ZCode"}],
        source_handles=[],
        target_handles=[str(layout.target_root / "v2" / "tasks-index.sqlite")],
    )

    assert result["status"] == "finalized"
    assert not layout.source_root.exists()
    assert (layout.manifest.parent / "source-before-finalize.zcode" / "v2" / "tasks-index.sqlite").is_file()


def test_cli_inspect_returns_structured_active_state(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "state-inspect",
            "--source-base",
            str(layout.source_base),
            "--target-base",
            str(layout.target_base),
            "--state-settings",
            str(layout.settings),
            "--manifest",
            str(layout.manifest),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode in (0, 1)
    assert payload["schema"] == "documents.zcode-state-relocation-inspection/v1"
    assert payload["source_present"] is True
    assert payload["target_present"] is False
    assert payload["critical_complete"] is True


def test_required_phase_gate_covers_relocation_cli_and_tests() -> None:
    workflow = (ROOT / ".github" / "workflows" / "phase-gate-enforce.yml").read_text(encoding="utf-8")
    registry = ROOT / "bin" / "_registry" / "scripts" / "governance" / "documents-zcode-config.yaml"

    assert "bin/gac/documents-zcode-config.py" in workflow
    assert "lib/documents_zcode_state_relocation.py" in workflow
    assert "tests/test_documents_zcode_state_relocation.py" in workflow
    assert registry.is_file()
