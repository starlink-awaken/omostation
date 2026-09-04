"""USP v1 Card Primitives — the 5 canonical surface card types.

Each card primitive is a pure data class that holds the domain-specific
structured content for a particular visual pattern.  Card instances are
serialised to dicts and placed in SurfaceEnvelope.payload.

Card types
----------
MetricGridCard   — KPI tiles / numeric metric grids
DataTableCard    — tabular data with sortable columns
LogStreamCard    — streaming log / event rows
DagGraphCard     — directed-acyclic-graph (nodes + edges)
ActionPanelCard  — interactive command / action buttons
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Common base
# ---------------------------------------------------------------------------


@dataclass
class _BaseCard:
    """Shared serialisation helpers for all card primitives."""

    def to_dict(self) -> dict[str, Any]:
        """Recursively convert this card to a JSON-serialisable dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> _BaseCard:
        """Reconstruct a card from a plain dict.

        Subclasses should override if nested objects need special handling.
        """
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# MetricGridCard
# ---------------------------------------------------------------------------


@dataclass
class MetricCell:
    """Single KPI tile inside a MetricGridCard."""

    label: str
    value: str | int | float
    unit: str = ""
    # "up" | "down" | "neutral" — visual trend indicator
    trend: Literal["up", "down", "neutral"] = "neutral"
    # Optional threshold for colouring (value > warn_threshold → warning)
    warn_threshold: float | None = None
    # Optional sub-label or description
    description: str = ""


