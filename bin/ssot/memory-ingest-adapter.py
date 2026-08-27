#!/usr/bin/env python3
"""memory-ingest-adapter — publish CodeBuddy local memory into Memory OS.

Globs the CodeBuddy local memory directory (~/.codebuddy/projects/<ws>/memory),
parses each file's frontmatter (name/description/type), maps the local type to
a Memory OS memory_type, and writes via `cockpit memory write` so the two
memory planes are unified and other agents can recall this memory.

Mapping: user→semantic, feedback→procedural, project→episodic, reference→governance_ref.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

DEFAULT_MEMORY_DIR = Path.home() / ".codebuddy" / "projects" / "Users-xiamingxing-Workspace" / "memory"

_TYPE_MAP = {
    "user": "semantic",
    "feedback": "procedural",
    "project": "episodic",
    "reference": "governance_ref",
}
_FALLBACK_TYPE = "semantic"
_MAX_CONTENT_CHARS = 1200
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text[:_MAX_CONTENT_CHARS]
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    body = text[m.end() :].strip()
    if not isinstance(meta, dict):
        meta = {}
    return meta, body[:_MAX_CONTENT_CHARS]


def _map_type(local_type: str) -> str:
    key = str(local_type or "").strip().lower()
    return _TYPE_MAP.get(key, _FALLBACK_TYPE)


def _write_memory(*, memory_type: str, content: str, subject: str, dry_run: bool) -> bool:
    cmd = [
        "cockpit",
        "memory",
        "write",
        "--type",
        memory_type,
        "--content",
        content,
    ]
    if subject:
        cmd += ["--subject", subject[:200]]
    if dry_run:
        print(f"  [dry-run] {memory_type}: {subject[:60]}")
        return True
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"  write_failed {subject[:40]}: {proc.stderr[:100]}", file=sys.stderr)
        return False
    return True


def ingest(*, memory_dir: Path, dry_run: bool = False) -> dict[str, Any]:
    files = sorted(memory_dir.glob("*.md"))
    report: dict[str, Any] = {"scanned": len(files), "written": 0, "skipped": 0, "errors": 0}
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        meta, body = _parse_frontmatter(text)
        name = str(meta.get("name") or path.stem)
        description = str(meta.get("description") or "")
        local_type = str(meta.get("type") or "")
        if not body and not description:
            report["skipped"] += 1
            continue
        memory_type = _map_type(local_type)
        content = f"{name}: {description}\n\n{body[:_MAX_CONTENT_CHARS]}"
        subject = description or name
        ok = _write_memory(memory_type=memory_type, content=content, subject=subject, dry_run=dry_run)
        if ok:
            report["written"] += 1
        else:
            report["errors"] += 1
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memory-dir", type=Path, default=DEFAULT_MEMORY_DIR)
    parser.add_argument("--dry-run", action="store_true", help="show writes without calling cockpit")
    args = parser.parse_args()
    report = ingest(memory_dir=args.memory_dir, dry_run=args.dry_run)
    print(report)
    return 0 if report["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
