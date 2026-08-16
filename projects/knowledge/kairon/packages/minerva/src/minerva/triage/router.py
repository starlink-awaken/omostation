"""
Minerva Triage Router — Classify research queries into L0-L4 execution levels.

Uses local LLM (Qwen3.6-35B-A3B via Ollama MLX) for classification,
with a rule-based fallback for edge cases.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ResearchLevel(Enum):
    L0 = "L0"  # Quick: <30s, $0
    L1 = "L1"  # Standard: <3min, $0
    L2 = "L2"  # Deep: 5-15min, ~$0.30
    L3 = "L3"  # Comprehensive: 10-30min, ~$2
    L4 = "L4"  # Max: 30min+, $2-10


@dataclass
class TriageResult:
    level: ResearchLevel
    scores: dict[str, int]
    cost_estimate: float
    model_plan: dict[str, str | None]
    search_plan: list[str]
    warnings: list[str] = field(default_factory=list)

    total_score: float = 0.0
    reasoning: str = ""


# --- Scoring dimensions and weights ---

DIMENSIONS = {
    "domain_complexity": 0.30,
    "timeliness": 0.15,
    "depth_required": 0.30,
    "multi_source": 0.15,
    "privacy_sensitivity": 0.10,
}

# --- Keyword boosts ---

BOOST_PATTERNS = [
    # General boosts
    (r"\b(compare|vs|versus|diff|contrast|or\s+just)\b", "depth_required", 1.0),
    (r"\b(latest|today|breaking|recent|just\s+announced)\b", "timeliness", 1.0),
    (r"\b(paper|academic|scholar|journal|conference|proceedings)\b", "multi_source", 1.0),
    (r"\b(code|implement|repo|github|source)\b", "domain_complexity", 1.0),
    (r"\b(privacy|confidential|internal|secret|sensitive)\b", "privacy_sensitivity", 1.0),
    # L2+: deeper analysis
    (
        r"\b(analy[sz]e|evolution|architecture|production|investigate|quantiz|deploy|impact of|trend)\b",
        "depth_required",
        1.0,
    ),
    # L3+: debate/counter-argument (or-questions asking "A or B?")
    (
        r"\b(debate|argument|counter|against|or\s+just|\?\s*[Aa]nalyze both|provid.*evidence)\b",
        "depth_required",
        1.0,
    ),
    (r"\b(debate|argument|counter|against)\b", "multi_source", 1.0),
    # L4+: future/synthesis/policy
    (
        r"\b(future|predict|forecast|decade|synthesize|history|trajectory|frontier|regulat|govern|stakeholder)\b",
        "depth_required",
        1.0,
    ),
]

# --- LLM prompt template ---

TRIAGE_SYSTEM_PROMPT = """You are a research task classifier for Minerva, a deep research system.

Analyze the user's query and score it on 5 dimensions (1-5). Output ONLY valid JSON.

## Scoring Guidelines

### domain_complexity (领域复杂度)
1 = Common knowledge, no specialized expertise needed
2 = Single domain, basic knowledge
3 = 2-3 related domains
4 = Deep technical expertise + cross-domain understanding
5 = Frontier research, no standard answer exists

### timeliness (时效性)
1 = Timeless / historical question
2 = Year-scale relevance
3 = Quarter-scale relevance
4 = Month/week-scale relevance
5 = Real-time / daily relevance

### depth_required (深度要求)
1 = One-sentence answer sufficient
2 = Brief overview needed
3 = Structured, multi-section answer needed
4 = Causal analysis + comparative evaluation needed
5 = Original insight generation + verifiable conclusions needed

### multi_source (多源需求)
1 = Single webpage sufficient
2 = 2-3 webpages sufficient
3 = 5-10 sources from web
4 = Papers + code + multiple content types
5 = All content types + specialized/paid databases

### privacy_sensitivity (隐私敏感度)
1 = Public information only
2 = General work documents
3 = Internal business data
4 = Confidential / PII
5 = Legal / medical / compliance data

