from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Layer: L3
Summary: "KnowledgeInjector — injects NKS knowledge graph context into worker spawn payloads."
Tags:
  - knowledge
  - nks
  - worker
  - swarm
  - injection
---

KnowledgeInjector — injects NKS knowledge graph context into worker spawn payloads.
Wraps NKSMCPBridge to extract role-relevant knowledge without requiring full NKS startup.
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# KnowledgeInjector ≡ Module
# 内涵 ≝ {KnowledgeSlice, KnowledgeInjector}
# 外延 ≝ {e | e ∈ D-Gateway ∧ injects(e, Knowledge)}
# 功能 ⊢ {StaticKnowledge, NKSKnowledge, Inject, Serialize}
# =============================================================================
import json  # noqa: E402
import logging  # noqa: E402
from dataclasses import asdict, dataclass, field  # noqa: E402
from typing import Any  # noqa: E402

logger = logging.getLogger(__name__)

_MAX_ENV_BYTES = 4096


@dataclass
class KnowledgeSlice:
    """A single knowledge unit for worker context injection.

    Attributes:
        concept:    Primary concept name.
        definition: Brief description / definition of the concept.
        related:    List of related concept names.
        source:     Origin of the knowledge — ``"nks"``, ``"local_index"``, or ``"static"``.
    """

    concept: str
    definition: str
    related: list[str] = field(default_factory=list)
    source: str = "static"


# ---------------------------------------------------------------------------
# Static knowledge registry (no NKS required)
# ---------------------------------------------------------------------------

_STATIC_KNOWLEDGE: dict[str, list[dict[str, Any]]] = {
    "analyst": [
        {
            "concept": "data_analysis",
            "definition": "Systematic inspection, cleansing, and modelling of data to discover useful information.",
            "related": ["statistics", "visualization", "hypothesis_testing"],
            "source": "static",
        },
        {
            "concept": "market_research",
            "definition": "Organised effort to gather information about target markets and customers.",
            "related": ["competitor_analysis", "survey_design", "trend_identification"],
            "source": "static",
        },
        {
            "concept": "report_structure",
            "definition": "Executive summary → findings → analysis → recommendations → appendix.",
            "related": ["data_analysis", "business_intelligence", "kpi_tracking"],
            "source": "static",
        },
        {
            "concept": "kpi_tracking",
            "definition": "Measurement of performance against key success indicators over time.",
            "related": ["dashboards", "metrics", "okr"],
            "source": "static",
        },
    ],
    "coder": [
        {
            "concept": "software_patterns",
            "definition": "Reusable solutions to commonly occurring problems in software design.",
            "related": ["factory", "observer", "strategy", "dependency_injection"],
            "source": "static",
        },
        {
            "concept": "code_review",
            "definition": "Systematic examination of source code to identify bugs and improve quality.",
            "related": ["pull_request", "static_analysis", "pair_programming"],
            "source": "static",
        },
        {
            "concept": "debugging",
            "definition": "Process of finding and resolving defects in software that prevent it from operating correctly.",
            "related": ["logging", "breakpoints", "stack_trace", "unit_tests"],
            "source": "static",
        },
        {
            "concept": "test_driven_development",
            "definition": "Write failing tests first, implement minimal code to pass, then refactor.",
            "related": ["red_green_refactor", "unit_tests", "ci_cd"],
            "source": "static",
        },
    ],
    "researcher": [
        {
            "concept": "research_methodology",
            "definition": "Systematic framework for conducting research including sampling, data collection, and analysis.",
            "related": ["qualitative", "quantitative", "mixed_methods"],
            "source": "static",
        },
        {
            "concept": "synthesis_techniques",
            "definition": "Methods for combining findings from multiple sources into coherent conclusions.",
            "related": ["meta_analysis", "thematic_synthesis", "narrative_review"],
            "source": "static",
        },
        {
            "concept": "literature_review",
            "definition": "Comprehensive survey of published works relevant to a research topic.",
            "related": ["citation_management", "systematic_review", "grey_literature"],
            "source": "static",
        },
        {
            "concept": "evidence_hierarchy",
            "definition": "Ranking of evidence quality from anecdotal reports to systematic reviews.",
            "related": ["peer_review", "clinical_trials", "meta_analysis"],
            "source": "static",
        },
    ],
    "_default": [
        {
            "concept": "task_decomposition",
            "definition": "Breaking a complex task into smaller, manageable sub-tasks.",
            "related": ["planning", "dependency_mapping", "work_breakdown_structure"],
            "source": "static",
        },
        {
            "concept": "iteration",
            "definition": "Repeating a process to approach a desired result incrementally.",
            "related": ["agile", "feedback_loop", "continuous_improvement"],
            "source": "static",
        },
        {
            "concept": "context_window_management",
            "definition": "Strategies for keeping relevant information within an LLM's active context.",
            "related": ["summarization", "chunking", "retrieval_augmented_generation"],
            "source": "static",
        },
    ],
}


