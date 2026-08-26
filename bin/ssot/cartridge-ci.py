#!/usr/bin/env python3
"""Cartridge CI: Automated Domain Hot-Compilation and Signing Pipeline."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent.parent
DOMAINS_DIR = WORKSPACE / "domains"

def compile_all_cartridges() -> int:
    """Find all domain directories and compile them into .cartridge packages."""
    if not DOMAINS_DIR.exists():
        print(f"[Cartridge-CI] No domains directory found at {DOMAINS_DIR}", file=sys.stderr)
        return 0

    success = True
    for item in DOMAINS_DIR.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            manifest = item / "manifest.json"
            if manifest.exists() or (item / "_truth").exists() or (item / "policies").exists():
                print(f"[Cartridge-CI] 📦 Packaging domain cartridge: {item.name} ...")
                res = subprocess.run(
                    ["uv", "run", "cockpit", "cartridge", "pack", str(item)],
                    cwd=str(WORKSPACE),
                    capture_output=True,
                    text=True
                )
                if res.returncode == 0:
                    print(f"  ✅ {item.name}.cartridge compiled successfully.")
                else:
                    print(f"  ❌ Failed to compile {item.name}: {res.stderr.strip()}", file=sys.stderr)
                    success = False

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(compile_all_cartridges())
