#!/usr/bin/env python3
"""Operate the redacted KEMS adjudication queue without exposing source text."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from kos.kems import AdjudicationStore


def _database_argument() -> Path:
    return Path(os.environ.get("KEMS_ADJUDICATION_DB", str(Path.home() / ".kems" / "adjudication.sqlite")))


def _labels(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read labels JSON: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise ValueError("labels JSON must be an object")
    return payload


def _store(args: argparse.Namespace) -> AdjudicationStore:
    return AdjudicationStore(args.database.expanduser().resolve())


def _run(args: argparse.Namespace) -> object:
    store = _store(args)
    if args.command == "list":
        return store.list_items(status=args.status, limit=args.limit)
    if args.command == "claim":
        return store.claim(args.sample_id, annotator=args.annotator)
    if args.command == "annotate":
        return store.submit_annotation(
            args.sample_id,
            labels=_labels(args.labels_file),
            annotation_version=args.annotation_version,
            annotator=args.annotator,
        )
    if args.command == "adjudicate":
        return store.adjudicate(
            args.sample_id,
            labels=_labels(args.labels_file),
            annotation_version=args.annotation_version,
            adjudicator=args.adjudicator,
        )
    raise ValueError(f"unsupported command: {args.command}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=_database_argument())
    commands = parser.add_subparsers(dest="command", required=True)

    list_parser = commands.add_parser("list", help="list redacted queue metadata")
    list_parser.add_argument("--status", choices=("pending", "reviewed", "conflict", "adjudicated"))
    list_parser.add_argument("--limit", type=int, default=100)

    claim_parser = commands.add_parser("claim", help="claim one independent annotation slot")
    claim_parser.add_argument("--sample-id", required=True)
    claim_parser.add_argument("--annotator", required=True)

    annotate_parser = commands.add_parser("annotate", help="submit one immutable independent annotation")
    annotate_parser.add_argument("--sample-id", required=True)
    annotate_parser.add_argument("--annotator", required=True)
    annotate_parser.add_argument("--annotation-version", required=True)
    annotate_parser.add_argument("--labels-file", required=True, type=Path)

    adjudicate_parser = commands.add_parser("adjudicate", help="record an independent final adjudication")
    adjudicate_parser.add_argument("--sample-id", required=True)
    adjudicate_parser.add_argument("--adjudicator", required=True)
    adjudicate_parser.add_argument("--annotation-version", required=True)
    adjudicate_parser.add_argument("--labels-file", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        result = _run(build_parser().parse_args(argv))
    except (OSError, KeyError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "succeeded", "result": result}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
