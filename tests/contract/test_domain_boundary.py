"""Static architecture guardrails for the pure domain package."""

from __future__ import annotations

import ast
from pathlib import Path

DOMAIN_ROOT = Path(__file__).parents[2] / "src" / "omlxc" / "domain"
FORBIDDEN_ROOTS = {
    "aiosqlite",
    "fastapi",
    "httpx",
    "platformdirs",
    "sqlite3",
    "textual",
    "tomlkit",
    "typer",
}


def test_domain_has_no_infrastructure_or_config_persistence_imports() -> None:
    files = sorted(DOMAIN_ROOT.glob("*.py"))
    assert files, "domain package must exist"

    violations: list[str] = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            for name in names:
                if name.split(".", maxsplit=1)[0] in FORBIDDEN_ROOTS:
                    violations.append(f"{path.name}:{node.lineno}:{name}")

    assert violations == []


def test_backend_adapter_protocol_is_runtime_checkable() -> None:
    from omlxc.domain import BackendAdapter

    assert getattr(BackendAdapter, "_is_runtime_protocol", False) is True
