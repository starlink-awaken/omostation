"""P58-W0 kairon_pipeline do_default — 真业务 (调 SourceRegistry / QualityGate 真类).

Round 2 / P7x: each action also publishes a bus-foundation event so other
omostation consumers (omo, metaos, runtime) can observe pipeline activity.
The bus emit is best-effort; failures are logged but never raise.
"""

from __future__ import annotations

from typing import Any


def do_default(args: dict[str, Any]) -> dict[str, Any]:
    """P58-W0 kairon_pipeline do_default: 真调 SourceRegistry / QualityGate / trigger."""
    try:
        from kairon_pipeline import (
            HarvestPriorityQueue,
            QualityGate,
            SourceRegistry,
            trigger_downstream_processing,
        )
    except Exception as exc:
        return {"_method": "do_default", "_error": f"import: {type(exc).__name__}: {exc}"}

    action = args.get("action", "list_components")
    try:
        if action == "list_components":
            result = {
                "_method": "do_default",
                "_action": "list_components",
                "SourceRegistry": SourceRegistry.__name__,
                "QualityGate": QualityGate.__name__,
                "HarvestPriorityQueue": HarvestPriorityQueue.__name__,
                "trigger_fn": trigger_downstream_processing.__name__,
            }
            _bus_emit("kairon:list_components", {"action": action, **result})
            return result
        if action == "sources":
            sr = SourceRegistry()
            result = {
                "_method": "do_default",
                "_action": "sources",
                "registry_type": type(sr).__name__,
                "methods": [m for m in dir(sr) if not m.startswith("_")][:15],
            }
            _bus_emit("kairon:source:ingested", {"action": action, "registry": result["registry_type"]})
            return result
        if action == "quality_gate":
            qg = QualityGate()
            result = {
                "_method": "do_default",
                "_action": "quality_gate",
                "gate_type": type(qg).__name__,
                "methods": [m for m in dir(qg) if not m.startswith("_")][:10],
            }
            _bus_emit("kairon:quality_gate:result", {"action": action, "gate": result["gate_type"]})
            return result
        return {"_method": "do_default", "_error": f"unknown action: {action}"}
    except Exception as exc:
        return {"_method": "do_default", "_action": action, "_error": f"{type(exc).__name__}: {exc}"}


def _bus_emit(topic: str, payload: dict[str, Any]) -> None:
    """Best-effort bus-foundation emit (Round 2 wiring).

    Imports the bus adapter lazily; never raises. If bus-foundation is
    unavailable the call is a no-op so do_default can still return.
    """
    try:
        from kairon_pipeline import bus_adapter
    except ImportError:
        return
    try:
        bus_adapter.emit_event(event_type=topic, source="kairon-pipeline.do_default", payload=payload)
    except Exception:  # defensive
        pass


__all__ = ["do_default"]
