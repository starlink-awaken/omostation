"""Tests for USP v1 surface protocol and card primitives.

Covers:
  - Protocol purity (no I/O, no side-effects)
  - Enum vocabulary completeness and value constraints
  - SurfaceEnvelope construction, serialisation, round-trip
  - SurfaceEnvelope edge cases (TTL expiry, missing optional fields, unknown extra keys)
  - All 5 card primitives: to_dict / from_dict round-trip
  - Integration: card → SurfaceEnvelope → to_dict → from_dict → card
"""

from __future__ import annotations

import json
import time
import uuid

import pytest

from cockpit.surface.cards import (
    ActionButton,
    ActionPanelCard,
    DagEdge,
    DagGraphCard,
    DagNode,
    DataTableCard,
    LogEntry,
    LogStreamCard,
    MetricCell,
    MetricGridCard,
    TableColumn,
)
from cockpit.surface.protocol import (
    CardType,
    RefreshMode,
    SurfaceDomain,
    SurfaceEnvelope,
)

# ===========================================================================
# Protocol purity
# ===========================================================================


class TestProtocolPurity:
    """USP v1 protocol must be pure (no I/O, no external calls)."""

    def test_import_has_no_side_effects(self) -> None:
        """Re-importing the modules must not raise or print."""
        import importlib

        import cockpit.surface.cards as cards
        import cockpit.surface.protocol as proto

        importlib.reload(proto)
        importlib.reload(cards)

    def test_envelope_creation_is_pure(self) -> None:
        """SurfaceEnvelope creation must not touch the filesystem or network."""
        env = SurfaceEnvelope(
            domain=SurfaceDomain.GOVERNANCE,
            card_type=CardType.METRIC_GRID,
            title="test",
            payload={},
        )
        assert env.schema == "usp/v1"


# ===========================================================================
# Enum vocabulary
# ===========================================================================


class TestEnumVocabulary:
    def test_surface_domain_values(self) -> None:
        expected = {
            "governance",
            "agent",
            "knowledge",
            "delivery",
            "compute",
            "observability",
            "system",
            "unknown",
        }
        assert {d.value for d in SurfaceDomain} == expected

    def test_card_type_values(self) -> None:
        expected = {"metric_grid", "data_table", "log_stream", "dag_graph", "action_panel"}
        assert {c.value for c in CardType} == expected

    def test_refresh_mode_values(self) -> None:
        expected = {"static", "poll", "stream", "auto"}
        assert {r.value for r in RefreshMode} == expected

    def test_domain_from_string(self) -> None:
        assert SurfaceDomain("governance") is SurfaceDomain.GOVERNANCE

    def test_card_type_from_string(self) -> None:
        assert CardType("metric_grid") is CardType.METRIC_GRID

    def test_refresh_mode_from_string(self) -> None:
        assert RefreshMode("stream") is RefreshMode.STREAM

    def test_invalid_domain_raises(self) -> None:
        with pytest.raises(ValueError):
            SurfaceDomain("not_a_domain")

    def test_invalid_card_type_raises(self) -> None:
        with pytest.raises(ValueError):
            CardType("not_a_card")


# ===========================================================================
# SurfaceEnvelope construction
# ===========================================================================


