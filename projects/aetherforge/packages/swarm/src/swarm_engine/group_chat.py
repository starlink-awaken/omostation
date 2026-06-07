"""GroupChat — 多 Agent 对话式协作 (vs AutoGen GroupChat).

Agents take turns speaking in a round-robin fashion, with an optional
moderator that controls the flow. Supports:
  - Round-robin turn taking
  - Moderator-guided selection
  - Max turns limit
  - Termination condition (by speaker or content)

Usage::

    from swarm_engine.group_chat import GroupChat, GroupChatAgent

    agent1 = GroupChatAgent(name="Researcher", system_prompt="You research...")
    agent2 = GroupChatAgent(name="Writer", system_prompt="You write...")

    chat = GroupChat(agents=[agent1, agent2], max_turns=6)
    result = chat.run("Research and write about AI safety")
    for msg in result.history:
        print(f"[{msg.sender}]: {msg.content[:100]}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .synapse_gateway import GatewaySynapse

_log = logging.getLogger(__name__)


@dataclass
class GroupChatMessage:
    """A single message in a GroupChat conversation."""

    sender: str = ""
    """Name of the agent who sent this message."""
    content: str = ""
    """Message content."""
    turn: int = 0
    """Conversation turn number."""
    agent_role: str = ""
    """Role of the sender (for display)."""


@dataclass
class GroupChatResult:
    """Result of a GroupChat session."""

    success: bool = False
    history: list[GroupChatMessage] = field(default_factory=list)
    final_output: str = ""
    total_turns: int = 0
    error: str = ""


@dataclass
class GroupChatAgent:
    """An agent participating in a GroupChat."""

    name: str = ""
    """Display name for this agent."""
    system_prompt: str = ""
    """System prompt that defines this agent's role."""
    role: str = ""
    """Short role description (e.g. ``"researcher"``)."""
    temperature: float = 0.7
    """Generation temperature."""


class GroupChat:
    """Round-robin multi-agent conversation manager.

    Agents take turns responding. The conversation continues until
    ``max_turns`` is reached or a termination condition is met.
    """

    def __init__(
        self,
        agents: list[GroupChatAgent],
        *,
        max_turns: int = 10,
        moderator: GroupChatAgent | None = None,
        synapse: GatewaySynapse | None = None,
    ) -> None:
        self._agents = agents
        self._max_turns = max_turns
        self._moderator = moderator
        self._synapse = synapse or GatewaySynapse()
        self._history: list[GroupChatMessage] = []

    # ── Public API ───────────────────────────────────────────────────────────

    def run(self, task: str) -> GroupChatResult:
        """Run a GroupChat conversation.

        Args:
            task: The initial task/query for the agents.

        Returns:
            A ``GroupChatResult`` with the full conversation history.
        """
        result = GroupChatResult()
        self._history = []

        # Initial user message
        self._history.append(GroupChatMessage(
            sender="user", content=task, turn=0,
        ))

        current_input = task

        for turn in range(1, self._max_turns + 1):
            # Select the next speaker
            speaker = self._select_speaker(turn, current_input)
            if speaker is None:
                break

            # Generate response
            response = self._generate(speaker, current_input)

            msg = GroupChatMessage(
                sender=speaker.name,
                content=response,
                turn=turn,
                agent_role=speaker.role,
            )
            self._history.append(msg)
            current_input = response

            # Check termination
            if self._check_termination(speaker.name, response):
                result.final_output = response
                break

        result.success = True
        result.history = list(self._history)
        result.total_turns = turn  # type: ignore[possibly-undefined]
        result.final_output = result.final_output or (self._history[-1].content if self._history else "")
        return result

    # ── Speaker selection ────────────────────────────────────────────────────

    def _select_speaker(self, turn: int, last_message: str) -> GroupChatAgent | None:
        """Select the next speaker."""
        if self._moderator:
            return self._moderator_select(turn, last_message)
        return self._round_robin_select(turn)

    def _round_robin_select(self, turn: int) -> GroupChatAgent | None:
        """Simple round-robin: cycle through agents."""
        if not self._agents:
            return None
        idx = (turn - 1) % len(self._agents)
        return self._agents[idx]

    def _moderator_select(self, turn: int, last_message: str) -> GroupChatAgent | None:
        """Use the moderator LLM to pick the next speaker."""
        agent_list = "\n".join(
            f"{i}. {a.name} ({a.role})" for i, a in enumerate(self._agents)
        )
        history_preview = "\n".join(
            f"[{m.sender}]: {m.content[:100]}" for m in self._history[-4:]
        )

        prompt = (
            f"Given the conversation so far:\n{history_preview}\n\n"
            f"Available agents:\n{agent_list}\n\n"
            f"Who should speak next? Reply with ONLY the agent number (0-{len(self._agents) - 1})."
        )

        resp = self._synapse.generate(
            model="",
            prompt=prompt,
            system=self._moderator.system_prompt or "You are a conversation moderator.",
            options={"max_tokens": 10, "temperature": 0.1},
        )

        if resp.get("status") != "success":
            return self._round_robin_select(turn)

        try:
            idx = int(resp.get("response", "0").strip())
            if 0 <= idx < len(self._agents):
                return self._agents[idx]
        except (ValueError, IndexError):
            pass
        return self._round_robin_select(turn)

    # ── Generation ───────────────────────────────────────────────────────────

    def _generate(self, agent: GroupChatAgent, input_text: str) -> str:
        """Generate a response for *agent* given *input_text*."""
        history_context = "\n".join(
            f"[{m.sender}]: {m.content[:200]}"
            for m in self._history[-6:]
        )

        system = (
            f"{agent.system_prompt}\n\n"
            f"Your name is {agent.name}, a {agent.role}."
        )
        prompt = (
            f"Conversation history:\n{history_context}\n\n"
            f"Your turn to respond (as {agent.name}):\n{input_text}"
        )

        resp = self._synapse.generate(
            model="",
            prompt=prompt,
            system=system,
            options={"max_tokens": 1024, "temperature": agent.temperature},
        )

        return resp.get("response", "") if resp.get("status") == "success" else ""

    # ── Termination ──────────────────────────────────────────────────────────

    def _check_termination(self, speaker: str, content: str) -> bool:
        """Check if the conversation should terminate.

        Override in subclass for custom termination logic.
        """
        # Default: terminate on "TERMINATE" keyword
        if "TERMINATE" in content.upper():
            return True
        return False

    @property
    def history(self) -> list[GroupChatMessage]:
        return list(self._history)
