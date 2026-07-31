"""Anti-corruption adapter for projects/runtime (L1).

Re-exports the runtime symbols used by cockpit so downstream interface changes
are absorbed here rather than scattered through L3 code.
"""

try:
    from runtime.executor.config import AGENT_RUNTIME_PORT
except ImportError:
    # NOTE: do not use KOS_REST_API_PORT — reserved by port-registry.
    # Runtime's agent-runtime uses 8770 by default.
    AGENT_RUNTIME_PORT = 0  # fallback: uvicorn picks free port

from runtime.arch_health import load_arch_health
from runtime.executor.config import AUTH_TOKEN, DEFAULT_MODEL, EXEC_LOG_FILE, log, setup_logging
from runtime.executor.engine import AgentRuntime, _build_alert_message, _log_execution
from runtime.i0 import i0_events, i0_protocols, i0_services, i0_status

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
