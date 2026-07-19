"""G-DEL.4 — role memory share measure (single-repo / gbrain caliber).

Does not claim multi-host. Optionally exercises gbrain AgentSharedContextStore
via a thin Node/Bun test subprocess when gbrain is present; otherwise runs a
pure-Python in-process store that mirrors the same R/W contract for root CI.
"""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from caliber import stamp_non_physical_goal


@dataclass
class _Record:
    key: str
    value: str
    writer: str
    written_at: float = field(default_factory=time.time)
    readers: list[str] | None = None  # None = all agents


class RoleMemoryStore:
    """Process-local shared context (caliber: single_repo_gbrain / process_local)."""

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
        if rec.readers is not None and reader not in rec.readers and reader != rec.writer:
            return None
        return rec.value


def measure_role_memory_share() -> dict[str, Any]:
    """Cross-agent write visibility + private isolation (process-local caliber)."""
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
    share_ok = visible == "G-DEL.2a ready"
    isolation_ok = hidden is None and self_ok

    # Optional: run gbrain bun tests when node_modules present (not required for gate)
    gbrain = Path(__file__).resolve().parents[2] / "projects" / "gbrain"
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
            "reason": "gbrain node_modules missing; submodule pointer has G-DEL.4 source",
            "source": "projects/gbrain/src/core/agent-shared-context.ts",
        }

    # Official process-local KPI: cross-agent share + isolation
    ok = share_ok and isolation_ok
    return stamp_non_physical_goal(
        {
            "gate": "G-DEL.4",
            "kpi": "cross-agent shared context R/W + isolation; gbrain adapter when present",
            "env": "process-local RoleMemoryStore + optional gbrain AgentSharedContextStore",
            "env_class": "in-process_simulation",
            "caliber": "single_repo_gbrain",
            "share_ok": share_ok,
            "isolation_ok": isolation_ok,
            "gbrain_test": gbrain_test,
            "gbrain_source_present": (
                gbrain / "src/core/agent-shared-context.ts"
            ).is_file(),
        },
        ok=ok,
    )


if __name__ == "__main__":
    print(json.dumps(measure_role_memory_share(), indent=2, ensure_ascii=False))
