"""Cockpit external-channels inventory (ECCP) — L3 entry for gen-external-channels-inventory."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any


def _workspace_root() -> Path:
    # commands/ → cockpit/ → src/ → cockpit package root → projects/cockpit → projects → workspace
    return Path(__file__).resolve().parents[5]


def cmd_channels(args: Any) -> int:
    """Generate / show external-channels inventory (ECCP)."""
    root = _workspace_root()
    script = root / "bin" / "ssot" / "gen-external-channels-inventory.py"
    if not script.is_file():
        print(f"❌ missing generator: {script}")
        return 1

    # Always regenerate for truthful health_summary (generator is the SSOT writer)
    r = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    if r.stdout:
        print(r.stdout.rstrip())
    if r.returncode != 0:
        if r.stderr:
            print(r.stderr.rstrip())
        print(f"❌ inventory generator failed (exit {r.returncode})")
        return r.returncode

    out = root / ".omo" / "_truth" / "registry" / "external-channels.yaml"
    if not out.is_file():
        print("⚠️  generator reported success but registry file missing")
        return 1

    show = not bool(getattr(args, "quiet", False))
    if show:
        try:
            import yaml

            data = yaml.safe_load(out.read_text(encoding="utf-8")) or {}
            hs = data.get("health_summary") or {}
            totals = data.get("totals") or {}
            print()
            print("═══ External Channels Inventory ═══")
            print(f"  path: {out.relative_to(root)}")
            print(f"  channels: {totals.get('channels') or len(data.get('channels') or [])}")
            if hs:
                print(
                    f"  health: available={hs.get('available')} "
                    f"unavailable={hs.get('unavailable')} "
                    f"pending={hs.get('pending')} "
                    f"error={hs.get('error')} "
                    f"available_rate={hs.get('available_rate')}%"
                )
            channels = data.get("channels") or []
            orphans = [c for c in channels if isinstance(c, dict) and c.get("status") == "orphan"]
            if orphans:
                print(f"  orphans ({len(orphans)}):")
                for c in orphans[:12]:
                    print(f"    - {c.get('id')}")
            print()
            print("  💡 SSOT: .omo/_truth/registry/external-channels.yaml")
            print("  💡 Attach: docs/operations/external-agent-attach-card.md")
        except Exception as exc:  # noqa: BLE001
            print(f"  (parse summary skipped: {exc})")
            print(f"  raw file: {out}")
    return 0