class KnowledgeInjector:
    """Injects role-relevant knowledge graph context into worker spawn payloads.

    Falls back gracefully when NKS is unavailable — static knowledge is always
    returned regardless of NKS connectivity.

    Usage::

        injector = KnowledgeInjector()
        ctx = injector.inject_into_context({}, role_id="coder")
    """

    def __init__(self, nks_bridge: Any | None = None) -> None:
        """Initialise the injector.

        Args:
            nks_bridge: Optional :class:`NKSMCPBridge` instance.  When provided,
                        ``get_nks_knowledge`` will attempt live graph queries.
                        If ``None``, all queries fall back to static knowledge.
        """
        self.status = "active"
        self._nks_bridge = nks_bridge

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_static_knowledge(self, role_id: str) -> list[KnowledgeSlice]:
        """Return hardcoded role-specific knowledge slices.

        Args:
            role_id: Worker role identifier (e.g. ``"analyst"``, ``"coder"``).

        Returns:
            List of :class:`KnowledgeSlice` objects for the role, falling back
            to the ``_default`` set for unknown roles.
        """
        raw = _STATIC_KNOWLEDGE.get(role_id, _STATIC_KNOWLEDGE["_default"])
        return [
            KnowledgeSlice(
                concept=r["concept"],
                definition=r["definition"],
                related=list(r.get("related", [])),
                source=r.get("source", "static"),
            )
            for r in raw
        ]

    def get_nks_knowledge(self, concepts: list[str]) -> list[KnowledgeSlice]:
        """Query the NKS graph for *concepts*, falling back gracefully.

        Args:
            concepts: List of concept names to look up.

        Returns:
            List of :class:`KnowledgeSlice` objects.  Returns an empty list
            when NKS is unavailable rather than raising.
        """
        if self._nks_bridge is None:
            logger.debug("[KnowledgeInjector] No NKS bridge — skipping graph query.")
            return []

        slices: list[KnowledgeSlice] = []
        for concept in concepts:
            try:
                result = self._nks_bridge.call(
                    "nks_query_entity",
                    {"name_pattern": concept, "limit": 3},
                )
                entities = (
                    result.get("entities", []) if isinstance(result, dict) else []
                )
                for ent in entities:
                    slices.append(
                        KnowledgeSlice(
                            concept=ent.get("name", concept),
                            definition=ent.get("description", ""),
                            related=[r.get("name", "") for r in ent.get("related", [])],
                            source="nks",
                        )
                    )
            except (OSError, ValueError, RuntimeError, Exception) as exc:
                logger.warning(
                    "[KnowledgeInjector] NKS query for '%s' failed (non-fatal): %s",
                    concept,
                    exc,
                )
        return slices

    def inject_into_context(self, worker_context: dict, role_id: str) -> dict:
        """Augment *worker_context* with a ``knowledge_context`` list.

        Combines static knowledge (always available) with NKS knowledge
        (when bridge is set).  Attaches under the ``"knowledge_context"`` key.

        Args:
            worker_context: Existing context dict (mutated in place and returned).
            role_id:        Worker role identifier.

        Returns:
            The augmented *worker_context* dict.
        """
        slices = self.get_static_knowledge(role_id)

        # Optionally enrich with live NKS data
        if self._nks_bridge is not None:
            concepts = [s.concept for s in slices]
            nks_slices = self.get_nks_knowledge(concepts)
            slices = slices + nks_slices

        worker_context["knowledge_context"] = [asdict(s) for s in slices]
        return worker_context

    def serialize_for_env(self, slices: list[KnowledgeSlice]) -> str:
        """Serialise *slices* to a JSON string for ``BOS_KNOWLEDGE_CONTEXT``.

        Truncates to ``_MAX_ENV_BYTES`` characters to fit inside environment
        variable size limits.

        Args:
            slices: List of :class:`KnowledgeSlice` objects.

        Returns:
            JSON string, truncated at ``_MAX_ENV_BYTES`` bytes if necessary.
        """
        payload = json.dumps([asdict(s) for s in slices], ensure_ascii=False)
        if len(payload) > _MAX_ENV_BYTES:
            for n in range(len(slices), 0, -1):
                candidate = json.dumps(
                    [asdict(s) for s in slices[:n]], ensure_ascii=False
                )
                if len(candidate) <= _MAX_ENV_BYTES:
                    return candidate
            return "[]"
        return payload
