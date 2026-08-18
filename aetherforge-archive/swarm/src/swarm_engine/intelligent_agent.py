"""Intelligent Agent Middleware — Unified decision chain.

Chains five layers into a single decide() pipeline:
  1. Risk gate (block forbidden actions before any work)
  2. MOS memory recall (query beliefs/skills/experiences)
  3. LLM generation (via ModelGateway unified entry)
  4. Decision recording (persist to MOS decision_outcomes)
  5. Trust feedback (record outcome for future risk calibration)

Replaces the stateless llm_ask() pattern across 3 duplicate implementations:
  - cli.py mcp_server.llm_generate
  - omo_agent_host._llm_deep_eval()
  - _llm_helper.llm_ask()

Usage::

    from swarm_engine.intelligent_agent import IntelligentAgent

    agent = IntelligentAgent("mail-agent", domain="work")
    result = agent.decide(
        question="Classify this email",
        context={"subject": "关于上报数据的通知"},
        action={"type": "classify", "target": "self"},
    )
    print(result["response"], result["risk_level"], result["memory_used"])
"""

from __future__ import annotations

import json
import logging
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

# ── Path injection (same pattern as _llm_helper.py, proven working) ────────

_FILE_DIR = Path(__file__).resolve().parent  # .../swarm_engine/
_SRC_DIR = _FILE_DIR.parent  # .../src/
_PACKAGE_DIR = _SRC_DIR.parent  # .../swarm/
_PACKAGES_DIR = _PACKAGE_DIR.parent  # .../packages/
_AETHERFORGE_ROOT = _PACKAGES_DIR.parent  # .../aetherforge/

# Workspace root: aetherforge is at workspace/projects/aetherforge
_WORKSPACE_ROOT = Path(
    os.environ.get(
        "WORKSPACE_ROOT",
        str(_AETHERFORGE_ROOT.parent.parent),  # aetherforge → projects → workspace
    )
)


def _ensure_paths() -> None:
    """Inject sys.path entries for gateway, swarm, aetherforge, omo, and workspace."""
    candidates = [
        str(_PACKAGES_DIR / "gateway" / "src"),  # aetherforge gateway
        str(_SRC_DIR),  # this swarm package
        str(_AETHERFORGE_ROOT / "src"),  # aetherforge top-level
        str(_WORKSPACE_ROOT / "projects" / "omo" / "src"),
        str(_WORKSPACE_ROOT),
    ]
    for p in candidates:
        if p not in sys.path and Path(p).exists():
            sys.path.insert(0, p)


_ensure_paths()


# ── Lazy singletons (avoid import failures when components are missing) ────

_gateway = None
_mos_manager = None
_risk_engine = None


def _get_gateway():
    """Lazy-init ModelGateway singleton (DRY: replaces 3 duplicate implementations)."""
    global _gateway
    if _gateway is not None:
        return _gateway
    try:
        from llm_gateway import get_gateway

        _gateway = get_gateway()
        return _gateway
    except Exception as e:
        _log.warning("[IntelligentAgent] ModelGateway init failed: %s", e)
        return None


def _get_mos():
    """Lazy-init MOSBeliefManager (shared brain for all agents)."""
    global _mos_manager
    if _mos_manager is not None:
        return _mos_manager
    try:
        from omo.omo_belief import MOSBeliefManager

        _mos_manager = MOSBeliefManager(root=_WORKSPACE_ROOT)
        return _mos_manager
    except Exception as e:
        _log.warning("[IntelligentAgent] MOS init failed: %s", e)
        return None


def _get_risk_engine():
    """Lazy-init RiskEngine (5-level dynamic safety gate)."""
    global _risk_engine
    if _risk_engine is not None:
        return _risk_engine
    try:
        # Try workspace bin/ssot first, then ws clone
        ssot_dirs = [
            str(_WORKSPACE_ROOT / "bin" / "ssot"),
            str(Path.home() / "agents" / "claude" / "ws" / "bin" / "ssot"),
        ]
        for sd in ssot_dirs:
            if sd not in sys.path and Path(sd).exists():
                sys.path.insert(0, sd)
        from risk_engine import RiskEngine

        _risk_engine = RiskEngine()
        return _risk_engine
    except Exception as e:
        _log.warning("[IntelligentAgent] RiskEngine init failed: %s", e)
        return None


# ── GLM cloud fallback (proven working, from _llm_helper.py) ───────────────

_GLM_API_KEY = "db6c1d03aadf4853b361448ee235fd14.aWijxBcAyAO7i1ct"