class TestSurfaceEnvelopeConstruction:
    def _make(self, **kwargs: object) -> SurfaceEnvelope:
        defaults: dict = dict(
            domain=SurfaceDomain.SYSTEM,
            card_type=CardType.ACTION_PANEL,
            title="Test Envelope",
            payload={"key": "value"},
        )
        defaults.update(kwargs)
        return SurfaceEnvelope(**defaults)

    def test_defaults(self) -> None:
        env = self._make()
        assert env.schema == "usp/v1"
        assert env.refresh_mode == RefreshMode.STATIC
        assert env.refresh_mode.value == "static"
        assert env.ttl is None
        assert env.tags == {}
        assert isinstance(env.envelope_id, str)
        assert len(env.envelope_id) == 36  # UUID4 format

    def test_explicit_envelope_id(self) -> None:
        eid = str(uuid.uuid4())
        env = self._make(envelope_id=eid)
        assert env.envelope_id == eid

    def test_explicit_ts(self) -> None:
        ts = 1234567890.0
        env = self._make(ts=ts)
        assert env.ts == ts

    def test_string_domain_accepted(self) -> None:
        env = self._make(domain="governance")
        assert env.domain == SurfaceDomain.GOVERNANCE
        assert env.domain.value == "governance"

    def test_string_card_type_accepted(self) -> None:
        env = self._make(card_type="data_table")
        assert env.card_type == CardType.DATA_TABLE
        assert env.card_type.value == "data_table"

    def test_string_refresh_mode_accepted(self) -> None:
        env = self._make(refresh_mode="stream")
        assert env.refresh_mode == RefreshMode.STREAM
        assert env.refresh_mode.value == "stream"

    def test_tags_copied(self) -> None:
        original_tags = {"env": "prod"}
        env = self._make(tags=original_tags)
        original_tags["env"] = "dev"  # mutate original
        assert env.tags["env"] == "prod"  # should not be affected

    def test_repr_contains_key_info(self) -> None:
        env = self._make(title="My Title")
        r = repr(env)
        assert "My Title" in r
        assert env.envelope_id in r


# ===========================================================================
# SurfaceEnvelope serialisation round-trip
# ===========================================================================


class TestSurfaceEnvelopeRoundTrip:
    def _make(self) -> SurfaceEnvelope:
        return SurfaceEnvelope(
            domain=SurfaceDomain.DELIVERY,
            card_type=CardType.DATA_TABLE,
            title="Delivery Table",
            payload={"rows": [{"id": 1, "name": "task"}], "columns": []},
            refresh_mode=RefreshMode.POLL,
            ttl=60.0,
            tags={"team": "platform"},
        )

    def test_to_dict_keys(self) -> None:
        d = self._make().to_dict()
        for key in (
            "schema",
            "envelope_id",
            "domain",
            "card_type",
            "refresh_mode",
            "title",
            "payload",
            "ts",
            "tags",
            "ttl",
        ):
            assert key in d, f"Missing key: {key}"

    def test_to_dict_enum_values_are_strings(self) -> None:
        d = self._make().to_dict()
        assert d["domain"] == "delivery"
        assert d["card_type"] == "data_table"
        assert d["refresh_mode"] == "poll"

    def test_json_serialisable(self) -> None:
        d = self._make().to_dict()
        dumped = json.dumps(d)
        assert isinstance(dumped, str)

    def test_from_dict_round_trip(self) -> None:
        original = self._make()
        restored = SurfaceEnvelope.from_dict(original.to_dict())
        assert restored.envelope_id == original.envelope_id
        assert restored.domain is original.domain
        assert restored.card_type is original.card_type
        assert restored.refresh_mode is original.refresh_mode
        assert restored.title == original.title
        assert restored.ttl == original.ttl
        assert restored.tags == original.tags

    def test_from_dict_ignores_unknown_keys(self) -> None:
        d = self._make().to_dict()
        d["future_field"] = "ignored"
        env = SurfaceEnvelope.from_dict(d)
        assert env.title == "Delivery Table"

    def test_from_dict_missing_required_raises(self) -> None:
        d = self._make().to_dict()
        del d["domain"]
        with pytest.raises(ValueError, match="missing required keys"):
            SurfaceEnvelope.from_dict(d)

    def test_equality_by_envelope_id(self) -> None:
        env = self._make()
        d = env.to_dict()
        env2 = SurfaceEnvelope.from_dict(d)
        assert env == env2

    def test_different_ids_not_equal(self) -> None:
        env1 = self._make()
        env2 = self._make()
        assert env1 != env2

    def test_hash_by_envelope_id(self) -> None:
        env = self._make()
        s = {env}
        assert env in s


# ===========================================================================
# SurfaceEnvelope TTL
# ===========================================================================


