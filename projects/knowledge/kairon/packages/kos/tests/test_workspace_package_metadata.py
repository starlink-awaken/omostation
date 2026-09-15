from __future__ import annotations

import tomllib
from pathlib import Path


def test_declared_package_readmes_exist() -> None:
    workspace_root = Path(__file__).resolve().parents[3]
    missing: list[str] = []

    for pyproject_path in workspace_root.glob("packages/*/pyproject.toml"):
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        readme = pyproject.get("project", {}).get("readme")
        if isinstance(readme, str) and not (pyproject_path.parent / readme).exists():
            missing.append(f"{pyproject_path.parent.name}:{readme}")

    assert missing == []
