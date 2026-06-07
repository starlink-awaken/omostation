#!/usr/bin/env python3
"""
File Catalog Daemon — 文件级索引引擎 (L1)

为存储卷建立文件级 SQLite 索引，支持增量扫描和 BOS URI 查询。

用法:
    python3 catalog-daemon.py --update bos://shareddisk    # 增量扫描
    python3 catalog-daemon.py --scan  bos://shareddisk     # 全量扫描
    python3 catalog-daemon.py --ls    bos://shareddisk/01  # 目录列表
    python3 catalog-daemon.py --search mp4 --limit 10       # 搜索
    python3 catalog-daemon.py --stats bos://shareddisk      # 统计

架构:
    L1: 本脚本 (ecos/scripts/catalog-daemon.py)
    L1: SQLite 数据库 (~/.ecos/catalog/{volume}.db)
    L3: CLI (ecos catalog) / MCP (catalog_search)
    L0: BOSRoute M1 (bos://catalog/**)
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

HOME = Path.home()
CATALOG_DIR = HOME / ".ecos" / "catalog"
DB_PATH = CATALOG_DIR / "{}.db"

# ── 卷 → 物理路径映射 ──
VOLUMES = {
    "shareddisk": "/Volumes/SharedDisk",
    "sharedmodel": "/Volumes/SharedModel",
    "model": "/Volumes/Model",
    "sharedwork": str(HOME / "SharedWork"),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    size INTEGER NOT NULL DEFAULT 0,
    mtime REAL NOT NULL DEFAULT 0,
    type TEXT NOT NULL DEFAULT 'file',
    ext TEXT NOT NULL DEFAULT '',
    depth INTEGER NOT NULL DEFAULT 0,
    scanned_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_files_ext ON files(ext);
CREATE INDEX IF NOT EXISTS idx_files_type ON files(type);
CREATE INDEX IF NOT EXISTS idx_files_mtime ON files(mtime);
CREATE INDEX IF NOT EXISTS idx_files_depth ON files(depth);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def _db(volume: str) -> Path:
    return CATALOG_DIR / f"{volume}.db"


def _init_db(volume: str):
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    db = _db(volume)
    conn = sqlite3.connect(str(db))
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def _bos_to_volume(bos_uri: str) -> tuple[str, str]:
    """bos://catalog/shareddisk/path → (shareddisk, /path)"""
    rest = bos_uri.replace("bos://catalog/", "", 1)
    parts = rest.split("/", 1)
    volume = parts[0]
    subpath = "/" + parts[1] if len(parts) > 1 else "/"
    return volume, subpath


def _physical_path(volume: str, subpath: str = "/") -> Path | None:
    base = VOLUMES.get(volume)
    if not base:
        return None
    p = Path(base)
    if subpath and subpath != "/":
        p = p / subpath.lstrip("/")
    return p


def scan(volume: str, full: bool = False, max_depth: int = 20) -> dict:
    """扫描卷并更新 SQLite 索引。返回统计。"""
    base = VOLUMES.get(volume)
    if not base:
        return {"error": f"未知卷: {volume}"}
    base_path = Path(base)
    if not base_path.exists():
        return {"error": f"卷不可达: {base}"}

    conn = _init_db(volume)
    now = datetime.now().isoformat()
    stats = {"total": 0, "new": 0, "updated": 0, "deleted": 0, "errors": 0}

    if full:
        # 全量扫描：清空重建
        conn.execute("DELETE FROM files")
        conn.commit()

    # 获取已索引的文件及其 mtime
    existing = {}
    if not full:
        for row in conn.execute("SELECT path, mtime FROM files"):
            existing[row[0]] = row[1]

    # Walk 文件系统
    new_paths = set()
    for root, dirs, files in os.walk(str(base_path)):
        rel_root = os.path.relpath(root, str(base_path))
        # 跳过依赖/构建目录
        SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', '.pytest_cache',
                     '.next', 'dist', 'build', 'target', '.turbo', '.cache',
                     '.local', '.DS_Store', '.obsidian'}
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        if rel_root == ".":
            rel_root = ""
        depth = rel_root.count(os.sep) + 1 if rel_root else 0
        if depth > max_depth:
            dirs.clear()
            continue

        entries = []
        for d in dirs:
            fp = os.path.join(root, d)
            try:
                st = os.lstat(fp)
            except OSError:
                stats["errors"] += 1
                continue
            rel = os.path.join(rel_root, d) if rel_root else d
            entries.append((rel, d, 0, st.st_mtime, "dir", "", depth, now))

        for f in files:
            fp = os.path.join(root, f)
            try:
                st = os.lstat(fp)
            except OSError:
                stats["errors"] += 1
                continue
            rel = os.path.join(rel_root, f) if rel_root else f
            ext = os.path.splitext(f)[1].lower()
            entries.append((rel, f, st.st_size, st.st_mtime, "file", ext, depth, now))

        for entry in entries:
            new_paths.add(entry[0])
            old_mtime = existing.get(entry[0])
            if old_mtime is None:
                stats["new"] += 1
                conn.execute(
                    "INSERT OR REPLACE INTO files (path, name, size, mtime, type, ext, depth, scanned_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    entry,
                )
            elif abs(old_mtime - entry[3]) > 0.001:
                stats["updated"] += 1
                conn.execute(
                    "UPDATE files SET size=?, mtime=?, scanned_at=? WHERE path=?",
                    (entry[2], entry[3], now, entry[0]),
                )

    # 删除不存在的文件
    if not full and existing:
        for old_path in existing:
            if old_path not in new_paths:
                conn.execute("DELETE FROM files WHERE path=?", (old_path,))
                stats["deleted"] += 1

    # 更新元数据
    total = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                 ("total_files", str(total)))
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                 ("last_scan", now))
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                 ("scan_type", "full" if full else "incremental"))
    conn.commit()
    conn.close()

    stats["total"] = total
    return stats