## Output Format
{
  "domain_complexity": <int 1-5>,
  "timeliness": <int 1-5>,
  "depth_required": <int 1-5>,
  "multi_source": <int 1-5>,
  "privacy_sensitivity": <int 1-5>,
  "reasoning": "<one sentence explaining the score>"
}"""


class TriageRouter:
    """Classify research queries into execution levels.

    Uses a two-phase approach:
    1. LLM classification (primary) — Qwen3.6-35B via Ollama
    2. Rule-based fallback (emergency) — keyword heuristics
    """

    # --- Cost estimates per level (USD) ---
    LEVEL_COST = {
        ResearchLevel.L0: 0.0,
        ResearchLevel.L1: 0.0,
        ResearchLevel.L2: 0.30,
        ResearchLevel.L3: 2.00,
        ResearchLevel.L4: 5.00,
    }

    # --- Model plans per level ---
    LEVEL_MODELS: dict[ResearchLevel, dict[str, str | None]] = {
        ResearchLevel.L0: {
            "agent": "qwen3.6:35b-a3b-coding-nvfp4",
            "reasoning": None,
            "writer": "qwen3.6:35b-a3b-coding-nvfp4",
        },
        ResearchLevel.L1: {
            "agent": "qwen3.6:35b-a3b-coding-nvfp4",
            "reasoning": "deepseek-r1:70b",
            "writer": "qwen3.5:27b",
        },
        ResearchLevel.L2: {
            "agent": "qwen3.6:35b-a3b-coding-nvfp4",
            "reasoning": "deepseek-r1:70b",
            "writer": "qwen3.5:27b",
        },
        ResearchLevel.L3: {
            "agent": "qwen3.6:35b-a3b-coding-nvfp4",
            "reasoning": "v4-flash",
            "writer": "qwen3.5:27b",
        },
        ResearchLevel.L4: {"agent": "v4-pro", "reasoning": "v4-pro-max", "writer": "v4-pro"},
    }

    # --- Search plans per level ---
    LEVEL_SEARCH = {
        ResearchLevel.L0: ["searxng"],
        ResearchLevel.L1: ["searxng", "scholar"],
        ResearchLevel.L2: ["searxng", "exa", "scholar", "metaso"],
        ResearchLevel.L3: ["searxng", "exa", "scholar", "metaso", "arxiv"],
        ResearchLevel.L4: ["searxng", "exa", "scholar", "arxiv", "scopus"],
    }

    def __init__(self, llm_client: Any) -> None:
        self.llm = llm_client  # OllamaClient or any OpenAI-compatible

    # ============================================================
    # Public API
    # ============================================================

    def classify_rule_based(self, query: str) -> TriageResult:
        """Classify using only rule-based heuristics (no LLM call)."""
        scores = self._rule_classify(query)
        scores = self._apply_boosts(query, scores)
        total = self._compute_total(scores)
        level = self._total_to_level(total, scores)
        warnings = self._generate_warnings(scores, level)
        cost_est = {"L0": 0.0, "L1": 0.0, "L2": 0.3, "L3": 2.0, "L4": 8.0}.get(level.value, 0.5)
        return TriageResult(
            level=level,
            scores=scores,
            cost_estimate=cost_est,
            model_plan={},
            search_plan=[],
            warnings=warnings,
            total_score=total,
        )

    async def classify(self, query: str) -> TriageResult:
        """Classify a research query and return routing decision.

        Args:
            query: Natural language research question

        Returns:
            TriageResult with level, scores, cost estimate, and plans
        """
        # Phase 1: Try LLM classification
        try:
            scores = await self._llm_classify(query)
        except Exception as exc:
            logger.warning("llm_classify_failed", error=str(exc))
            # Phase 2: Rule-based fallback
            scores = self._rule_classify(query)

        # Apply keyword boosts
        scores = self._apply_boosts(query, scores)

        # Calculate total and determine level
        total = self._compute_total(scores)
        level = self._total_to_level(total, scores)

        # Build result
        return TriageResult(
            level=level,
            scores=scores,
            total_score=total,
            cost_estimate=self.LEVEL_COST[level],
            model_plan=self.LEVEL_MODELS[level],
            search_plan=self.LEVEL_SEARCH[level],
            warnings=self._generate_warnings(scores, level),
        )

    # ============================================================
    # Phase 1: LLM-based classification
    # ============================================================

    async def _llm_classify(self, query: str) -> dict[str, int]:
        """Classify via local LLM (Qwen3.6-35B)."""

        # Load L4 CARDS context for alignment
        from minerva.shared.cards_context import get_cards_context

        l4_context = get_cards_context()
        system_prompt = TRIAGE_SYSTEM_PROMPT + l4_context

        response = await self.llm.generate(
            system=system_prompt,
            prompt=f"Classify this research query:\n\n{query}",
            temperature=0.1,  # Low temperature for consistent classification
        )
        # Parse JSON from response (handle potential markdown wrapping)
        json_str = self._extract_json(response)
        result = json.loads(json_str)

        # Validate and clamp scores
        scores = {}
        for dim in DIMENSIONS:
            scores[dim] = max(1, min(5, int(result.get(dim, 3))))
        return scores

    # ============================================================
    # Phase 2: Rule-based fallback classification
    # ============================================================

    def _rule_classify(self, query: str) -> dict[str, int]:
        """Keyword-based classification fallback."""
        lower = query.lower()

        # Domain complexity — count technical terms
        tech_terms = [
            "algorithm",
            "architecture",
            "framework",
            "protocol",
            "compiler",
            "kernel",
            "neural",
            "attention",
            "embedding",
            "optimization",
            "distributed",
            "concurrent",
            "cryptographic",
            "transformer",
            "deep learning",
            "machine learning",
            "llm",
            "gpu",
            "inference",
            "training",
            "fine-tuning",
            "tokenization",
        ]
        tech_count = sum(1 for t in tech_terms if t in lower)
        domain = min(5, 1 + tech_count // 3)

        # Timeliness — check for time-sensitive keywords
        time_keywords = ["latest", "today", "breaking", "recent", "just announced", "2026"]
        timeliness = 4 if any(k in lower for k in time_keywords) else 2

        # Depth — check for analysis keywords
        depth_keywords = ["analyze", "explain why", "compare", "evaluate", "synthesize"]
        depth = 4 if any(k in lower for k in depth_keywords) else (3 if "how" in lower else 2)

        # Multi-source — check for source-type keywords
        source_keywords = ["paper", "research", "academic", "code", "repo", "data"]
        multi_source = 4 if any(k in lower for k in source_keywords) else 2

        # Privacy — check for sensitive keywords
        privacy_keywords = ["confidential", "internal", "private", "secret", "proprietary"]
        privacy = 4 if any(k in lower for k in privacy_keywords) else 1

        return {
            "domain_complexity": domain,
            "timeliness": timeliness,
            "depth_required": depth,
            "multi_source": multi_source,
            "privacy_sensitivity": privacy,
        }

    # ============================================================
    # Scoring and routing logic
    # ============================================================

    def _apply_boosts(self, query: str, scores: dict[str, int]) -> dict[str, int]:
        """Apply keyword pattern boosts to scores."""
        lower = query.lower()
        boosted = dict(scores)
        for pattern, dimension, boost in BOOST_PATTERNS:
            if re.search(pattern, lower):
                boosted[dimension] = min(5, int(boosted[dimension] + boost))
        return boosted

    def _compute_total(self, scores: dict[str, int]) -> float:
        """Compute weighted total score."""
        return sum(scores[dim] * weight for dim, weight in DIMENSIONS.items())

    def _total_to_level(self, total: float, scores: dict[str, int]) -> ResearchLevel:
        """Map total score to research level, with privacy override."""
        # Privacy override: force local-only for sensitive data
        if scores.get("privacy_sensitivity", 1) >= 4:
            return ResearchLevel.L1  # Allow multi-step but no cloud

        if total <= 1.5:
            return ResearchLevel.L0
        elif total <= 2.5:
            return ResearchLevel.L1
        elif total <= 3.5:
            return ResearchLevel.L2
        elif total <= 4.2:
            return ResearchLevel.L3
        else:
            return ResearchLevel.L4

    def _generate_warnings(self, scores: dict[str, int], level: ResearchLevel) -> list[str]:
        """Generate user-facing warnings."""
        warnings = []
        if scores.get("privacy_sensitivity", 1) >= 4:
            warnings.append("PRIVACY_WARNING: Cloud APIs disabled due to data sensitivity")
        if level in (ResearchLevel.L3, ResearchLevel.L4):
            warnings.append(f"COST_WARNING: This research may cost up to ${self.LEVEL_COST[level]:.2f}")
        if scores.get("multi_source", 1) >= 4:
            warnings.append("MULTI_SOURCE: Academic sources recommended — ensure API keys are set")
        return warnings

    # ============================================================
    # Utility
    # ============================================================

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON from LLM response (handles markdown code blocks)."""
        # Try to find JSON in code block
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return match.group(1)
        # Try to find bare JSON object
        match = re.search(r"\{.*?\}", text, re.DOTALL)
        if match:
            return match.group(0)
        raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}")


