#!/usr/bin/env python3
"""Compatibility gateway for the Documents Manifest-derived DOMAIN-INDEX.

The former implementation compared a legacy global ``registry.py`` and MOF
snapshot, then could overwrite the Documents index.  Documents domain identity
now comes only from ``L4-DOMAIN-REGISTRY.yaml`` plus validated ``DOMAIN.yaml``
manifests.  Keep this filename for cron and historical callers, but delegate
the actual projection/check to the accepted Workspace release.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parents[2]
DOMAIN_REGISTRY = DOCS_ROOT / "@公共" / "_control" / "L4-DOMAIN-REGISTRY.yaml"
DOMAIN_INDEX = DOCS_ROOT / "@驾驶舱" / "_control" / "DOMAIN-INDEX.md"
BEGIN = "<!-- AUTOGEN:L4-DOMAIN-MANIFESTS BEGIN -->"
END = "<!-- AUTOGEN:L4-DOMAIN-MANIFESTS END -->"


def _workspace_candidates() -> tuple[Path, ...]:
    """Prefer an explicit root, then the accepted release used by Cockpit."""

    configured = os.environ.get("WORKSPACE_ROOT")
    candidates = [Path(configured).expanduser()] if configured else []
    candidates.extend(
        [
            Path.home() / ".local/share/omostation/accepted",
            DOCS_ROOT.parent / "Workspace",
        ]
    )
    return tuple(candidates)


def _index_tool() -> Path:
    for workspace in _workspace_candidates():
        tool = workspace / "bin/gac/documents-domain-index.py"
        if tool.is_file():
            return tool
    raise FileNotFoundError(
        "Documents Manifest index tool unavailable; install or select an accepted Workspace release"
    )


def _run(command: str) -> subprocess.CompletedProcess[str]:
    tool = _index_tool()
    return subprocess.run(
        [
            sys.executable,
            str(tool),
            command,
            "--domain-registry",
            str(DOMAIN_REGISTRY),
            "--index-path",
            str(DOMAIN_INDEX),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _emit_current_projection() -> str:
    text = DOMAIN_INDEX.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        raise ValueError("DOMAIN-INDEX lacks the Manifest projection markers")
    _before, remainder = text.split(BEGIN, 1)
    body, _after = remainder.split(END, 1)
    return BEGIN + body + END


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true")
    action.add_argument("--emit-index", action="store_true")
    action.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    command = "write" if args.write else "check"
    try:
        result = _run(command)
    except (OSError, UnicodeError, ValueError) as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"❌ {exc}")
        return 2

    if args.emit_index and result.returncode == 0:
        try:
            result_stdout = _emit_current_projection()
        except (OSError, UnicodeError, ValueError) as exc:
            if args.json:
                print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
            else:
                print(f"❌ {exc}")
            return 2
    else:
        result_stdout = result.stdout.strip()

    if args.json:
        print(
            json.dumps(
                {
                    "ok": result.returncode == 0,
                    "mode": "emit-index" if args.emit_index else command,
                    "domain_registry": str(DOMAIN_REGISTRY),
                    "index_path": str(DOMAIN_INDEX),
                    "source": "L4 Manifest Registry",
                    "error": result.stderr.strip() or None,
                },
                ensure_ascii=False,
            )
        )
    elif result_stdout:
        print(result_stdout)
    if result.stderr.strip() and not args.json:
        print(result.stderr.strip(), file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
