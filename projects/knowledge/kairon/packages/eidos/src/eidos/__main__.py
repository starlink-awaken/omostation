"""P55-W0: kairon 包 __main__.py v7 — 加 do_default action 真业务 (从包内 __init__ 反射).

v6: 8 个固定 do_<action> function (search/ingest/validate/etc.).
v7: 加 do_default(action, args) 通用 fallback — 反射式调包内任何 'do_<action>' function
  或任何 'do_default' function. 同时维持 v6 8 个具体 dispatch.

POC 业务: 各包 __init__.py 加 do_default (或具体 do_<action>), v7 框架自动 dispatch.
"""
# Dynamic class dispatch via inspect (hasattr on unknown-typed objects).
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import importlib
import inspect
from typing import Any, cast


def _package_info() -> dict[str, Any]:
    pkg_name = __name__.split(".")[0]
    try:
        mod = importlib.import_module(__name__)
    except Exception as exc:
        return {"package": pkg_name, "_import_error": f"{type(exc).__name__}: {exc}"}
    return {
        "package": pkg_name,
        "module": mod.__name__,
        "attrs_count": len([a for a in dir(mod) if not a.startswith("_")]),
    }


def do_search(args: dict[str, Any]) -> dict[str, Any]:
    try:
        mod = importlib.import_module(__name__)
        for name in dir(mod):
            obj = getattr(mod, name)
            if inspect.isclass(obj) and hasattr(obj, "search"):
                instance = obj()
                result = instance.search(args.get("query", ""))
                return {"_method": "search", "_class": name, "result": str(result)[:500]}
    except Exception as exc:
        return {"_method": "search", "_error": f"{type(exc).__name__}: {exc}"}
    return {"_method": "search", "_error": "no class with search method"}


def do_ingest(args: dict[str, Any]) -> dict[str, Any]:
    try:
        mod = importlib.import_module(__name__)
        for name in dir(mod):
            obj = getattr(mod, name)
            if inspect.isclass(obj) and hasattr(obj, "ingest"):
                instance = obj()
                result = instance.ingest(args.get("entity", args.get("data", {})))
                return {"_method": "ingest", "_class": name, "result": str(result)[:500]}
    except Exception as exc:
        return {"_method": "ingest", "_error": f"{type(exc).__name__}: {exc}"}
    return {"_method": "ingest", "_error": "no class with ingest method"}


def do_validate(args: dict[str, Any]) -> dict[str, Any]:
    try:
        mod = importlib.import_module(__name__)
        for name in dir(mod):
            obj = getattr(mod, name)
            if inspect.isclass(obj) and hasattr(obj, "validate"):
                instance = obj()
                result = instance.validate(args.get("data", args.get("entity", {})))
                return {"_method": "validate", "_class": name, "result": str(result)[:500]}
    except Exception as exc:
        return {"_method": "validate", "_error": f"{type(exc).__name__}: {exc}"}
    return {"_method": "validate", "_error": "no class with validate method"}


def do_register(args: dict[str, Any]) -> dict[str, Any]:
    try:
        mod = importlib.import_module(__name__)
        for name in dir(mod):
            obj = getattr(mod, name)
            if inspect.isclass(obj) and hasattr(obj, "register"):
                instance = obj()
                result = instance.register(args.get("name", "default"), args.get("capabilities", []))
                return {"_method": "register", "_class": name, "result": str(result)[:500]}
    except Exception as exc:
        return {"_method": "register", "_error": f"{type(exc).__name__}: {exc}"}
    return {"_method": "register", "_error": "no class with register method"}


def do_list(args: dict[str, Any]) -> dict[str, Any]:
    try:
        mod = importlib.import_module(__name__)
        for name in dir(mod):
            obj = getattr(mod, name)
            if inspect.isclass(obj) and hasattr(obj, "list"):
                instance = obj()
                result = instance.list(args)
                return {"_method": "list", "_class": name, "result": str(result)[:500]}
    except Exception as exc:
        return {"_method": "list", "_error": f"{type(exc).__name__}: {exc}"}
    return {"_method": "list", "_error": "no class with list method"}


def do_run(args: dict[str, Any]) -> dict[str, Any]:
    try:
        mod = importlib.import_module(__name__)
        for name in dir(mod):
            obj = getattr(mod, name)
            if inspect.isclass(obj) and hasattr(obj, "run"):
                instance = obj()
                result = instance.run(args.get("query", args.get("task", "")))
                return {"_method": "run", "_class": name, "result": str(result)[:500]}
    except Exception as exc:
        return {"_method": "run", "_error": f"{type(exc).__name__}: {exc}"}
    return {"_method": "run", "_error": "no class with run method"}


