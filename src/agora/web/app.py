"""Agora Web Dashboard — redirects to Cockpit Dashboard.

The canonical web dashboard is cockpit's dashboard_server.py on :8090.
This module provides a redirect for backward compatibility.
"""

from __future__ import annotations

import os
import sys

COCKPIT_DASHBOARD_URL = os.environ.get("COCKPIT_DASHBOARD_URL", "http://localhost:8090")


def main() -> int:
    """Redirect to cockpit dashboard."""
    print(f"Redirecting to Cockpit Dashboard: {COCKPIT_DASHBOARD_URL}")
    print("The Agora web dashboard has been consolidated into cockpit.")
    print(f"Direct access: {COCKPIT_DASHBOARD_URL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
