"""Governance data providers for cockpit dashboard routes.

Reads OMO state, ecos status, and L4 context from filesystem.
No external dependencies — pure file reading.
"""

from __future__ import annotations

import os
from pathlib import Path

OMO_DIR = Path(os.environ.get("OMO_DIR", str(Path.home() / "Workspace" / ".omo")))
RUNTIME_HOME = Path(os.environ.get("RUNTIME_HOME", str(Path.home() / "runtime")))


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def load_omo_status() -> dict:
    """Load OMO system status from .omo/state/."""
    system = _load_yaml(OMO_DIR / "state" / "system.yaml")
    health = _load_yaml(OMO_DIR / "state" / "system_health.yaml")
    debt = _load_yaml(OMO_DIR / "debt" / "dashboard" / "current.yaml")

    services = health.get("services", {}) if isinstance(health, dict) else {}
    service_list = []
    for name, svc in sorted(services.items()):
        if not isinstance(svc, dict):
            continue
        st = svc.get("health_check") or svc.get("runtime", {}).get("status", "") or "unknown"
        service_list.append({"name": name, "status": st})

    kei_lines = 0
    kei_path = RUNTIME_HOME / "data" / "kei_audit.jsonl"
    if kei_path.exists():
        try:
            kei_lines = len(kei_path.read_text(encoding="utf-8").strip().split("\n"))
        except Exception:
            pass

    return {
        "phase": system.get("current_phase", "?"),
        "health_score": system.get("health_score", "?"),
        "services": service_list,
        "debt": {
            "total": debt.get("total_items", debt.get("total", 0)),
            "open": debt.get("open_items", debt.get("open", 0)),
        },
        "kei_audit_lines": kei_lines,
    }


def load_debt_data() -> dict:
    """Load debt ledger from .omo/debt/."""
    return _load_yaml(OMO_DIR / "debt" / "dashboard" / "current.yaml")


def load_ecos_status() -> dict:
    """Load ecos status from M0 snapshot."""
    m0_path = Path.home() / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m0" / "snapshot.yaml"
    m0 = _load_yaml(m0_path)
    return {
        "m0_snapshot": m0,
        "node_count": len(m0.get("nodes", [])) if isinstance(m0, dict) else 0,
    }


def load_omo_report() -> dict:
    """Generate OMO governance report."""
    system = _load_yaml(OMO_DIR / "state" / "system.yaml")
    return {
        "phase": system.get("current_phase", "?"),
        "health_score": system.get("health_score", "?"),
        "updated": system.get("updated", ""),
    }


def load_e2e_status() -> dict:
    """Load E2E test status (stub)."""
    return {"status": "not_run", "note": "E2E tests require manual trigger via cockpit CLI"}


def load_healing_status() -> dict:
    """Load OMO self-healing engine status."""
    try:
        from omo.omo_self_healing import SelfHealingEngine
        engine = SelfHealingEngine()
        return engine.get_status()
    except Exception as e:
        return {"status": "unavailable", "error": str(e)}


def load_healing_fixes() -> list:
    """List available self-healing fixes."""
    try:
        from omo.omo_self_healing_fixes import list_fixes
        return list_fixes()
    except Exception:
        return []


def load_healing_trends() -> dict:
    """Load self-healing trend data."""
    try:
        from omo.omo_self_healing import SelfHealingEngine
        engine = SelfHealingEngine()
        return engine._trends.get_trends()
    except Exception as e:
        return {"error": str(e)}


def load_ecos_ssb_stats() -> dict:
    """Load SSB database statistics."""
    import sqlite3
    ssb_db = Path.home() / "Workspace" / "data" / "kos" / "ssb.db"
    if not ssb_db.exists():
        return {"error": "DB not found", "total": 0, "signed": 0, "coverage_pct": 0}
    try:
        db = sqlite3.connect(str(ssb_db))
        total = db.execute("SELECT COUNT(*) FROM ssb_events").fetchone()[0]
        signed = db.execute(
            "SELECT COUNT(*) FROM ssb_events WHERE agent_signature IS NOT NULL AND agent_signature != ''"
        ).fetchone()[0]
        max_seq = db.execute("SELECT MAX(seq) FROM ssb_events").fetchone()[0]
        db.close()
        return {
            "total": total,
            "signed": signed,
            "coverage_pct": round(signed / total * 100, 1) if total > 0 else 0,
            "max_seq": max_seq,
        }
    except Exception as e:
        return {"error": str(e), "total": 0}


def load_ecos_watchdog() -> dict:
    """Load watchdog failure data."""
    watchdog_file = Path.home() / ".hermes" / "ecos-watchdog" / "failures.json"
    if not watchdog_file.exists():
        return {"status": "no_data"}
    try:
        import json
        return json.loads(watchdog_file.read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": str(e)}
