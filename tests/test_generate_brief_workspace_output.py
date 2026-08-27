from __future__ import annotations

import importlib.util
import os
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "bin" / "mof" / "generate-brief.py"


def _load(monkeypatch, *, workspace: Path | None = None, output: Path | None = None):
    if workspace is None:
        monkeypatch.delenv("OMOSTATION_WORKSPACE_ROOT", raising=False)
    else:
        monkeypatch.setenv("OMOSTATION_WORKSPACE_ROOT", str(workspace))
    if output is None:
        monkeypatch.delenv("OMOSTATION_BRIEF_OUTPUT", raising=False)
    else:
        monkeypatch.setenv("OMOSTATION_BRIEF_OUTPUT", str(output))
    spec = importlib.util.spec_from_file_location("generate_brief_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_explicit_workspace_and_output_are_used(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "Workspace"
    output = workspace / "BRIEF.md"
    workspace.mkdir()

    module = _load(monkeypatch, workspace=workspace, output=output)

    assert module.WORKSPACE == workspace
    assert module.BRIEF_MD == output
    assert module.write_brief_if_changed("# generated\n") is True
    assert output.read_text(encoding="utf-8") == "# generated\n"


def test_default_output_remains_repo_root(monkeypatch) -> None:
    module = _load(monkeypatch)

    assert module.WORKSPACE == SCRIPT.parents[2]
    assert module.BRIEF_MD == SCRIPT.parents[2] / "BRIEF.md"


def test_explicit_output_never_targets_documents(monkeypatch, tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    workspace = tmp_path / "Workspace"
    documents.mkdir()
    workspace.mkdir()
    output = workspace / "BRIEF.md"

    module = _load(monkeypatch, workspace=workspace, output=output)
    module.write_brief_if_changed("# Workspace brief\n")

    assert output.is_file()
    assert not (documents / "@驾驶舱" / "_control" / "BRIEF.md").exists()
