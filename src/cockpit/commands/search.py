from __future__ import annotations

import json
import os
import re
import select
import subprocess
import time
from argparse import Namespace
from datetime import datetime
from pathlib import Path

from rich.console import Console

from ..storage import get_data_access


def _cmd_search(args: Namespace) -> int:
    """跨源搜索 — P2 记忆脊统一聚合搜索。"""
    console = Console()
    query = getattr(args, "query", "")
    if not query:
        console.print("[yellow]请输入搜索关键词[/]")
        console.print('  [cyan]cockpit search "关键词" --all[/]')
        return 1

    search_all = getattr(args, "all", False)
    limit = getattr(args, "limit", 10)

    zone_count: dict[str, int] = {}
    merged_results: list[dict] = []
    now = datetime.now().isoformat()

    # Zone 1: cockpit local SQLite FTS5
    try:
        local = get_data_access().search_research(query, limit=limit)
        zone_count["local"] = len(local)
        merged_results.extend(local)
    except Exception as e:
        zone_count["local"] = 0
        console.print(f"[dim]⚠ 本地搜索跳过: {e}[/]")

    # Zone 2: KOS (kairon/kos MCP stdio).
    if search_all:
        zone_count["kos"] = 0  # default; updated only on real success
        try:
            kos_items = _invoke_kos_search(query, limit=limit)
            if kos_items:
                for item in kos_items:
                    item.setdefault("_source", "kairon-kos")
                    item.setdefault("_source_path", item.get("canonical_path", "bos://memory/kos/search"))
                    item.setdefault("_zone", "structured-memory")
                    item.setdefault("_type", "knowledge")
                    item.setdefault("_freshness", "unknown")
                    item.setdefault("_owner", "kairon")
                    item.setdefault("_reuse_policy", "reference-only")
                    item.setdefault("_retrieved_at", now)
                merged_results.extend(kos_items)
                zone_count["kos"] = len(kos_items)
        except Exception as e:
            _log_kos_skip(f"unexpected: {type(e).__name__}: {e}")

    # Zone 3: Vault (@学习进化 markdown 知识库).
    if search_all:
        zone_count["vault"] = 0
        try:
            vault_items = _invoke_vault_search(query, limit=limit)
            if vault_items:
                for item in vault_items:
                    item.setdefault("_source", "@学习进化")
                    item.setdefault("_source_path", item.get("source_path", "vault://学习进化"))
                    item.setdefault("_zone", "document-vault")
                    item.setdefault("_type", "document")
                    item.setdefault("_freshness", "unknown")
                    item.setdefault("_owner", "vault")
                    item.setdefault("_reuse_policy", "derived-allowed")
                    item.setdefault("_retrieved_at", now)
                merged_results.extend(vault_items)
                zone_count["vault"] = len(vault_items)
        except Exception as e:
            _log_vault_skip(f"unexpected: {type(e).__name__}: {e}")

    # Zone 4: Trace Closure (Gate C4).
    trace: dict = {}
    if search_all:
        try:
            trace = _writeback_search_trace(
                query, zone_count, len(merged_results), limit, merged_results
            )
        except Exception as e:
            _log_trace_skip(f"unexpected: {type(e).__name__}: {e}")

    # ═══ P2 统一响应契约 ═══
    interleaved = _interleave_by_source(merged_results, limit)
    response = {
        "zone": "all",
        "query": query,
        "zone_count": zone_count,
        "results": interleaved,
        "total": len(merged_results),
    }
    if trace.get("trace_id"):
        response["_trace"] = trace

    if args.json:
        import sys as _sys
        _sys.stdout.write(json.dumps(response, ensure_ascii=False, indent=2))
        _sys.stdout.write("\n")
        _sys.stdout.flush()
    else:
        console.print(
            f"\n[bold cyan]query:[/] {query}  "
            f"[bold cyan]zone:[/] all  "
            f"[bold cyan]total:[/] {len(merged_results)}  "
            f"[bold cyan]zones:[/] {zone_count}"
        )
        for item in interleaved:
            title = str(item.get("topic", item.get("title", str(item)[:80])))[:70]
            zone = item.get("_zone", "?")
            src = item.get("_source", "?")
            console.print(f"  ▸ [{zone}] {title}  [dim]{src}[/dim]")
        if not search_all:
            console.print("[dim]提示: 加 --all 搜索 BOS 知识引擎[/]")
        if trace.get("trace_id"):
            console.print(f"[dim]trace_id: {trace['trace_id']} ({'deduped' if trace.get('deduped') else 'new'})[/dim]")

    return 0

