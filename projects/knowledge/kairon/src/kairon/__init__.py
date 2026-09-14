from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

_WORKSPACE_PACKAGES = (
    "core-models",
    "codeanalyze",
    "kronos",
    "eidos",
    "minerva",
    "agora",
    "sophia",
    "ontoderive",
    "forge",
    "kos",
    "iris",
    "ssot-kernel",
    "agent-runtime",
    "wksp",
    "ecos",
    "metaos",
    "cron-service",
)

try:
    __version__ = version("kairon")
except PackageNotFoundError:
    __version__ = "0.1.0"


def workspace_packages() -> tuple[str, ...]:
    """Return the workspace member packages shipped alongside the root distro."""

    return _WORKSPACE_PACKAGES


def describe() -> dict[str, object]:
    """Return a lightweight description of the root Kairon distribution."""

    return {
        "name": "kairon",
        "version": __version__,
        "workspace_member_count": len(_WORKSPACE_PACKAGES),
        "workspace_packages": list(_WORKSPACE_PACKAGES),
    }


__all__ = ["__version__", "describe", "workspace_packages"]
