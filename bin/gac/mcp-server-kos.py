#!/usr/bin/env python3
"""0-Dependency Python stdin/stdout MCP Server for KOS (Knowledge Operating System) SQLite index."""

import json
import sqlite3
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
# 真实索引在 data/kos/ (kos/ 布局已迁移; kos/kos-index.sqlite 不复存在,
# .gitignore:147 data/kos/ — 运行时产物不进 git). 根解析沿用本脚本既有约定
# (__file__ parents[2]), 不硬编码绝对路径 (AGENTS.md 根目录是参数不是事实).
SQLITE_DB = WORKSPACE / "data" / "kos" / "kos-index.sqlite"


# ── SQLite authorizer (ADR-0127 Finding 3.1) ─────────────────────────────
# DEFAULT-DENY. Action codes: https://sqlite.org/c3ref/c_alter_table.html
_SQLITE_PRAGMA = 19
_SQLITE_READ = 20
_SQLITE_SELECT = 21
_SQLITE_FUNCTION = 31
# 33 = SQLITE_RECURSIVE: raised for recursive CTEs. Legitimate read on a
# graph-shaped knowledge DB, so it is permitted alongside SELECT/READ.
_SQLITE_RECURSIVE = 33
# The only PRAGMAs the tool may run (all read-only).
_ALLOWED_READ_PRAGMAS = frozenset({"table_info", "index_list", "index_info", "database_list"})
# Functions that touch the filesystem / load code / are trigger- or FTS-internal.
_FORBIDDEN_FUNCS = frozenset(
    {"load_extension", "readfile", "writefile", "edit", "uuid", "fts5", "json_each", "json_tree"}
)


def _authorizer(action, arg1, arg2, dbname, trigger):
    """SQLite authorizer callback — allow-list only, everything else DENIED.

    Passes: SQLITE_SELECT, SQLITE_READ, SQLITE_RECURSIVE (recursive CTEs), the four
    allow-listed read-only PRAGMAs, and non-forbidden SQLITE_FUNCTION calls. Every
    other action is denied here — INSERT/UPDATE/DELETE, every CREATE_*/DROP_*
    (tables, indexes, views, triggers, virtual tables), ALTER_TABLE, REINDEX,
    ANALYZE, SAVEPOINT, TRANSACTION, ATTACH/DETACH, and any unknown/forward-compat
    code. This is the primary guard; `mode=ro` is kept as a second, independent
    layer. Protocol requires 5 params;
    only action + arg1 are read (arg2/dbname/trigger are callback scaffolding).
    """
    if action in (_SQLITE_SELECT, _SQLITE_READ, _SQLITE_RECURSIVE):
        return sqlite3.SQLITE_OK
    if action == _SQLITE_PRAGMA:
        pragma = (arg1 or "").lower() if arg1 else ""
        return sqlite3.SQLITE_OK if pragma in _ALLOWED_READ_PRAGMAS else sqlite3.SQLITE_DENY
    if action == _SQLITE_FUNCTION:
        func = (arg1 or "").lower() if arg1 else ""
        if any(f in func for f in _FORBIDDEN_FUNCS):
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def get_db_connection():
    if not SQLITE_DB.is_file():
        raise FileNotFoundError(f"KOS SQLite database not found at: {SQLITE_DB}")
    # Read-only URI is the second layer; the default-deny authorizer above is the
    # primary gate and stops DDL even if the handle were writable.
    conn = sqlite3.connect(f"file:{SQLITE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.set_authorizer(_authorizer)
    return conn


def handle_search_kos(arguments):
    query = arguments.get("query", "")
    limit = int(arguments.get("limit", 10))
    if not query:
        return {
            "content": [{"type": "text", "text": "Error: query parameter is required."}],
            "isError": True,
        }

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 优先在 documents 表里模糊查询 title 和 canonical_path
        cursor.execute(
            "SELECT doc_id, title, canonical_path, kind FROM documents WHERE title LIKE ? OR canonical_path LIKE ? LIMIT ?",
            (f"%{query}%", f"%{query}%", limit),
        )
        rows = cursor.fetchall()

        results = []
        for r in rows:
            results.append(
                {
                    "id": r["doc_id"],
                    "title": r["title"],
                    "path": r["canonical_path"],
                    "type": r["kind"],
                }
            )

        conn.close()
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {"query": query, "matches": results},
                        ensure_ascii=False,
                        indent=2,
                    ),
                }
            ]
        }
    except (sqlite3.Error, json.JSONDecodeError, OSError) as e:
        return {
            "content": [{"type": "text", "text": f"Database error: {type(e).__name__}: {e!s}"}],
            "isError": True,
        }