def _interleave_by_source(items: list[dict], limit: int) -> list[dict]:
    if limit <= 0 or not items:
        return items[:limit] if limit > 0 else []
    buckets: dict[str, list[dict]] = {}
    order: list[str] = []
    for it in items:
        src = it.get("_source", "_unknown")
        if src not in buckets:
            buckets[src] = []
            order.append(src)
        buckets[src].append(it)
    out: list[dict] = []
    for src in order:
        if buckets[src] and len(out) < limit:
            out.append(buckets[src].pop(0))
    while len(out) < limit:
        progressed = False
        for src in order:
            if buckets[src] and len(out) < limit:
                out.append(buckets[src].pop(0))
                progressed = True
        if not progressed:
            break
    return out[:limit]

def _log_kos_skip(reason: str) -> None:
    import logging as _logging
    _logging.getLogger("cockpit.cli.kos").debug("KOS skip: %s", reason)

def _invoke_kos_search(query: str, limit: int = 10, timeout: float = 60.0) -> list[dict]:
    ws_root = Path(os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace")))
    kairon_dir = ws_root / "projects" / "kairon"
    if not kairon_dir.exists():
        _log_kos_skip(f"kairon dir not found: {kairon_dir}")
        return []

    try:
        proc = subprocess.Popen(
            ["uv", "run", "python", "-m", "kos.mcp.server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, cwd=str(kairon_dir),
        )
    except (OSError, subprocess.SubprocessError) as e:
        _log_kos_skip(f"spawn failed: {type(e).__name__}: {e}")
        return []

    try:
        proc.stdin.write(json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        }) + "\n")
        proc.stdin.flush()
        proc.stdin.write(json.dumps({
            "jsonrpc": "2.0", "method": "notifications/initialized",
        }) + "\n")
        proc.stdin.flush()
        proc.stdin.write(json.dumps({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {
                "name": "search_knowledge",
                "arguments": {"query": query, "limit": limit},
            },
        }) + "\n")
        proc.stdin.flush()
        proc.stdin.close()

        buf = ""
        deadline = time.time() + timeout
        while time.time() < deadline:
            r, _, _ = select.select([proc.stdout], [], [], 0.5)
            if r:
                chunk = os.read(proc.stdout.fileno(), 65536).decode("utf-8", errors="replace")
                if not chunk:
                    break
                buf += chunk
                if '"id": 2' in buf and buf.rstrip().endswith("}"):
                    break
        else:
            _log_kos_skip(f"read timeout after {timeout}s")
            return []

        raw_results: list[dict] = []
        for line in buf.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") != 2:
                continue
            if "error" in msg:
                _log_kos_skip(f"kos error: {msg['error']}")
                return []
            content = msg.get("result", {}).get("content", [])
            for c in content:
                if c.get("type") == "text":
                    try:
                        payload = json.loads(c["text"])
                    except json.JSONDecodeError:
                        continue
                    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
                        raw_results = [r for r in payload["results"] if isinstance(r, dict)]
                    break
            break

        if not raw_results:
            return []

        mapped: list[dict] = []
        for r in raw_results:
            title = str(r.get("title", r.get("canonical_path", "?")))
            updated = str(r.get("updated_at", ""))
            timestamp = _kos_ts_to_iso(updated)
            body_preview_raw = r.get("body_preview", "")
            body_preview = _clean_control_chars(str(body_preview_raw))
            mapped.append({
                "id": r.get("doc_id", ""),
                "title": _clean_control_chars(title),
                "snippet": body_preview[:200],
                "source": "kairon-kos",
                "source_path": r.get("canonical_path", "bos://memory/kos/search"),
                "timestamp": timestamp,
                "type": "knowledge",
                "relevance": 1.0,
                "kind": r.get("kind", ""),
                "zone": r.get("zone", ""),
                "status": r.get("status", ""),
                "trust_level": r.get("trust_level", ""),
                "updated_at": updated,
                "body_preview": body_preview,
            })
        return mapped

    except Exception as e:
        _log_kos_skip(f"invoke error: {type(e).__name__}: {e}")
        return []
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            pass

