"""StateMachine — MET-STATE type for modeling state transitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StateTransition:
    """A single transition between states."""

    from_state: str
    to_state: str
    trigger: str
    guard: str = ""

    def to_dict(self) -> dict:
        return {"from": self.from_state, "to": self.to_state, "trigger": self.trigger, "guard": self.guard}


@dataclass
class StateMachine:
    """A state machine — defines states and transitions."""

    id: str
    name: str
    states: list[str]
    transitions: list[StateTransition]
    initial_state: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "states": self.states,
            "transitions": [t.to_dict() for t in self.transitions],
            "initial_state": self.initial_state,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> StateMachine:
        trans = [StateTransition(**t) if isinstance(t, dict) else t for t in d.get("transitions", [])]
        return cls(
            id=d["id"],
            name=d.get("name", ""),
            states=d.get("states", []),
            transitions=trans,
            initial_state=d.get("initial_state", ""),
            metadata=d.get("metadata", {}),
        )

    def validate(self) -> list[str]:
        errs = []
        if not self.id:
            errs.append("id is required")
        if not self.states:
            errs.append("at least one state required")
        if self.initial_state and self.initial_state not in self.states:
            errs.append(f"initial_state '{self.initial_state}' not in states")
        for t in self.transitions:
            if t.from_state not in self.states:
                errs.append(f"transition from '{t.from_state}' not in states")
            if t.to_state not in self.states:
                errs.append(f"transition to '{t.to_state}' not in states")
        return errs