class TestSurfaceEnvelopeTTL:
    def test_no_ttl_never_expires(self) -> None:
        env = SurfaceEnvelope(
            domain=SurfaceDomain.SYSTEM,
            card_type=CardType.METRIC_GRID,
            title="t",
            payload={},
        )
        assert not env.is_expired()
        assert not env.is_expired(now=time.time() + 999_999)

    def test_future_ttl_not_expired(self) -> None:
        env = SurfaceEnvelope(
            domain=SurfaceDomain.SYSTEM,
            card_type=CardType.METRIC_GRID,
            title="t",
            payload={},
            ttl=3600.0,
        )
        assert not env.is_expired()

    def test_past_ttl_expired(self) -> None:
        env = SurfaceEnvelope(
            domain=SurfaceDomain.SYSTEM,
            card_type=CardType.METRIC_GRID,
            title="t",
            payload={},
            ts=0.0,
            ttl=1.0,
        )
        assert env.is_expired(now=time.time())

    def test_ttl_absent_from_dict_when_none(self) -> None:
        env = SurfaceEnvelope(
            domain=SurfaceDomain.SYSTEM,
            card_type=CardType.METRIC_GRID,
            title="t",
            payload={},
        )
        d = env.to_dict()
        assert "ttl" not in d


# ===========================================================================
# MetricGridCard
# ===========================================================================


class TestMetricGridCard:
    def _make(self) -> MetricGridCard:
        return MetricGridCard(
            cells=[
                MetricCell(label="Uptime", value=99.9, unit="%", trend="up"),
                MetricCell(label="Errors", value=3, trend="down", warn_threshold=10.0),
            ],
            columns=2,
        )

    def test_to_dict_structure(self) -> None:
        d = self._make().to_dict()
        assert "cells" in d and "columns" in d
        assert d["columns"] == 2
        assert len(d["cells"]) == 2
        assert d["cells"][0]["label"] == "Uptime"

    def test_round_trip(self) -> None:
        original = self._make()
        restored = MetricGridCard.from_dict(original.to_dict())
        assert restored.columns == original.columns
        assert len(restored.cells) == len(original.cells)
        assert restored.cells[0].label == "Uptime"
        assert restored.cells[1].warn_threshold == 10.0

    def test_empty_cells(self) -> None:
        card = MetricGridCard()
        assert card.to_dict()["cells"] == []

    def test_json_serialisable(self) -> None:
        json.dumps(self._make().to_dict())


# ===========================================================================
# DataTableCard
# ===========================================================================


class TestDataTableCard:
    def _make(self) -> DataTableCard:
        return DataTableCard(
            columns=[
                TableColumn(key="id", label="ID", sortable=False),
                TableColumn(key="name", label="Name", align="left"),
            ],
            rows=[{"id": 1, "name": "alpha"}, {"id": 2, "name": "beta"}],
            sort_by="name",
            sort_asc=True,
            page=1,
            page_size=20,
            total_rows=2,
        )

    def test_to_dict_structure(self) -> None:
        d = self._make().to_dict()
        assert len(d["columns"]) == 2
        assert len(d["rows"]) == 2
        assert d["sort_by"] == "name"
        assert d["total_rows"] == 2

    def test_round_trip(self) -> None:
        original = self._make()
        restored = DataTableCard.from_dict(original.to_dict())
        assert restored.sort_by == "name"
        assert len(restored.columns) == 2
        assert restored.columns[0].key == "id"
        assert restored.rows[1]["name"] == "beta"

    def test_json_serialisable(self) -> None:
        json.dumps(self._make().to_dict())


# ===========================================================================
# LogStreamCard
# ===========================================================================


class TestLogStreamCard:
    def _make(self) -> LogStreamCard:
        return LogStreamCard(
            entries=[
                LogEntry(ts=1000.0, level="INFO", message="started", source="agent"),
                LogEntry(ts=1001.0, level="ERROR", message="crash", tags={"trace": "abc"}),
            ],
            max_entries=100,
            follow=True,
            filter_level="INFO",
        )

    def test_to_dict_structure(self) -> None:
        d = self._make().to_dict()
        assert len(d["entries"]) == 2
        assert d["max_entries"] == 100
        assert d["filter_level"] == "INFO"

    def test_round_trip(self) -> None:
        original = self._make()
        restored = LogStreamCard.from_dict(original.to_dict())
        assert len(restored.entries) == 2
        assert restored.entries[1].level == "ERROR"
        assert restored.entries[1].tags == {"trace": "abc"}

    def test_json_serialisable(self) -> None:
        json.dumps(self._make().to_dict())


