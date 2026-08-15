"""Pure, bounded presentation helpers for human CLI output."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final, cast
from unicodedata import category

from omlxc.cli_guide import validate_public_identifier
from omlxc.client import RemoteError

MAX_SECTION_LINES: Final = 8
MAX_GUIDANCE_COMMANDS: Final = 3
MAX_TITLE_LENGTH: Final = 80
MAX_LINE_LENGTH: Final = 256
MAX_REQUEST_ID_LENGTH: Final = 64
_INVALID_SECTION_TEXT: Final = "section text is invalid"
_UNAVAILABLE_REQUEST_ID: Final = "unavailable"


def _is_safe_text(value: object, maximum_length: int) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and len(value) <= maximum_length
        and not any(category(character).startswith("C") for character in value)
    )


def _require_safe_text(value: object, maximum_length: int, message: str) -> None:
    if not _is_safe_text(value, maximum_length):
        raise ValueError(message)


def _safe_request_id(value: object) -> str:
    if _is_safe_text(value, MAX_REQUEST_ID_LENGTH):
        return cast(str, value)
    return _UNAVAILABLE_REQUEST_ID


def _is_stable_error_code(value: str) -> bool:
    return len(value) == 4 and value.startswith("E") and value[1:].isascii() and value[1:].isdigit()


def _is_public_policy(value: str) -> bool:
    return (
        bool(value)
        and len(value) <= 32
        and value.isascii()
        and all(character.isalnum() or character in "-_" for character in value)
    )


class Severity(StrEnum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


class ErrorContext(StrEnum):
    GENERAL = "general"
    STATUS = "status"
    GUIDE = "guide"
    ROUTE = "route"
    JOB = "job"


@dataclass(frozen=True, slots=True)
class HumanSection:
    title: str
    lines: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_safe_text(self.title, MAX_TITLE_LENGTH, _INVALID_SECTION_TEXT)
        raw_lines = cast(object, self.lines)
        if not isinstance(raw_lines, tuple):
            raise ValueError("section lines must be a tuple")
        lines = cast(tuple[object, ...], raw_lines)
        if len(lines) > MAX_SECTION_LINES:
            raise ValueError("section lines exceed the limit")
        for line in lines:
            _require_safe_text(line, MAX_LINE_LENGTH, _INVALID_SECTION_TEXT)


@dataclass(frozen=True, slots=True)
class Guidance:
    severity: Severity
    summary: str
    explanation: str
    commands: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        raw_severity = cast(object, self.severity)
        if not isinstance(raw_severity, Severity):
            raise ValueError("guidance severity is invalid")
        _require_safe_text(self.summary, MAX_TITLE_LENGTH, "guidance summary is invalid")
        _require_safe_text(self.explanation, MAX_LINE_LENGTH, "guidance explanation is invalid")
        raw_commands = cast(object, self.commands)
        if not isinstance(raw_commands, tuple):
            raise ValueError("guidance commands must be a tuple")
        commands = cast(tuple[object, ...], raw_commands)
        if len(commands) > MAX_GUIDANCE_COMMANDS:
            raise ValueError("guidance commands exceed the limit")
        for command in commands:
            _require_safe_text(command, MAX_LINE_LENGTH, "guidance command is invalid")


_ERROR_GUIDANCE: Final[Mapping[str, Guidance]] = MappingProxyType(
    {
        "E100": Guidance(
            Severity.ERROR,
            "Invalid command or configuration",
            "the command input or local configuration was rejected.",
            ("omlxc --help",),
        ),
        "E200": Guidance(
            Severity.ERROR,
            "Daemon unavailable",
            "the private control socket could not be reached.",
            ("omlxc daemon status",),
        ),
        "E204": Guidance(
            Severity.ERROR,
            "Resource not found",
            "the requested daemon resource does not exist or is no longer retained.",
            ("omlxc jobs list",),
        ),
        "E300": Guidance(
            Severity.ERROR,
            "Backend unavailable",
            "the selected local backend did not complete the operation.",
            ("omlxc status",),
        ),
        "E305": Guidance(
            Severity.ERROR,
            "Operation timed out",
            "the daemon did not complete the requested operation within its budget.",
            ("omlxc status",),
        ),
        "E400": Guidance(
            Severity.ERROR,
            "No eligible route",
            "no placement currently satisfies the request constraints.",
            ("omlxc models list",),
        ),
        "E401": Guidance(
            Severity.ERROR,
            "Insufficient capacity",
            "eligible placements currently lack admitted capacity.",
            ("omlxc metrics show",),
        ),
        "E500": Guidance(
            Severity.ERROR,
            "Job did not complete",
            "the durable job ended without a complete result.",
            ("omlxc jobs list",),
        ),
        "E700": Guidance(
            Severity.ERROR,
            "Safety confirmation required",
            "the requested operation is protected by an explicit safety gate.",
        ),
        "E900": Guidance(
            Severity.ERROR,
            "Internal client error",
            "the client could not safely process the response.",
            ("omlxc status",),
        ),
    }
)

_CONTEXT_COMMANDS: Final[Mapping[tuple[str, ErrorContext], tuple[str, ...]]] = MappingProxyType(
    {
        ("E100", ErrorContext.GUIDE): ("omlxc guide --help", "omlxc --help"),
        ("E204", ErrorContext.JOB): ("omlxc jobs list",),
        ("E400", ErrorContext.ROUTE): ("omlxc models list",),
        ("E404", ErrorContext.ROUTE): ("omlxc models resolve <model_id>", "omlxc models list"),
        ("E401", ErrorContext.ROUTE): ("omlxc metrics show", "omlxc nodes list"),
    }
)


def render_sections(sections: tuple[HumanSection, ...]) -> str:
    """Render already validated sections in a stable, color-free block format."""
    raw_sections = cast(object, sections)
    if not isinstance(raw_sections, tuple):
        raise ValueError("sections are invalid")
    validated_sections: list[HumanSection] = []
    for section in cast(tuple[object, ...], raw_sections):
        if not isinstance(section, HumanSection):
            raise ValueError("sections are invalid")
        validated_sections.append(section)
    return "\n\n".join(
        "\n".join((section.title, *(f"  {line}" for line in section.lines)))
        for section in validated_sections
    )


def render_lifecycle_help(model_id: str) -> str:
    """Render static lifecycle education without invoking a model operation."""
    identifier = validate_public_identifier(model_id)
    HumanSection("Safe lifecycle plan", (identifier,))
    return "\n".join(
        (
            "Safe lifecycle plan",
            f"  Load: omlxc models load {identifier} --yes",
            "  Impact: reserves memory and may start a backend model.",
            "  Confirmation: R1; review the model ID before using --yes.",
            f"  Rollback: omlxc models unload {identifier} --yes",
        )
    )


def render_error(
    error: RemoteError,
    *,
    request_id: str,
    context: ErrorContext = ErrorContext.GENERAL,
) -> str:
    """Render only closed local guidance, never daemon-provided error details."""
    raw_error = cast(object, error)
    raw_context = cast(object, context)
    if not isinstance(raw_error, RemoteError):
        raise ValueError("error is invalid")
    if not isinstance(raw_context, ErrorContext):
        raise ValueError("error context is invalid")
    display_request_id = _safe_request_id(request_id)
    display_code = error.code if _is_stable_error_code(error.code) else "E900"

    guidance = _ERROR_GUIDANCE.get(display_code, _ERROR_GUIDANCE["E900"])
    commands = _CONTEXT_COMMANDS.get((display_code, raw_context), guidance.commands)
    return "\n".join(
        (
            f"ERROR {display_code} · {guidance.summary}",
            f"What happened: {guidance.explanation}",
            *(f"Next: {command}" for command in commands),
            f"Request: {display_request_id}",
        )
    )


def status_sections(data: object) -> tuple[HumanSection, HumanSection]:
    """Build status output only from the typed health values supplied by the caller."""
    if not isinstance(data, Mapping):
        raise ValueError("health data is invalid")
    typed_data = cast(Mapping[str, object], data)
    status = typed_data.get("status")
    degraded = typed_data.get("degraded")
    policy = typed_data.get("policy", "interactive")
    if not isinstance(status, str) or type(degraded) is not bool or not isinstance(policy, str):
        raise ValueError("health data is invalid")
    _require_safe_text(status, MAX_LINE_LENGTH, "health status is invalid")
    if "\n" in policy or "\r" in policy:
        raise ValueError("health policy is invalid")
    if not _is_public_policy(policy):
        policy = "interactive"

    healthy = status == "ready" and not degraded
    facts = (
        "Status: ready" if healthy else "Status: degraded",
        "Degraded: no" if healthy else "Degraded: yes",
        f"Policy: {policy}",
        "Jobs: not checked by status",
    )
    commands = (
        ("omlxc models list", "omlxc jobs list")
        if healthy
        else ("omlxc doctor", "omlxc nodes list", "omlxc jobs list")
    )
    title = "OK · Daemon ready" if healthy else "WARNING · Daemon is running in degraded mode"
    return HumanSection(title, facts), HumanSection("Next", commands)
