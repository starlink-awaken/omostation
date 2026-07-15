#!/usr/bin/env python3
"""Compatibility wrapper — SSOT: bin/ssot/submodule-reachability-gate.py."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

SSOT = Path(__file__).resolve().parent / "ssot" / "submodule-reachability-gate.py"
if not SSOT.is_file():
    sys.stderr.write(f"missing SSOT script: {SSOT}\n")
    sys.exit(2)
sys.argv[0] = str(SSOT)
runpy.run_path(str(SSOT), run_name="__main__")
