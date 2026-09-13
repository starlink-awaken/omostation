"""Pydantic models for the Mind Model Quartet (BET-Y2Q1-T3-05)."""

from pydantic import BaseModel, Field
from typing import Literal


class PersonaProfile(BaseModel):
    """认知画像 · 表达文风"""

    version: str = "1.0.0"
    tone: Literal["formal", "neutral", "casual", "assertive", "diplomatic"] = "neutral"
    verbosity: Literal["concise", "balanced", "elaborate"] = "balanced"
    expression_style: list[str] = Field(default_factory=list)
    preferred_formats: list[str] = Field(default_factory=list)
    updated_at: str = ""


class AgendaRadar(BaseModel):
    """决策偏好 · 轻重缓急"""

    version: str = "1.0.0"
    priority_axis: Literal[
        "impact-first", "urgency-first", "effort-first", "learning-first"
    ] = "impact-first"
    risk_appetite: Literal["conservative", "moderate", "aggressive"] = "moderate"
    time_horizon: Literal["daily", "weekly", "quarterly", "yearly"] = "weekly"
    decision_heuristics: list[str] = Field(default_factory=list)
    updated_at: str = ""


class AttentionField(BaseModel):
    """学习风格 · 精力分配"""

    version: str = "1.0.0"
    peak_hours: list[int] = Field(default_factory=list)
    info_density: Literal["low", "medium", "high", "variable"] = "medium"
    learning_modality: list[str] = Field(default_factory=list)
    context_switch_tolerance: Literal["low", "medium", "high"] = "medium"
    updated_at: str = ""


class ContextAnchor(BaseModel):
    """情绪基线 · 历史决策链"""

    version: str = "1.0.0"
    baseline_mood: Literal[
        "focused", "relaxed", "irritated", "fatigued", "creative"
    ] = "focused"
    cognitive_load: Literal["light", "moderate", "heavy", "saturated"] = "moderate"
    decision_chain_depth: int = Field(default=0, ge=0, le=20)
    recent_decisions: list[str] = Field(default_factory=list)
    updated_at: str = ""
