#!/usr/bin/env python3
"""TDD test script for validation of mcp-server-kos.py protocol compliance.

Exit contract:
    0  = all checks passed
    1  = a check failed
    78 = CONDITIONAL SKIP (runtime artifact absent). gac-local-gate maps 78 to a
         non-blocking [SKIP] — a skip must never be reported as PASS/ok
         (false-green), but it also must not block CI (DB is gitignored).
"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
MCP_SERVER = WORKSPACE / "bin" / "gac" / "mcp-server-kos.py"
# Canonical runtime location (kos/kos-index.sqlite is the pre-migration layout
# and no longer exists; see .gitignore data/kos/ and mcp-server-kos.py).
KOS_DB = WORKSPACE / "data" / "kos" / "kos-index.sqlite"
SKIP_EXIT_CODE = 78


def run_mcp_query(request_payloads: list[dict]) -> list[dict]:
    # 启动 MCP Server 进程
    proc = subprocess.Popen(
        [sys.executable, str(MCP_SERVER)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    responses = []
    try:
        for req in request_payloads:
            # 写入一行请求
            proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
            proc.stdin.flush()
            # 读取一行回复
            line = proc.stdout.readline()
            if line:
                responses.append(json.loads(line.strip()))
    finally:
        proc.terminate()
        proc.wait()

    return responses


def check_authorizer_default_deny() -> int:
    """Prove the default-deny authorizer on a WRITABLE handle.

    Runs without the runtime KOS DB, so it is the part of this gate that can never
    soft-skip. `mode=ro` is deliberately NOT used here: the point is that the
    authorizer is the primary gate. It must ALLOW reads (SELECT + a recursive CTE —
    graph-shaped knowledge queries need CTEs) and DENY every write/DDL/session
    action (CREATE_*/DROP_*/ALTER_TABLE/REINDEX/ANALYZE/SAVEPOINT) by itself.
    """
    import importlib.util
    import tempfile

    spec = importlib.util.spec_from_file_location("_mcp_server_kos", MCP_SERVER)
    if spec is None or spec.loader is None:
        print("❌ Error: cannot load mcp-server-kos.py for authorizer check")
        return 1
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    tmp = Path(tempfile.mkdtemp())
    db = tmp / "kos-shaped.sqlite"
    seed = sqlite3.connect(str(db))
    seed.execute("CREATE TABLE documents (doc_id TEXT, body TEXT, created_at TEXT)")
    # An index must exist so bare `REINDEX` actually engages the authorizer
    # (with no index it is a no-op and SQLITE_REINDEX is never raised).
    seed.execute("CREATE INDEX idx_doc ON documents (doc_id)")
    seed.execute("INSERT INTO documents VALUES ('1', 'x', '2026-01-01')")
    seed.commit()
    seed.close()

    conn = sqlite3.connect(str(db))  # WRITABLE handle: mode=ro is not the guard here
    conn.row_factory = sqlite3.Row
    conn.set_authorizer(mod._authorizer)
    try:
        # A legitimate read must still work through the same authorizer.
        count = conn.execute("SELECT count(*) FROM documents").fetchone()[0]
        if count != 1:
            print(f"❌ Error: authorizer blocked a legitimate SELECT (count={count})")
            return 1

        # A recursive CTE (SQLITE_RECURSIVE=33) must be allowed: graph-shaped
        # knowledge queries need it. Denying it was an over-tight allow-list.
        try:
            rows = conn.execute(
                "WITH RECURSIVE cnt(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM cnt WHERE x < 3)"
                " SELECT x FROM cnt"
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            print(f"❌ Error: authorizer blocked a recursive CTE: {exc}")
            return 1
        if [r[0] for r in rows] != [1, 2, 3]:
            print(f"❌ Error: recursive CTE returned unexpected rows: {[r[0] for r in rows]}")
            return 1

        # Write / DDL / session actions must be denied by the authorizer alone.
        for sql in (
            "DROP TABLE documents",
            "CREATE TABLE t (a)",
            "ALTER TABLE documents ADD COLUMN z TEXT",
            "CREATE INDEX ix ON documents (doc_id)",
            "REINDEX",
            "ANALYZE",
            "SAVEPOINT sp1",
        ):
            try:
                conn.execute(sql)
            except sqlite3.DatabaseError as exc:
                if "not authorized" not in str(exc):
                    print(f"❌ Error: {sql!r} failed for the wrong reason: {exc}")
                    return 1
                continue
            print(f"❌ Error: authorizer did NOT block {sql!r} on a writable handle")
            return 1
    finally:
        conn.close()

    print("✅ Authorizer default-deny (reads + recursive CTE allowed; DDL/session denied) PASS.")
    return 0


def main() -> int:
    print("🧪 Running TDD tests for mcp-server-kos.py...")

    if not MCP_SERVER.is_file():
        print(f"❌ Error: MCP Server target not found at: {MCP_SERVER}")
        return 1

    # Authorizer default-deny check needs no runtime DB — run it before the soft-skip.
    auth_rc = check_authorizer_default_deny()
    if auth_rc != 0:
        return auth_rc

    if not KOS_DB.is_file():
        # Not exit 0: a silent skip that reports ok is a false-green.
        print(
            f"⚠️  WARN SKIP: KOS database not found at {KOS_DB} "
            "(runtime artifact, not in git) — protocol checks NOT executed "
            f"(exit {SKIP_EXIT_CODE} = skipped, not passed)"
        )
        return SKIP_EXIT_CODE

    # 测试 Payload 1: initialize
    reqs = [
        {"jsonrpc": "2.0", "method": "initialize", "id": 1},
        {"jsonrpc": "2.0", "method": "tools/list", "id": 2},
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "query_custom_sql",
                "arguments": {"sql": "SELECT COUNT(*) as cnt FROM documents"},
            },
            "id": 3,
        },
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "query_custom_sql",
                "arguments": {"sql": "DROP TABLE documents"},
            },
            "id": 4,
        },
    ]

    try:
        res = run_mcp_query(reqs)
    except Exception as e:
        print(f"❌ Execution failed: {e}")
        return 1

    if len(res) < 4:
        print(f"❌ Error: Expected 4 responses, got {len(res)}: {res}")
        return 1

    # 1. 验证 initialize
    init_res = res[0]
    if init_res.get("result", {}).get("serverInfo", {}).get("name") != "mcp-server-kos":
        print(f"❌ Error: Initialize validation failed: {init_res}")
        return 1
    print("✅ Initialize handshake PASS.")

    # 2. 验证 tools/list
    list_res = res[1]
    tools = list_res.get("result", {}).get("tools", [])
    tool_names = {t["name"] for t in tools}
    expected_tools = {"search_kos", "get_document", "list_entities", "query_custom_sql"}
    if not expected_tools.issubset(tool_names):
        print(f"❌ Error: Tools list validation failed. Found: {tool_names}")
        return 1
    print("✅ Tools listing schema PASS.")

    # 3. 验证 query_custom_sql (只读读取行数)
    query_res = res[2]
    content = query_res.get("result", {}).get("content", [{}])[0].get("text", "")
    try:
        data = json.loads(content)
        cnt = data[0]["cnt"]
        print(f"✅ Database query PASS. KOS document count: {cnt}")
    except Exception as e:
        print(f"❌ Error: Database query result parsing failed: {content}, err={e}")
        return 1

    # 4. 验证安全拦截 (DROP TABLE). The handler no longer emits a legacy
    #    "prohibited" string (the substring blacklist was removed); rejection now
    #    comes from the default-deny SQLite authorizer. Assert the real guarantee:
    #    the write MUST be flagged as an error, MUST NOT be a successful read
    #    payload (a JSON array of rows), and MUST carry a denial message.
    sec_res = res[3]
    sec_result = sec_res.get("result", {})
    is_error = sec_result.get("isError") is True
    sec_text = sec_result.get("content", [{}])[0].get("text", "")
    try:
        parsed = json.loads(sec_text)
    except Exception:
        parsed = None
    looks_like_read = isinstance(parsed, list)
    lowered = sec_text.lower()
    denied = any(tok in lowered for tok in ("error", "not authorized", "prohibit", "readonly", "read-only"))
    if not (is_error and not looks_like_read and denied):
        print(f"❌ Error: Security protection failed to intercept write command: {sec_res}")
        return 1
    print("✅ Write interception security PASS (error, not a read payload).")

    print("\n🏁 ALL KOS MCP SERVER TESTS PASSED SUCCESSFULLY! (4/4 PASS)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
