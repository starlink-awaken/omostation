"""JSON Schema definitions for the Mind Model Quartet (BET-Y2Q1-T3-05)."""

PERSONA_PROFILE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://omostation.local/schema/mindmodel/persona-profile.json",
    "title": "PersonaProfile",
    "description": "认知画像 · 表达文风 — 描述用户的语言风格、详略偏好与表达习惯",
    "type": "object",
    "required": ["version", "tone", "verbosity", "expression_style"],
    "properties": {
        "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
        "tone": {
            "type": "string",
            "enum": ["formal", "neutral", "casual", "assertive", "diplomatic"],
        },
        "verbosity": {
            "type": "string",
            "enum": ["concise", "balanced", "elaborate"],
        },
        "expression_style": {
            "type": "array",
            "items": {"type": "string"},
            "examples": [["data-driven", "first-principles", "analogical"]],
        },
        "preferred_formats": {
            "type": "array",
            "items": {"type": "string"},
            "examples": [["bullet-list", "narrative", "table", "mermaid"]],
        },
        "updated_at": {"type": "string", "format": "date-time"},
    },
}

AGENDA_RADAR_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://omostation.local/schema/mindmodel/agenda-radar.json",
    "title": "AgendaRadar",
    "description": "决策偏好 · 轻重缓急 — 描述用户的优先级判断、风险偏好与时间视野",
    "type": "object",
    "required": ["version", "priority_axis", "risk_appetite", "time_horizon"],
    "properties": {
        "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
        "priority_axis": {
            "type": "string",
            "enum": ["impact-first", "urgency-first", "effort-first", "learning-first"],
        },
        "risk_appetite": {
            "type": "string",
            "enum": ["conservative", "moderate", "aggressive"],
        },
        "time_horizon": {
            "type": "string",
            "enum": ["daily", "weekly", "quarterly", "yearly"],
        },
        "decision_heuristics": {
            "type": "array",
            "items": {"type": "string"},
            "examples": [["first-principles", "inversion", "second-order"]],
        },
        "updated_at": {"type": "string", "format": "date-time"},
    },
}

ATTENTION_FIELD_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://omostation.local/schema/mindmodel/attention-field.json",
    "title": "AttentionField",
    "description": "学习风格 · 精力分配 — 描述用户的精力节律、学习时段偏好与信息密度承受",
    "type": "object",
    "required": ["version", "peak_hours", "info_density", "learning_modality"],
    "properties": {
        "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
        "peak_hours": {
            "type": "array",
            "items": {"type": "integer", "minimum": 0, "maximum": 23},
            "examples": [[6, 7, 8, 21, 22, 23]],
        },
        "info_density": {
            "type": "string",
            "enum": ["low", "medium", "high", "variable"],
        },
        "learning_modality": {
            "type": "array",
            "items": {"type": "string"},
            "examples": [["reading", "teaching", "hands-on", "discussing"]],
        },
        "context_switch_tolerance": {
            "type": "string",
            "enum": ["low", "medium", "high"],
        },
        "updated_at": {"type": "string", "format": "date-time"},
    },
}

CONTEXT_ANCHOR_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://omostation.local/schema/mindmodel/context-anchor.json",
    "title": "ContextAnchor",
    "description": "情绪基线 · 历史决策链 — 描述用户的情绪常态与认知负荷标记",
    "type": "object",
    "required": ["version", "baseline_mood", "cognitive_load", "decision_chain_depth"],
    "properties": {
        "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
        "baseline_mood": {
            "type": "string",
            "enum": ["focused", "relaxed", "irritated", "fatigued", "creative"],
        },
        "cognitive_load": {
            "type": "string",
            "enum": ["light", "moderate", "heavy", "saturated"],
        },
        "decision_chain_depth": {
            "type": "integer",
            "minimum": 0,
            "maximum": 20,
            "description": "当前上下文关联的历史决策链长度",
        },
        "recent_decisions": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 10,
        },
        "updated_at": {"type": "string", "format": "date-time"},
    },
}

ALL_SCHEMAS = {
    "persona_profile": PERSONA_PROFILE_SCHEMA,
    "agenda_radar": AGENDA_RADAR_SCHEMA,
    "attention_field": ATTENTION_FIELD_SCHEMA,
    "context_anchor": CONTEXT_ANCHOR_SCHEMA,
}
