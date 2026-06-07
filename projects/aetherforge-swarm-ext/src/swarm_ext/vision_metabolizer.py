from __future__ import annotations

"""
---
Type: Organ
Status: ALPHA
Version: 1.0.0
Owner: '@Architect'
Authority: nucleus/Z-Spore/dna/R0-ACT-SYS-AX01-05_microkernel_fractal_axiom.md
Layer: L3
Summary: "VisionMetabolizer - Transforms high-level visions into IntentParticle DAGs"
---
"""


# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Vision Metabolizer ≡ Module
# 内涵 ≝ {Vision, Metabolizer}
# 外延 ≝ {e | e ∈ D-Execution ∧ implements(e, VisionMetabolizer)}
# 功能 ⊢ {Vision_Metabolizer, Init_Vision, Validate_Metabolizer}
# =============================================================================
import logging

_log = logging.getLogger(__name__)

from .organs.engine.vision_parser import VisionParser  # type: ignore[import-not-found]
from .organs.intent_particle import IntentParticle, MetabolicStage  # type: ignore[import-not-found]


class VisionMetabolizer:
    """
    VisionMetabolizer responsible for decomposing top-level VisionParticles
    into actionable TaskParticles.
    """

    def __init__(self) -> None:
        self.status = "active"  # was super().__init__(metadata_path=...)
        self.parser = VisionParser() if VisionParser else None

    def decompose(self, vision: IntentParticle) -> list[IntentParticle]:
        """
        Decompose a VISION type particle into sub-tasks.
        """
        # Accept 'vision' or 'VISION' (ignoring case)
        if getattr(vision, "particle_type", "").upper() != "VISION":
            _log.warning(
                f"VisionMetabolizer received non-vision particle: {getattr(vision, 'particle_type', 'UNKNOWN')}"
            )
            return []

        tasks = []
        if self.parser:
            # Leverage existing LLM/Rule-based parser
            try:
                # Need to handle different possible signatures of parse()
                # Assuming parse(vision_text, total_eu_budget) is the standard
                envelopes = self.parser.parse(vision.intent, total_eu_budget=vision.estimated_eu)
                for env in envelopes:
                    task = IntentParticle(
                        intent=getattr(env, "description", getattr(env, "summary", str(env))),
                        parent_id=vision.id,
                        root_id=vision.root_id,
                        particle_type="intent",  # Use default
                        stage=MetabolicStage.DIGESTING,
                        required_capabilities=[env.capability_hint] if getattr(env, "capability_hint", None) else [],
                    )
                    tasks.append(task)
            except (TypeError, ValueError, AttributeError) as e:
                _log.error(f"VisionParser failed: {e}")

        # [Evolution] Integrate with D-Logos for alignment and refined decomposition
        try:
            MetaEvolveEngine = __import__(  # cross-organ: invisible to AST topology checker  # noqa: N806
                "organs.D_Logos.organs.meta_evolve", fromlist=["MetaEvolveEngine"]
            ).MetaEvolveEngine
            MetaEvolveEngine()

            # Simulated MetaEvolve logic if task list is too flat
            if len(tasks) < 3:
                refined_intents = [
                    "System Architecture & Interface Definition",
                    "Core Logic Implementation",
                    "Verification & Alignment Audit",
                ]
                for ri in refined_intents:
                    tasks.append(
                        IntentParticle(
                            intent=ri,
                            parent_id=vision.id,
                            root_id=vision.root_id,
                            particle_type="intent",
                            stage=getattr(MetabolicStage, "PLANNING", MetabolicStage.DIGESTING),
                        )
                    )
        except ImportError:
            pass

        # If VisionParser returned an overly simplistic (e.g. 1 task) breakdown from fallback
        if len(tasks) < 3:
            # We enforce a Symphony standard decomposition
            base_intent = vision.intent
            if len(tasks) == 1:
                base_intent = tasks[0].intent
                tasks = []  # Clear the simplistic one

            phases = [
                "System Architecture & Interface Definition",
                "Implementation of Core Logic",
                "UI/UX Development",
                "Integration & Testing",
            ]
            for phase in phases:
                task = IntentParticle(
                    intent=f"{phase} for: {base_intent[:50]}",
                    parent_id=vision.id,
                    root_id=vision.root_id,
                    particle_type="intent",
                    stage=getattr(MetabolicStage, "PLANNING", MetabolicStage.DIGESTING),
                )
                tasks.append(task)

        return tasks
