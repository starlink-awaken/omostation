"""MOS CLI — human flags + Agora StdioAdapter stdin JSON ({args, kwargs})."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from mos.persist import FileStore


def _read_stdio_request() -> dict[str, Any] | None:
    """If stdin is a pipe with JSON {args, kwargs}, return it; else None.

    Agora StdioAdapter does communicate(input=json). Flag-mode CLIs leave
    stdin empty / TTY. pytest capture raises OSError on read — ignore.
    """
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return None
    except Exception:
        return None
    # Prefer non-blocking detect so flag-mode does not consume pytest stdin
    try:
        import select

        ready, _, _ = select.select([sys.stdin], [], [], 0.0)
        if not ready:
            # Still allow env-forced stdio (tests / adapters that already filled buffer)
            if not __import__("os").environ.get("MOS_STDIO"):
                return None
    except Exception:
        if not __import__("os").environ.get("MOS_STDIO"):
            # Fall through to attempt read only when MOS_STDIO set
            pass
    try:
        raw = sys.stdin.read()
    except OSError:
        return None
    if not raw or not raw.strip():
        return None
    try:
        data = json.loads(raw.strip().splitlines()[0])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    # Agora StdioAdapter shape
    if "args" in data or "kwargs" in data:
        return data
    # Also accept a bare envelope / query object as kwargs
    return {"args": [], "kwargs": data}


def _emit(obj: dict[str, Any], *, pretty: bool = False) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2 if pretty else None))


def _rbac_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if kwargs.get("role"):
        out["role"] = kwargs["role"]
    if kwargs.get("agent_profile"):
        out["agent_profile"] = kwargs["agent_profile"]
    return out


def _guarded(fn_name: str, fn, *args: Any, **kwargs: Any) -> int:
    """Run mos op; map RbacDenied → JSON error exit 3."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        from mos.rbac import RbacDenied

        if isinstance(exc, RbacDenied):
            _emit({"ok": False, "error": "rbac_denied", "detail": str(exc)})
            return 3
        raise


def _run_write(mos: Any, store: FileStore, kwargs: dict[str, Any], *, pretty: bool = False) -> int:
    envelope: dict[str, Any] = {}
    if isinstance(kwargs.get("envelope"), dict):
        envelope = dict(kwargs["envelope"])
    else:
        envelope = {
            "type": kwargs.get("type") or kwargs.get("mem_type"),
            "content": kwargs.get("content"),
            "content_ref": kwargs.get("content_ref") or kwargs.get("contentRef"),
            "confidence": float(kwargs.get("confidence", 0.8)),
            "principal_id": kwargs.get("principal_id"),
            "agent_profile": kwargs.get("agent_profile"),
            "session_id": kwargs.get("session_id"),
            "run_id": kwargs.get("run_id"),
            "source": kwargs.get("source") or "bos-stdio",
            "metadata": kwargs.get("metadata") or {},
            "subject": kwargs.get("subject"),
            "predicate": kwargs.get("predicate"),
            "object": kwargs.get("object"),
            "valid_from": kwargs.get("valid_from"),
            "valid_to": kwargs.get("valid_to"),
        }
    # drop Nones for cleaner validation messages
    envelope = {k: v for k, v in envelope.items() if v is not None}

    def _do() -> int:
        result = mos.write(envelope, role=kwargs.get("role"))
        store.flush_from(mos)
        _emit(result.to_dict(), pretty=pretty)
        return 0 if result.ok else 1

    return _guarded("write", _do)


def _run_recall(mos: Any, kwargs: dict[str, Any], args_list: list[Any], *, pretty: bool = False) -> int:
    query = kwargs.get("query")
    if query is None and args_list:
        query = args_list[0]
    if not query:
        _emit({"ok": False, "error": "query required"})
        return 2
    intent = kwargs.get("intent")
    limit = int(kwargs.get("limit", 10))
    scope = kwargs.get("scope") if isinstance(kwargs.get("scope"), dict) else None
    if scope is None:
        scope = {}
        for k in ("principal_id", "agent_profile", "scene_id"):
            if kwargs.get(k):
                scope[k] = kwargs[k]
        if not scope:
            scope = None
    elif kwargs.get("agent_profile") and "agent_profile" not in scope:
        scope = {**scope, "agent_profile": kwargs["agent_profile"]}

    def _do() -> int:
        result = mos.recall(
            str(query),
            intent=intent,
            limit=limit,
            scope=scope,
            as_of=kwargs.get("as_of") or kwargs.get("asOf"),
            role=kwargs.get("role"),
        )
        _emit(result.to_dict(), pretty=pretty)
        return 0

    return _guarded("recall", _do)


