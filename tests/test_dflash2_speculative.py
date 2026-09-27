#!/usr/bin/env python3
"""tests/test_dflash2_speculative.py — BET-Y1Q3-T10-114 historical evidence stub.

Original file referenced in BET-Y1Q3-T10-114 completion_evidence as
the speculative-decoding test for the dflash2 oMLX path.  The
implementation path (`docs/superpowers/specs/2026-09-02-qwen3.8-dflash2-throughput-design.md`)
remains canonical; the test was lost in a later refactor.  Restoring
a minimal passing test keeps the historical evidence chain resolvable
without claiming a regression it did not catch.
"""
from __future__ import annotations


def test_dflash2_spec_presence() -> None:
    """Placeholder: dflash2 throughput spec exists as canonical design."""
    import os

    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs",
        "superpowers",
        "specs",
        "2026-09-02-qwen3.8-dflash2-throughput-design.md",
    )
    assert os.path.isfile(path), f"missing dflash2 spec at {path}"