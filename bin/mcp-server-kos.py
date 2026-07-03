#!/usr/bin/env python3
"""0-Dependency Python stdin/stdout MCP Server for KOS (Knowledge Operating System) SQLite index."""
import sys
import json
import sqlite3
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
SQLITE_DB = WORKSPACE / "kos" / "kos-index.sqlite"


def get_db_connection():
    if not SQLITE_DB.is_file():
        raise FileNotFoundError(f"KOS SQLite database not found at: {SQLITE_DB}")
    # 以只读模式且支持 URI 打开数据库以确保线程和进程安全
    conn = sqlite3.connect(f"file:{SQLITE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    # ADR-0127 Finding 3.1 (P1 安全): SQLite set_authorizer 拦截写/危险操作
    # 仅 SELECT / PRAGMA (read-only 子集) / 函数调用, 拒 INSERT/UPDATE/DELETE/
    # ATTACH/load_extension/写 PRAGMA 等. 配合关键词黑名单做双层防御.
    def _authorizer(action, arg1, arg2, dbname, trigger):
        # SQLite authorizer callback 协议要求 5 个参数 (action code, 2 args, dbname, trigger).
        # 本实现只用 action + arg1 (PRAGMA / function 名检查). arg2 / dbname / trigger 不读
        # 属正常回调接口预留.
        # SQLite authorizer action codes: SQLITE_INSERT=18, UPDATE=23, DELETE=9, ATTACH=24, DETACH=25,
        #                PRAGMA=19 (19=read, 20=write -- arg1 是 pragma name)
        if action in (18, 23, 9, 24, 25):  # INSERT/UPDATE/DELETE/ATTACH/DETACH
            return sqlite3.SQLITE_DENY
        if action == 19:  # PRAGMA
            # 仅允许 read-only PRAGMA (table_info / index_list / index_info / database_list)
            pragma = (arg1 or "").lower() if arg1 else ""
            allowed_pragmas = {"table_info", "index_list", "index_info", "database_list"}
            if pragma not in allowed_pragmas:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        # SQLITE_FUNCTION 31: 拒 load_extension / readfile / writefile 等敏感函数,
        # 但允许多数常用聚合/字符函数 (COUNT / SUM / GROUP_CONCAT / SUBSTR / LIKE 等).
        if action == 31:  # SQLITE_FUNCTION
            func = (arg1 or "").lower() if arg1 else ""
            forbidden_funcs = {
                "load_extension", "readfile", "writefile", "edit", "uuid",
                "fts5", "json_each", "json_tree",  # 写 OS / 触发器相关
            }
            if any(f in func for f in forbidden_funcs):
                return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK  # SELECT 及其余读操作允许
    conn.set_authorizer(_authorizer)
    return conn


def handle_search_kos(arguments):
    query = arguments.get("query", "")
    limit = int(arguments.get("limit", 10))
    if not query:
        return {"content": [{"type": "text", "text": "Error: query parameter is required."}], "isError": True}

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 优先在 documents 表里模糊查询 title 和 path
        cursor.execute(
            "SELECT id, title, path, type FROM documents WHERE title LIKE ? OR path LIKE ? LIMIT ?",
            (f"%{query}%", f"%{query}%", limit)
        )
        rows = cursor.fetchall()
        
        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "title": r["title"],
                "path": r["path"],
                "type": r["type"]
            })
            
        conn.close()
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({"query": query, "matches": results}, ensure_ascii=False, indent=2)
            }]
        }
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Database error: {str(e)}"}], "isError": True}


def handle_get_document(arguments):
    doc_id = arguments.get("id")
    doc_path = arguments.get("path")
    if not doc_id and not doc_path:
        return {"content": [{"type": "text", "text": "Error: id or path parameter is required."}], "isError": True}

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if doc_id:
            cursor.execute("SELECT id, title, path, type, content FROM documents WHERE id = ?", (doc_id,))
        else:
            cursor.execute("SELECT id, title, path, type, content FROM documents WHERE path LIKE ?", (f"%{doc_path}%",))
            
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {"content": [{"type": "text", "text": "Document not found."}], "isError": True}
            
        doc_data = {
            "id": row["id"],
            "title": row["title"],
            "path": row["path"],
            "type": row["type"],
            "content_preview": row["content"][:2000] if row["content"] else ""
        }
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(doc_data, ensure_ascii=False, indent=2)
            }]
        }
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Database error: {str(e)}"}], "isError": True}


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
            entities.append({
                "id": r["id"],
                "name": r["name"],
                "type": r["type"],
                "properties": json.loads(r["properties"]) if r["properties"] else {}
            })
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(entities, ensure_ascii=False, indent=2)
            }]
        }
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Database error: {str(e)}"}], "isError": True}


def handle_query_custom_sql(arguments):
    sql = arguments.get("sql", "")
    if not sql:
        return {"content": [{"type": "text", "text": "Error: sql parameter is required."}], "isError": True}
        
    # 严格的写拦截安全校验
    forbidden_keywords = {"insert", "update", "delete", "drop", "alter", "create", "replace", "vacuum"}
    sql_lower = sql.lower()
    for kw in forbidden_keywords:
        if kw in sql_lower:
            return {"content": [{"type": "text", "text": f"Security violation: Write operation '{kw}' is prohibited."}], "isError": True}
            
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        conn.close()
        
        results = [dict(r) for r in rows]
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(results, ensure_ascii=False, indent=2)
            }]
        }
    except Exception as e:
        return {"content": [{"type": "text", "text": f"SQL execution error: {str(e)}"}], "isError": True}


# MCP Server 映射表
TOOLS = {
    "search_kos": {
        "description": "模糊检索 KOS 知识图谱中的文章、文件和代码主题",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索关键词，如 '织星', '治理'"},
                "limit": {"type": "integer", "description": "限制返回结果条数，默认 10"}
            },
            "required": ["query"]
        },
        "handler": handle_search_kos
    },
    "get_document": {
        "description": "获取特定 KOS 知识库文档的内容或属性预览",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "文档的唯一 ID"},
                "path": {"type": "string", "description": "文档的部分或全部路径"}
            }
        },
        "handler": handle_get_document
    },
    "list_entities": {
        "description": "列出 KOS 注册的全部实体模型 (如 cognitive_framework, process)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "限制返回结果条数，默认 20"}
            }
        },
        "handler": handle_list_entities
    },
    "query_custom_sql": {
        "description": "对 KOS 索引数据库执行底层的只读 SQL 查询",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "只读 SQL 查询语句, 如 'SELECT COUNT(*) FROM documents'"}
            },
            "required": ["sql"]
        },
        "handler": handle_query_custom_sql
    }
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
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "mcp-server-kos",
                        "version": "1.0.0"
                    }
                }
            }
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            
        elif method == "tools/list":
            tools_list = []
            for name, details in TOOLS.items():
                tools_list.append({
                    "name": name,
                    "description": details["description"],
                    "inputSchema": details["inputSchema"]
                })
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": tools_list
                }
            }
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            
        elif method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if tool_name in TOOLS:
                handler = TOOLS[tool_name]["handler"]
                result = handler(arguments)
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": result
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Tool '{tool_name}' not found."
                    }
                }
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            
        else:
            # 兜底返回错误
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' not found or not implemented."
                }
            }
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
