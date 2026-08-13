"""Read-only Documents MCP surface for remote clients."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP  # type: ignore[import-not-found]

from cockpit.adapters import governance_context

mcp = FastMCP("documents-readonly")


def _configure_workspace_root(source: Path | None = None) -> None:
    if os.environ.get("WORKSPACE_ROOT"):
        return
    start = (source or Path(__file__)).resolve()
    for parent in start.parents:
        authority = parent / ".omo"
        if authority.is_symlink():
            continue
        registry = authority / "_truth" / "registry" / "documents-domain-projects.yaml"
        if registry.is_file():
            os.environ["WORKSPACE_ROOT"] = str(parent)
            return


def _json_envelope(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


@mcp.tool()
def workspace_context() -> str:
    """Read Workspace phase, Documents domains, and CARDS summary."""

    return _json_envelope(governance_context.workspace_context())


@mcp.tool()
def domain_context(domain_id: str) -> str:
    """Resolve one Documents domain and its Workspace binding."""

    return _json_envelope(governance_context.domain_context(domain_id))


@mcp.tool()
def cards_status() -> str:
    """List CARDS through the OMO authority."""

    return _json_envelope(governance_context.cards_status())


@mcp.tool()
def cards_check(card_id: str = "") -> str:
    """Run the read-only CARDS constraint check."""

    return _json_envelope(governance_context.cards_check(card_id=card_id))


def main() -> None:
    """Run the bounded MCP server over stdio."""

    _configure_workspace_root()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
