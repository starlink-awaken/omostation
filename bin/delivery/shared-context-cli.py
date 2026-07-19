#!/usr/bin/env python3
"""G-DEL.4 shared-context CLI — cross-process agent handoff.

Usage:
  python3 bin/delivery/shared-context-cli.py write \\
    --writer agent-A --key collab.handoff --value "ready" --scope bet-b7da
  python3 bin/delivery/shared-context-cli.py read \\
    --reader agent-B --key collab.handoff --scope bet-b7da
  python3 bin/delivery/shared-context-cli.py list --reader agent-B --scope bet-b7da
  python3 bin/delivery/shared-context-cli.py export-kos --scope bet-b7da \\
    --db kos/kos-index.sqlite
  python3 bin/delivery/shared-context-cli.py retrieve-kos --query collab.handoff \\
    --db kos/kos-index.sqlite
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared_context_store import (  # noqa: E402
    FileSharedContextStore,
    default_store_root,
    kos_retrieve,
    seed_into_kos,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--root",
        type=Path,
        default=None,
        help="store root (default: <workspace>/.omo/_delivery/shared-context)",
    )
    ap.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="workspace root for default store path",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("write", help="write a shared-context key")
    w.add_argument("--writer", required=True)
    w.add_argument("--key", required=True)
    w.add_argument("--value", required=True)
    w.add_argument("--scope", default="default")
    w.add_argument("--reader", action="append", default=[], help="restrict readers (repeatable)")
    w.add_argument("--tag", action="append", default=[])

    r = sub.add_parser("read", help="read a key as an agent")
    r.add_argument("--reader", required=True)
    r.add_argument("--key", required=True)
    r.add_argument("--scope", default="default")

    ls = sub.add_parser("list", help="list keys visible to an agent")
    ls.add_argument("--reader", required=True)
    ls.add_argument("--scope", default="default")

    ek = sub.add_parser("export-kos", help="seed scope into KOS sqlite")
    ek.add_argument("--scope", default="default")
    ek.add_argument("--db", type=Path, required=True)

    rk = sub.add_parser("retrieve-kos", help="LIKE search KOS for shared-context")
    rk.add_argument("--query", required=True)
    rk.add_argument("--db", type=Path, required=True)
    rk.add_argument("--limit", type=int, default=5)

    args = ap.parse_args(argv)
    ws = args.workspace
    if args.root:
        store = FileSharedContextStore(args.root)
    elif ws:
        store = FileSharedContextStore(default_store_root(ws))
    else:
        store = FileSharedContextStore()

    if args.cmd == "write":
        rec = store.write(
            args.writer,
            args.key,
            args.value,
            scope=args.scope,
            readers=args.reader or None,
            tags=args.tag or None,
        )
        print(json.dumps({"ok": True, "record": rec.__dict__}, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "read":
        rec = store.read(args.reader, args.key, scope=args.scope)
        if rec is None:
            print(json.dumps({"ok": False, "error": "not_found_or_forbidden"}))
            return 1
        print(json.dumps({"ok": True, "record": rec.__dict__}, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "list":
        items = store.list_visible(args.reader, scope=args.scope)
        print(
            json.dumps(
                {"ok": True, "n": len(items), "records": [r.__dict__ for r in items]},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.cmd == "export-kos":
        recs = store.export_scope(args.scope)
        result = seed_into_kos(recs, scope=args.scope, db_path=args.db)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    if args.cmd == "retrieve-kos":
        hits = kos_retrieve(args.db, args.query, limit=args.limit)
        print(json.dumps({"ok": True, "n": len(hits), "hits": hits}, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
