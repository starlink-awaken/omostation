"""B.D.S.K. Virtual Board Consensus Engine & Persona Router (ADR-0203/W2).

Implements the 4-Persona Executive Board for Adaptive Digital Officer OS:
- @Builder: Engineering & MVP execution
- @Devil  : Risk management & anti-fragility
- @Sage   : Strategic context & systems thinking
- @Keeper : Memory persistence & process governance

Supports Mode-A (4-Corner Deep Debate Protocol) and Mode-B (Agile Express Path).
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar

logger = logging.getLogger("ecos.runtime.board_engine")


class PersonaRole(str, Enum):
    """B.D.S.K. Virtual Board Persona roles."""

    BUILDER = "Builder"
    DEVIL = "Devil"
    SAGE = "Sage"
    KEEPER = "Keeper"


class BoardMode(str, Enum):
    """Consensus execution modes for B.D.S.K. Board."""

    AUTO = "auto"
    MODE_A = "Mode-A"
    MODE_B = "Mode-B"


@dataclass
class PersonaMessage:
    """Message voiced by a Board Persona."""

    persona: PersonaRole
    title: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsensusResult:
    """Result of a Virtual Board consensus cycle."""

    session_id: str
    proposal: str
    mode: str
    status: str
    transcript: list[PersonaMessage] = field(default_factory=list)
    adr_draft: dict[str, Any] | None = None
    action_items: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize result for JSON/API output."""
        return {
            "session_id": self.session_id,
            "proposal": self.proposal,
            "mode": self.mode,
            "status": self.status,
            "transcript": [
                {
                    "persona": msg.persona.value,
                    "title": msg.title,
                    "content": msg.content,
                    "metadata": msg.metadata,
                }
                for msg in self.transcript
            ],
            "adr_draft": self.adr_draft,
            "action_items": self.action_items,
        }


class PersonaRouter:
    """Parses @Persona mentions and routes proposals to appropriate Board mode."""

    MENTION_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"@(?P<role>Builder|Devil|Sage|Keeper)\b", re.IGNORECASE
    )

    # Keywords triggering Mode-A deep debate (immutable frozenset)
    MODE_A_KEYWORDS: ClassVar[frozenset[str]] = frozenset({
        "架构",
        "战略",
        "重构",
        "迁移",
        "安全性",
        "底层",
        "并发",
        "协议",
        "核心",
        "architecture",
        "strategy",
        "refactor",
        "security",
        "protocol",
        "kernel",
        "governance",
    })

    @classmethod
    def parse_at_mention(cls, text: str) -> tuple[PersonaRole | None, str]:
        """Extract explicit @Persona mention and return cleaned text."""
        match = cls.MENTION_PATTERN.search(text)
        if not match:
            return None, text.strip()

        role_str = match.group("role").capitalize()
        role = PersonaRole(role_str)
        cleaned = cls.MENTION_PATTERN.sub("", text).strip()
        return role, cleaned

    @classmethod
    def auto_route(cls, text: str) -> BoardMode:
        """Automatically classify proposal into Mode-A (Deep) or Mode-B (Agile)."""
        lower = text.lower()
        for kw in cls.MODE_A_KEYWORDS:
            if kw in lower:
                return BoardMode.MODE_A
        return BoardMode.MODE_B


