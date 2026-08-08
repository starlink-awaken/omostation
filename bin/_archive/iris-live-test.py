#!/usr/bin/env python3
"""Iris Live Test — 测试所有iris连接器的live可用性 (P0-T6/P2-T7).

Tests each connector by calling `iris --json list <connector> --limit 1`.
Reports success/failure for each. Exits 0 if all pass, 1 if any fail.

Usage: python3 bin/ssot/iris-live-test.py
       python3 bin/ssot/iris-live-test.py --connector wpsnote
"""

from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any

CONNECTORS = [
    "apple_mail",
    "netease_mailmaster",
    "seeyon_oa",
    "wpsnote",
    "rss",
    "zhihu",
    "wxread",
    "obsidian",
    "local_files",
]


def test_connector(connector: str) -> dict[str, Any]:
    """Test a single connector."""
    try:
        result = subprocess.run(
            ["iris", "--json", "list", connector, "--limit", "1"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            items = json.loads(result.stdout)
            count = len(items) if isinstance(items, list) else 0
            return {"connector": connector, "status": "ok", "items_returned": count}
        else:
            stderr = result.stderr.strip()[:100] if result.stderr else "no output"
            return {"connector": connector, "status": "error", "detail": stderr}
    except subprocess.TimeoutExpired:
        return {"connector": connector, "status": "timeout"}
    except Exception as e:
        return {"connector": connector, "status": "error", "detail": str(e)[:100]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connector", default=None, help="test single connector")
    args = parser.parse_args(argv)

    connectors = [args.connector] if args.connector else CONNECTORS
    results = []
    passed = 0
    failed = 0

    print("Iris Live Connector Test")
    print("=" * 50)

    for c in connectors:
        r = test_connector(c)
        results.append(r)
        if r["status"] == "ok":
            passed += 1
            print(f"  ✅ {c:25s} items={r['items_returned']}")
        else:
            failed += 1
            print(f"  ❌ {c:25s} {r['status']}: {r.get('detail', '')}")

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {len(results)} total")

    if failed == 0:
        print("✅ All connectors live!")
    else:
        print(f"⚠️  {failed} connector(s) need attention (may need app running or config)")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
