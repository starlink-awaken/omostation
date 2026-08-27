#!/usr/bin/env python3
"""Compatibility shim for the KOS search/user CLI under the kairon-cli name."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SRC_DIR = SCRIPT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _main() -> None:
    from kos.cli.__main__ import main  # type: ignore[import-not-found]

    main()


if __name__ == "__main__":
    sys.argv[0] = "kairon-cli.py"
    _main()
