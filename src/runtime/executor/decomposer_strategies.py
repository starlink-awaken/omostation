"""Decomposition strategies for different project archetypes.

Maps to TS source: agentmesh/packages/engine/src/decomposer.ts (strategies section)

Provides archetype-specific decomposition strategies:
  - software-dev: domain-driven sub-systems
  - creative-writing: sequential creative phases
  - visual-production: production pipeline phases
  - document-processing: linear processing pipeline
  - custom: monolithic fallback
"""

from __future__ import annotations

import uuid
from typing import Any

from runtime.executor.decomposer import (
    ComplexityLevel,
    ProjectArchetype,
    ProjectConfig,
    SubProject,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_sub_project(overrides: dict[str, Any]) -> SubProject:
    base = {
        "id": uuid.uuid4().hex,
        "goals": [],
        "dependencies": [],
        "estimated_complexity": ComplexityLevel.STANDARD,
        "priority": 5,
        "tags": [],
        "metadata": {},
    }
    base.update(overrides)
    return SubProject(**base)  # type: ignore[arg-type]


def _filter_goals_by_keywords(goals: list[str], keywords: list[str]) -> list[str]:
    matched = [g for g in goals if any(kw in g.lower() for kw in keywords)]
    return matched if matched else [f"Complete tasks related to: {', '.join(keywords)}"]


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


def software_dev_strategy(config: ProjectConfig) -> list[SubProject]:
    g = config.goals
    infra = _create_sub_project({
        "name": "infrastructure",
        "description": "Shared infrastructure: CI/CD, database, networking, monitoring",
        "archetype": ProjectArchetype.SOFTWARE_DEV,
        "goals": _filter_goals_by_keywords(g, ["infra", "deploy", "ci", "cd", "monitor", "database", "config"]),
        "estimated_complexity": ComplexityLevel.STANDARD, "priority": 10, "tags": ["infrastructure", "foundation"],
    })
    user_sys = _create_sub_project({
        "name": "user-system",
        "description": "User auth, authorization, profiles, session management",
        "archetype": ProjectArchetype.SOFTWARE_DEV,
        "goals": _filter_goals_by_keywords(g, ["user", "auth", "login", "profile", "account", "permission"]),
        "dependencies": [infra.id], "estimated_complexity": ComplexityLevel.STANDARD, "priority": 9, "tags": ["core", "auth"],
    })
    prod_sys = _create_sub_project({
        "name": "product-system",
        "description": "Product catalog, categories, inventory management",
        "archetype": ProjectArchetype.SOFTWARE_DEV,
        "goals": _filter_goals_by_keywords(g, ["product", "catalog", "inventory", "content", "item"]),
        "dependencies": [infra.id], "estimated_complexity": ComplexityLevel.STANDARD, "priority": 8, "tags": ["core", "product"],
    })
    order_sys = _create_sub_project({
        "name": "order-system",
        "description": "Order processing, payment, cart, fulfillment",
        "archetype": ProjectArchetype.SOFTWARE_DEV,
        "goals": _filter_goals_by_keywords(g, ["order", "payment", "cart", "checkout", "fulfill"]),
        "dependencies": [infra.id, user_sys.id, prod_sys.id],
        "estimated_complexity": ComplexityLevel.ADVANCED, "priority": 7, "tags": ["core", "order"],
    })
    search_sys = _create_sub_project({
        "name": "search-system",
        "description": "Search indexing, filtering, sorting, recommendations",
        "archetype": ProjectArchetype.SOFTWARE_DEV,
        "goals": _filter_goals_by_keywords(g, ["search", "filter", "sort", "recommend", "index"]),
        "dependencies": [infra.id, prod_sys.id],
        "estimated_complexity": ComplexityLevel.STANDARD, "priority": 6, "tags": ["feature", "search"],
    })
    admin_sys = _create_sub_project({
        "name": "admin-system",
        "description": "Admin dashboard, analytics, reporting, user management",
        "archetype": ProjectArchetype.SOFTWARE_DEV,
        "goals": _filter_goals_by_keywords(g, ["admin", "dashboard", "analytics", "report", "manage"]),
        "dependencies": [infra.id, user_sys.id, prod_sys.id, order_sys.id],
        "estimated_complexity": ComplexityLevel.STANDARD, "priority": 5, "tags": ["feature", "admin"],
    })
    return [infra, user_sys, prod_sys, order_sys, search_sys, admin_sys]


def creative_writing_strategy(config: ProjectConfig) -> list[SubProject]:
    g = config.goals
    wb = _create_sub_project({
        "name": "worldbuilding",
        "description": "World creation: setting, geography, history, culture, rules",
        "archetype": ProjectArchetype.CREATIVE_WRITING,
        "goals": _filter_goals_by_keywords(g, ["world", "setting", "geography", "culture", "history", "rules"]),
        "estimated_complexity": ComplexityLevel.STANDARD, "priority": 10, "tags": ["foundation", "world"],
    })
    cd = _create_sub_project({
        "name": "character-design",
        "description": "Character creation: profiles, backstories, motivations, arcs",
        "archetype": ProjectArchetype.CREATIVE_WRITING,
        "goals": _filter_goals_by_keywords(g, ["character", "protagonist", "antagonist", "motivation", "relationship"]),
        "dependencies": [wb.id], "estimated_complexity": ComplexityLevel.STANDARD, "priority": 9, "tags": ["foundation", "character"],
    })
    pa = _create_sub_project({
        "name": "plot-architecture",
        "description": "Plot structure: story arcs, conflict, pacing, themes",
        "archetype": ProjectArchetype.CREATIVE_WRITING,
        "goals": _filter_goals_by_keywords(g, ["plot", "story", "arc", "conflict", "theme", "structure"]),
        "dependencies": [wb.id, cd.id], "estimated_complexity": ComplexityLevel.ADVANCED, "priority": 8, "tags": ["structure", "plot"],
    })
    cw = _create_sub_project({
        "name": "chapter-writing",
        "description": "Chapter drafting: scene composition, dialogue, prose, transitions",
        "archetype": ProjectArchetype.CREATIVE_WRITING,
        "goals": _filter_goals_by_keywords(g, ["chapter", "scene", "dialogue", "write", "draft", "prose"]),
        "dependencies": [pa.id], "estimated_complexity": ComplexityLevel.ADVANCED, "priority": 7, "tags": ["production", "writing"],
    })
    qr = _create_sub_project({
        "name": "quality-review",
        "description": "Editorial review: consistency, style, pacing, polish",
        "archetype": ProjectArchetype.CREATIVE_WRITING,
        "goals": _filter_goals_by_keywords(g, ["review", "edit", "quality", "consistency", "polish"]),
        "dependencies": [cw.id], "estimated_complexity": ComplexityLevel.STANDARD, "priority": 6, "tags": ["quality", "review"],
    })
    return [wb, cd, pa, cw, qr]


def visual_production_strategy(config: ProjectConfig) -> list[SubProject]:
    g = config.goals
    sp = _create_sub_project({
        "name": "screenplay",
        "description": "Script writing: narrative, dialogue, scene directions",
        "archetype": ProjectArchetype.VISUAL_PRODUCTION,
        "goals": _filter_goals_by_keywords(g, ["script", "screenplay", "dialogue", "scene", "narrative"]),
        "estimated_complexity": ComplexityLevel.STANDARD, "priority": 10, "tags": ["pre-production", "script"],
    })
    vd = _create_sub_project({
        "name": "visual-design",
        "description": "Visual language: art direction, color, typography, mood boards",
        "archetype": ProjectArchetype.VISUAL_PRODUCTION,
        "goals": _filter_goals_by_keywords(g, ["visual", "design", "art", "color", "style", "mood"]),
        "dependencies": [sp.id], "estimated_complexity": ComplexityLevel.STANDARD, "priority": 9, "tags": ["pre-production", "design"],
    })
    sb = _create_sub_project({
        "name": "storyboard",
        "description": "Storyboarding: shot composition, camera angles, timing, flow",
        "archetype": ProjectArchetype.VISUAL_PRODUCTION,
        "goals": _filter_goals_by_keywords(g, ["storyboard", "shot", "camera", "composition", "flow"]),
        "dependencies": [sp.id, vd.id], "estimated_complexity": ComplexityLevel.ADVANCED, "priority": 8, "tags": ["pre-production", "storyboard"],
    })
    prod = _create_sub_project({
        "name": "production",
        "description": "Asset creation: rendering, animation, compositing, sound",
        "archetype": ProjectArchetype.VISUAL_PRODUCTION,
        "goals": _filter_goals_by_keywords(g, ["render", "animate", "composite", "sound", "asset", "produce"]),
        "dependencies": [sb.id], "estimated_complexity": ComplexityLevel.ADVANCED, "priority": 7, "tags": ["production", "asset"],
    })
    qr = _create_sub_project({
        "name": "quality-review",
        "description": "QA: visual consistency, audio sync, color grading, approval",
        "archetype": ProjectArchetype.VISUAL_PRODUCTION,
        "goals": _filter_goals_by_keywords(g, ["review", "quality", "consistency", "approval", "final"]),
        "dependencies": [prod.id], "estimated_complexity": ComplexityLevel.STANDARD, "priority": 6, "tags": ["post-production", "quality"],
    })
    return [sp, vd, sb, prod, qr]


def document_processing_strategy(config: ProjectConfig) -> list[SubProject]:
    g = config.goals
    analysis = _create_sub_project({
        "name": "analysis",
        "description": "Document analysis: structure detection, classification, metadata extraction",
        "archetype": ProjectArchetype.DOCUMENT_PROCESSING,
        "goals": _filter_goals_by_keywords(g, ["analyze", "detect", "classify", "extract", "schema"]),
        "estimated_complexity": ComplexityLevel.STANDARD, "priority": 10, "tags": ["analysis", "foundation"],
    })
    processing = _create_sub_project({
        "name": "processing",
        "description": "Content processing: transformation, normalization, enrichment",
        "archetype": ProjectArchetype.DOCUMENT_PROCESSING,
        "goals": _filter_goals_by_keywords(g, ["process", "transform", "normalize", "enrich", "convert"]),
        "dependencies": [analysis.id], "estimated_complexity": ComplexityLevel.STANDARD, "priority": 8, "tags": ["processing", "transform"],
    })
    formatting = _create_sub_project({
        "name": "formatting",
        "description": "Output formatting: template, layout, styling, export",
        "archetype": ProjectArchetype.DOCUMENT_PROCESSING,
        "goals": _filter_goals_by_keywords(g, ["format", "template", "layout", "style", "export"]),
        "dependencies": [processing.id], "estimated_complexity": ComplexityLevel.SIMPLE, "priority": 6, "tags": ["formatting", "output"],
    })
    validation = _create_sub_project({
        "name": "validation",
        "description": "Output validation: schema compliance, data integrity, acceptance",
        "archetype": ProjectArchetype.DOCUMENT_PROCESSING,
        "goals": _filter_goals_by_keywords(g, ["validate", "verify", "test", "compliance", "integrity"]),
        "dependencies": [formatting.id], "estimated_complexity": ComplexityLevel.SIMPLE, "priority": 5, "tags": ["validation", "quality"],
    })
    return [analysis, processing, formatting, validation]


def custom_strategy(config: ProjectConfig) -> list[SubProject]:
    return [
        _create_sub_project({
            "name": config.name,
            "description": config.description,
            "archetype": ProjectArchetype.CUSTOM,
            "goals": list(config.goals),
            "estimated_complexity": config.complexity,
            "priority": 10,
            "tags": ["custom", "monolithic"],
            "metadata": {"original_constraints": list(config.constraints)},
        }),
    ]


# ---------------------------------------------------------------------------
# Strategy Registry
# ---------------------------------------------------------------------------

STRATEGIES: dict[ProjectArchetype, Any] = {
    ProjectArchetype.SOFTWARE_DEV: software_dev_strategy,
    ProjectArchetype.CREATIVE_WRITING: creative_writing_strategy,
    ProjectArchetype.VISUAL_PRODUCTION: visual_production_strategy,
    ProjectArchetype.DOCUMENT_PROCESSING: document_processing_strategy,
    ProjectArchetype.CUSTOM: custom_strategy,
}
