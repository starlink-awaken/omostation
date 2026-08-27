from __future__ import annotations

from pathlib import Path


def _documents_root(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    import os

    configured = os.environ.get("L4_DOCUMENTS_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "Documents").resolve()


def _registry_path(
    explicit: str | Path | None = None,
    *,
    documents_root: str | Path | None = None,
) -> Path:
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    import os

    configured = os.environ.get("L4_DOMAIN_REGISTRY")
    if configured:
        return Path(configured).expanduser().resolve()
    return _documents_root(documents_root) / "@公共" / "_control" / "L4-DOMAIN-REGISTRY.yaml"


def _relative_path(value: object, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or path == Path(".") or ".." in path.parts:
        raise ValueError(f"{label} must be a non-traversing relative path")
    return path
