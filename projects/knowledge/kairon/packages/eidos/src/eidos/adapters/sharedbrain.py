"""SharedBrain → Eidos ontology adapter — deep integration layer.

Reads SharedBrain organ data directly from storage (SQLite DBs, JSON files)
and converts to Eidos-compatible types (KnowledgeCard, Fact, OntologyNode).

Design principles:
- Zero dependency on SharedBrain/nucleus runtime — reads data files directly
- Returns plain dicts (not Eidos objects) for loose coupling
- Path-aware: accepts optional SharedBrain root path at call time
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any, cast

_log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# Organ → MetaType mapping (from AGENTS.md governance)
# ──────────────────────────────────────────────────────────────────────
ORGAN_MAP: dict[str, str] = {
    "D_Memory": "document",
    "D_KnowledgeIntegration": "domain",
    "D_Intelligence": "inference",
    "D_Monitoring": "state",
    "D_Continuity": "state",
    "D_Immunity": "state",
    "D_Logos": "domain",
    "D_Genesis": "domain",
    "D_Harvest": "domain",
    "D_Economy": "domain",
    "D_Gateway": "processor",
    "D_Execution": "processor",
    "D_Extension": "processor",
    "D_Cloud": "domain",
    "D_Voice": "processor",
    "D_Window": "processor",
    "D_Harness": "processor",
    "D_Governance": "constraint",
}

# Alternative naming with hyphens (SharedBrain uses both dash and underscore)
ORGAN_ALIASES: dict[str, str] = {
    "D-Memory": "D_Memory",
    "D-KnowledgeIntegration": "D_KnowledgeIntegration",
    "D-Intelligence": "D_Intelligence",
    "D-Monitoring": "D_Monitoring",
    "D-Continuity": "D_Continuity",
    "D-Immunity": "D_Immunity",
    "D-Logos": "D_Logos",
    "D-Genesis": "D_Genesis",
    "D-Harvest": "D_Harvest",
    "D-Economy": "D_Economy",
    "D-Gateway": "D_Gateway",
    "D-Execution": "D_Execution",
    "D-Extension": "D_Extension",
    "D-Cloud": "D_Cloud",
    "D-Voice": "D_Voice",
    "D-Window": "D_Window",
    "D-Harness": "D_Harness",
    "D-Governance": "D_Governance",
}


def _normalize_organ_name(name: str) -> str:
    """Resolve hyphenated organ names to underscore form."""
    if name in ORGAN_ALIASES:
        return ORGAN_ALIASES[name]
    return name


def organ_to_meta_type(organ_name: str) -> str:
    """Map an SharedBrain organ name to an Eidos MetaType value."""
    name = _normalize_organ_name(organ_name)
    return ORGAN_MAP.get(name, "domain")


def list_available_organs() -> list[dict]:
    """List all known organs and their mapped Eidos MetaType."""
    return [{"organ": k, "meta_type": v} for k, v in ORGAN_MAP.items()]


# ──────────────────────────────────────────────────────────────────────
# SharedBrain file system discovery
# ──────────────────────────────────────────────────────────────────────


def find_sharedbrain_root() -> str | None:
    """Discover the SharedBrain project root from common locations."""
    candidates = [
        os.environ.get("SHAREDBRAIN_ROOT", ""),
        os.path.expanduser("~/Workspace/SharedBrain"),
        os.path.expanduser("../SharedBrain"),
    ]
    for path in candidates:
        if path and (Path(path) / "AGENTS.md").exists():
            return path
    return None


def get_organ_path(organ_name: str, sharedbrain_root: str | None = None) -> str | None:
    """Resolve the filesystem path for a given organ."""
    root = sharedbrain_root or find_sharedbrain_root()
    if not root:
        return None
    name = _normalize_organ_name(organ_name)
    # Try underscore form first, then hyphen form
    for candidate in [name, name.replace("_", "-")]:
        p = Path(root) / "organs" / candidate
        if p.is_dir():
            return str(p)
    return None


def discover_organs_on_disk(sharedbrain_root: str | None = None) -> list[dict]:
    """Scan the SharedBrain organs directory and return found organs."""
    root = sharedbrain_root or find_sharedbrain_root()
    if not root:
        return []
    organs_dir = Path(root) / "organs"
    if not organs_dir.is_dir():
        return []

    results: list[dict] = []
    for entry in sorted(organs_dir.iterdir()):
        if entry.is_dir() and entry.name.startswith("D_"):
            results.append(
                {
                    "name": entry.name,
                    "path": str(entry),
                    "meta_type": organ_to_meta_type(entry.name),
                }
            )
    return results


# ──────────────────────────────────────────────────────────────────────
# Data readers — read SharedBrain storage into raw dicts
# ──────────────────────────────────────────────────────────────────────


def read_sqlite_tables(db_path: str) -> dict[str, list[dict]]:
    """Read all tables from a SQLite database into lists of dicts.

    Returns dict of {table_name: [row_dict, ...]}.  Empty dict on error.
    """
    result: dict[str, list[dict]] = {}
    if not os.path.isfile(db_path):
        _log.debug("SQLite DB not found: %s", db_path)
        return result

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row["name"] for row in cursor.fetchall()]

        for table in tables:
            cursor.execute(f"SELECT * FROM [{table}]")
            rows = [dict(row) for row in cursor.fetchall()]
            if rows:
                result[table] = rows

        conn.close()
    except (sqlite3.Error, OSError, RuntimeError) as exc:
        _log.warning("Failed to read SQLite DB %s: %s", db_path, exc)

    return result


def read_json_file(file_path: str) -> dict | list | None:
    """Read a JSON file and return parsed data.

    Returns None if file doesn't exist or is not valid JSON.
    """
    if not os.path.isfile(file_path):
        return None
    try:
        with open(file_path, encoding="utf-8") as f:
            return cast("dict[Any, Any] | list[Any] | None", json.load(f))
    except (json.JSONDecodeError, OSError, RuntimeError) as exc:
        _log.warning("Failed to read JSON %s: %s", file_path, exc)
        return None


def read_organ_data(organ_name: str, sharedbrain_root: str | None = None) -> dict[str, Any]:
    """Read all discoverable data from an SharedBrain organ.

    Returns a dict with keys:
      - ``organ_name``: the resolved name
      - ``organ_path``: filesystem path (or None)
      - ``meta_type``: Eidos MetaType value
      - ``found``: dict of {source_type: list_of_dicts} for all data found
      - ``json_files``: list of raw JSON file contents (keyed by filename stem)
    """
    name = _normalize_organ_name(organ_name)
    organ_path = get_organ_path(name, sharedbrain_root)
    result: dict[str, Any] = {
        "organ_name": name,
        "organ_path": organ_path,
        "meta_type": organ_to_meta_type(name),
        "found": {},
        "json_files": {},
    }

    if not organ_path:
        return result

    base = Path(organ_path)
    data_dir = base / "data"

    # 1. SQLite databases in data/
    if data_dir.is_dir():
        for db_file in data_dir.glob("*.db"):
            tables = read_sqlite_tables(str(db_file))
            if tables:
                result["found"][f"sqlite:{db_file.name}"] = tables

        # Also check .db-wal / .db-shm primary
        for db_file in data_dir.glob("*.db-wal"):
            stem = db_file.stem.replace(".db-wal", "").replace(".db", "")
            primary = data_dir / f"{stem}.db"
            if not primary.exists():
                # WAL without primary — skip
                continue

        # 2. JSON files in data/
        for json_file in sorted(data_dir.glob("*.json")):
            data = read_json_file(str(json_file))
            if data is not None:
                result["json_files"][json_file.stem] = data

    # 3. Schema SQL files
    schema_dir = data_dir / "schema" if data_dir.is_dir() else base / "schema"
    if schema_dir.is_dir():
        schemas: dict[str, str] = {}
        for sql_file in sorted(schema_dir.glob("*.sql")):
            try:
                schemas[sql_file.stem] = sql_file.read_text(encoding="utf-8")
            except OSError as exc:
                _log.warning("Failed to read schema %s: %s", sql_file, exc)
        if schemas:
            result["found"]["schemas"] = schemas

    return result


# ──────────────────────────────────────────────────────────────────────
# Conversion — SharedBrain data → Eidos-compatible dicts
# ──────────────────────────────────────────────────────────────────────


def organ_to_knowledge_cards(organ_name: str, organ_data: dict[str, Any]) -> list[dict]:
    """Convert SharedBrain organ data into Eidos KnowledgeCard-like dicts.

    Each card contains: id, title, content, source, source_type, schema_type, tags, relations.
    """
    cards: list[dict] = []
    name = _normalize_organ_name(organ_name)

    # 1) SQLite table rows → KnowledgeCards
    for source_key, tables in organ_data.get("found", {}).items():
        if not source_key.startswith("sqlite:"):
            continue
        db_name = source_key.replace("sqlite:", "")
        for table_name, rows in tables.items():
            for row in rows:
                card = _sqlite_row_to_card(name, db_name, table_name, row)
                if card:
                    cards.append(card)

    # 2) JSON files → KnowledgeCards
    for stem, data in organ_data.get("json_files", {}).items():
        card = _json_file_to_card(name, stem, data)
        if card:
            cards.append(card)

    return cards


def _sqlite_row_to_card(organ_name: str, db_name: str, table_name: str, row: dict) -> dict | None:
    """Convert a single SQLite row to a KnowledgeCard dict."""
    # Find a title/name field
    title = (
        row.get("title")
        or row.get("name")
        or row.get("memory_id")
        or row.get("role_id")
        or row.get("pattern_id")
        or f"{table_name}:{row.get('id', hash(str(row)))}"
    )

    # Find content — prefer content/text fields, then JSON fields, then full row
    content = (
        row.get("content")
        or row.get("experience")
        or row.get("definition_json")
        or row.get("facts_json")
        or json.dumps(row, ensure_ascii=False, default=str)
    )

    # Extract relations if available
    relations: list[dict] = []
    if "subject" in row and "predicate" in row:
        relations.append(
            {
                "target_id": str(row.get("object", "")),
                "relation_type": str(row.get("predicate", "")),
                "label": str(row.get("predicate", "")),
            }
        )
    if "from_role" in row and "to_role" in row:
        relations.append(
            {
                "target_id": str(row.get("to_role", "")),
                "relation_type": str(row.get("relationship_type", "relates_to")),
                "label": str(row.get("relationship_type", "relates_to")),
            }
        )

    # Tags from various sources
    tags: list[str] = [table_name, organ_name]
    if row.get("type"):
        tags.append(str(row["type"]))
    if row.get("category"):
        tags.append(str(row["category"]))
    if row.get("status"):
        tags.append(str(row["status"]))
    if row.get("tags"):
        raw = row["tags"]
        if isinstance(raw, str):
            tags.extend(t.strip() for t in raw.split(",") if t.strip())
        elif isinstance(raw, list):
            tags.extend(t for t in raw if isinstance(t, str))

    card_id = (
        row.get("id")
        or row.get("memory_id")
        or row.get("knowledge_id")
        or row.get("pattern_id")
        or row.get("role_id")
        or f"{organ_name}_{table_name}_{hash(str(row))}"
    )

    return {
        "id": str(card_id),
        "title": str(title),
        "content": str(content)[:10000],  # cap at 10k chars
        "source": f"sharedbrain://{organ_name}/{db_name}/{table_name}",
        "source_type": f"sharedbrain-{organ_name}",
        "schema_type": organ_to_meta_type(organ_name),
        "tags": tags,
        "relations": relations,
        "metadata": {"row_keys": list(row.keys())},
    }


def _json_file_to_card(organ_name: str, stem: str, data: dict | list) -> dict | None:
    """Convert a JSON file to a KnowledgeCard dict."""
    if isinstance(data, dict):
        title = data.get("title") or data.get("name") or stem
        content = data.get("description") or data.get("intent") or json.dumps(data, ensure_ascii=False, default=str)
        tags = [organ_name, stem]
        if isinstance(data.get("status"), str):
            tags.append(data["status"])
        return {
            "id": f"{organ_name}_{stem}",
            "title": str(title),
            "content": str(content)[:10000],
            "source": f"sharedbrain://{organ_name}/json/{stem}",
            "source_type": f"sharedbrain-{organ_name}",
            "schema_type": organ_to_meta_type(organ_name),
            "tags": tags,
            "relations": [],
        }

    if isinstance(data, list):
        return {
            "id": f"{organ_name}_{stem}",
            "title": stem,
            "content": json.dumps(data, ensure_ascii=False, default=str)[:10000],
            "source": f"sharedbrain://{organ_name}/json/{stem}",
            "source_type": f"sharedbrain-{organ_name}",
            "schema_type": organ_to_meta_type(organ_name),
            "tags": [organ_name, stem],
            "relations": [],
        }

    return None


def _extract_nested_tasks_from_json(organ_name: str, stem: str, data: dict, facts: list[dict]) -> None:
    """Recursively extract task-related facts from nested JSON structures.

    Handles structures like:
      {"active_tasks": {"TASK_001": {"name": "...", "status": "...", ...}}}
      {"strategic_backlog": [{"id": "TSK-601", "title": "...", "status": "...", ...}]}
    """
    for task_key, task_data in data.items():
        # Direct task dict (name/status at top level)
        if isinstance(task_data, dict) and "name" in task_data:
            facts.append(
                {
                    "id": f"task_{organ_name}_{stem}_{task_key}",
                    "subject": f"task:{task_data.get('name', task_key)}",
                    "predicate": "has_status",
                    "object": str(task_data.get("status", "unknown")),
                    "confidence": 1.0,
                    "source_card_id": f"{organ_name}_json_{stem}",
                }
            )
            if task_data.get("assigned_to"):
                facts.append(
                    {
                        "id": f"assign_{organ_name}_{stem}_{task_key}",
                        "subject": f"task:{task_data.get('name', task_key)}",
                        "predicate": "assigned_to",
                        "object": str(task_data["assigned_to"]),
                        "confidence": 1.0,
                        "source_card_id": f"{organ_name}_json_{stem}",
                    }
                )

        # Nested group (active_tasks → {id: task_dict})
        elif isinstance(task_data, dict):
            for nested_key, nested_val in task_data.items():
                if isinstance(nested_val, dict) and "name" in nested_val:
                    facts.append(
                        {
                            "id": f"task_{organ_name}_{stem}_{nested_key}",
                            "subject": f"task:{nested_val.get('name', nested_key)}",
                            "predicate": "has_status",
                            "object": str(nested_val.get("status", "unknown")),
                            "confidence": 1.0,
                            "source_card_id": f"{organ_name}_json_{stem}",
                        }
                    )
                    if nested_val.get("assigned_to"):
                        facts.append(
                            {
                                "id": f"assign_{organ_name}_{stem}_{nested_key}",
                                "subject": f"task:{nested_val.get('name', nested_key)}",
                                "predicate": "assigned_to",
                                "object": str(nested_val["assigned_to"]),
                                "confidence": 1.0,
                                "source_card_id": f"{organ_name}_json_{stem}",
                            }
                        )

        # Array of task objects
        elif isinstance(task_data, list):
            for item in task_data:
                if isinstance(item, dict):
                    item_id = item.get("id") or item.get("title") or str(hash(str(item)))
                    if item.get("title"):
                        facts.append(
                            {
                                "id": f"task_{organ_name}_{stem}_{item_id}",
                                "subject": f"task:{item.get('title', item_id)}",
                                "predicate": "has_status",
                                "object": str(item.get("status", "unknown")),
                                "confidence": 1.0,
                                "source_card_id": f"{organ_name}_json_{stem}",
                            }
                        )


def organ_to_facts(organ_name: str, organ_data: dict[str, Any]) -> list[dict]:
    """Extract subject-predicate-object facts from SharedBrain organ data.

    Returns list of Eidos Fact-compatible dicts (id, subject, predicate, object, confidence).
    """
    facts: list[dict] = []
    name = _normalize_organ_name(organ_name)

    for source_key, tables in organ_data.get("found", {}).items():
        if not source_key.startswith("sqlite:"):
            continue
        db_name = source_key.replace("sqlite:", "")

        for table_name, rows in tables.items():
            for row in rows:
                # Direct fact_triple-like tables
                if "subject" in row and "predicate" in row:
                    facts.append(
                        {
                            "id": row.get("id") or f"fact_{name}_{table_name}_{hash(str(row))}",
                            "subject": str(row.get("subject", "")),
                            "predicate": str(row.get("predicate", "")),
                            "object": str(row.get("object", "")),
                            "confidence": float(row.get("confidence", 1.0) or 1.0),
                            "source_card_id": f"{name}_{db_name}_{table_name}",
                        }
                    )
                # Role relationships
                elif "from_role" in row and "to_role" in row:
                    facts.append(
                        {
                            "id": f"rel_{row.get('id', hash(str(row)))}",
                            "subject": f"role:{row['from_role']}",
                            "predicate": str(row.get("relationship_type", "relates_to")),
                            "object": f"role:{row['to_role']}",
                            "confidence": float(row.get("trust_level", 0.5)),
                            "source_card_id": f"{name}_{db_name}_{table_name}",
                        }
                    )
                # Pattern facts (stored as JSON)
                if "facts_json" in row and row["facts_json"]:
                    try:
                        pattern_facts = json.loads(row["facts_json"])
                        if isinstance(pattern_facts, list):
                            for i, pf in enumerate(pattern_facts):
                                if isinstance(pf, (list, tuple)) and len(pf) >= 3:
                                    facts.append(
                                        {
                                            "id": f"pf_{row.get('pattern_id', hash(str(row)))}_{i}",
                                            "subject": str(pf[0]),
                                            "predicate": str(pf[1]),
                                            "object": str(pf[2]),
                                            "confidence": float(row.get("confidence", 0.7)),
                                            "source_card_id": f"{name}_{db_name}_{table_name}",
                                        }
                                    )
                    except (json.JSONDecodeError, TypeError):
                        pass

    # JSON-derived facts
    for stem, data in organ_data.get("json_files", {}).items():
        if isinstance(data, dict):
            _extract_nested_tasks_from_json(name, stem, data, facts)

    return facts


def organ_to_ontology_nodes(organ_name: str, organ_data: dict[str, Any]) -> list[dict]:
    """Generate Eidos OntologyNode dicts describing an organ's structure."""
    name = _normalize_organ_name(organ_name)
    meta_type = organ_to_meta_type(name)
    path = organ_data.get("organ_path", "")

    nodes: list[dict] = []

    # Root organ node
    nodes.append(
        {
            "id": f"organ_{name}",
            "name": name,
            "node_type": meta_type,
            "parent": "sharedbrain",
            "properties": {"path": path, "meta_type": meta_type},
            "aliases": [name.replace("_", "-")],
            "description": f"SharedBrain organ: {name}",
        }
    )

    # Table-level nodes
    for source_key, tables in organ_data.get("found", {}).items():
        if not source_key.startswith("sqlite:"):
            continue
        db_name = source_key.replace("sqlite:", "")
        for table_name in tables:
            child_id = f"table_{name}_{db_name}_{table_name}"
            nodes.append(
                {
                    "id": child_id,
                    "name": f"{table_name} ({db_name})",
                    "node_type": "dataset",
                    "parent": f"organ_{name}",
                    "properties": {"db": db_name, "table": table_name},
                    "aliases": [],
                    "description": f"SQLite table {table_name} in {db_name}",
                }
            )

    # JSON file nodes
    for stem in organ_data.get("json_files", {}):
        child_id = f"json_{name}_{stem}"
        nodes.append(
            {
                "id": child_id,
                "name": f"{stem}.json",
                "node_type": "dataset",
                "parent": f"organ_{name}",
                "properties": {"file": f"{stem}.json"},
                "aliases": [],
                "description": f"JSON data file: {stem}.json",
            }
        )

    return nodes