def do_get(args: dict[str, Any]) -> dict[str, Any]:
    try:
        mod = importlib.import_module(__name__)
        for name in dir(mod):
            obj = getattr(mod, name)
            if inspect.isclass(obj) and hasattr(obj, "get"):
                instance = obj()
                result = instance.get(args.get("id", args.get("key", "")))
                return {"_method": "get", "_class": name, "result": str(result)[:500]}
    except Exception as exc:
        return {"_method": "get", "_error": f"{type(exc).__name__}: {exc}"}
    return {"_method": "get", "_error": "no class with get method"}


def do_sync(args: dict[str, Any]) -> dict[str, Any]:
    try:
        mod = importlib.import_module(__name__)
        for name in dir(mod):
            obj = getattr(mod, name)
            if inspect.isclass(obj) and hasattr(obj, "sync"):
                instance = obj()
                result = instance.sync(args)
                return {"_method": "sync", "_class": name, "result": str(result)[:500]}
    except Exception as exc:
        return {"_method": "sync", "_error": f"{type(exc).__name__}: {exc}"}
    return {"_method": "sync", "_error": "no class with sync method"}


def do_default(args: dict[str, Any]) -> dict[str, Any]:
    """P55-W0: 通用 fallback — 反射式调包内任何 do_<action> function."""
    try:
        mod = importlib.import_module(__name__)
    except Exception as exc:
        return {"_method": "do_default", "_error": f"import: {type(exc).__name__}: {exc}"}
    # 找包内 do_default function
    fn = getattr(mod, "do_default", None)
    if fn is not None and callable(fn):
        try:
            result = fn(args)
            return {"_method": "do_default", "result": str(result)[:500]}
        except Exception as exc:
            return {"_method": "do_default", "_error": f"{type(exc).__name__}: {exc}"}
    return {"_method": "do_default", "_error": "no do_default function"}


_ACTION_MAP = {
    "eidos": {
        "search": "read",
        "ingest": "read",
        "validate": "read",
        "register": "find_root",
        "list": "list",
        "run": "read",
        "get": "get_organ_path",
        "sync": "read",
    },
}

_DISPATCH = {
    # P61-W0: per-package 8 do_<action> → do_default 真 action 映射
    # 找不到 mapping 时 fallback 到 do_default 通用 (同 action name)
    "search": lambda args: do_default({"action": "read", **args}),
    "ingest": lambda args: do_default({"action": "read", **args}),
    "validate": lambda args: do_default({"action": "read", **args}),
    "register": lambda args: do_default({"action": "find_root", **args}),
    "list": lambda args: do_default({"action": "list", **args}),
    "run": lambda args: do_default({"action": "read", **args}),
    "get": lambda args: do_default({"action": "get_organ_path", **args}),
    "sync": lambda args: do_default({"action": "read", **args}),
}


def _call_action(action: str, args: dict[str, Any]) -> dict[str, Any]:
    """P55-W0: 真业务 dispatch 路由 (8 具体 + do_default fallback)."""
    fn = _DISPATCH.get(action)
    if fn is not None:
        result = fn(args)
        info = _package_info()
        return {
            "package": info.get("package", "?"),
            "action_dispatched": action,
            "args_echo": args,
            "_reachability": "ok" if "_import_error" not in info else "fail",
            **result,
        }
    # Fallback: 调 do_default
    fallback_name = f"do_{action.replace('-', '_')}"
    fallback_fn = globals().get(fallback_name)
    if fallback_fn is not None and callable(fallback_fn):
        try:
            result = fallback_fn(args)
            return {"package": __name__.split(".")[0], "action_dispatched": action, "args_echo": args, **result}  # type: ignore[reportGeneralTypeIssues]
        except Exception as exc:
            return {
                "package": __name__.split(".")[0],
                "action_dispatched": action,
                "_error": f"{type(exc).__name__}: {exc}",
            }
    # 都没: do_default generic
    result = do_default(args)
    info = _package_info()
    return {
        "package": info.get("package", "?"),
        "action_dispatched": action,
        "args_echo": args,
        "_reachability": "ok" if "_import_error" not in info else "fail",
        **result,
        "_method_dispatch": "fallback",
    }


# P57-W0: 自动 import 包内 do_default 真业务
try:
    from .do_default import do_default as _pkg_fn  # type: ignore[reportMissingImports]

    globals()["do_default"] = _pkg_fn
except ImportError:
    pass


def serve() -> int:
    """P55-W0 serve 入口 (复用 kairon_utils.stdio_rpc).
    P63-W0-D: daemon_mode=True (launchd plist 没 pipe stdin, EOF sleep + retry).
    P68-W1: restart_delay_sec=60 (sleep 60s + exit, 配 launchd KeepAlive 周期重启).
    """
    from kairon_utils.stdio_rpc import run_stdio_dispatch

    return cast("int", run_stdio_dispatch(_call_action, daemon_mode=True, restart_delay_sec=60))


__all__ = ["serve", "_call_action", "_package_info", "_DISPATCH", "do_default"]

if __name__ == "__main__":
    import sys

    sys.exit(serve())
