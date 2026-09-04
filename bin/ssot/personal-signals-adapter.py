#!/usr/bin/env python3
"""personal-signals-adapter — poll personal-signals dir and publish to the bus.

Watches a personal-signals directory (default ~/.codebuddy/personal-signals)
for new/updated files, publishes a `mesh:personal:signal` bus event per new
file, and tracks a processed watermark so re-runs never re-publish. Mirrors the
event-ingest-adapter publish pattern (bus_foundation facade, idempotent).

Input channel (WP-D): 个人文件 → 事件中心 → resident agents 可订阅。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_SIGNALS_DIR = Path.home() / ".codebuddy" / "personal-signals"
WATERMARK_FILE = Path(__file__).resolve().parents[2] / ".omo" / "_delivery" / "personal-signals" / "watermark.json"
TOPIC = "mesh:personal:signal"


def _load_watermark() -> dict[str, str]:
    try:
        data = json.loads(WATERMARK_FILE.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if isinstance(v, str)}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_watermark(processed: dict[str, str]) -> None:
    WATERMARK_FILE.parent.mkdir(parents=True, exist_ok=True)
    WATERMARK_FILE.write_text(json.dumps(processed, indent=2), encoding="utf-8")


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _publish(topic: str, payload: dict[str, Any], trace_id: str) -> bool:
    try:
        import sys as _sys  # noqa: PLC0415
        from pathlib import Path as path_cls  # noqa: PLC0415

        ws = path_cls(__file__).resolve().parents[2]
        cand = ws / "projects" / "bus-foundation" / "src"
        if cand.is_dir() and str(cand) not in _sys.path:
            _sys.path.insert(0, str(cand))
        from bus_foundation.facade import event as bus_event  # noqa: PLC0415

        bus_event.publish(
            topic=topic, payload=payload, source_uri="bos://capability/personal-signals", trace_id=trace_id
        )
        return True
    except Exception as exc:  # noqa: BLE001 - best-effort publish
        print(f"  publish_failed {topic}: {exc}", file=sys.stderr)
        return False


def poll(*, signals_dir: Path, dry_run: bool = False) -> dict[str, Any]:
    watermark = _load_watermark()
    files = sorted(signals_dir.glob("*.md"))
    new_files = [p for p in files if watermark.get(p.name) != _file_digest(p)]
    report: dict[str, Any] = {"scanned": len(files), "new": len(new_files), "published": 0}
    for path in new_files:
        digest = _file_digest(path)
        payload = {
            "source": "personal-signals",
            "file": path.name,
            "content_digest": f"sha256:{digest}",
            "size_bytes": path.stat().st_size,
            "modified_at": path.stat().st_mtime,
        }
        trace_id = f"personal-signal:{path.stem}"
        if dry_run:
            print(f"  [dry-run] {path.name} → {TOPIC}")
        elif _publish(TOPIC, payload, trace_id):
            report["published"] += 1
        watermark[path.name] = digest
    if not dry_run:
        _save_watermark(watermark)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signals-dir", type=Path, default=DEFAULT_SIGNALS_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = poll(signals_dir=args.signals_dir, dry_run=args.dry_run)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
