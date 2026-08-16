"""Shim — 已迁移到 kairon-governance 包.

原 scripts/agora_route_generator.py 的全部逻辑已搬到 kairon_governance.agora_routes 模块.

请改用:
    kairon-governance agora-routes [--dry-run] [--only PKG,...] [--report PATH]
"""

from __future__ import annotations

import warnings

warnings.warn(
    "scripts/agora_route_generator.py 已迁移到 kairon-governance 包 (P29-W2 / ADR-0005 阶段 2), "
    "请改用 'kairon-governance agora-routes'",
    DeprecationWarning,
    stacklevel=2,
)

from kairon_governance.agora_routes import main  # type: ignore[reportMissingImports]

if __name__ == "__main__":
    raise SystemExit(main())