@dataclass
class MetricGridCard(_BaseCard):
    """Grid of KPI metric tiles.

    Attributes:
        cells:    Ordered list of MetricCell objects.
        columns:  Number of columns to render (0 = auto).
    """

    cells: list[MetricCell] = field(default_factory=list)
    columns: int = 0  # 0 = auto-layout

    def to_dict(self) -> dict[str, Any]:
        return {
            "cells": [asdict(c) for c in self.cells],
            "columns": self.columns,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetricGridCard:
        cells = [MetricCell(**c) for c in data.get("cells", [])]
        return cls(cells=cells, columns=data.get("columns", 0))


# ---------------------------------------------------------------------------
# DataTableCard
# ---------------------------------------------------------------------------


@dataclass
class TableColumn:
    """Column definition for a DataTableCard."""

    key: str
    label: str
    sortable: bool = True
    width: int = 0  # 0 = auto
    # "left" | "right" | "center"
    align: Literal["left", "right", "center"] = "left"


@dataclass
class DataTableCard(_BaseCard):
    """Tabular data with optional sorting and pagination.

    Attributes:
        columns:      Ordered column definitions.
        rows:         List of row dicts (keys must match column.key).
        sort_by:      Column key currently sorted (empty = unsorted).
        sort_asc:     Sort direction (True = ascending).
        page:         Current page (1-indexed).
        page_size:    Rows per page (0 = no pagination).
        total_rows:   Total rows across all pages (0 = unknown).
    """

    columns: list[TableColumn] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    sort_by: str = ""
    sort_asc: bool = True
    page: int = 1
    page_size: int = 0
    total_rows: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "columns": [asdict(c) for c in self.columns],
            "rows": list(self.rows),
            "sort_by": self.sort_by,
            "sort_asc": self.sort_asc,
            "page": self.page,
            "page_size": self.page_size,
            "total_rows": self.total_rows,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DataTableCard:
        columns = [TableColumn(**c) for c in data.get("columns", [])]
        return cls(
            columns=columns,
            rows=data.get("rows", []),
            sort_by=data.get("sort_by", ""),
            sort_asc=data.get("sort_asc", True),
            page=data.get("page", 1),
            page_size=data.get("page_size", 0),
            total_rows=data.get("total_rows", 0),
        )


# ---------------------------------------------------------------------------
# LogStreamCard
# ---------------------------------------------------------------------------


@dataclass
class LogEntry:
    """Single log / event row for a LogStreamCard."""

    ts: float  # unix epoch
    level: str  # "DEBUG" | "INFO" | "WARN" | "ERROR" | "CRITICAL"
    message: str
    source: str = ""
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class LogStreamCard(_BaseCard):
    """Streaming log / event feed.

    Attributes:
        entries:     Ordered list of log entries (oldest first).
        max_entries: Maximum entries to keep in memory (0 = unlimited).
        follow:      If True, surface auto-scrolls to newest entry.
        filter_level: Minimum log level to display (empty = all).
    """

    entries: list[LogEntry] = field(default_factory=list)
    max_entries: int = 500
    follow: bool = True
    filter_level: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "entries": [asdict(e) for e in self.entries],
            "max_entries": self.max_entries,
            "follow": self.follow,
            "filter_level": self.filter_level,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LogStreamCard:
        entries = [LogEntry(**e) for e in data.get("entries", [])]
        return cls(
            entries=entries,
            max_entries=data.get("max_entries", 500),
            follow=data.get("follow", True),
            filter_level=data.get("filter_level", ""),
        )


# ---------------------------------------------------------------------------
# DagGraphCard
# ---------------------------------------------------------------------------


@dataclass
class DagNode:
    """Node in a directed-acyclic-graph."""

    id: str
    label: str
    # "pending" | "running" | "done" | "error" | "skipped"
    status: str = "pending"
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DagEdge:
    """Directed edge between two DagNode objects."""

    source: str  # node id
    target: str  # node id
    label: str = ""


@dataclass
class DagGraphCard(_BaseCard):
    """Directed-acyclic-graph (DAG) visualisation.

    Attributes:
        nodes:       All nodes in the graph.
        edges:       All directed edges.
        layout:      Layout hint for renderer ("TB" = top-bottom, "LR" = left-right).
        highlight:   Node IDs to visually highlight.
    """

    nodes: list[DagNode] = field(default_factory=list)
    edges: list[DagEdge] = field(default_factory=list)
    layout: Literal["TB", "LR", "RL", "BT"] = "TB"
    highlight: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [asdict(e) for e in self.edges],
            "layout": self.layout,
            "highlight": list(self.highlight),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DagGraphCard:
        nodes = [DagNode(**n) for n in data.get("nodes", [])]
        edges = [DagEdge(**e) for e in data.get("edges", [])]
        return cls(
            nodes=nodes,
            edges=edges,
            layout=data.get("layout", "TB"),
            highlight=data.get("highlight", []),
        )


# ---------------------------------------------------------------------------
# ActionPanelCard
# ---------------------------------------------------------------------------


@dataclass
class ActionButton:
    """Single interactive action button."""

    id: str
    label: str
    # "primary" | "secondary" | "danger" | "ghost"
    variant: Literal["primary", "secondary", "danger", "ghost"] = "secondary"
    description: str = ""
    # Whether the action requires a confirmation step
    confirm: bool = False
    # Arbitrary metadata passed back to domain on execution
    payload: dict[str, Any] = field(default_factory=dict)
    # Disabled with optional reason
    disabled: bool = False
    disabled_reason: str = ""


@dataclass
class ActionPanelCard(_BaseCard):
    """Interactive command / action panel.

    Attributes:
        actions:     Ordered list of action buttons.
        title:       Optional panel-level title (separate from envelope title).
        description: Optional descriptive text shown above the actions.
        layout:      "vertical" | "horizontal" — button arrangement hint.
    """

    actions: list[ActionButton] = field(default_factory=list)
    title: str = ""
    description: str = ""
    layout: Literal["vertical", "horizontal"] = "vertical"

    def to_dict(self) -> dict[str, Any]:
        return {
            "actions": [asdict(a) for a in self.actions],
            "title": self.title,
            "description": self.description,
            "layout": self.layout,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionPanelCard:
        actions = [ActionButton(**a) for a in data.get("actions", [])]
        return cls(
            actions=actions,
            title=data.get("title", ""),
            description=data.get("description", ""),
            layout=data.get("layout", "vertical"),
        )
