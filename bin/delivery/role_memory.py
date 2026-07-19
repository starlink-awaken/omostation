"""G-DEL.4 — role memory share measure (single-repo / gbrain caliber).

Proves:
1. In-process RoleMemoryStore visibility rules
2. Cross-process handoff via shared-context-cli + file store
3. KOS seed + retrieve of shared-context documents
4. Optional gbrain TS tests when node_modules present
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from caliber import stamp_non_physical_goal

ROOT = Path(__file__).resolve().parents[2]
CLI = Path(__file__).resolve().parent / "shared-context-cli.py"


@dataclass
class _Record:
    key: str
    value: str
    writer: str
    written_at: float = field(default_factory=time.time)
    readers: list[str] | None = None


class RoleMemoryStore:
    """In-process shared context (mirrors gbrain visibility rules)."""

    def __init__(self) -> None:
        self._scopes: dict[str, dict[str, _Record]] = {}

    def write(
        self,
        writer: str,
        key: str,
        value: str,
        *,
        scope: str = "default",
        readers: list[str] | None = None,
    ) -> None:
        bucket = self._scopes.setdefault(scope, {})
        bucket[key] = _Record(key=key, value=value, writer=writer, readers=readers)

    def read(self, reader: str, key: str, *, scope: str = "default") -> str | None:
        rec = self._scopes.get(scope, {}).get(key)
        if rec is None:
            return None
        if rec.readers is not None and rec.readers and reader not in rec.readers and reader != rec.writer:
            return None
        # empty readers list or None ⇒ shared to all (align with gbrain: empty = all)
        if rec.readers is not None and len(rec.readers) == 0:
            return rec.value
        if rec.readers is None:
            return rec.value
        if reader == rec.writer or reader in rec.readers:
            return rec.value
        return None


def _cli(args: list[str], *, cwd: Path | None = None) -> dict[str, Any]:
    r = subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    try:
        data = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        data = {"ok": False, "error": "bad_json", "stdout": (r.stdout or "")[:300], "stderr": (r.stderr or "")[:300]}
    data["_returncode"] = r.returncode
    return data


def measure_cross_process_handoff(tmp: Path) -> dict[str, Any]:
    """Agent-A write via CLI → agent-B read in separate process; KOS seed+retrieve."""
    store_root = tmp / "shared-context"
    db = tmp / "kos-index.sqlite"
    scope = "bet-b7da"
    base = ["--root", str(store_root)]

    w = _cli(
        [
            *base,
            "write",
            "--writer",
            "agent-A",
            "--key",
            "collab.handoff",
            "--value",
            "G-DEL.2a contract ready for implementers",
            "--scope",
            scope,
            "--tag",
            "handoff",
        ]
    )
    # private key
    _cli(
        [
            *base,
            "write",
            "--writer",
            "agent-A",
            "--key",
            "secret.notes",
            "--value",
            "private-only",
            "--scope",
            scope,
            "--reader",
            "agent-A",
        ]
    )
    r_ok = _cli(
        [
            *base,
            "read",
            "--reader",
            "agent-B",
            "--key",
            "collab.handoff",
            "--scope",
            scope,
        ]
    )
    r_forbid = _cli(
        [
            *base,
            "read",
            "--reader",
            "agent-B",
            "--key",
            "secret.notes",
            "--scope",
            scope,
        ]
    )
    export = _cli([*base, "export-kos", "--scope", scope, "--db", str(db)])
    hits = _cli(
        ["retrieve-kos", "--query", "collab.handoff", "--db", str(db)]
    )
    share_ok = (
        w.get("ok")
        and r_ok.get("ok")
        and (r_ok.get("record") or {}).get("value") == "G-DEL.2a contract ready for implementers"
    )
    isolation_ok = r_forbid.get("ok") is False or r_forbid.get("_returncode") != 0
    kos_ok = bool(export.get("ok")) and bool(hits.get("n", 0) >= 1)
    return {
        "share_ok": bool(share_ok),
        "isolation_ok": bool(isolation_ok),
        "kos_export_ok": bool(export.get("ok")),
        "kos_retrieve_ok": kos_ok,
        "export": {k: export.get(k) for k in ("upserted", "total_documents", "db") if k in export},
        "hits_n": hits.get("n"),
        "ok": bool(share_ok and isolation_ok and kos_ok),
    }


def measure_role_memory_share() -> dict[str, Any]:
    store = RoleMemoryStore()
    store.write("agent-A", "collab.handoff", "G-DEL.2a ready", scope="bet-b7da")
    store.write(
        "agent-A",
        "secret.notes",
        "private",
        scope="bet-b7da",
        readers=["agent-A"],
    )
    visible = store.read("agent-B", "collab.handoff", scope="bet-b7da")
    hidden = store.read("agent-B", "secret.notes", scope="bet-b7da")
    self_ok = store.read("agent-A", "secret.notes", scope="bet-b7da") == "private"
    inproc_share = visible == "G-DEL.2a ready"
    inproc_isolation = hidden is None and self_ok

    with tempfile.TemporaryDirectory(prefix="gdel4-") as td:
        cross = measure_cross_process_handoff(Path(td))

    gbrain = ROOT / "projects" / "gbrain"
    gbrain_test: dict[str, Any] = {"ran": False, "skipped": True}
    test_file = gbrain / "test" / "agent-shared-context.test.ts"
    node_modules = gbrain / "node_modules"
    if test_file.is_file() and node_modules.is_dir():
        r = subprocess.run(
            ["bun", "test", "test/agent-shared-context.test.ts"],
            cwd=str(gbrain),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        gbrain_test = {
            "ran": True,
            "skipped": False,
            "returncode": r.returncode,
            "pass": r.returncode == 0,
            "stdout_tail": (r.stdout or "")[-400:],
        }
    elif test_file.is_file():
        gbrain_test = {
            "ran": False,
            "skipped": True,
            "reason": "gbrain node_modules missing; source present",
            "source": "projects/gbrain/src/core/agent-shared-context.ts",
        }

    ok = inproc_share and inproc_isolation and cross.get("ok") is True
    return stamp_non_physical_goal(
        {
            "gate": "G-DEL.4",
            "kpi": (
                "cross-agent shared context R/W + isolation; "
                "cross-process CLI handoff; KOS seed/retrieve"
            ),
            "env": "file store .omo/_delivery/shared-context + optional gbrain TS",
            "env_class": "in-process_simulation",
            "caliber": "single_repo_gbrain",
            "in_process": {
                "share_ok": inproc_share,
                "isolation_ok": inproc_isolation,
            },
            "cross_process": cross,
            "gbrain_test": gbrain_test,
            "gbrain_source_present": (
                gbrain / "src/core/agent-shared-context.ts"
            ).is_file(),
            "cli": str(CLI.relative_to(ROOT)) if CLI.is_file() else None,
            "callchain": [
                "agent-A → shared-context-cli write",
                "file store .omo/_delivery/shared-context/{scope}/{key}.json",
                "agent-B → shared-context-cli read",
                "export-kos → kos/kos-index.sqlite documents",
                "retrieve-kos LIKE query",
            ],
        },
        ok=ok,
    )


if __name__ == "__main__":
    print(json.dumps(measure_role_memory_share(), indent=2, ensure_ascii=False))
