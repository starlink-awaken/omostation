"""re-export from cockpit.adapters.runtime (破跨层 agora I0 → cockpit L3).

load_arch_health 已提取到 runtime L1 (workspace 级聚合, 非 cockpit 专属).
cockpit 调用点 (dashboard) 通过 adapter 不破跨层.
"""

from cockpit.adapters.runtime import load_arch_health

__all__ = ["load_arch_health"]
