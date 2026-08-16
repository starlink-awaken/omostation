#!/usr/bin/env python3
# ruff: noqa
"""KOS API Server — lightweight HTTP knowledge API.

Endpoints:
    GET  /search?q=xxx&domains=...&limit=10   → search results
    GET  /status                               → system health
    GET  /digest                               → daily overview
    GET  /diff?days=7                          → knowledge changes
    GET  /export?q=xxx                          → MD export of search results
    GET  /history                              → recent search history
    POST /ingest  {"text": "..."}              → ingest knowledge

Start: kos api
"""

import json
import sqlite3
import sys
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
# sys.path.insert(0, str(SCRIPT_DIR))  # removed by replace_imports.py

# sys.path.insert(0, str(get_vault_ops_dir()))  # removed by replace_imports.py
from kos.config import get_artifact_path  # type: ignore[import-not-found]

HISTORY_FILE = Path.home() / "Documents" / "KOS-Inbox" / ".search_history.jsonl"
PORT = 8765


def get_db() -> sqlite3.Connection | None:
    db_path = get_artifact_path("retrievalDatabase")
    if not db_path.exists():  # type: ignore[attr-defined]
        return None
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def search(q: str, domains: str = "", limit: int = 10) -> dict:  # type: ignore[type-arg]
    conn = get_db()  # type: ignore[no-untyped-call]
    if not conn:
        return {"error": "No DB"}
    domain_filter = ""
    params = [q]
    if domains:
        dl = [d.strip() for d in domains.split(",")]
        placeholders = ",".join(["?"] * len(dl))
        domain_filter = f"AND d.zone IN ({placeholders})"
        params.extend(dl)
    params.append(limit)  # type: ignore[arg-type]
    try:
        rows = conn.execute(
            f"""SELECT d.title, d.zone, d.kind, d.canonical_path,
                snippet(documents_fts,1,'<b>','</b>','...',60) as s
                FROM documents_fts f JOIN documents d ON f.doc_id=d.doc_id
                WHERE documents_fts MATCH ? {domain_filter} ORDER BY rank LIMIT ?""",
            params,
        ).fetchall()
        return {"results": [dict(r) for r in rows], "count": len(rows)}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}
    finally:
        conn.close()


def status() -> dict:  # type: ignore[type-arg]
    conn = get_db()  # type: ignore[no-untyped-call]
    if not conn:
        return {"error": "No DB"}
    zones = conn.execute("SELECT zone, COUNT(*) as cnt FROM documents GROUP BY zone").fetchall()
    total = sum(z["cnt"] for z in zones)
    conn.close()
    return {"documents": total, "zones": {z["zone"]: z["cnt"] for z in zones}}


def digest() -> dict:  # type: ignore[type-arg]
    s = status()
    try:
        e = conn.execute("SELECT COUNT(*) FROM kos_entities").fetchone()[0]  # type: ignore[name-defined]
    except Exception:  # noqa: BLE001
        logger.error("Unexpected exception caught", exc_info=True)  # type: ignore[name-defined]
        e = 0
    s["entities"] = e
    s["timestamp"] = datetime.now().isoformat()[:19]
    return s


def diff(days: int = 7) -> dict:  # type: ignore[type-arg]
    conn = get_db()  # type: ignore[no-untyped-call]
    if not conn:
        return {"error": "No DB"}
    since = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    rows = conn.execute(
        "SELECT title, zone, updated_at FROM documents WHERE updated_at >= ? ORDER BY updated_at DESC LIMIT 50",
        (since,),
    ).fetchall()
    conn.close()
    return {"since_days": days, "changed": len(rows), "documents": [dict(r) for r in rows]}


def history(limit: int = 20) -> dict:  # type: ignore[type-arg]
    if not HISTORY_FILE.exists():
        return {"history": [], "count": 0}
    lines = HISTORY_FILE.read_text().strip().splitlines()[-limit:]
    entries = [json.loads(l) for l in lines if l.strip()]
    return {"history": entries, "count": len(entries)}


def export_md(q: str, domains: str = "") -> str:
    r = search(q, domains)
    if r.get("error"):
        return f"Error: {r['error']}"
    lines = [f"# KOS Search: {q}", f"*{r['count']} results*", ""]
    for i, doc in enumerate(r.get("results", []), 1):
        lines.append(f"## {i}. {doc['title']}")
        lines.append(f"Zone: {doc['zone']} | {doc.get('kind', '')}")
        lines.append(f"Path: {doc.get('canonical_path', '')}")
        lines.append("")
    return "\n".join(lines)


class KOSHandler(BaseHTTPRequestHandler):
    def _json(self, data: object, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode())

    def _text(self, text: str, code: int = 200, ct: str = "text/markdown") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.end_headers()
        self.wfile.write(text.encode())

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        path = parsed.path.rstrip("/")

        if path == "/search":
            q = params.get("q", [""])[0]
            domains = params.get("domains", [""])[0]
            limit = int(params.get("limit", ["10"])[0])

            # Log history
            if q:
                HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(HISTORY_FILE, "a") as f:
                    f.write(json.dumps({"q": q, "t": datetime.now().isoformat()[:19]}, ensure_ascii=False) + "\n")

            result = search(q, domains, limit)
            self._json(result)  # type: ignore[no-untyped-call]

        elif path == "/status":
            self._json(status())  # type: ignore[no-untyped-call]
        elif path == "/digest":
            self._json(digest())  # type: ignore[no-untyped-call]
        elif path == "/diff":
            days = int(params.get("days", ["7"])[0])
            self._json(diff(days))  # type: ignore[no-untyped-call]
        elif path == "/history":
            self._json(history())  # type: ignore[no-untyped-call]
        elif path == "/export":
            q = params.get("q", [""])[0]
            domains = params.get("domains", [""])[0]
            md = export_md(q, domains)
            self._text(md)  # type: ignore[no-untyped-call]
        else:
            self._json(  # type: ignore[no-untyped-call]
                {"endpoints": ["/search?q=xx", "/status", "/digest", "/diff?days=7", "/history", "/export?q=xx"]}
            )

    def do_POST(self) -> None:
        if self.path.rstrip("/") == "/ingest":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            text = body.get("text", "")
            if not text:
                self._json({"error": "missing text field"}, 400)  # type: ignore[no-untyped-call]
                return
            # Import and call ingest
            import subprocess as sp

            r = sp.run(
                [sys.executable, str(SCRIPT_DIR / "kos-ingest.py"), text], capture_output=True, text=True, timeout=30
            )
            self._text(r.stdout, ct="application/json")  # type: ignore[no-untyped-call]
        else:
            self._json({"error": "not found"}, 404)  # type: ignore[no-untyped-call]


if __name__ == "__main__":
    print(f"🚀 KOS API Server → http://localhost:{PORT}")
    print("   /search /status /digest /diff /history /export")
    server = HTTPServer(("127.0.0.1", PORT), KOSHandler)
    server.serve_forever()