def _glm_fallback(prompt: str, timeout: int = 30) -> str | None:
    """GLM cloud direct call — used when ModelGateway has no available model."""
    try:
        body = json.dumps(
            {
                "model": "glm-4.7-flash",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
            }
        ).encode()
        req = urllib.request.Request(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {_GLM_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            data = json.loads(resp.read())
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content.strip() if content else None
    except Exception as e:
        _log.warning("[IntelligentAgent] GLM fallback failed: %s", e)
        return None


# ── Core: IntelligentAgent ─────────────────────────────────────────────────


class IntelligentAgent:
    """Unified agent decision chain: Risk → MOS → LLM → Record → Trust.

    Replaces the stateless llm_ask() pattern with a memory-aware,
    trust-calibrated, risk-gated intelligent middleware.
    """

    def __init__(self, agent_id: str, domain: str = "work") -> None:
        self.agent_id = agent_id
        self.domain = domain

    # ── Main pipeline ───────────────────────────────────────────────────

    def decide(
        self,
        question: str,
        context: dict[str, Any] | None = None,
        action: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Full decision pipeline.

        Args:
            question: The question or task to process.
            context: Additional context data.
            action: Action descriptor for risk evaluation.
                Keys: type (str), target (str), domain (str), sensitivity (str).

        Returns:
            Dict with: response, risk_level, memory_used, agent_id, blocked.
        """
        context = context or {}
        action = action or {"type": "read", "target": "self", "domain": self.domain}

        # 1. Risk gate — block forbidden actions before any work
        risk_result = self._check_risk(action)
        if risk_result.get("forbidden"):
            return {
                "response": None,
                "risk_level": "L4",
                "memory_used": False,
                "agent_id": self.agent_id,
                "blocked": True,
                "reason": risk_result.get("reasoning", "forbidden by risk engine"),
            }

        # 2. Recall relevant memory from MOS
        memory = self._recall_memory(question)
        memory_used = bool(memory.get("beliefs") or memory.get("skills"))

        # 3. Generate response via unified LLM entry
        response = self._llm_ask(question, context, memory)

        # 4. Record decision to MOS (shared brain accumulates knowledge)
        self._record_decision(question, response, action)

        return {
            "response": response,
            "risk_level": risk_result.get("level", "L1"),
            "memory_used": memory_used,
            "agent_id": self.agent_id,
            "blocked": False,
        }

    # ── Layer 1: Risk gate ──────────────────────────────────────────────

    def _check_risk(self, action: dict[str, Any]) -> dict[str, Any]:
        """Evaluate action risk through the 5-level RiskEngine."""
        engine = _get_risk_engine()
        if engine is None:
            # No risk engine → default to L1 (auto + notify)
            return {"level": "L1", "forbidden": False, "reasoning": "risk engine unavailable"}

        try:
            from risk_engine import Action

            act = Action(
                type=action.get("type", "read"),
                target=action.get("target", "self"),
                domain=action.get("domain", self.domain),
                sensitivity=action.get("sensitivity", "routine"),
                confidence=action.get("confidence", 0.8),
            )
            decision = engine.evaluate(act)
            return {
                "level": decision.level,
                "forbidden": decision.is_forbidden(),
                "needs_confirmation": decision.needs_confirmation(),
                "reasoning": decision.reasoning,
                "trust_adjusted": decision.trust_adjusted,
            }
        except Exception as e:
            _log.warning("[IntelligentAgent] Risk eval failed: %s", e)
            return {"level": "L2", "forbidden": False, "reasoning": f"risk eval error: {e}"}

    # ── Layer 2: MOS memory recall ─────────────────────────────────────

    def _recall_memory(self, question: str) -> dict[str, Any]:
        """Query MOS for relevant beliefs, skills, and experiences."""
        mos = _get_mos()
        if mos is None:
            return {"beliefs": [], "skills": [], "experiences": []}

        try:
            beliefs = mos.query_beliefs(keyword=question[:50])
            state = mos._load_state()
            skills = [
                s
                for s in state.get("agent_skills", [])
                if s.get("agent_id") == self.agent_id and s.get("reusable", True)
            ]
            experiences = [e for e in state.get("agent_experiences", []) if e.get("agent_id") == self.agent_id]
            return {
                "beliefs": beliefs[:3],
                "skills": skills[:2],
                "experiences": experiences[:2],
            }
        except Exception as e:
            _log.warning("[IntelligentAgent] Memory recall failed: %s", e)
            return {"beliefs": [], "skills": [], "experiences": []}

    # ── Layer 3: Unified LLM entry ─────────────────────────────────────

    def _llm_ask(
        self,
        question: str,
        context: dict[str, Any],
        memory: dict[str, Any],
    ) -> str | None:
        """Single LLM entry point — replaces 3 duplicate _get_gateway() impls."""
        prompt = self._build_prompt(question, context, memory)

        # Backend 1: AetherForge ModelGateway (omlx local → fallback chain)
        gw = _get_gateway()
        if gw is not None:
            try:
                from llm_gateway import GatewayRequest
                from llm_gateway.gateway import run_async

                resp = run_async(
                    gw.generate(
                        GatewayRequest(
                            messages=[{"role": "user", "content": prompt}],
                            timeout=60.0,
                        )
                    )
                )
                if resp and resp.content:
                    return resp.content.strip()
            except Exception as e:
                _log.warning("[IntelligentAgent] ModelGateway failed: %s", e)

        # Backend 2: GLM cloud (proven working, key embedded)
        return _glm_fallback(prompt)

    def _build_prompt(
        self,
        question: str,
        context: dict[str, Any],
        memory: dict[str, Any],
    ) -> str:
        """Build LLM prompt with memory injection."""
        parts = [question]

        if context:
            parts.append(f"\nContext: {json.dumps(context, ensure_ascii=False)[:500]}")

        beliefs = memory.get("beliefs", [])
        if beliefs:
            belief_text = "; ".join(f"[{b.get('topic', '?')}] {b.get('belief', '')[:80]}" for b in beliefs)
            parts.append(f"\nRelevant beliefs: {belief_text}")

        skills = memory.get("skills", [])
        if skills:
            skill_text = "; ".join(f"{s.get('skill_name', '?')}: {s.get('code_or_pattern', '')[:60]}" for s in skills)
            parts.append(f"\nApplicable skills: {skill_text}")

        experiences = memory.get("experiences", [])
        if experiences:
            exp_text = "; ".join(f"({e.get('outcome', '?')}) {e.get('experience', '')[:60]}" for e in experiences)
            parts.append(f"\nPast experiences: {exp_text}")

        return "\n".join(parts)

    # ── Layer 4: Decision recording ────────────────────────────────────

    def _record_decision(
        self,
        question: str,
        response: str | None,
        action: dict[str, Any],
    ) -> None:
        """Record decision to MOS decision_outcomes table."""
        mos = _get_mos()
        if mos is None:
            return

        try:
            mos.record_decision_outcome(
                decision_type=action.get("type", "unknown"),
                input_summary=question[:200],
                expected_outcome=action.get("expected", ""),
                actual_outcome=(response or "")[:200],
                delta="",
                source_run_id=self.agent_id,
            )
        except Exception as e:
            _log.warning("[IntelligentAgent] Decision recording failed: %s", e)

    # ── Layer 5b: PI deep evaluation ────────────────────────────────────

    def _deep_eval(self, question: str, context: dict[str, Any]) -> dict[str, Any] | None:
        """Call PI for deep evaluation when rule/LLM confidence is insufficient.

        Uses pi-adapter.py from ws/bin/ssot/ or workspace bin/ssot/.
        Returns None if PI is unavailable.
        """
        try:
            # Find pi_adapter in the ssot dirs
            from pathlib import Path as _P  # noqa: N814 — 函数内局部别名

            ssot_dirs = [
                _P.home() / "agents" / "claude" / "ws" / "bin" / "ssot",
                _WORKSPACE_ROOT / "bin" / "ssot",
            ]
            for sd in ssot_dirs:
                pi_path = sd / "pi-adapter.py"
                if pi_path.exists():
                    sd_str = str(sd)
                    if sd_str not in sys.path:
                        sys.path.insert(0, sd_str)
                    from pi_adapter import deep_evaluate

                    return deep_evaluate(question, context)
        except Exception as e:
            _log.debug("[IntelligentAgent] PI deep eval skipped: %s", e)
        return None

    # ── Layer 5c: Trust feedback ────────────────────────────────────────

    def record_outcome(self, action: dict[str, Any], success: bool) -> None:
        """Record execution outcome for trust calibration.

        After an action completes, call this to update trust scores.
        High trust (10+ successes) → risk level downgrades automatically.
        Low trust (failures) → risk level upgrades automatically.
        """
        # Update RiskEngine trust store
        engine = _get_risk_engine()
        if engine is not None:
            try:
                from risk_engine import Action

                act = Action(
                    type=action.get("type", "read"),
                    target=action.get("target", "self"),
                    domain=action.get("domain", self.domain),
                )
                engine.record_outcome(act, success)
            except Exception as e:
                _log.warning("[IntelligentAgent] Trust record failed: %s", e)

        # Update MOS capability calibration
        mos = _get_mos()
        if mos is not None:
            try:
                mos.record_capability_calibration(
                    capability_ref=f"{self.agent_id}:{action.get('type', 'unknown')}",
                    success_rate=1.0 if success else 0.0,
                    sample_size=1,
                )
            except Exception as e:
                _log.warning("[IntelligentAgent] MOS calibration failed: %s", e)

    # ── Convenience: backward-compatible llm_ask ────────────────────────

    @classmethod
    def llm_ask(
        cls,
        question: str,
        context: dict[str, Any] | None = None,
        timeout: float = 60.0,
    ) -> str | None:
        """Drop-in replacement for _llm_helper.llm_ask().

        Uses the same unified LLM path but without memory/risk overhead.
        Existing daemon scripts (mail_daemon, health_agent, etc.) can call
        this without modification.
        """
        agent = cls("legacy", "work")
        return agent._llm_ask(question, context or {}, {"beliefs": [], "skills": [], "experiences": []})


# ── Convenience: create agent with auto-detection ──────────────────────────


def create_agent(agent_id: str, domain: str = "work") -> IntelligentAgent:
    """Factory: create an IntelligentAgent with the given ID and domain."""
    return IntelligentAgent(agent_id, domain)
