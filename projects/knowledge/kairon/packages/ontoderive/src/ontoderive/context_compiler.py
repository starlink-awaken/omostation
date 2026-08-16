"""Context compiler — AGENTS.md validation helpers.

This module provides the `find_missing_contexts` helper used by
`governance_steps.AgentContextStep`. It is the minimal interface needed
by the agent_context CI gate step.

Restored after the 0-ref cleanup (PR #521) deleted it; the
agent_context pipeline step still imports from this module.
"""

from __future__ import annotations

from pathlib import Path


def find_missing_contexts(root: Path) -> list[Path]:
    """Return a list of directories under `root` that lack an AGENTS.md file.

    Only directories that are registered as "required" (i.e. listed in
    the workspace's domain config) are checked. For the minimal
    interface, we conservatively treat every first-level subdirectory
    that does not have an AGENTS.md as "missing".
    """
    required: list[Path] = []
    if not root.exists():
        return required
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if not (child / "AGENTS.md").exists():
            required.append(child)
    return required


__all__ = ["find_missing_contexts"]