# ──────────────────────────────────────────────────────────────────────
# Public API — batch processing
# ──────────────────────────────────────────────────────────────────────


def batch_import_organs(
    organ_names: list[str] | None = None,
    sharedbrain_root: str | None = None,
) -> dict[str, Any]:
    """Process all (or selected) SharedBrain organs into Eidos-compatible dicts.

    Args:
        organ_names: List of organ names to process.  If None, discovers all on disk.
        sharedbrain_root: Optional explicit path to SharedBrain root.

    Returns:
        dict with keys:
          - ``cards``: list of KnowledgeCard dicts
          - ``facts``: list of Fact dicts
          - ``nodes``: list of OntologyNode dicts
          - ``organs``: list of organ metadata dicts
          - ``summary``: per-organ statistics
    """
    if organ_names is None:
        discovered = discover_organs_on_disk(sharedbrain_root)
        organ_names = [d["name"] for d in discovered]

    all_cards: list[dict] = []
    all_facts: list[dict] = []
    all_nodes: list[dict] = []
    summary: dict[str, dict[str, Any]] = {}

    for name in organ_names:
        data = read_organ_data(name, sharedbrain_root)
        resolved_name = data.get("organ_name", name)
        cards = organ_to_knowledge_cards(name, data)
        facts = organ_to_facts(name, data)
        nodes = organ_to_ontology_nodes(name, data)

        all_cards.extend(cards)
        all_facts.extend(facts)
        all_nodes.extend(nodes)

        summary[resolved_name] = {
            "cards": len(cards),
            "facts": len(facts),
            "nodes": len(nodes),
            "path": str(data.get("organ_path", "")),
            "meta_type": data.get("meta_type", "domain"),
        }

    return {
        "cards": all_cards,
        "facts": all_facts,
        "nodes": all_nodes,
        "organs": discover_organs_on_disk(sharedbrain_root),
        "summary": summary,
    }