# ===========================================================================
# DagGraphCard
# ===========================================================================


class TestDagGraphCard:
    def _make(self) -> DagGraphCard:
        return DagGraphCard(
            nodes=[
                DagNode(id="A", label="Build", status="done"),
                DagNode(id="B", label="Test", status="running"),
                DagNode(id="C", label="Deploy", status="pending"),
            ],
            edges=[
                DagEdge(source="A", target="B"),
                DagEdge(source="B", target="C", label="on-success"),
            ],
            layout="LR",
            highlight=["B"],
        )

    def test_to_dict_structure(self) -> None:
        d = self._make().to_dict()
        assert len(d["nodes"]) == 3
        assert len(d["edges"]) == 2
        assert d["layout"] == "LR"
        assert d["highlight"] == ["B"]

    def test_round_trip(self) -> None:
        original = self._make()
        restored = DagGraphCard.from_dict(original.to_dict())
        assert len(restored.nodes) == 3
        assert restored.nodes[1].status == "running"
        assert restored.edges[1].label == "on-success"
        assert restored.highlight == ["B"]

    def test_json_serialisable(self) -> None:
        json.dumps(self._make().to_dict())


# ===========================================================================
# ActionPanelCard
# ===========================================================================


class TestActionPanelCard:
    def _make(self) -> ActionPanelCard:
        return ActionPanelCard(
            actions=[
                ActionButton(id="deploy", label="Deploy", variant="primary", confirm=True),
                ActionButton(
                    id="rollback",
                    label="Rollback",
                    variant="danger",
                    disabled=True,
                    disabled_reason="No previous version",
                ),
            ],
            title="Deployment Actions",
            description="Manage the current deployment.",
            layout="horizontal",
        )

    def test_to_dict_structure(self) -> None:
        d = self._make().to_dict()
        assert len(d["actions"]) == 2
        assert d["title"] == "Deployment Actions"
        assert d["layout"] == "horizontal"

    def test_round_trip(self) -> None:
        original = self._make()
        restored = ActionPanelCard.from_dict(original.to_dict())
        assert len(restored.actions) == 2
        assert restored.actions[0].confirm is True
        assert restored.actions[1].disabled is True
        assert restored.actions[1].disabled_reason == "No previous version"

    def test_json_serialisable(self) -> None:
        json.dumps(self._make().to_dict())


# ===========================================================================
# Integration: card → envelope → to_dict → from_dict → verify card
# ===========================================================================


class TestEnvelopeCardIntegration:
    """Verify that the envelope correctly carries each card type end-to-end."""

    @pytest.mark.parametrize(
        "card,card_type",
        [
            (MetricGridCard(cells=[MetricCell(label="CPU", value=72)]), CardType.METRIC_GRID),
            (DataTableCard(columns=[TableColumn(key="x", label="X")], rows=[{"x": 1}]), CardType.DATA_TABLE),
            (LogStreamCard(entries=[LogEntry(ts=1.0, level="INFO", message="ok")]), CardType.LOG_STREAM),
            (DagGraphCard(nodes=[DagNode(id="X", label="X")]), CardType.DAG_GRAPH),
            (ActionPanelCard(actions=[ActionButton(id="go", label="Go")]), CardType.ACTION_PANEL),
        ],
    )
    def test_envelope_round_trip_with_card(self, card: object, card_type: CardType) -> None:
        env = SurfaceEnvelope(
            domain=SurfaceDomain.SYSTEM,
            card_type=card_type,
            title="Integration Test",
            payload=card.to_dict(),  # type: ignore[attr-defined]
            refresh_mode=RefreshMode.AUTO,
        )
        d = env.to_dict()
        restored = SurfaceEnvelope.from_dict(d)

        assert restored.card_type == card_type
        assert restored.card_type.value == card_type.value
        assert restored.refresh_mode.value == "auto"
        # Payload must survive JSON serialisation
        json.dumps(restored.payload)
