#!/usr/bin/env python3
"""
ecos_common — 共享基础设施模块
消除 capture_watcher/filter_scorer/ssb_client 中的重复代码

提供:
  - DB_PATH, TZ 常量
  - _now() 时间工具
  - _get_conn() 数据库连接工厂
  - CREATE_SSB_EVENTS_SQL 建表语句
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

ECOS_HOME = Path(__file__).resolve().parents[3]
SSB_DB_DIR = ECOS_HOME / "LADS" / "ssb"
SSB_DB_PATH = SSB_DB_DIR / "ecos.db"
TZ = timezone(timedelta(hours=8), "CST")

# ─── 共享 SQL ───
CREATE_SSB_EVENTS_SQL = """
CREATE TABLE IF NOT EXISTS ssb_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    seq         INTEGER NOT NULL,
    event_id    TEXT NOT NULL UNIQUE,
    timestamp   TEXT NOT NULL,
    source_zone TEXT DEFAULT '',
    source_agent TEXT NOT NULL,
    event_type  TEXT NOT NULL DEFAULT 'UNKNOWN',
    action      TEXT DEFAULT '',
    target_zone TEXT DEFAULT '',
    target_agent TEXT DEFAULT '',
    priority    INTEGER DEFAULT 0,
    status      TEXT DEFAULT 'active',
    action_required TEXT DEFAULT '',
    confidence  REAL DEFAULT 0.0,
    payload_json TEXT,
    payload_size INTEGER DEFAULT 0,
    media_path  TEXT DEFAULT '',
    schema_version TEXT DEFAULT '1.0',
    agent_signature TEXT,
    created_at  TEXT DEFAULT (datetime('now', 'localtime'))
)
"""


def now_iso() -> str:
    """ISO8601 timestamp with Asia/Shanghai timezone"""
    return datetime.now(TZ).isoformat()


def get_conn(db_path=None):
    """数据库连接工厂 — WAL模式, Row工厂"""
    SSB_DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path or SSB_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_ssb_table(conn: sqlite3.Connection = None):
    """确保 SSB 表存在"""
    close_after = conn is None
    if conn is None:
        conn = get_conn()
    conn.execute(CREATE_SSB_EVENTS_SQL)
    conn.commit()
    if close_after:
        conn.close()


# ─── 命名常量 ──────────────────────────────────────────────────────────
MAX_FILE_READ_SIZE = 5000  # filter_scorer: 文件读取字符上限
DEFAULT_QUALITY_THRESHOLD = 60  # filter_scorer: 质量通过阈值
DEFAULT_RELEVANCE_THRESHOLD = 40  # filter_scorer: 相关性通过阈值
INTEGRATE_AUTO_SCORE = 0.6  # integrate_pipeline: 自动链接阈值
INTEGRATE_CANDIDATE_SCORE = 0.4  # integrate_pipeline: 候选链接阈值
SSB_JSONL_PATH = SSB_DB_DIR / "ecos.jsonl"  # JSONL 事件流路径
"""
eCOS — 外化认知操作系统脚本集。

跨项目桥接:
- eCOS → minerva: research_push.py 调用 minerva API
- eCOS → kos: knowledge_gap.py 调用 KOS CLI
- eCOS → SharedBrain: bos_bridge.py 文件桥双向同步
"""

# Cross-project bridge markers
# eCOS → minerva: see research_push.py
# eCOS → kos: see knowledge_gap.py
# eCOS → SharedBrain: see bos_bridge.py
