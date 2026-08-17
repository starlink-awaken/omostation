#!/usr/bin/env python3
# ruff: noqa
"""
KOS TUI — Knowledge Graph Explorer (Textual-based).

Interactive terminal interface for exploring KOS ontology:
  - Entity list with search/filter
  - Entity detail with relation lists
  - ASCII relation graph
  - Path finding between entities
  - Implicit connection discovery

Usage:
    kos-tui                → Start TUI (default: entity explorer)
    kos-tui --view graph   → Start in graph view

Requires: textual>=0.50
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent
ONTOLOGY_SCRIPT = SCRIPT_DIR / "_legacy" / "kos-ontology.py"

try:
    from textual.app import App, ComposeResult  # type: ignore[reportMissingImports]
    from textual.binding import Binding  # type: ignore[reportMissingImports]
    from textual.containers import Horizontal, Vertical  # type: ignore[reportMissingImports]
    from textual.widgets import Footer, Header, Label, ListItem, ListView, Static  # type: ignore[reportMissingImports]

    TEXTUAL_OK = True
except ImportError:
    TEXTUAL_OK = False


def _get_onto_db() -> sqlite3.Connection:
    """Get SQLite connection to KOS retrieval DB (contains ontology tables)."""
    from config import get_vault_ops_dir  # type: ignore[import-not-found]

    VAULT_OPS_DIR = get_vault_ops_dir()
    from config import get_artifact_path  # type: ignore[reportMissingImports]

    db_path = get_artifact_path("retrievalDatabase")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _load_entities(filter_text: str = "") -> list[dict]:  # type: ignore[type-arg]
    """Load entities directly from SQLite."""
    try:
        conn = _get_onto_db()  # type: ignore[no-untyped-call]
        if filter_text:
            rows = conn.execute(
                "SELECT entity_id, entity_type, label FROM kos_entities WHERE label LIKE ? OR entity_id LIKE ? ORDER BY entity_type, label LIMIT 200",
                (f"%{filter_text}%", f"%{filter_text}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT entity_id, entity_type, label FROM kos_entities ORDER BY entity_type, label LIMIT 100"
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:  # noqa: BLE001
        return [{"entity_id": "ERROR", "entity_type": "Error", "label": f"DB error: {str(e)[:60]}"}]


def _load_entity_detail(entity_id: str) -> dict:  # type: ignore[type-arg]
    """Load entity detail + relations from SQLite."""
    try:
        conn = _get_onto_db()  # type: ignore[no-untyped-call]
        entity = conn.execute("SELECT * FROM kos_entities WHERE entity_id=?", (entity_id,)).fetchone()
        if not entity:
            conn.close()
            return {"error": "Not found"}

        outgoing = conn.execute(
            "SELECT predicate, target_id, confidence FROM kos_relations WHERE source_id=?", (entity_id,)
        ).fetchall()
        incoming = conn.execute(
            "SELECT source_id, predicate, confidence FROM kos_relations WHERE target_id=?", (entity_id,)
        ).fetchall()
        conn.close()
        return {
            "entity_id": entity["entity_id"],
            "entity_type": entity["entity_type"],
            "label": entity["label"],
            "description": (entity["description"] or "")[:200],
            "primary_zone": entity["primary_zone"],
            "outgoing_relations": [dict(r) for r in outgoing],
            "incoming_relations": [dict(r) for r in incoming],
        }
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def _load_implicit_connections() -> list[dict]:  # type: ignore[type-arg]
    """Find entities sharing documents but without direct relations."""
    try:
        conn = _get_onto_db()  # type: ignore[no-untyped-call]
        rows = conn.execute("""
            SELECT e1.entity_id as a, e2.entity_id as b, COUNT(*) as shared_docs
            FROM kos_entity_docs e1
            JOIN kos_entity_docs e2 ON e1.doc_id = e2.doc_id AND e1.entity_id < e2.entity_id
            WHERE NOT EXISTS (
                SELECT 1 FROM kos_relations r
                WHERE (r.source_id=e1.entity_id AND r.target_id=e2.entity_id)
                   OR (r.source_id=e2.entity_id AND r.target_id=e1.entity_id)
            )
            GROUP BY 1,2 HAVING shared_docs >= 2
            ORDER BY shared_docs DESC LIMIT 10
        """).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:  # noqa: BLE001
        return []


class EntityListWidget(Static):  # type: ignore[reportPossiblyUnboundVariable]
    """Left panel: scrollable entity list."""

    def __init__(self) -> None:
        super().__init__("Loading entities...")
        self.entities: list[dict] = []
        self.selected_index = 0

    def on_mount(self) -> None:
        self.refresh_entities()

    def refresh_entities(self, filter_text: str = "") -> None:
        self.entities = _load_entities(filter_text)
        if not self.entities:
            self.update("No entities found. Run: kos onto rebuild")
            return
            self.entities = [
                e
                for e in self.entities
                if filter_text.lower() in e["label"].lower() or filter_text.lower() in e["entity_id"].lower()
            ]

        lines = [" Entities " + ("─" * (self.size.width - 10))]
        for i, e in enumerate(self.entities):
            prefix = "→" if i == self.selected_index else " "
            entity_type_map = {"Person": "👤", "Organization": "🏢", "Project": "📋", "Concept": "💡"}
            icon = entity_type_map.get(e.get("entity_type", ""), "•")
            line = f"{prefix} {icon} {e['label']}"
            if len(line) > self.size.width - 2:
                line = line[: self.size.width - 5] + "…"
            lines.append(line)
        self.update("\n".join(lines))

    def move_up(self) -> None:
        if self.entities:
            self.selected_index = (self.selected_index - 1) % len(self.entities)
            self.refresh_entities()

    def move_down(self) -> None:
        if self.entities:
            self.selected_index = (self.selected_index + 1) % len(self.entities)
            self.refresh_entities()

    def get_selected(self) -> dict | None:  # type: ignore[type-arg]
        if self.entities and 0 <= self.selected_index < len(self.entities):
            return self.entities[self.selected_index]
        return None


class EntityDetailWidget(Static):  # type: ignore[reportPossiblyUnboundVariable]
    """Right panel: entity detail with relations."""

    def show_entity(self, entity_id: str) -> None:
        data = _load_entity_detail(entity_id)
        if data.get("error"):
            self.update(f"Error: {data['error']}")
            return

        lines = [f" {data.get('label', entity_id)} ({data.get('entity_type', '')}) "]
        lines.append("─" * (self.size.width - 2))

        desc = data.get("description", "")[:120]
        if desc:
            lines.append(f" {desc}")
            lines.append("")

        # Relations
        outgoing = data.get("outgoing_relations", [])
        incoming = data.get("incoming_relations", [])

        if outgoing:
            lines.append(" ▸ Relations (outgoing):")
            for r in outgoing[:15]:
                pred = r.get("predicate", "related_to")
                target = r.get("target", "")
                lines.append(f"   {pred} → {target}")
            if len(outgoing) > 15:
                lines.append(f"   ... and {len(outgoing) - 15} more")

        if incoming:
            if outgoing:
                lines.append("")
            lines.append(" ▸ Referenced by (incoming):")
            for r in incoming[:10]:
                pred = r.get("predicate", "related_to")
                source = r.get("source", "")
                lines.append(f"   {source} ──{pred}──→")

        # Document zones
        doc_zones = data.get("document_zones", {})
        if doc_zones:
            lines.append("")
            lines.append(" ▸ Document zones:")
            for zone, count in doc_zones.items():
                lines.append(f"   {zone}: {count} docs")

        self.update("\n".join(lines))


class GraphViewWidget(Static):  # type: ignore[reportPossiblyUnboundVariable]
    """Bottom panel: ASCII relation graph centered on the current entity."""

    def show_graph(self, entity_id: str, label: str) -> None:
        data = _load_entity_detail(entity_id)
        if data.get("error"):
            self.update("[No graph data]")
            return

        outgoing = data.get("outgoing_relations", [])
        incoming = data.get("incoming_relations", [])

        lines = [" Relation Graph — " + label + " " + "─" * 20]
        lines.append("")

        # Show as tree: center entity, relations radiating
        for i, r in enumerate(incoming[:8]):
            source = r.get("source", "")[:20]
            pred = r.get("predicate", "related_to")
            prefix = "├──" if i < min(len(incoming), 8) - 1 or outgoing else "└──"
            lines.append(f"  {source} ──{pred}──→ {label}")

        if incoming and outgoing:
            lines.append(f"  {' ' * 20} │")

        lines.append(f"  {' ' * 20} ● {label}")
        lines.append(f"  {' ' * 20} │")

        for i, r in enumerate(outgoing[:8]):
            pred = r.get("predicate", "")
            target = r.get("target", "")[:20]
            prefix = "├──" if i < len(outgoing[:8]) - 1 else "└──"
            lines.append(f"  {' ' * 20} {prefix}──{pred}──→ {target}")

        self.update("\n".join(lines))


class GraphExplorerApp(App):  # type: ignore[type-arg]
    """KOS Knowledge Graph Explorer TUI."""

    CSS_PATH = "styles/kos.css"
    BINDINGS = [
        Binding("j", "move_down", "Down", show=True),  # type: ignore[reportPossiblyUnboundVariable]
        Binding("k", "move_up", "Up", show=True),  # type: ignore[reportPossiblyUnboundVariable]
        Binding("enter", "select_entity", "Detail", show=True),  # type: ignore[reportPossiblyUnboundVariable]
        Binding("s", "search_entity", "Search", show=True),  # type: ignore[reportPossiblyUnboundVariable]
        Binding("p", "find_path", "Path", show=True),  # type: ignore[reportPossiblyUnboundVariable]
        Binding("d", "discover", "Discover", show=True),  # type: ignore[reportPossiblyUnboundVariable]
        Binding("r", "refresh", "Refresh", show=True),  # type: ignore[reportPossiblyUnboundVariable]
        Binding("q", "quit", "Quit", show=True),  # type: ignore[reportPossiblyUnboundVariable]
    ]

    def __init__(self, view: str = "graph") -> None:
        super().__init__()
        self.view = view
        self.current_entity_id = None

    def compose(self) -> ComposeResult:
        yield Header()  # type: ignore[reportPossiblyUnboundVariable]
        with Horizontal():  # type: ignore[reportPossiblyUnboundVariable]
            self.entity_list = EntityListWidget()  # type: ignore[no-untyped-call]
            yield self.entity_list
            self.entity_detail = EntityDetailWidget()
            yield self.entity_detail
        self.graph_panel = GraphViewWidget()
        yield self.graph_panel
        yield Footer()  # type: ignore[reportPossiblyUnboundVariable]

    def on_mount(self) -> None:
        self.title = "KOS Graph Explorer"
        self.entity_list.focus()

    def action_move_down(self) -> None:
        self.entity_list.move_down()  # type: ignore[no-untyped-call]
        self._show_selected()

    def action_move_up(self) -> None:
        self.entity_list.move_up()  # type: ignore[no-untyped-call]
        self._show_selected()

    def action_select_entity(self) -> None:
        self._show_selected(full=True)

    def _show_selected(self, full: bool = False) -> None:
        entity = self.entity_list.get_selected()
        if entity:
            self.current_entity_id = entity["entity_id"]
            self.entity_detail.show_entity(entity["entity_id"])
            if full:
                self.graph_panel.show_graph(entity["entity_id"], entity["label"])
            self.sub_title = f"Entity: {entity['label']}"

    def action_refresh(self) -> None:
        self.entity_list.refresh_entities()
        self._show_selected(full=True)

    def action_search_entity(self) -> None:
        # Simple: just refresh with no filter
        self.entity_list.refresh_entities()
        self.notify("Type to filter entities (not yet implemented)", timeout=2)

    def action_find_path(self) -> None:
        if not self.current_entity_id:
            self.notify("Select an entity first")
            return
        self.notify(f"Path finding from {self.current_entity_id} (enter target ID)")

    def action_discover(self) -> None:
        try:
            data = _run_onto("discover")  # type: ignore[name-defined]
            connections = data.get("implicit_connections", [])
            if connections:
                c = connections[0]
                self.notify(
                    f"Found {len(connections)} implicit connections. Top: {c['entity_a']} ↔ {c['entity_b']} "
                    f"({c['shared_docs']} shared docs)",
                    timeout=5,
                )
            else:
                self.notify("No implicit connections found")
        except Exception:  # noqa: BLE001
            self.notify("Discovery failed")

    def action_quit(self) -> None:
        self.exit()


def main() -> None:
    view = "graph"
    for i, a in enumerate(sys.argv):
        if a == "--view" and i + 1 < len(sys.argv):
            view = sys.argv[i + 1]

    if not TEXTUAL_OK:
        print("Error: textual not installed. Run: pip install textual --break-system-packages")
        sys.exit(1)

    app = GraphExplorerApp(view=view)
    app.run()


if __name__ == "__main__":
    main()  # type: ignore[no-untyped-call]
