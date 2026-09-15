"""P58-W0 sophia do_default — 真业务 (调 sophia compiler / learner 真函数)."""

from __future__ import annotations

from typing import Any


def do_default(args: dict[str, Any]) -> dict[str, Any]:
    """P58-W0 sophia do_default: 真调 compile_paradigm_sync / ParadigmLearner / symbols."""
    try:
        from sophia import (
            ParadigmLearner,
            compile_paradigm_sync,
            recompile_from_dict,
        )
        from sophia.symbols import BASE_TRANSITIONS, AtomicOp  # type: ignore[import-not-found]
    except Exception as exc:
        return {"_method": "do_default", "_error": f"import: {type(exc).__name__}: {exc}"}

    action = args.get("action", "list_components")
    try:
        if action == "list_components":
            return {
                "_method": "do_default",
                "_action": "list_components",
                "compile_fn": compile_paradigm_sync.__name__,
                "recompile_fn": recompile_from_dict.__name__,
                "ParadigmLearner": ParadigmLearner.__name__,
                "AtomicOp": AtomicOp.__name__,
                "base_transitions_count": len(BASE_TRANSITIONS),
            }
        if action == "compile":
            query = args.get("query", "Hello world research")
            program = compile_paradigm_sync(query)
            return {
                "_method": "do_default",
                "_action": "compile",
                "query": query,
                "program_type": type(program).__name__,
            }
        if action == "transitions":
            return {
                "_method": "do_default",
                "_action": "transitions",
                "count": len(BASE_TRANSITIONS),
                "states": sorted({t.get("from", "?") for t in BASE_TRANSITIONS if isinstance(t, dict)}),
            }
        return {"_method": "do_default", "_error": f"unknown action: {action}"}
    except Exception as exc:
        return {"_method": "do_default", "_action": action, "_error": f"{type(exc).__name__}: {exc}"}


__all__ = ["do_default"]
