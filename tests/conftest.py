"""Pytest conftest for runtime tests.

Shim: a number of legacy test files (test_core.py, test_cron*_basic.py,
test_scheduler.py) were written when `cron_service` was a standalone
package. After its absorption into `runtime.cron_service` (P30-M2.1),
those test imports still reference the top-level `cron_service` module.

To avoid mass-rewriting ~30 test imports, prepend `src/runtime/` to
sys.path so the inner `cron_service/` package becomes importable as a
top-level module. This is a test-only shim; production code keeps using
`runtime.cron_service`.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC_RUNTIME = Path(__file__).resolve().parent.parent / "src" / "runtime"
if _SRC_RUNTIME.exists() and str(_SRC_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_SRC_RUNTIME))