# ============================================================
# Pseudocode for key methods
# ============================================================

"""
async def classify(query: str) -> TriageResult:
    '''
    Full classification flow:

    1. Send query + TRIAGE_SYSTEM_PROMPT to Qwen3.6-35B via Ollama
       → Parse JSON response: {domain_complexity, timeliness, depth_required, multi_source, privacy_sensitivity}

    2. If LLM fails (timeout, parse error, offline):
       → _rule_classify(): count tech_terms, time_keywords, depth_keywords, source_keywords, privacy_keywords
       → Map counts to 1-5 scores

    3. Apply keyword boosts:
       → "compare/vs/diff" → depth += 1
       → "latest/today" → timeliness += 1
       → "paper/academic" → multi_source += 1

    4. Compute total = Σ(score_i × weight_i):
       total = domain×0.30 + timeliness×0.15 + depth×0.30 + multi_source×0.15 + privacy×0.10

    5. Determine level:
       privacy ≥ 4 → L1 (force local)
       total ≤ 1.5 → L0
       total ≤ 2.5 → L1
       total ≤ 3.5 → L2
       total ≤ 4.2 → L3
       total > 4.2 → L4

    6. Generate TriageResult:
       - level: ResearchLevel
       - cost_estimate: from LEVEL_COST map
       - model_plan: {agent, reasoning, writer} from LEVEL_MODELS map
       - search_plan: list[str] from LEVEL_SEARCH map
       - warnings: privacy/cost/multi_source warnings
    '''
    pass
"""
