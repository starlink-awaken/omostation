#!/usr/bin/env python3
"""Backward-compatible entry point for omo-debt CLI.

Previously at scripts/omo_debt.py, moved to src/omo/omo_debt.py.
This wrapper ensures old callers (tests, scripts) still work.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add src/ to path so the package is importable from the repo root
_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from omo.omo_debt import main

raise SystemExit(main())
