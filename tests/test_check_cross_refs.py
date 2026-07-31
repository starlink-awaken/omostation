# ---
# status: active
# lifecycle: active
# owner: governance-agent
# ssot: bin/ssot/check-cross-refs.py
# verifier: pytest tests/test_check_cross_refs.py
# ---
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "bin/ssot/check-cross-refs.py"
SPEC = importlib.util.spec_from_file_location("check_cross_refs", MODULE_PATH)
assert SPEC and SPEC.loader
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


def test_workspace_scope_excludes_runtime_and_knowledge_documents(tmp_path: Path) -> None:
    for relative_path in (
        ".omo/active.md",
        ".omo/plans/ignored.md",
        ".omo/_knowledge/history.md",
        ".omo/_delivery/evidence.md",
        ".omo/tasks/registry/generated.md",
    ):
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# document\n", encoding="utf-8")

    files = CHECKER.collect_markdown_files(tmp_path, scope="workspace")

    assert files == [tmp_path / ".omo/active.md", tmp_path / ".omo/plans/ignored.md"]


def test_tracked_scope_uses_git_index_and_applies_same_exclusions(tmp_path: Path) -> None:
    for relative_path in (
        ".omo/active.md",
        ".omo/plans/ignored.md",
        ".omo/_knowledge/history.md",
        ".omo/_delivery/evidence.md",
        ".omo/tasks/registry/generated.md",
    ):
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# document\n", encoding="utf-8")

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", ".omo/active.md", ".omo/_knowledge/history.md"], cwd=tmp_path, check=True)

    files = CHECKER.collect_markdown_files(tmp_path, scope="tracked")

    assert files == [tmp_path / ".omo/active.md"]
