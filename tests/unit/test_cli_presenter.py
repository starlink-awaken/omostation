"""Contracts for the pure, safe CLI human presentation boundary."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from omlxc.cli_presenter import (
    MAX_GUIDANCE_COMMANDS,
    MAX_LINE_LENGTH,
    MAX_REQUEST_ID_LENGTH,
    MAX_SECTION_LINES,
    MAX_TITLE_LENGTH,
    ErrorContext,
    Guidance,
    HumanSection,
    Severity,
    render_error,
    render_lifecycle_help,
    render_sections,
    status_sections,
)
from omlxc.client import RemoteError


def test_sections_are_deterministic_color_free_and_bounded() -> None:
    rendered = render_sections(
        (
            HumanSection("State", ("Daemon: ready", "Degraded: no")),
            HumanSection("Next", ("omlxc models list", "omlxc jobs list")),
        )
    )

    assert rendered == (
        "State\n  Daemon: ready\n  Degraded: no\n\nNext\n  omlxc models list\n  omlxc jobs list"
    )
    assert "\x1b[" not in rendered


@pytest.mark.parametrize(
    ("title", "lines"),
    (
        ("\x1b[31mState", ("Daemon: ready",)),
        ("State", ("Daemon: \x07ready",)),
    ),
)
def test_sections_reject_terminal_control_characters(title: str, lines: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        HumanSection(title, lines)


@pytest.mark.parametrize(
    ("title", "lines"),
    (
        ("\u009bState", ("Daemon: ready",)),
        ("State", ("Daemon: \u009bready",)),
    ),
)
def test_sections_reject_c1_terminal_control_characters(title: str, lines: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="section text is invalid"):
        HumanSection(title, lines)


def test_sections_reject_values_beyond_explicit_output_limits() -> None:
    assert (MAX_TITLE_LENGTH, MAX_LINE_LENGTH, MAX_REQUEST_ID_LENGTH) == (80, 256, 64)

    with pytest.raises(ValueError, match="section text is invalid"):
        HumanSection("t" * (MAX_TITLE_LENGTH + 1), ("Daemon: ready",))
    with pytest.raises(ValueError, match="section text is invalid"):
        HumanSection("State", ("l" * (MAX_LINE_LENGTH + 1),))


def test_presentation_values_are_immutable_and_enforce_bounds() -> None:
    section = HumanSection("State", ("Daemon: ready",))

    with pytest.raises(FrozenInstanceError):
        section.title = "Changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="section lines exceed the limit"):
        HumanSection("State", tuple("line" for _ in range(MAX_SECTION_LINES + 1)))
    with pytest.raises(ValueError, match="guidance commands exceed the limit"):
        Guidance(
            Severity.ERROR,
            "Summary",
            "Explanation.",
            tuple("omlxc status" for _ in range(MAX_GUIDANCE_COMMANDS + 1)),
        )


@pytest.mark.parametrize(
    ("code", "title", "explanation", "commands"),
    (
        (
            "E100",
            "Invalid command or configuration",
            "the command input or local configuration was rejected.",
            ("omlxc --help",),
        ),
        (
            "E200",
            "Daemon unavailable",
            "the private control socket could not be reached.",
            ("omlxc daemon status",),
        ),
        (
            "E204",
            "Resource not found",
            "the requested daemon resource does not exist or is no longer retained.",
            ("omlxc jobs list",),
        ),
        (
            "E300",
            "Backend unavailable",
            "the selected local backend did not complete the operation.",
            ("omlxc status",),
        ),
        (
            "E305",
            "Operation timed out",
            "the daemon did not complete the requested operation within its budget.",
            ("omlxc status",),
        ),
        (
            "E400",
            "No eligible route",
            "no placement currently satisfies the request constraints.",
            ("omlxc models list",),
        ),
        (
            "E401",
            "Insufficient capacity",
            "eligible placements currently lack admitted capacity.",
            ("omlxc metrics show",),
        ),
        (
            "E500",
            "Job did not complete",
            "the durable job ended without a complete result.",
            ("omlxc jobs list",),
        ),
        (
            "E700",
            "Safety confirmation required",
            "the requested operation is protected by an explicit safety gate.",
            (),
        ),
        (
            "E900",
            "Internal client error",
            "the client could not safely process the response.",
            ("omlxc status",),
        ),
    ),
)
def test_closed_error_guidance_has_exact_stable_text(
    code: str, title: str, explanation: str, commands: tuple[str, ...]
) -> None:
    error = RemoteError(code=code, message="ignored", retryable=False)

    rendered = render_error(error, request_id="req-safe")

    assert rendered == "\n".join(
        (
            f"ERROR {code} · {title}",
            f"What happened: {explanation}",
            *(f"Next: {command}" for command in commands),
            "Request: req-safe",
        )
    )


@pytest.mark.parametrize(
    ("code", "context", "commands"),
    (
        ("E100", ErrorContext.GUIDE, ("omlxc guide --help", "omlxc --help")),
        ("E204", ErrorContext.JOB, ("omlxc jobs list",)),
        ("E400", ErrorContext.ROUTE, ("omlxc models list",)),
        ("E404", ErrorContext.ROUTE, ("omlxc models resolve <model_id>", "omlxc models list")),
        ("E401", ErrorContext.ROUTE, ("omlxc metrics show", "omlxc nodes list")),
    ),
)
def test_error_context_uses_static_command_overrides(
    code: str, context: ErrorContext, commands: tuple[str, ...]
) -> None:
    rendered = render_error(
        RemoteError(code=code, message="ignored", retryable=False),
        request_id="req-safe",
        context=context,
    )

    assert [
        line.removeprefix("Next: ") for line in rendered.splitlines() if line.startswith("Next: ")
    ] == list(commands)


def test_error_guidance_ignores_all_untrusted_remote_fields() -> None:
    hostile = RemoteError(
        code="E200",
        message="Bearer secret at https://identity.example/private/path",
        technical_detail="prompt=response-body",
        suggested_action="curl https://backend.example",
        affected_resources=("node/private/identity",),
        partial_result={"authorization": "Bearer token"},
    )

    rendered = render_error(hostile, request_id="req-safe", context=ErrorContext.STATUS)

    assert rendered == (
        "ERROR E200 · Daemon unavailable\n"
        "What happened: the private control socket could not be reached.\n"
        "Next: omlxc daemon status\n"
        "Request: req-safe"
    )
    for forbidden in (
        "secret",
        "https://",
        "/private/",
        "prompt",
        "response-body",
        "Bearer",
        "identity",
    ):
        assert forbidden not in rendered


def test_unknown_error_uses_e900_guidance_but_retains_safe_actual_code() -> None:
    rendered = render_error(
        RemoteError(code="E777", message="ignored", retryable=False), request_id="req-safe"
    )

    assert rendered == (
        "ERROR E777 · Internal client error\n"
        "What happened: the client could not safely process the response.\n"
        "Next: omlxc status\n"
        "Request: req-safe"
    )


def test_unknown_noncanonical_error_code_uses_safe_e900_heading() -> None:
    hostile_code = "E777\x1b[31mhttps://x/y"

    rendered = render_error(
        RemoteError(code=hostile_code, message="ignored", retryable=False), request_id="req-safe"
    )

    assert rendered == (
        "ERROR E900 · Internal client error\n"
        "What happened: the client could not safely process the response.\n"
        "Next: omlxc status\n"
        "Request: req-safe"
    )
    for forbidden in ("\x1b", "https://", "/y"):
        assert forbidden not in rendered


@pytest.mark.parametrize("request_id", ("req\u009b[31m", "r" * (MAX_REQUEST_ID_LENGTH + 1)))
def test_error_uses_unavailable_for_invalid_request_id(request_id: str) -> None:
    rendered = render_error(
        RemoteError(code="E200", message="ignored", retryable=False), request_id=request_id
    )

    assert rendered == (
        "ERROR E200 · Daemon unavailable\n"
        "What happened: the private control socket could not be reached.\n"
        "Next: omlxc daemon status\n"
        "Request: unavailable"
    )
    assert request_id not in rendered


@pytest.mark.parametrize(
    "data",
    (
        {"status": "ready", "degraded": False, "policy": "interactive"},
        {"status": "ready", "degraded": False},
    ),
)
def test_status_sections_render_only_typed_healthy_health_values(data: dict[str, object]) -> None:
    data.update(
        {
            "diagnostic": "https://daemon.example/private",
            "config_identity": "Bearer secret",
            "unexpected": {"authorization": "token"},
        }
    )

    rendered = render_sections(status_sections(data))

    policy = data.get("policy", "interactive")
    assert rendered == (
        "OK · Daemon ready\n"
        "  Status: ready\n"
        "  Degraded: no\n"
        f"  Policy: {policy}\n"
        "  Jobs: not checked by status\n\n"
        "Next\n"
        "  omlxc models list\n"
        "  omlxc jobs list"
    )
    for forbidden in ("https://", "/private", "Bearer", "secret", "authorization", "token"):
        assert forbidden not in rendered


def test_status_sections_render_degraded_commands_without_querying_jobs() -> None:
    rendered = render_sections(
        status_sections({"status": "not-ready", "degraded": True, "policy": "strict"})
    )

    assert rendered == (
        "WARNING · Daemon is running in degraded mode\n"
        "  Status: degraded\n"
        "  Degraded: yes\n"
        "  Policy: strict\n"
        "  Jobs: not checked by status\n\n"
        "Next\n"
        "  omlxc doctor\n"
        "  omlxc nodes list\n"
        "  omlxc jobs list"
    )


def test_status_sections_ignore_hostile_policy_and_use_interactive() -> None:
    hostile_policy = "\x1b[31mhttps://daemon.invalid/private/path"

    rendered = render_sections(
        status_sections({"status": "ready", "degraded": False, "policy": hostile_policy})
    )

    assert "  Policy: interactive\n" in rendered
    for forbidden in ("\x1b", "https://", "/private", "/path", "daemon.invalid"):
        assert forbidden not in rendered


@pytest.mark.parametrize(
    "data",
    (
        None,
        [],
        {"status": "ready"},
        {"status": 1, "degraded": False},
        {"status": "ready", "degraded": "false"},
        {"status": "ready", "degraded": False, "policy": 1},
        {"status": "ready", "degraded": False, "policy": "line\nbreak"},
    ),
)
def test_status_sections_reject_malformed_data_without_echoing_it(data: object) -> None:
    with pytest.raises(ValueError) as exc_info:
        status_sections(data)

    assert str(data) not in str(exc_info.value)


def test_lifecycle_help_has_exact_static_safe_plan() -> None:
    rendered = render_lifecycle_help("local/model-a")

    assert rendered == (
        "Safe lifecycle plan\n"
        "  Load: omlxc models load local/model-a --yes\n"
        "  Impact: reserves memory and may start a backend model.\n"
        "  Confirmation: R1; review the model ID before using --yes.\n"
        "  Rollback: omlxc models unload local/model-a --yes"
    )
    assert "\x1b[" not in rendered
    assert len(rendered) <= MAX_LINE_LENGTH * 5


@pytest.mark.parametrize("model_id", ("../private", "/absolute", "local/\x00model", "m\u00f6del"))
def test_lifecycle_help_rejects_unsafe_model_ids_without_echoing_them(model_id: str) -> None:
    with pytest.raises(ValueError, match="^guide input is invalid$") as exc_info:
        render_lifecycle_help(model_id)

    assert model_id not in str(exc_info.value)
