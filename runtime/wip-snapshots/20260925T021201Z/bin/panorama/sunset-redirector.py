#!/usr/bin/env python3
"""sunset-redirector.py — CLI entry for sunset_redirector."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bin.panorama.sunset_redirector import main


if __name__ == "__main__":
    sys.exit(main())
