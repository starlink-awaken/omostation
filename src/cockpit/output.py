"""Cockpit CLI output helpers — ANSI purity and JSON envelopes (BET-Y1Q4-T8-12)."""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from rich.console import Console

from cockpit.logger import get_or_create_trace_id


def wants_machine_output(
    *,
    force_json: bool = False,
    stream: TextIO | None = None,
) -> bool:
    """True when output must be ANSI-free (JSON mode or non-TTY)."""
    if force_json:
        return True
    target = stream if stream is not None else sys.stdout
    try:
        return not target.isatty()
    except Exception:
        return True


def get_console(
    *,
    force_json: bool = False,
    stderr: bool = False,
    file: TextIO | None = None,
) -> Console:
    """Return a Rich Console that disables color/markup pollution for machine paths.

    When ``force_json`` is set or the target stream is not a TTY, construct with
    ``no_color=True`` and ``force_terminal=False`` so markup never emits ANSI.

    Important: do **not** bind ``file=sys.stdout`` at construction for the default
    path — Rich keeps a live ``sys.stdout`` lookup when ``file`` is omitted, which
    keeps pytest monkeypatches working.
    """
    if file is not None:
        machine = wants_machine_output(force_json=force_json, stream=file)
        return Console(
            file=file,
            no_color=machine,
            force_terminal=False if machine else None,
            highlight=False if machine else True,
        )

    probe = sys.stderr if stderr else sys.stdout
    machine = wants_machine_output(force_json=force_json, stream=probe)
    kwargs: dict[str, Any] = {
        "stderr": stderr,
        "no_color": machine,
        "highlight": not machine,
    }
    if machine:
        kwargs["force_terminal"] = False
    return Console(**kwargs)


def ansi_free_print(text: str, *, file: TextIO | None = None) -> None:
    """Print plain text with no Rich markup processing."""
    target = file if file is not None else sys.stdout
    print(text, file=target)


def json_print(
    payload: dict[str, Any] | list[Any],
    *,
    include_trace_id: bool = True,
    file: TextIO | None = None,
    indent: int | None = None,
) -> None:
    """Dump a JSON payload to stdout (or ``file``) with optional ``trace_id`` injection."""
    target = file if file is not None else sys.stdout
    data: Any
    if include_trace_id and isinstance(payload, dict):
        data = dict(payload)
        data.setdefault("trace_id", get_or_create_trace_id())
    else:
        data = payload
    print(json.dumps(data, ensure_ascii=False, indent=indent), file=target)


def apply_machine_consoles(cli_module: Any) -> None:
    """Switch module-level ``console`` / ``err`` singletons to ANSI-free Consoles."""
    cli_module.console = get_console(force_json=True)
    cli_module.err = get_console(force_json=True, stderr=True)


__all__ = [
    "apply_machine_consoles",
    "ansi_free_print",
    "get_console",
    "json_print",
    "wants_machine_output",
]
