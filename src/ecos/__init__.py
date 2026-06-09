# eCOS L0 — Protocol Weave
# ============================
from __future__ import annotations

import importlib
import sys
from typing import Any

__version__ = "5.0.0"

_LAZY_IMPORTS = {
    # l0.ssb
    "ssb_auth": ".l0.ssb.ssb_auth",
    "ssb_client": ".l0.ssb.ssb_client",
    "ssb_dump": ".l0.ssb.ssb_dump",
    "ssb_init": ".l0.ssb.ssb_init",
    "ssb_integrity": ".l0.ssb.ssb_integrity",
    "ssb_schema_migrate": ".l0.ssb.ssb_schema_migrate",
    "ssb_seq_migrate": ".l0.ssb.ssb_seq_migrate",
    # l0.emergence
    "calc_emergence": ".l0.emergence.calc_emergence",
    "emergence_auto": ".l0.emergence.emergence_auto",
    "emergence_watch": ".l0.emergence.emergence_watch",
    "snapshot_emergence": ".l0.emergence.snapshot_emergence",
    # services
    "constitution_watcher": ".services.constitution_watcher",
    "realtime_guard": ".services.realtime_guard",
    "kos_health_monitor": ".services.kos_health_monitor",
    "critic_auto_trigger": ".services.critic_auto_trigger",
    "model_balancer": ".services.model_balancer",
    "planner": ".services.planner",
    "email_sender": ".services.email_sender",
    # common
    "common": ".common.common",
    "ecos_common": ".common.ecos_common",
    "ecos_timeout": ".common.ecos_timeout",
    "content_integrity": ".common.content_integrity",
    "integrate_pipeline": ".common.integrate_pipeline",
    "mcp_vfs": ".common.mcp_vfs",
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module_path = _LAZY_IMPORTS[name]
        try:
            return importlib.import_module(module_path, __name__)
        except ImportError:
            # Replicate previous behaviour: standalone/mof CLI mode pass
            if any(term in sys.argv[0] for term in ("ssot/tools", "mof")):
                return None
            raise
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + __all__)
