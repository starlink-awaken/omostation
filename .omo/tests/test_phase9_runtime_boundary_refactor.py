from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = OMO_ROOT.parent


def _read_workspace(rel_path: str) -> str:
    return (WORKSPACE_ROOT / rel_path).read_text(encoding="utf-8")


def test_run_continuation_moves_to_runtime_root() -> None:
    assert not (OMO_ROOT / "run-continuation").exists()
    assert (WORKSPACE_ROOT / "runtime" / "run-continuation").exists()

    for rel_path in [
        ".omo/_knowledge/usage/AGENT.md",
        ".omo/DOC-ARCH.md",
        ".omo/_delivery/INDEX.md",
        ".omo/INDEX.md",
    ]:
        assert "runtime/run-continuation/" in _read_workspace(rel_path)

    assert ".omo/run-continuation" not in _read_workspace("scripts/check-index-coverage.py")
