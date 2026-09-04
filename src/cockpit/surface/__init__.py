"""Cockpit Surface Protocol — Unified Surface Protocol (USP) v1.

This package provides the canonical exchange format and card primitives for
all Cockpit surface renders (TUI, Web, API, MCP).  Any surface that wants to
display data to users MUST go through the SurfaceEnvelope protocol; raw
business-logic objects must never leak into render layers.

Public surface:
    SurfaceEnvelope     — top-level container sent by domain → surface
    SurfaceDomain       — enumeration of originating domains
    CardType            — enumeration of supported card primitives
    RefreshMode         — how the surface should refresh after receiving data

Card primitives (see cards.py):
    MetricGridCard      — KPI / numeric metric grids
    DataTableCard       — tabular data with sortable columns
    LogStreamCard       — streaming log / event feed
    DagGraphCard        — directed-acyclic-graph visualization
    ActionPanelCard     — interactive action / command panel
"""

from cockpit.surface.cards import (
    ActionPanelCard,
    DagGraphCard,
    DataTableCard,
    LogStreamCard,
    MetricGridCard,
)
from cockpit.surface.protocol import (
    CardType,
    RefreshMode,
    SurfaceDomain,
    SurfaceEnvelope,
)

__all__ = [
    # Protocol
    "SurfaceEnvelope",
    "SurfaceDomain",
    "CardType",
    "RefreshMode",
    # Cards
    "MetricGridCard",
    "DataTableCard",
    "LogStreamCard",
    "DagGraphCard",
    "ActionPanelCard",
]