# ── B3a: Batch organ sync (added by Phase B3a) ─────────────────────────────

import hashlib

_log = logging.getLogger(__name__)

SHAREDBRAIN_ORGANS = Path(
    __import__("os").environ.get(
        "SHAREDBRAIN_ORGANS",
        str(Path.home() / "Workspace" / "projects" / "SharedBrain" / "organs"),
    )
)


def get_active_organs() -> list[dict[str, Any]]:
    organs: list[dict[str, Any]] = []
    if not SHAREDBRAIN_ORGANS.exists():
        return organs
    for organ_dir in sorted(SHAREDBRAIN_ORGANS.iterdir()):
        if not organ_dir.is_dir() or not organ_dir.name.startswith("D-"):
            continue
        status_file = organ_dir / ".organ_status"
        status = status_file.read_text().strip() if status_file.exists() else "active"
        organs.append({"name": organ_dir.name, "status": status, "path": str(organ_dir)})
    return organs


def compute_organ_sha256(organs: list[dict[str, Any]]) -> str:
    raw = json.dumps(organs, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


def batch_organs_to_kos_index(kos_index_path: str | Path = "kos_entities") -> dict[str, Any]:
    organs = get_active_organs()
    fingerprint = compute_organ_sha256(organs)
    index_path = Path(kos_index_path)
    index_path.mkdir(parents=True, exist_ok=True)

    entities = []
    for organ in organs:
        entity = {
            "id": f"sharedbrain/{organ['name']}",
            "type": "organ",
            "name": organ["name"],
            "status": organ["status"],
            "source": "sharedbrain",
            "attributes": {"status": organ["status"], "path": organ["path"]},
        }
        entities.append(entity)
        (index_path / f"{organ['name']}.json").write_text(json.dumps(entity, indent=2, ensure_ascii=False))

    manifest = {
        "_fingerprint": fingerprint,
        "_count": len(entities),
        "_updated": __import__("datetime").datetime.now().isoformat(),
        "entities": entities,
    }
    (index_path / "_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    status_counts: dict[str, int] = {}
    for e in entities:
        s = e["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    return {
        "total_organs": len(organs),
        "total_entities": len(entities),
        "fingerprint": fingerprint,
        "status_counts": status_counts,
    }


def sync_incremental(kos_index_path: str | Path = "kos_entities") -> dict[str, Any]:
    index_path = Path(kos_index_path)
    manifest_file = index_path / "_manifest.json"
    current_organs = get_active_organs()
    current_fp = compute_organ_sha256(current_organs)

    previous_fp = None
    if manifest_file.exists():
        try:
            previous_fp = json.loads(manifest_file.read_text()).get("_fingerprint")
        except (json.JSONDecodeError, KeyError):
            pass

    if previous_fp == current_fp:
        _log.info("Organ state unchanged — skipping sync")
        return {"synced": False, "reason": "no_change"}

    _log.info("Organ state changed — re-indexing")
    return {"synced": True, **batch_organs_to_kos_index(kos_index_path)}


def organ_identity_to_agent_registry(agent_registry_path: str | Path = "agent_registry") -> dict[str, Any]:
    identity_bridge_path = (
        Path(
            __import__("os").environ.get(
                "SHAREDBRAIN_DATA",
                str(Path.home() / "Workspace" / "projects" / "SharedBrain" / "data"),
            )
        )
        / "identity"
        / "bridge_registry.json"
    )

    if not identity_bridge_path.exists():
        return {"total_agents": 0, "error": "identity_bridge not found"}

    try:
        bridge_data = json.loads(identity_bridge_path.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return {"total_agents": 0, "error": "invalid identity_bridge data"}

    registry_path = Path(agent_registry_path)
    registry_path.mkdir(parents=True, exist_ok=True)

    agents = bridge_data.get("agents", [])
    for agent in agents:
        agent_file = registry_path / f"{agent.get('agent_id', 'unknown')}.json"
        agent_file.write_text(json.dumps(agent, indent=2, ensure_ascii=False))

    return {"total_agents": len(agents), "registry_path": str(registry_path)}
