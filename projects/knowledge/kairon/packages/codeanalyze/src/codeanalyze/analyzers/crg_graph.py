"""CRG 知识图谱查询 — 直接查询 Tree-sitter SQLite 数据库。

提供 CodeGraph-style 的 MCP 查询能力：
- search: 搜索符号
- context: 入口点 + 相关符号
- callers: 上游调用链
- callees: 下游调用链
- files: 文件结构
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def _get_db_path(repo_path: str = ".") -> str | None:
    """查找 CRG SQLite 数据库路径。"""
    p = Path(repo_path).resolve()
    candidates = [
        p / ".code-review-graph" / "graph.db",
        p / ".codegraph" / "graph.db",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def _connect(repo_path: str = ".") -> sqlite3.Connection | None:
    db = _get_db_path(repo_path)
    if not db:
        return None
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def search(pattern: str, kind: str | None = None, repo_path: str = ".", limit: int = 20) -> list[dict[str, Any]]:
    """搜索代码符号。类似 codegraph_search。"""
    conn = _connect(repo_path)
    if not conn:
        return [{"error": "CRG database not found. Run: codeanalyze crg build"}]

    try:
        query = "SELECT * FROM nodes WHERE (name LIKE ? OR qualified_name LIKE ?)"
        params: list[str | int] = [f"%{pattern}%", f"%{pattern}%"]
        if kind:
            query += " AND kind = ?"
            params.append(kind)
        query += " LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def context(file_path: str, repo_path: str = ".") -> dict[str, Any]:
    """获取文件上下文：符号列表 + 调用关系。类似 codegraph_context。"""
    conn = _connect(repo_path)
    if not conn:
        return {"error": "CRG database not found"}

    try:
        # 文件中的符号
        nodes = conn.execute(
            "SELECT * FROM nodes WHERE file_path LIKE ? ORDER BY id",
            (f"%{file_path}%",),
        ).fetchall()

        qualified_names = [n["qualified_name"] for n in nodes if n["qualified_name"]]

        # 调用关系
        calls_in = []
        calls_out = []
        if qualified_names:
            placeholders = ",".join("?" for _ in qualified_names[:50])
            calls_in = conn.execute(
                "SELECT * FROM edges WHERE target_qualified IN (" + placeholders + ") LIMIT 50",
                qualified_names[:50],
            ).fetchall()
            calls_out = conn.execute(
                "SELECT * FROM edges WHERE source_qualified IN (" + placeholders + ") LIMIT 50",
                qualified_names[:50],
            ).fetchall()

        return {
            "nodes": [dict(n) for n in nodes],
            "callers": [dict(e) for e in calls_in],
            "callees": [dict(e) for e in calls_out],
        }
    finally:
        conn.close()


def callers(qualified_name: str, repo_path: str = ".", limit: int = 20) -> list[dict[str, Any]]:
    """查谁调用了这个符号。类似 codegraph_callers。"""
    conn = _connect(repo_path)
    if not conn:
        return [{"error": "CRG database not found"}]
    try:
        rows = conn.execute(
            "SELECT e.*, n.kind AS source_kind, n.name AS source_name "
            "FROM edges e JOIN nodes n ON e.source_qualified = n.qualified_name "
            "WHERE e.target_qualified = ? AND e.kind = 'calls' "
            "LIMIT ?",
            (qualified_name, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def callees(qualified_name: str, repo_path: str = ".", limit: int = 20) -> list[dict[str, Any]]:
    """查这个符号调用了什么。类似 codegraph_callees。"""
    conn = _connect(repo_path)
    if not conn:
        return [{"error": "CRG database not found"}]
    try:
        rows = conn.execute(
            "SELECT e.*, n.kind AS target_kind, n.name AS target_name "
            "FROM edges e JOIN nodes n ON e.target_qualified = n.qualified_name "
            "WHERE e.source_qualified = ? AND e.kind = 'calls' "
            "LIMIT ?",
            (qualified_name, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def file_structure(file_path: str, repo_path: str = ".") -> list[dict[str, Any]]:
    """查看文件结构。类似 codegraph_files。"""
    conn = _connect(repo_path)
    if not conn:
        return [{"error": "CRG database not found"}]
    try:
        rows = conn.execute(
            "SELECT id, kind, name, qualified_name, source_location "
            "FROM nodes WHERE file_path LIKE ? ORDER BY source_location",
            (f"%{file_path}%",),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def affected_tests(diff: str, repo_path: str = ".") -> list[dict[str, Any]]:
    """找受变更影响的测试文件。简化版 codegraph_affected。"""
    conn = _connect(repo_path)
    if not conn:
        return [{"error": "CRG database not found"}]
    try:
        # 找 changed files 中的符号
        changed_files = [f.strip() for f in diff.replace("...", " ").split() if f.strip() and not f.startswith("-")]
        if not changed_files:
            return [{"error": "无法解析 diff 参数。格式: --diff main...branch 或直接传文件路径"}]

        all_affected = []
        for cf in changed_files:
            symbols = conn.execute(
                "SELECT qualified_name FROM nodes WHERE file_path LIKE ? AND qualified_name IS NOT NULL",
                (f"%{cf}%",),
            ).fetchall()
            for sym in symbols:
                callers = conn.execute(
                    "SELECT DISTINCT e.file_path FROM edges e WHERE e.target_qualified = ? AND e.kind = 'calls'",
                    (sym["qualified_name"],),
                ).fetchall()
                for c in callers:
                    fp = c["file_path"]
                    if "test" in fp.lower() or "spec" in fp.lower():
                        all_affected.append({"file_path": fp, "reason": f"引用变更符号 {sym['qualified_name']}"})

        seen = set()
        unique = []
        for a in all_affected:
            if a["file_path"] not in seen:
                seen.add(a["file_path"])
                unique.append(a)
        return unique[:20]
    finally:
        conn.close()