def handle_get_document(arguments):
    doc_id = arguments.get("id")
    doc_path = arguments.get("path")
    if not doc_id and not doc_path:
        return {
            "content": [{"type": "text", "text": "Error: id or path parameter is required."}],
            "isError": True,
        }

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if doc_id:
            cursor.execute(
                "SELECT doc_id, title, canonical_path, kind, body FROM documents WHERE doc_id = ?",
                (doc_id,),
            )
        else:
            cursor.execute(
                "SELECT doc_id, title, canonical_path, kind, body FROM documents WHERE canonical_path LIKE ?",
                (f"%{doc_path}%",),
            )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return {
                "content": [{"type": "text", "text": "Document not found."}],
                "isError": True,
            }

        doc_data = {
            "id": row["doc_id"],
            "title": row["title"],
            "path": row["canonical_path"],
            "type": row["kind"],
            "content_preview": row["body"][:2000] if row["body"] else "",
        }
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(doc_data, ensure_ascii=False, indent=2),
                }
            ]
        }
    except (sqlite3.Error, json.JSONDecodeError, OSError) as e:
        return {
            "content": [{"type": "text", "text": f"Database error: {type(e).__name__}: {e!s}"}],
            "isError": True,
        }


def handle_list_entities(arguments):
    limit = int(arguments.get("limit", 20))
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, type, properties FROM kos_entities LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()

        entities = []
        for r in rows:
            entities.append(
                {
                    "id": r["id"],
                    "name": r["name"],
                    "type": r["type"],
                    "properties": json.loads(r["properties"]) if r["properties"] else {},
                }
            )
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(entities, ensure_ascii=False, indent=2),
                }
            ]
        }
    except (sqlite3.Error, json.JSONDecodeError, OSError) as e:
        return {
            "content": [{"type": "text", "text": f"Database error: {type(e).__name__}: {e!s}"}],
            "isError": True,
        }


def handle_query_custom_sql(arguments):
    sql = arguments.get("sql", "")
    if not sql:
        return {
            "content": [{"type": "text", "text": "Error: sql parameter is required."}],
            "isError": True,
        }

    # 写操作由 get_db_connection() 内挂载的 SQLite authorizer 拦截
    # (ADR-0127 Finding 3.1, 2026-10-06 改为 default-deny): 只放行 SELECT / READ /
    # 四个只读 PRAGMA / 非敏感函数; 其余全部拒绝 —— 含 INSERT/UPDATE/DELETE 与
    # 所有 CREATE_*/DROP_*/ALTER_TABLE/REINDEX/ANALYZE/SAVEPOINT/TRANSACTION/
    # ATTACH/DETACH。`mode=ro` 仅作第二层。这里不再做子串黑名单 —— 它按文本子串
    # 匹配, 会把 SELECT created_at FROM documents 这类合法读误判为写操作。
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        conn.close()

        results = [dict(r) for r in rows]
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(results, ensure_ascii=False, indent=2),
                }
            ]
        }
    except (sqlite3.Error, json.JSONDecodeError, OSError) as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"SQL execution error: {type(e).__name__}: {e!s}",
                }
            ],
            "isError": True,
        }


# MCP Server 映射表
TOOLS = {
    "search_kos": {
        "description": "模糊检索 KOS 知识图谱中的文章、文件和代码主题",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索关键词，如 '织星', '治理'",
                },
                "limit": {
                    "type": "integer",
                    "description": "限制返回结果条数，默认 10",
                },
            },
            "required": ["query"],
        },
        "handler": handle_search_kos,
    },
    "get_document": {
        "description": "获取特定 KOS 知识库文档的内容或属性预览",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "文档的唯一 ID"},
                "path": {"type": "string", "description": "文档的部分或全部路径"},
            },
        },
        "handler": handle_get_document,
    },
    "list_entities": {
        "description": "列出 KOS 注册的全部实体模型 (如 cognitive_framework, process)",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "限制返回结果条数，默认 20"}},
        },
        "handler": handle_list_entities,
    },
    "query_custom_sql": {
        "description": "对 KOS 索引数据库执行底层的只读 SQL 查询",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "只读 SQL 查询语句, 如 'SELECT COUNT(*) FROM documents'",
                }
            },
            "required": ["sql"],
        },
        "handler": handle_query_custom_sql,
    },
}


def main():
    # 强制将 stdout 设为无缓冲
    sys.stdout.reconfigure(line_buffering=True)

    # 循环读取 stdin
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = request.get("id")
        method = request.get("method")

        # 仅处理带有 id 的 JSON-RPC 请求
        if req_id is None:
            continue

        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "mcp-server-kos", "version": "1.0.0"},
                },
            }
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")

        elif method == "tools/list":
            tools_list = []
            for name, details in TOOLS.items():
                tools_list.append(
                    {
                        "name": name,
                        "description": details["description"],
                        "inputSchema": details["inputSchema"],
                    }
                )
            response = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools_list}}
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")

        elif method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if tool_name in TOOLS:
                handler = TOOLS[tool_name]["handler"]
                result = handler(arguments)
                response = {"jsonrpc": "2.0", "id": req_id, "result": result}
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Tool '{tool_name}' not found.",
                    },
                }
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")

        else:
            # 兜底返回错误
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' not found or not implemented.",
                },
            }
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
