"""Pure, bounded state transitions and prompts for the interactive CLI guide."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

MAX_GUIDE_TRANSITIONS: Final = 8
MAX_GUIDE_IDENTIFIER_LENGTH: Final = 256
_INVALID_GUIDE_INPUT: Final = "guide input is invalid"
_PUBLIC_IDENTIFIER_CHARACTERS: Final = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:@/-"
)


class GuideState(StrEnum):
    GOAL = "goal"
    ROUTE_MODEL = "route-model"
    JOB_ID = "job-id"
    LIFECYCLE_MODEL = "lifecycle-model"
    COMPLETE = "complete"


class GuideOperation(StrEnum):
    HEALTH = "health"
    MODELS = "models"
    ROUTE = "route"
    JOB = "job"
    DAEMON_HEALTH = "daemon-health"
    LIFECYCLE_HELP = "lifecycle-help"


DAEMON_OPERATIONS: Final = frozenset(
    {
        GuideOperation.HEALTH,
        GuideOperation.MODELS,
        GuideOperation.ROUTE,
        GuideOperation.JOB,
        GuideOperation.DAEMON_HEALTH,
    }
)


@dataclass(frozen=True, slots=True)
class GuideChoice:
    key: str
    label: str
    next_state: GuideState
    operation: GuideOperation | None = None


@dataclass(frozen=True, slots=True)
class GuideRequest:
    operation: GuideOperation
    argument: str | None = None


@dataclass(frozen=True, slots=True)
class GuideTransition:
    next_state: GuideState
    request: GuideRequest | None = None


_GOAL_CHOICES: Final = (
    GuideChoice("1", "Check system health", GuideState.COMPLETE, GuideOperation.HEALTH),
    GuideChoice("2", "Find an available model", GuideState.COMPLETE, GuideOperation.MODELS),
    GuideChoice("3", "Explain a route decision", GuideState.ROUTE_MODEL),
    GuideChoice("4", "Inspect a running job", GuideState.JOB_ID),
    GuideChoice(
        "5", "Troubleshoot a daemon problem", GuideState.COMPLETE, GuideOperation.DAEMON_HEALTH
    ),
    GuideChoice("6", "Learn safe model lifecycle commands", GuideState.LIFECYCLE_MODEL),
)


def validate_public_identifier(value: object) -> str:
    """Return a bounded public identifier or fail without echoing input."""
    if (
        not isinstance(value, str)
        or not value.isascii()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError(_INVALID_GUIDE_INPUT)
    identifier = value.strip()
    if (
        not identifier
        or len(identifier) > MAX_GUIDE_IDENTIFIER_LENGTH
        or identifier.startswith("/")
        or identifier.isdecimal()
        or any(character.isspace() for character in identifier)
        or any(character not in _PUBLIC_IDENTIFIER_CHARACTERS for character in identifier)
    ):
        raise ValueError(_INVALID_GUIDE_INPUT)
    if any(segment in {"", ".", ".."} for segment in identifier.split("/")):
        raise ValueError(_INVALID_GUIDE_INPUT)
    return identifier


def available_choices(state: GuideState) -> tuple[GuideChoice, ...]:
    """Return the one static menu; all other states require direct input."""
    if state is not GuideState.GOAL:
        raise ValueError(_INVALID_GUIDE_INPUT)
    return _GOAL_CHOICES


def advance(state: GuideState, answer: object) -> GuideTransition:
    """Advance one bounded guide state without performing an operation."""
    if state is GuideState.GOAL:
        if not isinstance(answer, str):
            raise ValueError(_INVALID_GUIDE_INPUT)
        for choice in _GOAL_CHOICES:
            if answer == choice.key:
                request = GuideRequest(choice.operation) if choice.operation is not None else None
                return GuideTransition(choice.next_state, request)
        raise ValueError(_INVALID_GUIDE_INPUT)
    if state is GuideState.ROUTE_MODEL:
        return GuideTransition(
            GuideState.COMPLETE,
            GuideRequest(GuideOperation.ROUTE, validate_public_identifier(answer)),
        )
    if state is GuideState.JOB_ID:
        return GuideTransition(
            GuideState.COMPLETE,
            GuideRequest(GuideOperation.JOB, validate_public_identifier(answer)),
        )
    if state is GuideState.LIFECYCLE_MODEL:
        return GuideTransition(
            GuideState.COMPLETE,
            GuideRequest(GuideOperation.LIFECYCLE_HELP, validate_public_identifier(answer)),
        )
    raise ValueError(_INVALID_GUIDE_INPUT)


def render_prompt(state: GuideState) -> str:
    """Render only static, color-free prompt text for the supplied guide state."""
    if state is GuideState.GOAL:
        return "\n".join(
            (
                "What would you like to do?",
                *(f"{choice.key}. {choice.label}" for choice in _GOAL_CHOICES),
            )
        )
    if state is GuideState.ROUTE_MODEL:
        return "Model ID"
    if state is GuideState.JOB_ID:
        return "Job ID"
    if state is GuideState.LIFECYCLE_MODEL:
        return "Model ID for lifecycle guidance"
    raise ValueError(_INVALID_GUIDE_INPUT)
