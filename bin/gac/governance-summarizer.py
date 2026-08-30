#!/usr/bin/env python3
"""Thin wrapper: governance-summarizer -> governance-orchestrator (CONV-02)."""
import importlib.util
import sys
from pathlib import Path

_canonical = Path(__file__).resolve().parent / "governance-orchestrator.py"
_spec = importlib.util.spec_from_file_location("_canonical", _canonical)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

if __name__ == "__main__":
    sys.argv[0] = "governance-summarizer.py"
    sys.exit(_mod.main())
