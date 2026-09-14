#!/usr/bin/env python3
"""Compatibility shim for kos‑tui script.

This wrapper forwards to the actual Textual UI implementation located at
kos.web.tui.kos_tui.app.
"""

import sys

from kos.web.tui.kos_tui.app import main  # type: ignore[import-not-found]

if __name__ == "__main__":
    sys.argv[0] = "kos-tui.py"
    main()
