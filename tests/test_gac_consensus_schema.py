"""Schema-tolerant KOS consensus inject helpers (DEBT-L0 triage)."""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC = REPO / "bin" / "gac" / "gac-consensus-inject.py"


def _load():
    spec = importlib.util.spec_from_file_location("gci", SPEC)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_ensure_entity_type_column(tmp_path) -> None:
    gci = _load()
    db = tmp_path / "kos.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE kos_entities (entity_id TEXT, label TEXT, source_file TEXT)"
    )
    conn.execute(
        "INSERT INTO kos_entities VALUES (\'consensus-1\', \'Consensus gene\', \'x.md\')"
    )
    conn.commit()
    gci._ensure_entity_type_column(conn)
    cols = gci._kos_entity_columns(conn)
    assert "entity_type" in cols
    rows = gci._select_consensus_entities(conn, full=False)
    assert len(rows) >= 1
    conn.close()


def test_fallback_without_entity_type(tmp_path) -> None:
    gci = _load()
    db = tmp_path / "kos2.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE kos_entities (entity_id TEXT, label TEXT, source_file TEXT)"
    )
    conn.execute(
        "INSERT INTO kos_entities VALUES (\'other-1\', \'normal\', \'y.md\')"
    )
    conn.execute(
        "INSERT INTO kos_entities VALUES (\'p74-consensus\', \'Consensus pattern\', \'z.md\')"
    )
    conn.commit()
    rows = gci._select_consensus_entities(conn, full=True)
    assert any("consensus" in (r[0] or "").lower() for r in rows)
    conn.close()
