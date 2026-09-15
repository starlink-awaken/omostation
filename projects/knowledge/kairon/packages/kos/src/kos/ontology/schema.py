#!/usr/bin/env python3
# ruff: noqa
"""KOS Ontology Schema — db 连接 + 表结构 + 模式常量 + manifest 配置.

从 ontology/engine.py 抽出 (God Module 拆分第一步, engine.py 1474->~1294).
engine.py 通过 re-export 保持 API (外部 import ontology.engine.get_db 不变).
"""

import re
import sqlite3
from pathlib import Path
from typing import Any, cast

from kos.config import (  # type: ignore[unused-ignore, import-not-found]
    get_artifact_path,
    get_workspace_manifest,
)

# ── Patterns ─────────────────────────────────────────────

PREDICATE_RE = re.compile(r"(\w+)::\[\[([^\]]+)\]\]")
ENTITY_REF_RE = re.compile(
    r"\[(person|org|project|regulation|doc|concept|event|role|axiom|principle|theory|framework|skill|consensus|task|node)-([\w-]+)\]",
    re.IGNORECASE,
)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
MD_HEADING_RE = re.compile(r"^###\s+(.+)", re.MULTILINE)
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(#([^)]+)\)")
MD_TAG_RE = re.compile(r"#(\w[\w/-]*)")

# ── Manifest-driven configuration (lazy) ────────────────
# These are computed at first call, not import time, so the module
# can be imported without a fully configured workspace.

_MANIFEST = None


def _manifest() -> dict[str, Any]:  # type: ignore[no-untyped-def]
    global _MANIFEST
    if _MANIFEST is None:
        _MANIFEST = get_workspace_manifest()
    return cast("dict[str, Any]", _MANIFEST)


def _entity_sources() -> list[str]:  # type: ignore[no-untyped-def]
    sources = _manifest().get("entitySources", [])
    if not sources:
        raise RuntimeError(
            "manifest 'entitySources' is empty or missing. "
            "Run 'kos init' to scaffold a workspace, or add entitySources to your manifest."
        )
    return cast("list[str]", sources)


def entity_files() -> list[str]:  # type: ignore[no-untyped-def]
    return _entity_sources()


def cross_domain_file() -> str:  # type: ignore[no-untyped-def]
    return _entity_sources()[0]


PREFIX_LIST = [
    "person-",
    "org-",
    "project-",
    "regulation-",
    "doc-",
    "concept-",
    "role-",
    "axiom-",
    "principle-",
    "theory-",
    "framework-",
    "skill-",
    "consensus-",
    "task-",
]

_PREDICATE_PATTERNS = None


def _predicate_patterns() -> dict[str, list[str]]:  # type: ignore[no-untyped-def]
    """Load predicate patterns from manifest, merging all language sets."""
    global _PREDICATE_PATTERNS
    if _PREDICATE_PATTERNS is not None:
        return _PREDICATE_PATTERNS
    configured = _manifest().get("predicatePatterns", {})
    if not configured:
        raise RuntimeError(
            "manifest 'predicatePatterns' is empty or missing. "
            "Run 'kos init' to scaffold a workspace, or add predicatePatterns to your manifest."
        )
    merged: dict[str, Any] = {}
    for lang_patterns in configured.values():
        for predicate, patterns in lang_patterns.items():
            merged.setdefault(predicate, []).extend(patterns)
    _PREDICATE_PATTERNS = merged
    return merged


TYPE_MAP = {
    "person": "Person",
    "people": "Person",
    "org": "Organization",
    "organization": "Organization",
    "project": "Project",
    "regulation": "Regulation",
    "doc": "Document",
    "document": "Document",
    "concept": "Concept",
    "event": "Event",
    "role": "Role",
    "axiom": "Axiom",
    "principle": "Principle",
    "theory": "Theory",
    "framework": "Framework",
    "skill": "Skill",
    "consensus": "Consensus",
    "task": "Task",
}

KNOWN_PREDICATES = [
    "works_at",
    "seconded_to",
    "reports_to",
    "works_on",
    "described_in",
    "derived_from",
    "related_to",
    "conforms_to",
    "depends_on",
    "triggers",
    "member_of",
    "manages",
    "belongs_to",
    "applied_in",
]


def get_db() -> sqlite3.Connection:  # type: ignore[no-untyped-def]
    path = Path(get_artifact_path("retrievalDatabase"))
    if not path.exists():
        raise FileNotFoundError(f"Retrieval DB not found: {path}")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def init_schema(conn) -> None:  # type: ignore[no-untyped-def]
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS kos_entities (
            entity_id   TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            label       TEXT NOT NULL,
            aliases     TEXT,
            description TEXT,
            primary_zone TEXT,
            source_file TEXT,
            metadata    TEXT,
            updated_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS kos_relations (
            source_id   TEXT,
            predicate   TEXT,
            target_id   TEXT,
            confidence  REAL DEFAULT 1.0,
            source_doc  TEXT,
            source_type TEXT DEFAULT 'manual',
            updated_at  TEXT,
            PRIMARY KEY (source_id, predicate, target_id)
        );
        CREATE TABLE IF NOT EXISTS kos_entity_docs (
            entity_id TEXT,
            doc_id    TEXT,
            relevance REAL DEFAULT 0.5,
            PRIMARY KEY (entity_id, doc_id)
        );
        CREATE TABLE IF NOT EXISTS kos_ontology_meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_kos_rel_src ON kos_relations(source_id);
        CREATE INDEX IF NOT EXISTS idx_kos_rel_tgt ON kos_relations(target_id);
        CREATE INDEX IF NOT EXISTS idx_kos_ent_doc ON kos_entity_docs(entity_id);
    """)
