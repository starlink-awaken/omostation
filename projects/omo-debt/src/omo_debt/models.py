"""
Debt item data models for omo-debt CLI.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

StageType = Literal["rapid_evolution", "stable_growth", "maintenance"]
PriorityType = Literal["P0", "P1", "P2"]


class DebtItem(BaseModel):
    """Technical debt item model."""

    id: str = Field(..., description="Unique debt ID (e.g., GBR-D01)")
    title: str = Field(..., description="Brief debt description")
    impact: int = Field(..., ge=1, le=10, description="Impact score (1-10)")
    frequency: int = Field(..., ge=1, le=10, description="Frequency score (1-10)")
    cost: int = Field(..., ge=1, le=10, description="Remediation cost (1-10)")
    stage: StageType | None = Field(None, description="Project lifecycle stage")
    project: str | None = Field(None, description="Project name")
    created_at: str | None = Field(None, description="Creation date")

    class Config:
        extra = "allow"  # Allow additional fields


class DebtConfig(BaseModel):
    """Debt scoring configuration."""

    project_name: str = Field(..., description="Project name")
    project_path: str = Field(..., description="Project path")
    stage: StageType | None = Field(None, description="Lifecycle stage (auto-detect if None)")
    weights: dict[str, float] | None = Field(None, description="Custom weights")
    normalization_factor: float | None = Field(None, description="Custom normalization factor")

    class Config:
        extra = "allow"
