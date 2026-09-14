#!/usr/bin/env python3
# ruff: noqa
"""bionic-memory-consolidation.py -- CLI wrapper (BET-Y1Q4-T6-29).

Thin entry point that delegates to bionic_memory_consolidation module.
保留连字符文件名以符合 bet spec verify 命令。
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bin.ops.bionic_memory_consolidation import main

sys.exit(main())
