#!/usr/bin/env python3
# ruff: noqa
"""
KOS Search Explain — AI-powered result summaries via local Ollama (curl).

Usage:
    kos explain "query" --limit 10
    kos explain "query" --limit 3 --debug

Requires: Ollama running locally (http://localhost:11434)
"""

import json
import re
import sqlite3
import subprocess as sp
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
# sys.path.insert(0, str(SCRIPT_DIR))  # removed by replace_imports.py
from kos.config import get_vault_ops_dir  # type: ignore[unused-ignore, import-not-found]

VAULT_OPS_DIR = get_vault_ops_dir()
# sys.path.insert(0, str(VAULT_OPS_DIR))  # removed by replace_imports.py
from kos.config import get_artifact_path

# Preferred models: smallest/fastest first
OLLAMA_MODEL_CANDIDATES = [
    "qwen3.5:4b",
    "qwen3.5:7b",
    "qwen2.5:7b",
    "qwen3.6:27b-coding-nvfp4",
    "qwen3.6:35b-a3b-coding-nvfp4",
    "gemma4:latest",
    "llama3.2:3b",
    "mistral:7b",
]
TIMEOUT = 90  # seconds for curl --max-time

# 推理端点: 默认本机 ollama, 可通过 OLLAMA_ENDPOINT 指向 omlxc/aetherforge 网关
OLLAMA_GENERATE_URL = os.environ.get("OLLAMA_ENDPOINT", OLLAMA_GENERATE_URL)

_ollama_model = None
_ollama_ok = None  # tri-state: None=unknown, True/False


def _ollama_available() -> bool:
    global _ollama_model, _ollama_ok
    if _ollama_ok is not None:
        return _ollama_ok
    try:
        r = sp.run(
            ["curl", "-s", "--max-time", "5", "http://localhost:11434/api/tags"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            available = {m["name"] for m in data.get("models", [])}
            for candidate in OLLAMA_MODEL_CANDIDATES:
                if candidate in available:
                    _ollama_model = candidate
                    _ollama_ok = True
                    return True
    except Exception:  # noqa: BLE001
        pass
    _ollama_ok = False
    return False


def _call_ollama(model: str, prompt: str) -> str | None:
    """Call Ollama via curl (reliable, no Python HTTP issues)."""
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False})
    try:
        r = sp.run(
            ["curl", "-s", "--max-time", str(TIMEOUT), OLLAMA_GENERATE_URL, "-d", payload],
            capture_output=True,
            text=True,
            timeout=TIMEOUT + 10,
        )
        if r.returncode == 0 and r.stdout.strip():
            result = json.loads(r.stdout)
            text = (result.get("response", "") or "").strip()
            if text:
                for prefix in ["一句话解释：", "解释：", "答：", "回答："]:
                    if text.startswith(prefix):
                        text = text[len(prefix) :].strip()
                return text
    except Exception:  # noqa: BLE001
        pass
    return None


def _generate_explanation(query: str, title: str, body: str) -> str | None:
    model = _ollama_model or "qwen3.5:4b"
    content = (body or "").replace("\n", " ")[:400].strip()
    if len(content) < 10:
        return None
    prompt = f'根据文档内容用一句话解释为什么它与"{query}"相关（不超过30字）：\n\n{content}'
    return _call_ollama(model, prompt)


