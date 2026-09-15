"""Shim — 已迁移到 kairon-governance 包.

原 scripts/sync_system_state.py 的全部逻辑已搬到 kairon_governance.sync_state 模块.

请改用:
    kairon-governance sync [--apply] [--output PATH]
"""

from __future__ import annotations

import sys
import warnings

warnings.warn(
    "scripts/sync_system_state.py 已迁移到 kairon-governance 包 (P29-W2 / ADR-0005 阶段 2), "
    "请改用 'kairon-governance sync'",
    DeprecationWarning,
    stacklevel=2,
)

from kairon_governance.sync_state import main  # type: ignore[reportMissingImports]

if __name__ == "__main__":
    sys.exit(main())
