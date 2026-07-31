#!/usr/bin/env python3
"""CLI for the committed KEMS ReachBridge transport contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from reach_gateway.kems import dispatch_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--timeout", type=int, default=15)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    try:
        result = dispatch_manifest(manifest, timeout=args.timeout)
    except (OSError, RuntimeError, ValueError) as exc:
        print(
            json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result.as_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
