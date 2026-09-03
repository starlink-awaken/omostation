#!/usr/bin/env python3
"""Compatibility entrypoint for the canonical GaC healthcheck.

The historical monthly command remains a stable BOS/Make target, but health
logic has one owner: ``bin/gac/gac-healthcheck.py``. This adapter accepts the
legacy flags and forwards them without creating a second health database or
writing state in Documents.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]


def main() -> int:
    """Run the canonical healthcheck and stream its JSON result."""

    supported = {"--full", "--maturity", "--report", "--json"}
    unknown = [arg for arg in sys.argv[1:] if arg not in supported]
    if unknown:
        print(f"unsupported monthly-healthcheck arguments: {unknown}", file=sys.stderr)
        return 2
    command = [sys.executable, str(WORKSPACE / "bin/gac/gac-healthcheck.py"), "--json"]
    return subprocess.run(command, cwd=WORKSPACE, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
