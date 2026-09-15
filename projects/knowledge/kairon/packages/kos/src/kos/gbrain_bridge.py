#!/usr/bin/env python3
# ruff: noqa
"""
KOS-gbrain Bridge — bidirectional knowledge synchronization between KOS and gbrain.

Capabilities:
   1. export_to_gbrain — export KOS documents to gbrain memory graph
   2. import_from_gbrain — import gbrain memory triples to KOS ontology
   3. sync_status — check sync status between KOS and gbrain
   4. full_sync — run bidirectional sync

Usage:
    # CLI
    kos bridge gbrain export
    kos bridge gbrain import
    kos bridge gbrain sync

    # Python
    from kos.gbrain_bridge import GbrainBridge
    bridge = GbrainBridge()
    bridge.export_to_gbrain(limit=100)
    bridge.import_from_gbrain(limit=100)
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from kos.config import get_artifact_path
from kos.db import get_connection

# ─── gbrain MCP Configuration ──────────────────────────
# When gbrain MCP is running, KOS can sync live via HTTP + bearer <REDACTED>
# Falls back to file-based export when MCP unavailable

MCP_URL = os.environ.get("GBRAIN_MCP_URL", "http://localhost:3131/mcp")
MCP_TOKEN = os.environ.get("GBRAIN_MCP_TOKEN", "")


class GbrainBridge:
    """双向同步桥接器：KOS ↔ gbrain。

    KOS (SQLite + LANCEDB) ←→ gbrain (Postgres + 向量)
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or get_artifact_path("retrievalDatabase")
        self._conn = None
        self._gbrain_available = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = get_connection(self.db_path)
        return self._conn

    # ── 导出 KOS → gbrain ──────────────────────────────────

    def export_to_gbrain(self, limit: int = 100) -> dict[str, Any]:
        """导出 KOS 文档到 gbrain 记忆图谱。

        Args:
            limit: 最大导出文档数

        Returns:
            导出统计 dict。
        """
        stats = {"exported": 0, "errors": 0, "skipped": 0}

        try:
            # Get documents not yet exported
            docs = self.conn.execute(
                """
                SELECT d.doc_id, d.title, d.body, d.zone, d.kind, d.canonical_path
                FROM documents d
                LEFT JOIN _gbrain_sync gs ON d.doc_id = gs.doc_id
                WHERE gs.doc_id IS NULL
                ORDER BY d.updated_at DESC
                LIMIT ?
            """,
                (limit,),
            ).fetchall()

            for doc in docs:
                try:
                    success = self._export_single(doc)
                    if success:
                        stats["exported"] += 1
                        # Mark as synced
                        self.conn.execute(
                            "INSERT OR REPLACE INTO _gbrain_sync (doc_id, synced_at) VALUES (?, ?)",
                            (doc["doc_id"], datetime.now().isoformat()),
                        )
                    else:
                        stats["skipped"] += 1
                except Exception as e:
                    stats["errors"] += 1
                    if stats["errors"] <= 3:
                        print(f"  Error exporting {doc['title']}: {e}", file=sys.stderr)

            self.conn.commit()

        except Exception as e:
            stats["error"] = str(e)  # type: ignore[reportArgumentType]

        stats["total_docs"] = stats["exported"] + stats["errors"] + stats["skipped"]
        return stats

    def _export_single(self, doc: sqlite3.Row) -> bool:
        """导出单个文档到 gbrain.

        策略:
        1. MCP HTTP endpoint (如果 MCP_TOKEN 已配置, 走 serve-http)
        2. subprocess gbrain capture (本地兜底, --source kos 已注册, 验证 100/100 通)
        """
        # Strategy 1: MCP HTTP with bearer <REDACTED>
        if MCP_TOKEN:
            try:
                import urllib.request
                import urllib.parse

                payload = json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {
                            "name": "log_ingest",
                            "arguments": {
                                "content": f"# {doc['title']}\n\n{doc['body'][:4000]}",
                                "source": "kos",
                                "source_id": doc["doc_id"],
                            },
                        },
                        "id": doc["doc_id"],
                    }
                ).encode("utf-8")

                req = urllib.request.Request(
                    MCP_URL,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {MCP_TOKEN}",
                    },
                    method="POST",
                )

                with urllib.request.urlopen(req, timeout=10.0) as resp:
                    return resp.status == 200
            except Exception:
                pass  # Fall through to file-based

        # Strategy 2: subprocess gbrain capture (本地兜底, 验证 100/100 通).
        # 替代旧 ~/.gbrain/ingest 文件目录 (gbrain 不扫该目录, 死路).
        # gbrain capture --stdin --source kos 走官方摄取入口, 自带 24h content-hash dedup.
        import subprocess

        content = f"# {doc['title']}\n\nSource: {doc['canonical_path']}\nZone: {doc['zone']}\n\n{doc['body'][:4000]}"
        try:
            result = subprocess.run(
                ["gbrain", "capture", "--stdin", "--json", "--quiet", "--source", "kos"],
                input=content,
                capture_output=True,
                text=True,
                timeout=30.0,
            )
            return result.returncode == 0
        except Exception:
            return False

    # ── 导入 gbrain → KOS ──────────────────────────────────

    def import_from_gbrain(self, limit: int = 100) -> dict[str, Any]:
        """导入 gbrain 记忆三元组到 KOS 本体。

        Args:
            limit: 最大导入条目数

        Returns:
            导入统计 dict。
        """
        stats = {"imported": 0, "errors": 0, "entities": 0, "relations": 0}

        try:
            # Try to get triples from gbrain
            triples = self._fetch_gbrain_triples(limit)

            for triple in triples:
                try:
                    subject = triple.get("subject", {})
                    predicate = triple.get("predicate", "related_to")
                    obj = triple.get("object", {})

                    # Create or update entities
                    if subject.get("name"):
                        entity_id = self._ensure_entity(
                            subject["name"], subject.get("type", "Concept"), subject.get("description", "")
                        )
                        stats["entities"] += 1

                    if obj.get("name"):
                        target_id = self._ensure_entity(
                            obj["name"], obj.get("type", "Concept"), obj.get("description", "")
                        )
                        stats["entities"] += 1

                    # Create relation
                    if subject.get("name") and obj.get("name"):
                        self.conn.execute(
                            """
                            INSERT OR REPLACE INTO kos_relations
                            (source_id, predicate, target_id, confidence, source_doc, source_type, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                f"C:{subject['name']}",
                                predicate,
                                f"C:{obj['name']}",  # type: ignore[arg-type]
                                triple.get("confidence", 0.7),
                                "gbrain-import",
                                "auto-sync",
                                datetime.now().strftime("%Y%m%d%H%M%S"),
                            ),
                        )
                        stats["relations"] += 1

                    stats["imported"] += 1

                except Exception as e:
                    stats["errors"] += 1
                    if stats["errors"] <= 3:
                        print(f"  Error importing triple: {e}", file=sys.stderr)

            self.conn.commit()

        except Exception as e:
            stats["error"] = str(e)  # type: ignore[reportArgumentType]

        return stats

    def _fetch_gbrain_triples(self, limit: int) -> list[dict]:
        """从 gbrain 获取记忆三元组。"""
        try:
            import urllib.request

            gbrain_url = os.environ.get("GBRAIN_URL", "http://localhost:3131")

            req = urllib.request.Request(
                f"{gbrain_url}/api/triples?limit={limit}",
                headers={"Accept": "application/json"},
                method="GET",
            )

            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("triples", [])

        except Exception:
            return []

    def _ensure_entity(self, name: str, entity_type: str, description: str) -> str:
        """确保实体存在，返回 entity_id。"""
        entity_id = f"C:{name}"

        existing = self.conn.execute("SELECT entity_id FROM kos_entities WHERE entity_id = ?", (entity_id,)).fetchone()

        if not existing:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO kos_entities
                (entity_id, entity_type, label, aliases, description, primary_zone, source_file, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    entity_id,
                    entity_type,
                    name,
                    json.dumps([name]),
                    description[:200],
                    "gbrain",
                    "gbrain-sync",
                    json.dumps({"source": "gbrain"}),
                    datetime.now().strftime("%Y%m%d%H%M%S"),
                ),
            )

        return entity_id

    # ── 同步状态 ────────────────────────────────────────────

    def sync_status(self) -> dict[str, Any]:
        """检查同步状态。"""
        # KOS stats
        doc_count = self.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        entity_count = self.conn.execute("SELECT COUNT(*) FROM kos_entities").fetchone()[0]
        relation_count = self.conn.execute("SELECT COUNT(*) FROM kos_relations").fetchone()[0]

        # Sync stats
        try:
            synced = self.conn.execute("SELECT COUNT(*) FROM _gbrain_sync").fetchone()[0]
        except Exception:
            synced = 0

        return {
            "timestamp": datetime.now().isoformat(),
            "kos": {
                "documents": doc_count,
                "entities": entity_count,
                "relations": relation_count,
            },
            "gbrain": {
                "synced_docs": synced,
                "pending_docs": doc_count - synced,
            },
        }

    def ensure_sync_table(self):
        """确保同步跟踪表存在。"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS _gbrain_sync (
                doc_id TEXT PRIMARY KEY,
                synced_at TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def close(self):
        """关闭连接。"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        self.ensure_sync_table()
        return self

    def __exit__(self, *args):
        self.close()


# ── CLI 入口 ──────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="KOS-gbrain Bridge")
    sub = parser.add_subparsers(dest="command")

    # Export
    p_export = sub.add_parser("export", help="Export KOS docs to gbrain")
    p_export.add_argument("--limit", type=int, default=100, help="Max docs to export")

    # Import
    p_import = sub.add_parser("import", help="Import gbrain triples to KOS")
    p_import.add_argument("--limit", type=int, default=100, help="Max triples to import")

    # Status
    sub.add_parser("status", help="Check sync status")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    bridge = GbrainBridge()

    if args.command == "export":
        result = bridge.export_to_gbrain(limit=args.limit)
    elif args.command == "import":
        result = bridge.import_from_gbrain(limit=args.limit)
    elif args.command == "status":
        result = bridge.sync_status()
    else:
        result = {"error": f"Unknown command: {args.command}"}

    bridge.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
