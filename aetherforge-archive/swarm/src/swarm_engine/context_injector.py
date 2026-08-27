"""Context injection for Holo-Context and Hi-Fi prompt generation."""

from __future__ import annotations

import json
import os
from typing import Any


class ContextInjector:
    """Prepares execution environments and generates Hi-Fi prompts for workers.

    Usage in ``cli_avatar_worker.py``::

        env = ContextInjector.prepare_environment(persona, sandbox_path)
        prompt = ContextInjector.generate_hifi_prompt(persona, msg, sandbox_path)
    """

    @staticmethod
    def prepare_environment(persona: str, sandbox_path: str) -> dict[str, str]:
        """Build the environment dict for a worker subprocess.

        Returns a copy of ``os.environ`` augmented with BOS-specific
        variables that describe the persona and workspace sandbox.
        """
        env = dict(os.environ)
        env["BOS_PERSONA"] = persona
        env["BOS_SANDBOX"] = sandbox_path
        env["BOS_WORKER_CONTEXT"] = json.dumps(
            {
                "persona_path": os.path.join(sandbox_path, "persona.md"),
                "workspace_path": sandbox_path,
            }
        )
        return env

    @staticmethod
    def generate_hifi_prompt(
        persona: str,
        msg: dict[str, Any],
        sandbox_path: str,
    ) -> str:
        """Generate a high-fidelity prompt string for a worker task.

        Combines the persona identity, task summary/content, and workspace
        path into a single structured prompt that a CLI worker can consume.
        """
        summary = msg.get("summary", "")
        content = msg.get("content", "")
        task_id = msg.get("id", "unknown")

        parts = [
            f"# Persona: {persona}",
            f"# Task: {task_id}",
            "## Summary",
            summary,
            "## Instructions",
            content,
            "## Workspace",
            sandbox_path,
        ]
        return "\n\n".join(parts)
