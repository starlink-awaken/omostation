"""Anti-corruption adapter for projects/runtime (L1).

Re-exports the runtime symbols used by cockpit so downstream interface changes
are absorbed here rather than scattered through L3 code.

When the runtime package (or the executor/i0/arch_health modules it needs) is
not importable — e.g. runtime is not installed, or its current tree only ships
the registry subset — every symbol degrades to None so L3 callers keep working.
Callers must guard with `sym if sym else <fallback>` (already done at all
dashboard / API call sites).
"""

try:
    from runtime.arch_health import load_arch_health  # type: ignore[import-not-found]
    from runtime.executor.config import (  # type: ignore[import-not-found]
        AGENT_RUNTIME_PORT,
        AUTH_TOKEN,
        DEFAULT_MODEL,
        EXEC_LOG_FILE,
        log,
        setup_logging,
    )
    from runtime.executor.engine import (  # type: ignore[import-not-found]
        AgentRuntime,
        _build_alert_message,
        _log_execution,
    )
    from runtime.i0 import (  # type: ignore[import-not-found]
        i0_events,
        i0_protocols,
        i0_services,
        i0_status,
    )
except ImportError:  # runtime unavailable or tree without executor/i0/arch_health
    # NOTE: do not use KOS_REST_API_PORT — reserved by port-registry.
    # Runtime's agent-runtime uses 8770 by default.
    AGENT_RUNTIME_PORT = 0  # type: ignore[assignment]  # fallback: uvicorn picks free port
    AUTH_TOKEN = None  # type: ignore[assignment]
    DEFAULT_MODEL = None  # type: ignore[assignment]
    EXEC_LOG_FILE = None  # type: ignore[assignment]
    AgentRuntime = None  # type: ignore[assignment]
    _build_alert_message = None  # type: ignore[assignment]
    _log_execution = None  # type: ignore[assignment]
    i0_events = None  # type: ignore[assignment]
    i0_protocols = None  # type: ignore[assignment]
    i0_services = None  # type: ignore[assignment]
    i0_status = None  # type: ignore[assignment]
    load_arch_health = None  # type: ignore[assignment]
    log = None  # type: ignore[assignment]

    def setup_logging(*_args, **_kwargs) -> None:  # type: ignore[no-redef]
        """No-op fallback so cockpit entry points survive without runtime."""
        return None


__all__ = [
    "AGENT_RUNTIME_PORT",
    "AUTH_TOKEN",
    "DEFAULT_MODEL",
    "EXEC_LOG_FILE",
    "AgentRuntime",
    "_build_alert_message",
    "_log_execution",
    "i0_events",
    "i0_protocols",
    "i0_services",
    "i0_status",
    "load_arch_health",
    "log",
    "setup_logging",
]
