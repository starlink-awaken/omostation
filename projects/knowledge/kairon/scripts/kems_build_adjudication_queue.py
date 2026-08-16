#!/usr/bin/env python3
"""Build a redacted JSONL queue for human KEMS adjudication."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

SOURCE_PATTERNS = (
    "*-auto-seeyon-oa-pending.md",
    "*-auto-netease-mailmaster.md",
    "*-auto-apple-mail.md",
    "*-auto-iphone-sms.md",
)
QUEUE_SCHEMA = "kems.adjudication-queue.v1"
DEFAULT_SCENARIO_ID = "private-source-review-v1"
SPLITS = {"train", "validation", "test", "shadow"}


class QueueInputError(ValueError):
    """The controlled source inventory cannot become an adjudication queue."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_files(docs_root: Path) -> list[Path]:
    inbox = docs_root / "_inbox"
    return sorted(
        {path for pattern in SOURCE_PATTERNS for path in inbox.glob(pattern) if path.is_file()},
        key=lambda path: path.name,
    )


def _sample_id(name: str, source_sha256: str) -> str:
    identity = f"{name}\0{source_sha256}".encode()
    return f"sample-{hashlib.sha256(identity).hexdigest()[:24]}"


def build_queue(
    docs_root: Path,
    *,
    scenario_id: str,
    split: str,
) -> list[dict[str, object]]:
    if not scenario_id.strip():
        raise QueueInputError("scenario_id must be non-empty")
    if split not in SPLITS:
        raise QueueInputError(f"split is unsupported: {split}")

    rows: list[dict[str, object]] = []
    for path in _source_files(docs_root):
        source_sha256 = _sha256(path)
        rows.append(
            {
                "queue_schema": QUEUE_SCHEMA,
                "sample_id": _sample_id(path.name, source_sha256),
                "source_sha256": source_sha256,
                "source_ref": f"vault://redacted/{path.name}",
                "scenario_id": scenario_id.strip(),
                "split": split,
                "annotation_status": "pending",
                "annotation_version": "",
                "labels": {},
            }
        )
    if not rows:
        raise QueueInputError("no controlled source files found")
    return rows


def write_queue(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        temporary.chmod(0o600)
        temporary.replace(output_path)
        output_path.chmod(0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path(os.environ.get("BOS_DOCS_ROOT", "/Users/xiamingxing/Documents")),
    )
    parser.add_argument("--output", required=True, type=Path, help="redacted adjudication JSONL")
    parser.add_argument("--scenario-id", default=DEFAULT_SCENARIO_ID)
    parser.add_argument("--split", default="shadow", choices=sorted(SPLITS))
    args = parser.parse_args()
    try:
        rows = build_queue(
            args.docs_root.expanduser().resolve(),
            scenario_id=args.scenario_id,
            split=args.split,
        )
        write_queue(rows, args.output.expanduser().resolve())
    except (OSError, QueueInputError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(
        json.dumps(
            {
                "status": "succeeded",
                "queue_schema": QUEUE_SCHEMA,
                "sample_count": len(rows),
                "pending_count": len(rows),
                "output": str(args.output.expanduser().resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