def _run_status(mos: Any, store: FileStore, kwargs: dict[str, Any] | None = None, *, pretty: bool = False) -> int:
    kwargs = kwargs or {}

    def _do() -> int:
        st = mos.status(role=kwargs.get("role"), agent_profile=kwargs.get("agent_profile"))
        st["store_path"] = str(store.path)
        _emit(st, pretty=pretty)
        return 0

    return _guarded("status", _do)


def _run_forget(
    mos: Any, store: FileStore, kwargs: dict[str, Any], args_list: list[Any], *, pretty: bool = False
) -> int:
    mid = kwargs.get("memory_id") or kwargs.get("id")
    if mid is None and args_list:
        mid = args_list[0]
    if not mid:
        _emit({"ok": False, "error": "memory_id required"})
        return 2

    def _do() -> int:
        result = mos.forget(
            str(mid),
            reason=kwargs.get("reason"),
            role=kwargs.get("role"),
            agent_profile=kwargs.get("agent_profile"),
        )
        store.flush_from(mos)
        _emit(result.to_dict(), pretty=pretty)
        return 0 if result.ok else 1

    return _guarded("forget", _do)


def _run_consolidate(mos: Any, store: FileStore, kwargs: dict[str, Any], *, pretty: bool = False) -> int:
    phases = kwargs.get("phases")
    if isinstance(phases, str):
        phases = [p.strip() for p in phases.split(",") if p.strip()]
    dry_run = bool(kwargs.get("dry_run", False))
    # Cron/foundry defaults to governance-agent so consolidate is allowed
    role = kwargs.get("role")
    agent_profile = kwargs.get("agent_profile") or ("governance-agent" if not role else None)

    def _do() -> int:
        result = mos.consolidate(
            phases=phases,
            dry_run=dry_run,
            role=role,
            agent_profile=agent_profile,
        )
        store.flush_from(mos)
        _emit(result.to_dict(), pretty=pretty)
        return 0 if result.ok or result.degraded else 1

    return _guarded("consolidate", _do)


def _run_knowledge_ref(
    mos: Any, store: FileStore, kwargs: dict[str, Any], args_list: list[Any], *, pretty: bool = False
) -> int:
    query = kwargs.get("query")
    if query is None and args_list:
        query = args_list[0]
    if not query:
        _emit({"ok": False, "error": "query required"})
        return 2
    scope = kwargs.get("scope") if isinstance(kwargs.get("scope"), dict) else None
    if scope is None and kwargs.get("principal_id"):
        scope = {"principal_id": kwargs.get("principal_id"), "scene_id": kwargs.get("scene_id")}

    def _do() -> int:
        ref = mos.create_knowledge_ref(
            str(query),
            intent=kwargs.get("intent"),
            scope=scope,
            limit=int(kwargs.get("limit", 5)),
            role=kwargs.get("role"),
        )
        store.flush_from(mos)
        _emit(ref.to_dict(), pretty=pretty)
        return 0

    return _guarded("knowledge_ref", _do)


