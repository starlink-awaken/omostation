"""Shim — 已迁移到 kairon-governance 包.

原 scripts/adr_collect.py 的全部逻辑已搬到 kairon_governance.adr_collect 模块.

请改用:
    kairon-governance adr-scan [--output PATH] [--days N]
"""

from __future__ import annotations

import sys
import warnings

warnings.warn(
    "scripts/adr_collect.py 已迁移到 kairon-governance 包 (P29-W2 / ADR-0005 阶段 2), "
    "请改用 'kairon-governance adr-scan'",
    DeprecationWarning,
    stacklevel=2,
)

from kairon_governance.adr_collect import main  # type: ignore[reportMissingImports]

if __name__ == "__main__":
    sys.exit(main())