def ls(volume: str, subpath: str = "/") -> list[dict]:
    """列出目录内容。"""
    base_path = _physical_path(volume, subpath)
    if not base_path or not base_path.exists():
        return [{"error": f"路径不可达: {volume}{subpath}"}]

    conn = _init_db(volume)
    prefix = subpath.lstrip("/")
    if prefix:
        prefix = prefix + "/"
        rows = conn.execute(
            "SELECT path, name, size, type, ext FROM files WHERE path LIKE ? AND path != ? AND path NOT LIKE ?",
            (f"{prefix}%", prefix, f"{prefix}%/%"),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT path, name, size, type, ext FROM files WHERE depth = 1 ORDER BY type, name"
        ).fetchall()
    conn.close()
    return [{"path": r[0], "name": r[1], "size": r[2], "type": r[3], "ext": r[4]} for r in rows]


def search(volume: str, query: str, limit: int = 20) -> list[dict]:
    """搜索文件名。"""
    conn = _init_db(volume)
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT path, name, size, type, ext, mtime FROM files WHERE name LIKE ? "
        "ORDER BY size DESC LIMIT ?",
        (like, limit),
    ).fetchall()
    conn.close()
    return [{"path": r[0], "name": r[1], "size": r[2], "type": r[3], "ext": r[4], "mtime": r[5]} for r in rows]


def stats(volume: str) -> dict:
    """卷统计。"""
    base_path = _physical_path(volume)
    if not base_path or not base_path.exists():
        return {"error": f"卷不可达: {volume}"}

    conn = _init_db(volume)
    total = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    total_size = conn.execute("SELECT COALESCE(SUM(size), 0) FROM files WHERE type='file'").fetchone()[0]
    by_ext = conn.execute("SELECT ext, COUNT(*) FROM files WHERE type='file' GROUP BY ext ORDER BY COUNT(*) DESC LIMIT 15").fetchall()
    by_type = conn.execute("SELECT type, COUNT(*) FROM files GROUP BY type").fetchall()
    last_scan = conn.execute("SELECT value FROM meta WHERE key='last_scan'").fetchone()
    conn.close()

    # Real disk usage
    try:
        st = os.statvfs(str(base_path))
        disk = {
            "total_gb": round(st.f_frsize * st.f_blocks / 1e9, 1),
            "free_gb": round(st.f_frsize * st.f_bfree / 1e9, 1),
            "used_pct": round((1 - st.f_bfree / st.f_blocks) * 100, 1),
        }
    except:
        disk = {"error": "不可达"}

    return {
        "volume": volume,
        "path": str(base_path),
        "files": total,
        "total_size_gb": round(total_size / 1e9, 2),
        "disk": disk,
        "by_type": dict(by_type),
        "top_extensions": [{"ext": r[0] or "(无)", "count": r[1]} for r in by_ext[:10]],
        "last_scan": last_scan[0] if last_scan else None,
    }


# ── CLI ──

def main():
    parser = argparse.ArgumentParser(description="文件目录引擎")
    parser.add_argument("--scan", metavar="VOLUME", help="全量扫描卷 (bos://catalog/xxx)")
    parser.add_argument("--update", metavar="VOLUME", help="增量扫描卷")
    parser.add_argument("--ls", metavar="BOS_URI", help="列出目录")
    parser.add_argument("--search", metavar="QUERY", help="搜索文件")
    parser.add_argument("--volume", default="shareddisk", help="搜索的卷 (默认 shareddisk)")
    parser.add_argument("--stats", metavar="VOLUME", help="卷统计")
    parser.add_argument("--limit", type=int, default=20, help="结果限制")
    parser.add_argument("--max-depth", type=int, default=15, help="最大扫描深度")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    result = None

    if args.scan:
        vol, _ = _bos_to_volume(f"bos://catalog/{args.scan}")
        result = scan(vol, full=True, max_depth=args.max_depth)
    elif args.update:
        vol, _ = _bos_to_volume(f"bos://catalog/{args.update}")
        result = scan(vol, full=False, max_depth=args.max_depth)
    elif args.ls:
        vol, sub = _bos_to_volume(args.ls)
        result = ls(vol, sub)
    elif args.search:
        result = search(args.volume, args.search, args.limit)
    elif args.stats:
        vol, _ = _bos_to_volume(f"bos://catalog/{args.stats}")
        result = stats(vol)
    else:
        parser.print_help()
        return

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif isinstance(result, list):
        if not result:
            print("(空)")
        elif "error" in result[0]:
            print(f"❌ {result[0]['error']}")
        else:
            for item in result:
                if item["type"] == "dir":
                    print(f"  📁 {item['name']:30s}")
                else:
                    sz = item.get("size", 0)
                    if sz > 1e9:
                        sz_str = f"{sz/1e9:.1f}GB"
                    elif sz > 1e6:
                        sz_str = f"{sz/1e6:.1f}MB"
                    else:
                        sz_str = f"{sz/1e3:.0f}KB"
                    print(f"  📄 {item['name']:30s} {sz_str:>8s}")
    elif isinstance(result, dict):
        if "error" in result:
            print(f"❌ {result['error']}")
        else:
            for k, v in result.items():
                print(f"  {k:20s} {v}")


if __name__ == "__main__":
    main()