def dispatch(cmd: str, stdio: dict[str, Any] | None, argv_ns: argparse.Namespace | None = None) -> int:
    store = FileStore()
    mos = store.build_memory_os()
    pretty = bool(getattr(argv_ns, "json", False)) if argv_ns is not None else False

    if stdio is not None:
        args_list = list(stdio.get("args") or [])
        kwargs = dict(stdio.get("kwargs") or {})
        if cmd == "write":
            return _run_write(mos, store, kwargs, pretty=False)
        if cmd == "recall":
            return _run_recall(mos, kwargs, args_list, pretty=False)
        if cmd == "forget":
            return _run_forget(mos, store, kwargs, args_list, pretty=False)
        if cmd == "consolidate":
            return _run_consolidate(mos, store, kwargs, pretty=False)
        if cmd in {"knowledge-ref", "knowledge_ref", "kref"}:
            return _run_knowledge_ref(mos, store, kwargs, args_list, pretty=False)
        if cmd == "status":
            return _run_status(mos, store, kwargs, pretty=False)
        _emit({"ok": False, "error": f"unknown cmd {cmd}"})
        return 2

    assert argv_ns is not None
    if cmd == "write":
        return _run_write(
            mos,
            store,
            {
                "type": argv_ns.mem_type,
                "content": argv_ns.content,
                "content_ref": argv_ns.content_ref,
                "confidence": argv_ns.confidence,
                "principal_id": getattr(argv_ns, "principal_id", None),
                "subject": getattr(argv_ns, "subject", None),
                "predicate": getattr(argv_ns, "predicate", None),
                "object": getattr(argv_ns, "object", None),
                "valid_from": getattr(argv_ns, "valid_from", None),
                "valid_to": getattr(argv_ns, "valid_to", None),
            },
            pretty=pretty,
        )
    if cmd == "recall":
        scope = None
        if getattr(argv_ns, "principal_id", None):
            scope = {"principal_id": argv_ns.principal_id}
        return _run_recall(
            mos,
            {
                "query": argv_ns.query,
                "intent": argv_ns.intent,
                "limit": argv_ns.limit,
                "scope": scope,
                "as_of": getattr(argv_ns, "as_of", None),
            },
            [],
            pretty=pretty,
        )
    if cmd == "forget":
        return _run_forget(
            mos,
            store,
            {"memory_id": argv_ns.memory_id, "reason": argv_ns.reason},
            [],
            pretty=pretty,
        )
    if cmd == "consolidate":
        phases = None
        if getattr(argv_ns, "phases", None):
            phases = [p.strip() for p in argv_ns.phases.split(",") if p.strip()]
        return _run_consolidate(
            mos,
            store,
            {"phases": phases, "dry_run": bool(getattr(argv_ns, "dry_run", False))},
            pretty=pretty,
        )
    if cmd == "knowledge-ref":
        return _run_knowledge_ref(
            mos,
            store,
            {
                "query": argv_ns.query,
                "intent": argv_ns.intent,
                "principal_id": getattr(argv_ns, "principal_id", None),
                "limit": argv_ns.limit,
            },
            [],
            pretty=pretty,
        )
    if cmd == "status":
        return _run_status(mos, store, {}, pretty=pretty)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mos", description="Memory OS control plane")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_write = sub.add_parser("write", help="Write a memory envelope")
    p_write.add_argument("--type", dest="mem_type", default=None, help="Required for flag mode")
    p_write.add_argument("--content", default=None)
    p_write.add_argument("--content-ref", default=None)
    p_write.add_argument("--confidence", type=float, default=0.8)
    p_write.add_argument("--principal-id", default=None)
    p_write.add_argument("--subject", default=None)
    p_write.add_argument("--predicate", default=None)
    p_write.add_argument("--object", default=None)
    p_write.add_argument("--valid-from", default=None)
    p_write.add_argument("--valid-to", default=None)
    p_write.add_argument("--json", action="store_true", help="Pretty JSON")

    p_recall = sub.add_parser("recall", help="Recall memories")
    p_recall.add_argument("query", nargs="?", default=None)
    p_recall.add_argument("--intent", default=None)
    p_recall.add_argument("--limit", type=int, default=10)
    p_recall.add_argument("--principal-id", default=None)
    p_recall.add_argument(
        "--as-of",
        dest="as_of",
        default=None,
        help="ISO-8601 bi-temporal as-of for neo4j/temporal (current-state if omitted)",
    )
    p_recall.add_argument("--json", action="store_true")

    p_forget = sub.add_parser("forget", help="Forget a memory id (propagates raw+theta+mem0)")
    p_forget.add_argument("memory_id", nargs="?", default=None)
    p_forget.add_argument("--reason", default=None)
    p_forget.add_argument("--json", action="store_true")

    p_cons = sub.add_parser("consolidate", help="Orchestrate gbrain dream sleep-time cycle")
    p_cons.add_argument(
        "--phases",
        default=None,
        help="Comma-separated dream phases (default: extract_facts,consolidate,embed)",
    )
    p_cons.add_argument("--dry-run", action="store_true")
    p_cons.add_argument("--json", action="store_true")

    p_kref = sub.add_parser("knowledge-ref", help="ADR-0315 citation from recall (no body)")
    p_kref.add_argument("query", nargs="?", default=None)
    p_kref.add_argument("--intent", default=None)
    p_kref.add_argument("--principal-id", default=None)
    p_kref.add_argument("--limit", type=int, default=5)
    p_kref.add_argument("--json", action="store_true")

    sub.add_parser("status", help="Control plane status")

    # When invoked via Agora stdio, argv is like ["write"] and payload is on stdin.
    # Parse known args first so --help still works; stdio path does not require flags.
    args = parser.parse_args(argv)
    stdio = _read_stdio_request()

    if args.cmd == "write" and stdio is None and not args.mem_type:
        parser.error("write requires --type (or Agora stdin JSON with kwargs.type)")
    if args.cmd == "recall" and stdio is None and not args.query:
        parser.error("recall requires query (or Agora stdin JSON with kwargs.query)")
    if args.cmd == "forget" and stdio is None and not args.memory_id:
        parser.error("forget requires memory_id (or Agora stdin JSON with kwargs.memory_id)")

    return dispatch(args.cmd, stdio, args)


if __name__ == "__main__":
    sys.exit(main())
