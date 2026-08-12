"""Contracts for the bounded, pure CLI guide state machine."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from omlxc.cli_guide import (
    DAEMON_OPERATIONS,
    MAX_GUIDE_IDENTIFIER_LENGTH,
    MAX_GUIDE_TRANSITIONS,
    GuideChoice,
    GuideOperation,
    GuideRequest,
    GuideState,
    GuideTransition,
    advance,
    available_choices,
    render_prompt,
)


def test_goal_menu_declares_only_read_only_operations() -> None:
    choices = available_choices(GuideState.GOAL)

    assert tuple(choice.key for choice in choices) == ("1", "2", "3", "4", "5", "6")
    assert {choice.operation for choice in choices if choice.operation is not None} <= {
        GuideOperation.HEALTH,
        GuideOperation.MODELS,
        GuideOperation.ROUTE,
        GuideOperation.JOB,
        GuideOperation.DAEMON_HEALTH,
    }
    assert MAX_GUIDE_TRANSITIONS == 8
    assert GuideOperation.LIFECYCLE_HELP not in DAEMON_OPERATIONS


def test_goal_choices_have_exact_order_labels_and_transitions() -> None:
    assert available_choices(GuideState.GOAL) == (
        GuideChoice("1", "Check system health", GuideState.COMPLETE, GuideOperation.HEALTH),
        GuideChoice("2", "Find an available model", GuideState.COMPLETE, GuideOperation.MODELS),
        GuideChoice("3", "Explain a route decision", GuideState.ROUTE_MODEL),
        GuideChoice("4", "Inspect a running job", GuideState.JOB_ID),
        GuideChoice(
            "5", "Troubleshoot a daemon problem", GuideState.COMPLETE, GuideOperation.DAEMON_HEALTH
        ),
        GuideChoice("6", "Learn safe model lifecycle commands", GuideState.LIFECYCLE_MODEL),
    )


@pytest.mark.parametrize(
    ("answer", "next_state", "operation"),
    (
        ("1", GuideState.COMPLETE, GuideOperation.HEALTH),
        ("2", GuideState.COMPLETE, GuideOperation.MODELS),
        ("3", GuideState.ROUTE_MODEL, None),
        ("4", GuideState.JOB_ID, None),
        ("5", GuideState.COMPLETE, GuideOperation.DAEMON_HEALTH),
        ("6", GuideState.LIFECYCLE_MODEL, None),
    ),
)
def test_goal_transitions_are_explicit(
    answer: str,
    next_state: GuideState,
    operation: GuideOperation | None,
) -> None:
    transition = advance(GuideState.GOAL, answer)

    assert transition.next_state is next_state
    assert transition.request is None or transition.request.operation is operation


@pytest.mark.parametrize(
    ("state", "identifier", "operation"),
    (
        (GuideState.ROUTE_MODEL, " local/model-a ", GuideOperation.ROUTE),
        (GuideState.JOB_ID, "job-1", GuideOperation.JOB),
        (GuideState.LIFECYCLE_MODEL, "local/model-a", GuideOperation.LIFECYCLE_HELP),
    ),
)
def test_identifier_transitions_return_validated_requests(
    state: GuideState, identifier: str, operation: GuideOperation
) -> None:
    transition = advance(state, identifier)

    assert transition == GuideTransition(
        GuideState.COMPLETE, GuideRequest(operation, identifier.strip())
    )


@pytest.mark.parametrize("value", ("", " " * 3, "x" * 257, "7", "../../../private"))
def test_invalid_or_unsafe_input_fails_closed(value: str) -> None:
    with pytest.raises(ValueError, match="^guide input is invalid$"):
        advance(GuideState.ROUTE_MODEL, value)


@pytest.mark.parametrize(
    "value",
    ("/absolute", "a//b", "a/./b", "a/../b", "model\\x00", "m\u00f6del", "model\nnext"),
)
def test_identifier_validation_rejects_paths_controls_and_unicode(value: str) -> None:
    with pytest.raises(ValueError, match="^guide input is invalid$") as exc_info:
        advance(GuideState.LIFECYCLE_MODEL, value)

    assert value not in str(exc_info.value)


def test_guide_prompts_are_static_exact_and_color_free() -> None:
    assert render_prompt(GuideState.GOAL) == (
        "What would you like to do?\n"
        "1. Check system health\n"
        "2. Find an available model\n"
        "3. Explain a route decision\n"
        "4. Inspect a running job\n"
        "5. Troubleshoot a daemon problem\n"
        "6. Learn safe model lifecycle commands"
    )
    assert render_prompt(GuideState.ROUTE_MODEL) == "Model ID"
    assert render_prompt(GuideState.JOB_ID) == "Job ID"
    assert render_prompt(GuideState.LIFECYCLE_MODEL) == "Model ID for lifecycle guidance"
    assert "\x1b[" not in render_prompt(GuideState.GOAL)


@pytest.mark.parametrize("state", (GuideState.ROUTE_MODEL, GuideState.JOB_ID, GuideState.COMPLETE))
def test_non_goal_choices_and_complete_operations_fail_closed(state: GuideState) -> None:
    with pytest.raises(ValueError, match="^guide input is invalid$"):
        available_choices(state)

    if state is GuideState.COMPLETE:
        with pytest.raises(ValueError, match="^guide input is invalid$"):
            advance(state, "anything")
        with pytest.raises(ValueError, match="^guide input is invalid$"):
            render_prompt(state)


def test_guide_values_are_frozen_slotted_and_bounded() -> None:
    choice = GuideChoice("1", "Check system health", GuideState.COMPLETE, GuideOperation.HEALTH)
    request = GuideRequest(GuideOperation.HEALTH)
    transition = GuideTransition(GuideState.COMPLETE, request)

    assert (MAX_GUIDE_IDENTIFIER_LENGTH, MAX_GUIDE_TRANSITIONS) == (256, 8)
    assert not hasattr(choice, "__dict__")
    with pytest.raises(FrozenInstanceError):
        request.argument = "other"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        transition.next_state = GuideState.GOAL  # type: ignore[misc]
