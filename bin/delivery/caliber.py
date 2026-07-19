"""G-DEL metrics caliber helpers (ADR-0225).

Physical multi-host is the official gate for G-DEL.1 / G-DEL.3.
In-process simulation may only claim meets_sim_harness.
"""
from __future__ import annotations

from typing import Any

ENV_CLASS_SIM = "in-process_simulation"
ENV_CLASS_PHYSICAL = "physical_multi_host"

# Substrings that mark a measurement as simulation (case-insensitive)
_SIM_MARKERS = (
    "in-process",
    "simulation",
    "not physical",
    "process-local",
    "logical node",
)

PHYSICAL_GOALS = frozenset({"G-DEL.1", "G-DEL.3", "g_del_1", "g_del_3"})


def classify_env(env: str | None, env_class: str | None = None) -> str:
    """Return canonical env_class from explicit field or free-text env note."""
    if env_class:
        ec = str(env_class).strip().lower().replace("-", "_").replace(" ", "_")
        if "physical" in ec or "multi_host" in ec or "multihost" in ec:
            return ENV_CLASS_PHYSICAL
        if "sim" in ec or "in_process" in ec or "inprocess" in ec:
            return ENV_CLASS_SIM
    text = (env or "").lower()
    if any(m in text for m in _SIM_MARKERS):
        return ENV_CLASS_SIM
    if "physical" in text and ("host" in text or "multi" in text):
        return ENV_CLASS_PHYSICAL
    # fail-closed: unlabeled → treat as simulation for physical-gate purposes
    return ENV_CLASS_SIM


def is_simulation(metric: dict[str, Any]) -> bool:
    return (
        classify_env(metric.get("env"), metric.get("env_class")) == ENV_CLASS_SIM
    )


def stamp_physical_goal(
    result: dict[str, Any],
    *,
    sim_ok: bool,
    physical_hosts: int = 0,
) -> dict[str, Any]:
    """Stamp G-DEL.1/3 style metric: official meets_gate == physical only."""
    env_class = classify_env(result.get("env"), result.get("env_class"))
    result["env_class"] = env_class
    result["meets_sim_harness"] = bool(sim_ok)
    result["physical_hosts"] = int(physical_hosts)
    physical_ok = (
        env_class == ENV_CLASS_PHYSICAL
        and physical_hosts >= 2
        and bool(sim_ok)
    )
    result["meets_physical_gate"] = physical_ok
    # Official ADR-0210/0225 gate
    result["meets_gate"] = physical_ok
    return result


def stamp_non_physical_goal(result: dict[str, Any], *, ok: bool) -> dict[str, Any]:
    """G-DEL.2b / 5b — process-local protocol gates may use meets_gate."""
    if "env_class" not in result:
        result["env_class"] = classify_env(result.get("env"), None)
    result["meets_sim_harness"] = bool(ok)
    result["meets_physical_gate"] = None
    result["meets_gate"] = bool(ok)
    return result
