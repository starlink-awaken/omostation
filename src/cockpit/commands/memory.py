"""cockpit.commands.memory — Memory OS L3 CLI (ADR-0372).

Subcommands map 1:1 to mos control plane:
  status | recall | write | forget | consolidate | knowledge-ref

Does not import kairon/gbrain internals; invokes `uv … python -m mos` with
memory_env (NEO4J_*/MOS_*). Prefer bos://memory/mos/* for Agora MCP agents.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from cockpit.compat import WORKSPACE_ROOT
from cockpit.web.memory_env import apply_memory_os_env, mos_subprocess_env, mos_uv_extra_args

from .base import _get_console, _get_err, _panel


def _invoke_mos(cmd: str, kwargs: dict[str, Any] | None = None, *, args_list: list[Any] | None = None) -> dict[str, Any]:
    """Call mos via stdin JSON (same contract as Agora StdioAdapter / api_memory)."""
    apply_memory_os_env()
    kairon = Path(WORKSPACE_ROOT) / "projects" / "kairon"
    proc_cmd = [
        "uv",
        "run",
        "--directory",
        str(kairon),
        "--package",
        "mos",
        *mos_uv_extra_args(),
        "python",
        "-m",
        "mos",
        cmd,
    ]
    payload = json.dumps(
        {"args": list(args_list or []), "kwargs": dict(kwargs or {})},
        ensure_ascii=False,
    )
    try:
        proc = subprocess.run(
            proc_cmd,
            input=payload,
            text=True,
            capture_output=True,
            timeout=float(os.environ.get("MOS_HTTP_TIMEOUT", "60")),
            check=False,
            env=mos_subprocess_env(),
        )
    except FileNotFoundError as exc:
        return {"ok": False, "error": f"uv/mos unavailable: {exc}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    if not proc.stdout.strip():
        return {
            "ok": False,
            "error": proc.stderr.strip() or f"empty stdout rc={proc.returncode}",
            "returncode": proc.returncode,
        }
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid json", "raw": proc.stdout[-500:]}


def _emit(result: dict[str, Any], *, as_json: bool) -> int:
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if as_json:
        print(text)
    else:
        _get_console().print(text)
    if result.get("error") == "rbac_denied":
        return 3
    if result.get("ok") is False:
        return 1
    return 0


def cmd_memory_status(args: argparse.Namespace) -> int:
    kw: dict[str, Any] = {}
    if getattr(args, "role", None):
        kw["role"] = args.role
    if getattr(args, "agent_profile", None):
        kw["agent_profile"] = args.agent_profile
    return _emit(_invoke_mos("status", kw), as_json=bool(getattr(args, "json", False)))


def cmd_memory_recall(args: argparse.Namespace) -> int:
    query = getattr(args, "query", None)
    if not query:
        _get_err().print("[red]❌ 需要 query: cockpit memory recall \"…\"[/red]")
        return 2
    kw: dict[str, Any] = {
        "query": query,
        "limit": int(getattr(args, "limit", 10) or 10),
    }
    if getattr(args, "intent", None):
        kw["intent"] = args.intent
    if getattr(args, "as_of", None):
        kw["as_of"] = args.as_of
    if getattr(args, "role", None):
        kw["role"] = args.role
    scope: dict[str, Any] = {}
    for k in ("principal_id", "agent_profile", "scene_id"):
        v = getattr(args, k, None)
        if v:
            scope[k] = v
    if scope:
        kw["scope"] = scope
        if "agent_profile" in scope:
            kw["agent_profile"] = scope["agent_profile"]
    return _emit(_invoke_mos("recall", kw), as_json=bool(getattr(args, "json", False)))


def cmd_memory_write(args: argparse.Namespace) -> int:
    content = getattr(args, "content", None)
    content_ref = getattr(args, "content_ref", None)
    mem_type = getattr(args, "mem_type", None) or getattr(args, "type", None)
    if not mem_type:
        _get_err().print("[red]❌ 需要 --type semantic|episodic|…[/red]")
        return 2
    if not content and not content_ref:
        _get_err().print("[red]❌ 需要 --content 或 --content-ref[/red]")
        return 2
    kw: dict[str, Any] = {
        "type": mem_type,
        "confidence": float(getattr(args, "confidence", 0.8) or 0.8),
    }
    if content:
        kw["content"] = content
    if content_ref:
        kw["content_ref"] = content_ref
    for k in (
        "principal_id",
        "agent_profile",
        "scene_id",
        "subject",
        "predicate",
        "object",
        "valid_from",
        "valid_to",
        "role",
    ):
        v = getattr(args, k, None)
        if v is not None:
            kw[k] = v
    return _emit(_invoke_mos("write", kw), as_json=bool(getattr(args, "json", False)))


def cmd_memory_forget(args: argparse.Namespace) -> int:
    mid = getattr(args, "memory_id", None)
    if not mid:
        _get_err().print("[red]❌ 需要 memory_id: cockpit memory forget <id>[/red]")
        return 2
    kw: dict[str, Any] = {"memory_id": mid}
    if getattr(args, "reason", None):
        kw["reason"] = args.reason
    if getattr(args, "role", None):
        kw["role"] = args.role
    if getattr(args, "agent_profile", None):
        kw["agent_profile"] = args.agent_profile
    return _emit(_invoke_mos("forget", kw), as_json=bool(getattr(args, "json", False)))


def cmd_memory_consolidate(args: argparse.Namespace) -> int:
    kw: dict[str, Any] = {
        "dry_run": bool(getattr(args, "dry_run", True)),
    }
    if getattr(args, "live", False):
        kw["dry_run"] = False
    if getattr(args, "phases", None):
        kw["phases"] = args.phases
    if getattr(args, "role", None):
        kw["role"] = args.role
    else:
        kw["agent_profile"] = getattr(args, "agent_profile", None) or "governance-agent"
    return _emit(_invoke_mos("consolidate", kw), as_json=bool(getattr(args, "json", False)))


def cmd_memory_knowledge_ref(args: argparse.Namespace) -> int:
    query = getattr(args, "query", None)
    if not query:
        _get_err().print("[red]❌ 需要 query: cockpit memory knowledge-ref \"…\"[/red]")
        return 2
    kw: dict[str, Any] = {
        "query": query,
        "limit": int(getattr(args, "limit", 5) or 5),
    }
    if getattr(args, "intent", None):
        kw["intent"] = args.intent
    if getattr(args, "principal_id", None):
        kw["principal_id"] = args.principal_id
    if getattr(args, "role", None):
        kw["role"] = args.role
    return _emit(_invoke_mos("knowledge-ref", kw), as_json=bool(getattr(args, "json", False)))


def cmd_memory(args: argparse.Namespace) -> int:
    """cockpit memory — Memory OS 统一控制面 CLI."""
    sub = getattr(args, "memory_command", None)
    dispatch = {
        "status": cmd_memory_status,
        "recall": cmd_memory_recall,
        "write": cmd_memory_write,
        "forget": cmd_memory_forget,
        "consolidate": cmd_memory_consolidate,
        "knowledge-ref": cmd_memory_knowledge_ref,
        "kref": cmd_memory_knowledge_ref,
    }
    if sub in dispatch:
        return dispatch[sub](args)

    console = _get_console()
    console.print(_panel("[bold cyan]🧠 Memory OS (ADR-0372 · phase10)[/bold cyan]", "cyan"))
    apply_memory_os_env()
    st = _invoke_mos("status", {})
    if st.get("ok"):
        ad = st.get("adapters") or {}
        live = ad.get("kos_gbrain_live") or {}
        console.print(
            f"[green]status ok[/] version={st.get('version')} "
            f"neo4j={st.get('neo4j_configured')}/{st.get('neo4j_available')} "
            f"as_of={st.get('neo4j_as_of')} rbac={st.get('rbac_enforced')}"
        )
        console.print(
            f"[dim]live kos={((live.get('kos') or {}).get('flag'))} "
            f"gbrain={((live.get('gbrain') or {}).get('flag'))} · "
            f"consolidate last={'yes' if st.get('last_consolidate') else 'none'}[/dim]"
        )
    else:
        console.print(f"[yellow]status degraded:[/] {st.get('error') or st}")
    console.print("\n[bold]子命令 / BOS URI:[/]")
    console.print("  [cyan]cockpit memory status [--json][/]                         bos://memory/mos/status")
    console.print(
        '  [cyan]cockpit memory recall "query" [--intent …] [--as-of ISO][/]  '
        "bos://memory/mos/recall"
    )
    console.print("  [cyan]cockpit memory write --type semantic --content …[/]       bos://memory/mos/write")
    console.print("  [cyan]cockpit memory forget <id>[/]                             bos://memory/mos/forget")
    console.print("  [cyan]cockpit memory consolidate [--live][/]                    bos://memory/mos/consolidate")
    console.print('  [cyan]cockpit memory knowledge-ref "query"[/]                   bos://memory/mos/knowledge-ref')
    console.print("\n[bold]帮助:[/]")
    console.print("  [cyan]cockpit memory recall --help[/]   · [cyan]cockpit bos resolve bos://memory/mos/status[/]")
    console.print(
        "\n[dim]环境: source bin/memory-os-env.sh · 图库: bash bin/memory-os-neo4j-up.sh · "
        "live: MOS_LIVE_KOS / MOS_LIVE_GBRAIN · 文档: docs/architecture/memory-os.md[/dim]"
    )
    return 0