def _kos_ts_to_iso(ts: str) -> str:
    if not ts or not ts.isdigit() or len(ts) != 14:
        return ts
    try:
        from datetime import datetime as _dt
        return _dt.strptime(ts, "%Y%m%d%H%M%S").isoformat() + "Z"
    except ValueError:
        return ts

def _clean_control_chars(s: str) -> str:
    if not s:
        return s
    cleaned = re.sub(r"[\x00-\x1f\x7f]+", " ", s)
    return re.sub(r"\s+", " ", cleaned).strip()

def _log_vault_skip(reason: str) -> None:
    import logging as _logging
    _logging.getLogger("cockpit.cli.vault").debug("vault skip: %s", reason)

def _invoke_vault_search(query: str, limit: int = 10, timeout: float = 30.0) -> list[dict]:
    candidates = [
        os.environ.get("LEARNING_VAULT"),
        os.path.expanduser("~/Documents/@学习进化"),
        str(Path(os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace"))).parent / "Documents" / "@学习进化"),
    ]
    vault_root = None
    for c in candidates:
        if c and Path(c).is_dir() and (Path(c) / "_control" / "executors" / "vault-search.sh").is_file():
            vault_root = c
            break
    if vault_root is None:
        _log_vault_skip("vault root not found")
        return []

    script = Path(vault_root) / "_control" / "executors" / "vault-search.sh"

    try:
        proc = subprocess.Popen(
            ["bash", str(script), query],
            cwd=vault_root,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        try:
            stdout, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            _log_vault_skip(f"timeout after {timeout}s")
            return []
    except (OSError, subprocess.SubprocessError) as e:
        _log_vault_skip(f"spawn failed: {type(e).__name__}: {e}")
        return []

    if proc.returncode != 0 or not stdout:
        return []

    raw_items: list[dict] = []
    path_re = re.compile(r"^\./.+\.md$")
    for line in stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("🔍"):
            continue
        if not path_re.match(line):
            continue
        raw_items.append({"rel_path": line[2:]})
        if len(raw_items) >= limit:
            break

    if not raw_items:
        return []

    mapped: list[dict] = []
    for r in raw_items:
        rel = r["rel_path"]
        abs_path = Path(vault_root) / rel
        title = abs_path.stem
        snippet = _read_vault_snippet(abs_path)
        mapped.append({
            "id": rel,
            "title": _clean_control_chars(title),
            "snippet": snippet,
            "source": "@学习进化",
            "source_path": rel,
            "timestamp": _vault_file_mtime(abs_path),
            "type": "document",
            "relevance": 1.0,
            "vault_zone": _infer_vault_zone(rel),
        })
    return mapped

def _read_vault_snippet(abs_path: Path) -> str:
    try:
        text = abs_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            text = text[end + 4 :]
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        return _clean_control_chars(line)[:200]
    return ""

def _vault_file_mtime(abs_path: Path) -> str:
    try:
        import datetime as _dt2
        mtime = abs_path.stat().st_mtime
        return _dt2.datetime.fromtimestamp(mtime, tz=_dt2.UTC).isoformat()
    except OSError:
        return "unknown"

def _infer_vault_zone(rel_path: str) -> str:
    parts = rel_path.split("/", 1)
    if parts and parts[0].startswith("_"):
        return parts[0].lstrip("_")
    return "knowledge"

def _log_trace_skip(reason: str) -> None:
    import logging as _logging
    _logging.getLogger("cockpit.cli.trace").debug("trace skip: %s", reason)

def _writeback_search_trace(
    query: str,
    zone_count: dict,
    total: int,
    limit: int,
    merged_results: list[dict] | None = None,
) -> dict:
    da = get_data_access()
    now = time.time()

    hit_summary = _build_hit_summary(merged_results or [], per_zone=3)

    try:
        da._ensure_db()
        _conn = da._connect()
        _rows = _conn.execute(
            "SELECT id, created_at FROM research "
            "WHERE topic LIKE ? AND agent = ? AND created_at > ? "
            "ORDER BY created_at DESC LIMIT 3",
            (f"search-trace: {query[:50]}%", "opc-p2-trace", now - 60),
        ).fetchall()
        _conn.close()
        recent = [{"id": r[0], "created_at": r[1]} for r in _rows]
    except Exception as e:
        _log_trace_skip(f"dedup check failed: {type(e).__name__}: {e}")
        recent = []

    for r in recent:
        created = r.get("created_at", 0)
        if created and (now - float(created)) < 60:
            return {
                "trace_id": r.get("id"),
                "query": query,
                "zone_count": zone_count,
                "total": total,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(created))),
                "deduped": True,
                "hit_summary": hit_summary,
            }

    summary_dict = {
        "query": query,
        "zone_count": zone_count,
        "total": total,
        "limit": limit,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "hit_summary": hit_summary,
    }
    try:
        trace_id = da.save_research(
            topic=f"search-trace: {query[:200]}",
            summary=json.dumps(summary_dict, ensure_ascii=False),
            full_text=_format_trace_full_text(query, zone_count, hit_summary),
            source_count=total,
            agent="opc-p2-trace",
        )
    except Exception as e:
        _log_trace_skip(f"save failed: {type(e).__name__}: {e}")
        return {}

    return {
        "trace_id": trace_id,
        "query": query,
        "zone_count": zone_count,
        "total": total,
        "timestamp": summary_dict["timestamp"],
        "deduped": False,
        "hit_summary": hit_summary,
    }

def _build_hit_summary(
    items: list[dict], per_zone: int = 3
) -> list[dict]:
    if not items:
        return []
    by_zone: dict[str, list[dict]] = {}
    order: list[str] = []
    for it in items:
        zone = it.get("_zone") or it.get("source") or "_unknown"
        if zone not in by_zone:
            by_zone[zone] = []
            order.append(zone)
        by_zone[zone].append(it)
    out: list[dict] = []
    for zone in order:
        bucket = by_zone[zone]
        sample = []
        for it in bucket[:per_zone]:
            sample.append(
                {
                    "id": it.get("id"),
                    "title": it.get("title") or it.get("topic") or "",
                    "source": it.get("source") or it.get("_source") or "",
                    "source_path": it.get("source_path")
                    or it.get("_source_path")
                    or "",
                    "timestamp": it.get("timestamp") or it.get("_retrieved_at") or "",
                }
            )
        out.append({"zone": zone, "count": len(bucket), "sample": sample})
    return out

def _format_trace_full_text(query: str, zone_count: dict, hit_summary: list[dict]) -> str:
    lines: list[str] = []
    lines.append("P2 C4 search-trace writeback")
    lines.append(f"query: {query}")
    lines.append(f"zone_count: {json.dumps(zone_count, ensure_ascii=False, sort_keys=True)}")
    if not hit_summary:
        lines.append("hits: <none>")
        return "\n".join(lines) + "\n"
    for entry in hit_summary:
        zone = entry.get("zone", "?")
        count = entry.get("count", 0)
        lines.append(f"hits[{zone}]: count={count}")
        for s in entry.get("sample", []):
            sid = s.get("id", "")
            title = s.get("title", "")
            source = s.get("source", "")
            spath = s.get("source_path", "")
            ts = s.get("timestamp", "")
            lines.append(f"  - id={sid} title={title!r}")
            lines.append(f"    source={source} source_path={spath}")
            if ts:
                lines.append(f"    timestamp={ts}")
    return "\n".join(lines) + "\n"
