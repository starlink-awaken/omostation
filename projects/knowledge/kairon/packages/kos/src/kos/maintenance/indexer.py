#!/usr/bin/env python3
# ruff: noqa
"""
KOS Incremental Indexer — 增量索引服务

检测文件变更并增量更新 SQLite FTS5 + LanceDB 向量索引。

Usage:
    from kos.maintenance.indexer import IncrementalIndexer

    indexer = IncrementalIndexer()
    result = indexer.run()  # Run incremental update

    # Or via CLI:
    # kos index --incremental
    # kos index --watch     # continuous watching
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from kos.config import get_artifact_path
from kos.db import get_connection
from kos.semantic import _chunk_text


class IncrementalIndexer:
    """增量索引器。

    检测文件系统变更，仅对新增/变更的文档重新索引。
    使用 SHA-256 指纹对比判断文件是否变更。
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or get_artifact_path("retrievalDatabase")
        self.now = datetime.now().strftime("%Y%m%d%H%M%S")
        self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = get_connection(self.db_path)
        return self._conn

    # ── 核心 API ────────────────────────────────────────────

    def run(self, embed: bool = True, force_embed: bool = False) -> dict[str, Any]:
        """运行增量索引更新。

        Args:
            embed: 是否更新向量索引 (False 仅更新 FTS5)

        Returns:
            更新统计 dict。
        """
        t0 = time.time()
        stats = {
            "scanned": 0,
            "added": 0,
            "updated": 0,
            "removed": 0,
            "unchanged": 0,
            "errors": 0,
        }

        try:
            # 1. 获取所有域配置
            zones = self._get_zones()

            # 2. 扫描每个域的文件
            for zone_id, zone_config in zones.items():
                zone_stats = self._scan_zone(zone_id, zone_config)
                for k in stats:
                    stats[k] += zone_stats.get(k, 0)

            # 3. 清理已删除文档
            stats["removed"] += self._cleanup_deleted()

            # 4. 更新向量索引 (如果启用). force_embed 回灌模式忽略 added/updated 触发.
            if embed and (force_embed or stats["added"] > 0 or stats["updated"] > 0):
                vector_stats = self._update_vector_index(full=force_embed)
                stats["vector"] = vector_stats  # type: ignore[reportArgumentType]

        except Exception as e:
            stats["errors"] += 1
            stats["error_msg"] = str(e)  # type: ignore[reportArgumentType]

        stats["elapsed_seconds"] = round(time.time() - t0, 1)  # type: ignore[reportArgumentType]
        stats["timestamp"] = self.now  # type: ignore[reportArgumentType]
        return stats

    # ── 域扫描 ──────────────────────────────────────────────

    def _get_zones(self) -> dict[str, dict]:
        """获取所有 indexable 域配置。"""
        from kos.config import get_workspace_manifest

        manifest = get_workspace_manifest()
        zones = manifest.get("zones", {})
        return {zid: zcfg for zid, zcfg in zones.items() if zcfg.get("indexable") and zcfg.get("authoritative")}

    def _scan_zone(self, zone_id: str, zone_config: dict) -> dict[str, int]:
        """扫描单个域的文件变更。"""
        stats = {"scanned": 0, "added": 0, "updated": 0, "removed": 0, "unchanged": 0, "errors": 0}

        # 获取扫描根目录
        scan_roots = zone_config.get("path", "")
        if not scan_roots:
            return stats

        scan_path = Path(scan_roots).expanduser().resolve()
        if not scan_path.exists():
            return stats

        # 获取文件模式
        file_patterns = zone_config.get("filePatterns", ["*.md", "*.txt", "*.json"])
        exclude_prefixes = zone_config.get("excludePrefixes", [])

        # 获取已索引文件的最后时间戳 (用于快速跳过)
        last_index = self.conn.execute(
            "SELECT MAX(last_indexed) FROM file_fingerprints WHERE zone = ?", (zone_id,)
        ).fetchone()
        last_index_ts = last_index[0] if last_index and last_index[0] else "20000101000000"

        # 扫描文件
        for root, dirs, files in os.walk(str(scan_path)):
            # 过滤排除目录
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and not any(d == ep or d.startswith(ep + os.sep) for ep in exclude_prefixes)
            ]

            for fname in files:
                if fname.startswith("."):
                    continue

                # 检查文件模式
                if not any(self._match_pattern(fname, p) for p in file_patterns):
                    continue

                fpath = Path(root) / fname
                rel_path = str(fpath.relative_to(scan_path))
                stats["scanned"] += 1

                try:
                    # 快速检查: mtime 是否晚于上次索引
                    fmtime = datetime.fromtimestamp(fpath.stat().st_mtime).strftime("%Y%m%d%H%M%S")
                    if fmtime <= last_index_ts:
                        # 文件未修改，跳过
                        stats["unchanged"] += 1
                        continue

                    # 计算文件指纹
                    fhash = self._compute_hash(fpath)

                    # 检查是否已索引
                    existing = self.conn.execute(
                        "SELECT sha256_hash FROM file_fingerprints WHERE canonical_path = ?",
                        (f"{zone_id}::{rel_path}",),
                    ).fetchone()

                    if not existing:
                        # 新增文档
                        self._index_document(fpath, zone_id, rel_path, fhash, fmtime)
                        stats["added"] += 1
                    elif existing["sha256_hash"] != fhash:
                        # 文档变更
                        self._update_document(fpath, zone_id, rel_path, fhash, fmtime)
                        stats["updated"] += 1
                    else:
                        stats["unchanged"] += 1

                except Exception as e:
                    stats["errors"] += 1
                    if stats["errors"] <= 3:
                        print(f"  Error indexing {fpath}: {e}", file=sys.stderr)

        return stats

    def _index_document(self, fpath: Path, zone_id: str, rel_path: str, fhash: str, fmtime: str):
        """索引新文档。"""
        canonical = f"kos::{zone_id}::{rel_path}"
        doc_id = hashlib.sha1(canonical.encode()).hexdigest()

        # 提取文本
        text = self._extract_text(fpath)
        if not text.strip():
            return

        title = self._extract_title(text, fpath.stem)
        body = text[:8000]

        # 插入 FTS5
        self.conn.execute("DELETE FROM documents WHERE doc_id=?", (doc_id,))
        self.conn.execute("DELETE FROM documents_fts WHERE doc_id=?", (doc_id,))
        self.conn.execute(
            """INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                doc_id,
                title,
                "note",
                zone_id,
                "active",
                "auto-index",
                "",
                self.now,
                self.now,
                "working",
                "active",
                "pending",
                "1.0",
                canonical,
                str(fpath),
                "managed",
                json.dumps({"source_path": str(fpath)}),
                body,
                len(body.encode("utf-8")),
                fmtime,
            ),
        )
        self.conn.execute(
            "INSERT INTO documents_fts (doc_id,title,body,tags,canonical_path) VALUES (?,?,?,?,?)",
            (doc_id, title, body, "", canonical),
        )

        # 记录指纹
        self.conn.execute(
            "INSERT OR REPLACE INTO file_fingerprints VALUES (?,?,?,?,?,?,?,?)",
            (canonical, zone_id, fhash, len(body.encode("utf-8")), fmtime, self.now, None, fpath.suffix),
        )
        self.conn.commit()

    def _update_document(self, fpath: Path, zone_id: str, rel_path: str, fhash: str, fmtime: str):
        """更新已索引文档。"""
        canonical = f"kos::{zone_id}::{rel_path}"
        doc_id = hashlib.sha1(canonical.encode()).hexdigest()

        # 提取文本
        text = self._extract_text(fpath)
        if not text.strip():
            return

        title = self._extract_title(text, fpath.stem)
        body = text[:8000]

        # 更新 FTS5
        self.conn.execute("DELETE FROM documents WHERE doc_id=?", (doc_id,))
        self.conn.execute("DELETE FROM documents_fts WHERE doc_id=?", (doc_id,))
        self.conn.execute(
            """INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                doc_id,
                title,
                "note",
                zone_id,
                "active",
                "auto-index",
                "",
                self.now,
                self.now,
                "working",
                "active",
                "pending",
                "1.0",
                canonical,
                str(fpath),
                "managed",
                json.dumps({"source_path": str(fpath)}),
                body,
                len(body.encode("utf-8")),
                fmtime,
            ),
        )
        self.conn.execute(
            "INSERT INTO documents_fts (doc_id,title,body,tags,canonical_path) VALUES (?,?,?,?,?)",
            (doc_id, title, body, "", canonical),
        )

        # 更新指纹
        self.conn.execute(
            """UPDATE file_fingerprints SET sha256_hash=?, file_size=?, file_mtime=?,
               last_indexed=?, absent_since=NULL WHERE canonical_path=?""",
            (fhash, len(body.encode("utf-8")), fmtime, self.now, canonical),
        )
        self.conn.commit()

    # ── 向量索引更新 ───────────────────────────────────────

    def _update_vector_index(self, full: bool = False) -> dict[str, int]:
        """更新向量索引.

        Args:
            full: True=回灌全量 (LIMIT 5000, 忽略时间窗口, 历史文档回灌);
                  False=最近1小时增量 (默认).
        """
        stats = {"embedded": 0, "errors": 0}

        try:
            from kos.semantic import _embed_texts_st

            # 获取需要向量化的文档 (full=回灌全量; 默认=最近增量)
            if full:
                docs = self.conn.execute(
                    "SELECT doc_id, title, body FROM documents WHERE body != '' ORDER BY updated_at DESC LIMIT 5000"
                ).fetchall()
            else:
                docs = self.conn.execute("""
                    SELECT doc_id, title, body FROM documents
                    WHERE updated_at >= datetime('now', '-1 hour')
                    AND body != ''
                    LIMIT 100
                """).fetchall()

            if not docs:
                return stats

            all_texts = []
            all_doc_ids = []

            for d in docs:
                text = f"{d['title'] or ''}\n{d['body'] or ''}"
                chunks = _chunk_text(text)
                if not chunks:
                    chunks = [d["title"] or ""]
                for chunk in chunks:
                    all_texts.append(chunk[:2000])
                    all_doc_ids.append(d["doc_id"])

            if not all_texts:
                return stats

            # 本地嵌入
            embeddings = _embed_texts_st(all_texts)

            # 存储到 LanceDB
            import lancedb

            lancedb_dir = Path(self.db_path).parent / "vectors"
            db = lancedb.connect(str(lancedb_dir))

            table_data = []
            for i, doc_id in enumerate(all_doc_ids):
                if i < len(embeddings) and embeddings[i]:
                    table_data.append(
                        {
                            "vector": embeddings[i],
                            "doc_id": doc_id,
                            "chunk_idx": i,
                        }
                    )

            # 写入 LanceDB. 用 try open/except create 替代 `"x" in db.list_tables()`
            # 判断 — list_tables 返回 ListTablesResponse (非 list), `in` 判断失效
            # (Pyright L334 警告, 致 "Table already exists" 错). mode=overwrite 清脏状态.
            if table_data:
                try:
                    tbl = db.open_table("kos_documents")
                    tbl.add(table_data)
                except Exception:
                    db.create_table("kos_documents", table_data, mode="overwrite")

            stats["embedded"] = len(table_data)

        except Exception as e:
            stats["errors"] += 1
            stats["error_msg"] = str(e)  # type: ignore[reportArgumentType]

        return stats

    # ── 清理 ────────────────────────────────────────────────

    def _cleanup_deleted(self) -> int:
        """清理已删除文档的索引。"""
        # 标记 fingerprints 中但文件不存在的为 absent
        rows = self.conn.execute(
            "SELECT canonical_path, zone FROM file_fingerprints WHERE absent_since IS NULL"
        ).fetchall()

        removed = 0
        for row in rows:
            canonical = row["canonical_path"]
            # 从 canonical_path 提取文件路径
            # 格式: kos::zone::relative_path
            parts = canonical.split("::", 2)
            if len(parts) >= 3:
                # 尝试找到实际文件路径
                zone_path = parts[2]
                # 简化处理: 检查 fingerprint 是否超过 7 天未更新
                fp = self.conn.execute(
                    "SELECT last_indexed FROM file_fingerprints WHERE canonical_path=?", (canonical,)
                ).fetchone()
                if fp and fp["last_indexed"]:
                    try:
                        last = datetime.strptime(fp["last_indexed"], "%Y%m%d%H%M%S")
                        if (datetime.now() - last).days > 7:
                            self.conn.execute(
                                "UPDATE file_fingerprints SET absent_since=? WHERE canonical_path=?",
                                (self.now, canonical),
                            )
                            removed += 1
                    except ValueError:
                        pass

        self.conn.commit()
        return removed

    # ── 工具方法 ────────────────────────────────────────────

    @staticmethod
    def _compute_hash(file_path: Path) -> str:
        """计算文件 SHA-256 指纹 (前 64KB + 文件大小)。"""
        h = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                h.update(f.read(65536))
        except Exception:
            return "ERROR"
        h.update(str(file_path.stat().st_size).encode())
        return h.hexdigest()

    @staticmethod
    def _match_pattern(filename: str, pattern: str) -> bool:
        """简单的 glob 匹配。"""
        import fnmatch

        return fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(filename.lower(), pattern.lower())

    @staticmethod
    def _extract_text(fpath: Path) -> str:
        """从文件提取文本。"""
        try:
            if fpath.suffix.lower() in (".md", ".txt", ".markdown", ".mdx"):
                return fpath.read_text(encoding="utf-8")[:8000]
            elif fpath.suffix.lower() == ".json":
                data = json.loads(fpath.read_text(encoding="utf-8"))
                return json.dumps(data, ensure_ascii=False)[:8000]
            else:
                return fpath.read_text(encoding="utf-8", errors="ignore")[:8000]
        except Exception:
            return ""

    @staticmethod
    def _extract_title(text: str, fallback: str) -> str:
        """从文本提取标题。"""
        import re

        m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        if m:
            return m.group(1).strip()
        return fallback

    def close(self):
        """关闭数据库连接。"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ── CLI 入口 ──────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="KOS Incremental Indexer")
    parser.add_argument("--no-embed", action="store_true", help="Skip vector index update")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon (loop until killed)")
    parser.add_argument("--interval", type=int, default=300, help="Daemon loop interval seconds (default 300)")
    parser.add_argument(
        "--full-embed", action="store_true", help="Force embed all docs (backfill, ignores added/updated trigger)"
    )
    args = parser.parse_args()

    indexer = IncrementalIndexer()
    if args.daemon:
        # 守护模式: 循环 run 直到被 kill. daemon.py DAEMONS["indexer"] 传 --daemon 依赖此模式.
        while True:
            try:
                result = indexer.run(embed=not args.no_embed, force_embed=args.full_embed)
                print(json.dumps(result, ensure_ascii=False), flush=True)
            except Exception as e:  # noqa: BLE001
                print(json.dumps({"error": str(e)}), flush=True)
            time.sleep(args.interval)
    else:
        result = indexer.run(embed=not args.no_embed, force_embed=args.full_embed)
        indexer.close()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