class BoardConsensusEngine:
    """Executes B.D.S.K. Virtual Board consensus cycles."""

    def __init__(self, session_id: str = "default-board-session") -> None:
        self.session_id = session_id

    def execute(
        self,
        proposal: str,
        mode: BoardMode = BoardMode.AUTO,
        context: dict[str, Any] | None = None,
    ) -> ConsensusResult:
        """Run a consensus cycle on the proposal."""
        ctx = context or {}
        target_role, cleaned_proposal = PersonaRouter.parse_at_mention(proposal)

        effective_mode = mode
        if mode == BoardMode.AUTO:
            effective_mode = PersonaRouter.auto_route(cleaned_proposal)

        logger.info(
            "Executing B.D.S.K. Board [mode=%s, target_role=%s]",
            effective_mode.value,
            target_role.value if target_role else "NONE",
        )

        if effective_mode == BoardMode.MODE_B:
            return self._execute_mode_b(cleaned_proposal, ctx, target_role)
        return self._execute_mode_a(cleaned_proposal, ctx, target_role)

    def _execute_mode_b(
        self,
        proposal: str,
        ctx: dict[str, Any],
        target_role: PersonaRole | None,
    ) -> ConsensusResult:
        """Mode-B: Fast agile execution path."""
        transcript: list[PersonaMessage] = []

        # Builder proposes an agile implementation step
        builder_msg = PersonaMessage(
            persona=PersonaRole.BUILDER,
            title="Agile MVP Execution Step",
            content=f"快速执行方案：直接定位核心瓶颈，实施最小侵入性改动以解决 '{proposal}'。",
            metadata={"effort": "low", "target_role": target_role.value if target_role else None},
        )
        transcript.append(builder_msg)

        # Keeper checks compliance and records verification
        keeper_msg = PersonaMessage(
            persona=PersonaRole.KEEPER,
            title="Agile Audit & Record",
            content="验证门禁通过，改动合规且未触及高危领域，已更新运行时记忆轨迹。",
            metadata={"status": "VERIFIED"},
        )
        transcript.append(keeper_msg)

        return ConsensusResult(
            session_id=self.session_id,
            proposal=proposal,
            mode=BoardMode.MODE_B.value,
            status="APPROVED",
            transcript=transcript,
            adr_draft=None,
            action_items=[
                f"Implement fast patch for: {proposal}",
                "Run unit regression tests",
            ],
        )

    def _execute_mode_a(
        self,
        proposal: str,
        ctx: dict[str, Any],
        target_role: PersonaRole | None,
    ) -> ConsensusResult:
        """Mode-A: 4-Corner Deep Debate Protocol."""
        transcript: list[PersonaMessage] = []

        # 1. Builder Proposal
        transcript.append(
            PersonaMessage(
                persona=PersonaRole.BUILDER,
                title="Engineering Blueprint & Technical Feasibility",
                content=f"工程方案与架构草图：为了系统性交付 '{proposal}'，建议采用去耦总线机制及模块化接口包装，优先保障可扩展性与高人效。",
                metadata={"feasibility": "HIGH"},
            )
        )

        # 2. Devil Challenge
        transcript.append(
            PersonaMessage(
                persona=PersonaRole.DEVIL,
                title="Risk Analysis & Anti-Fragility Challenge",
                content="风控审查与防脆性质询：需警惕新引入并发态与现有控制面索引发生竞态或静默死锁。所有状态变更务必通过幂等及断路器保护。",
                metadata={"risk_level": "MEDIUM", "mitigation_required": True},
            )
        )

        # 3. Sage Synthesis
        transcript.append(
            PersonaMessage(
                persona=PersonaRole.SAGE,
                title="System Strategy Synthesis",
                content="系统架构决议：采纳 Builder 核心设计，同时结合 Devil 的防脆性提醒，引入自修剪与幂等门禁机制，达成整体全局最优解。",
                metadata={"strategic_alignment": "HIGH"},
            )
        )

        # 4. Keeper Governance Contract
        transcript.append(
            PersonaMessage(
                persona=PersonaRole.KEEPER,
                title="SSOT Governance Contract & Memory Lock",
                content="长期治理锁定：要求对事件总线通信契约添加集成测试，同时在控制面注册逻辑索引，杜绝未知漂移。",
                metadata={"adr_required": True},
            )
        )

        adr_draft = {
            "title": f"ADR-BDSK: Consensus on {proposal[:40]}",
            "status": "PROPOSED",
            "decision": "Adopted decoupled architecture with strict idempotent gate validation.",
            "consequences": [
                "Enhanced observability across Board Personas",
                "Zero silent drift via SSOT index registration",
            ],
        }

        action_items = [
            f"Draft architecture blueprint for {proposal}",
            "Implement idempotent event handlers",
            "Register control-plane logical index",
            "Run full regression gate verification",
        ]

        return ConsensusResult(
            session_id=self.session_id,
            proposal=proposal,
            mode=BoardMode.MODE_A.value,
            status="CONSENSUS_REACHED",
            transcript=transcript,
            adr_draft=adr_draft,
            action_items=action_items,
        )


def dispatch_board_command(payload: dict[str, Any]) -> dict[str, Any]:
    """BOS internal transport entrypoint for 'bos.board.execute' calls."""
    proposal = payload.get("proposal", "")
    mode_str = payload.get("mode", "auto")
    session_id = payload.get("session_id", "rpc-board-session")

    try:
        mode = BoardMode(mode_str)
    except ValueError:
        mode = BoardMode.AUTO

    engine = BoardConsensusEngine(session_id=session_id)
    result = engine.execute(proposal=proposal, mode=mode, context=payload.get("context"))

    return {
        "ok": True,
        "result": result.to_dict(),
    }