def explain_search(
    query: str,
    limit: int = 10,
    model_override: str | None = None,
    zone: str | None = None,
    use_semantic: bool = False,  # type: ignore[unknown]
) -> dict:  # type: ignore[type-arg]
    global _ollama_model
    if model_override:
        _ollama_model = model_override
    db_path = get_artifact_path("retrievalDatabase")
    if not db_path.exists():  # type: ignore[attr-defined]
        return {"error": "No index", "results": []}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    zone_filter = "AND d.zone = ?" if zone else ""
    params = [query]
    if zone:
        params.append(zone)
    params.append(limit)  # type: ignore[arg-type]

    try:
        rows = conn.execute(
            f"""SELECT d.doc_id, d.title, d.zone, d.kind, d.canonical_path,
                      substr(d.body, 1, 2000) as body_preview
               FROM documents_fts f JOIN documents d ON f.doc_id = d.doc_id
               WHERE documents_fts MATCH ? {zone_filter}
               ORDER BY rank LIMIT ?""",
            params,
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()

    # If semantic mode, try LanceDB first
    if use_semantic:
        try:
            sem_args = [sys.executable, str(SCRIPT_DIR / "kos-semantic.py"), "search", query, "--limit", str(limit * 3)]
            if zone:
                sem_args.extend(["--domain", zone])
            r = sp.run(sem_args, capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                sem_data = json.loads(r.stdout)
                sem_results = sem_data.get("results", [])
                if sem_results:
                    sem_rows = []
                    for s in sem_results:
                        sem_rows.append(
                            {
                                "doc_id": s["doc_id"],
                                "title": s.get("title", ""),
                                "zone": s.get("zone", ""),
                                "kind": s.get("kind", ""),
                                "canonical_path": s.get("canonical_path", ""),
                                "body_preview": "",
                            }
                        )
                    # Merge: semantic first, FTS5 (keyword-zone-filtered) appended
                    sem_ids = {s["doc_id"] for s in sem_rows}
                    for r in rows:
                        if r["doc_id"] not in sem_ids:
                            sem_rows.append(r)
                    rows = sem_rows
        except Exception:  # noqa: BLE001
            pass

    # Fetch body content for all results BEFORE sorting
    conn2 = sqlite3.connect(str(db_path))
    conn2.row_factory = sqlite3.Row
    for s in rows:
        bp = s["body_preview"] if "body_preview" in s.keys() else ""
        if not bp:
            body_row = conn2.execute(
                "SELECT substr(body, 1, 2000) as bp FROM documents WHERE doc_id=?", (s["doc_id"],)
            ).fetchone()
            if body_row:
                s["body_preview"] = body_row["bp"] or ""
    conn2.close()

    # Sort: results with body content first
    rows = sorted(rows, key=lambda r: -(len(r["body_preview"] or "") > 30))
    rows = rows[:limit]

    has_ollama = _ollama_available()
    model = _ollama_model or "none"
    results = []

    # Build entries first
    for r in rows:
        entry = {
            "doc_id": r["doc_id"],
            "title": r["title"],
            "zone": r["zone"],
            "kind": r["kind"],
            "canonical_path": r["canonical_path"],
        }
        body_text = (r["body_preview"] or "").strip()
        entry["_body"] = body_text
        results.append(entry)

    # Batch explain: one LLM call for all results with real content
    explainable = [e for e in results if len(e["_body"]) > 30]
    if has_ollama and explainable:
        print(
            f"\r  🔥 Explaining {len(explainable)}/{len(results)} results with {model}...",
            end="",
            file=sys.stderr,
            flush=True,
        )
        batch_prompt = f'查询: "{query}"\n\n'
        for i, e in enumerate(explainable, 1):
            # Use short body (150 chars, de-jieba: remove extra spaces from tokenized text)
            body_short = e["_body"][:150].replace("  ", " ").replace("\n", " ")
            batch_prompt += f"文档{i}: {e['title'][:40]}\n内容: {body_short}\n\n"
        batch_prompt += (
            f'为每个文档用一句话（不超过20字）解释为什么它与"{query}"相关。只输出编号和解释，格式: 1:解释\\n2:解释'
        )
        batch_text = _call_ollama(model, batch_prompt)
        if batch_text:
            # Debug
            if "--debug" in sys.argv:
                print(f"\n  [DEBUG] batch response ({len(batch_text)} chars): {batch_text[:300]}...", file=sys.stderr)
            # Match: "1: xxx" or "1. xxx" or "1、xxx" or "1）xxx"
            parsed = re.findall(r"(\d+)\s*[：:\.\)、]\s*(.+?)(?=\s*\d+\s*[：:\.\)、]|\s*$)", batch_text, re.DOTALL)
            if not parsed:
                # Fallback: try per-line match
                for line in batch_text.strip().split("\n"):
                    m = re.match(r"(\d+)\s*[：:\.\)、]\s*(.+)", line)
                    if m:
                        parsed.append((m.group(1), m.group(2)))
            for num_str, explanation in parsed:
                try:
                    idx = int(num_str) - 1
                    if 0 <= idx < len(explainable):
                        explainable[idx]["explanation"] = explanation.strip()[:80]
                except ValueError:
                    pass

    # Fallback: individual snippets for un-explained results
    for i, e in enumerate(results):
        if not e.get("explanation") and len(e["_body"]) > 10:
            e["explanation"] = "…" + e["_body"].replace("\n", " ")[:80] + "…"
        elif not e.get("explanation"):
            e["explanation"] = None
        e.pop("_body", None)

    return {"query": query, "results": results, "count": len(results), "ollama_available": has_ollama, "_model": model}


def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else ""
    limit = 10
    model = None
    zone = None
    use_semantic = "--semantic" in sys.argv
    json_out = "--json" in sys.argv
    for i, a in enumerate(sys.argv):
        if a == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
        if a == "--model" and i + 1 < len(sys.argv):
            model = sys.argv[i + 1]
        if a == "--zone" and i + 1 < len(sys.argv):
            zone = sys.argv[i + 1]

    if not query:
        print(json.dumps({"error": "No query"}))
        sys.exit(1)

    t0 = time.time()
    result = explain_search(query, limit=limit, model_override=model, zone=zone, use_semantic=use_semantic)  # type: ignore[arg-type]
    elapsed = time.time() - t0

    if json_out:
        result["elapsed"] = round(elapsed, 1)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("\r" + " " * 50 + "\r", end="", file=sys.stderr)
        model = result.get("_model", "none")
        has_ai = result.get("ollama_available", False)
        status = f"AI: {model}" if has_ai else "keyword (no LLM)"

        print("\n╔══ KOS Explain ═══════════════════════════════════╗")
        print(f"║  Query : {query[:40]}")
        print(f"║  Results: {result['count']}    │  Backend: {status}")
        print(f"║  Time  : {elapsed:.1f}s")
        print(f"╚{'═' * 52}╝")

        for i, r in enumerate(result["results"], 1):
            print(f"  {i}. {r['title'][:60]}")
            if r.get("explanation"):
                print(f"     ── {r['explanation']}")
            print(f"     {r['zone']}::{r['canonical_path']}")
            print()


if __name__ == "__main__":
    main()  # type: ignore[no-untyped-call]
