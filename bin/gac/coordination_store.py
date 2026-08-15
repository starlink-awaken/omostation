#!/usr/bin/env python3
"""coordination_store.py — BET-Y1Q1-T1-05A 共享运行时协调层 (shadow).

跨 clone 的任务认领 / agent 心跳 / 跨 agent 消息, 落在所有 checkout 之外的
共享 SQLite (WAL):
    ~/agents/_shared/runtime/coordination.sqlite3

shadow 语义: 文件锁 (.omo/_delivery/) 仍是权威判定源; 本 store 是镜像,
写入失败只落 shadow_events, 不阻断主流程. warning/fail 阶段翻开关时,
判断逻辑不变, 只改处置 (KISS + 可替换访问层, daemon 化只差一层封装).

设计参照:
  - projects/omlxc/src/omlxc/storage/database.py  (PRAGMA busy_timeout=5000
    + journal_mode=WAL + PRAGMA user_version 版本迁移 + StorageDegradedError
    fail-closed)
  - bin/delivery/shared_context_store.py          (幂等 executescript 风格)

用法 (sibling import):
    sys.path.insert(0, str(ROOT / "bin" / "gac"))
    import coordination_store as cs
    cs.claim_resource("branch", "work/foo", owner="session-a", ttl_hours=24)
"""
from __future__ import annotations

import calendar
import fcntl
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

# ── 路径 ─────────────────────────────────────────────────────────────

DEFAULT_DB_PATH = Path.home() / "agents" / "_shared" / "runtime" / "coordination.sqlite3"
ENV_DB_PATH = "OMO_COORDINATION_DB"  # 测试用: 指向 tmp_path 下的 DB

SCHEMA_VERSION = 1
STALE_AFTER_TICKS = 3  # stale 判定 <= 3 个心跳周期 (tick 5min → 15min)

# ── 异常 ─────────────────────────────────────────────────────────────


class CoordinationStoreError(RuntimeError):
    """store 操作失败 (DB 打不开 / 版本超前). shadow 挂点捕获后落事件."""

    def __init__(self, message: str, *, db_path: str = ""):
        super().__init__(message)
        self.db_path = db_path


# ── dataclass ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Claim:
    resource_type: str
    resource_id: str
    owner: str
    token: int
    claimed_at: str
    expires_at: str


@dataclass(frozen=True)
class Verdict:
    ok: bool
    reason: str
    current_token: int | None
    local_token: int


# ── 连接工厂 (单点; 未来 daemon 化只替换这一层) ─────────────────────


def db_path() -> Path:
    override = os.environ.get(ENV_DB_PATH)
    if override:
        return Path(override).expanduser()
    return DEFAULT_DB_PATH


def _connect(*, automatic_backup: bool = True) -> sqlite3.Connection:
    path = db_path()
    fresh = not path.exists()
    if fresh:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CoordinationStoreError(
                f"cannot create coordination db dir: {exc}", db_path=str(path)
            ) from exc
    try:
        conn = sqlite3.connect(str(path), timeout=5.0, isolation_level=None)
    except sqlite3.Error as exc:
        raise CoordinationStoreError(
            f"cannot open coordination db: {exc}", db_path=str(path)
        ) from exc
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")  # omlxc :1347 同款
    conn.execute("PRAGMA journal_mode = WAL")   # omlxc :1349 同款
    conn.execute("PRAGMA synchronous = NORMAL")
    if fresh:
        # 懒初始化兜底: 挂点首次调用可能没走 ensure_ready(); 幂等 DDL + 版本推进
        _migrate(conn, str(path))
    if automatic_backup:
        try:
            _backup_with_connection(conn, path, max_age_h=24.0, keep=3)
        except (CoordinationStoreError, OSError, sqlite3.Error) as exc:
            # shadow fallback 不能反噬主操作；显式 --backup 仍会抛错。
            print(f"[coordination] automatic backup skipped: {exc}", file=__import__("sys").stderr)
    return conn


def _migrate(conn: sqlite3.Connection, path_str: str) -> None:
    """按 user_version 顺序跑迁移. 版本超前 → fail-closed 抛异常."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise CoordinationStoreError(
            f"schema version {version} > supported {SCHEMA_VERSION}: newer writer exists",
            db_path=path_str,
        )
    for target in sorted(MIGRATIONS):
        if version < target:
            for ddl in MIGRATIONS[target]:
                conn.execute(ddl)
            conn.execute(f"PRAGMA user_version = {target}")


# ── schema (v1) ──────────────────────────────────────────────────────
# DDL 组织为 dict + executescript, 沿用 shared_context_store.py 幂等风格.

SCHEMA_V1: dict[str, str] = {
    "claims": """
        CREATE TABLE IF NOT EXISTS claims (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          resource_type TEXT NOT NULL,
          resource_id TEXT NOT NULL,
          owner TEXT NOT NULL,
          token INTEGER NOT NULL,
          state TEXT NOT NULL DEFAULT 'active',
          claimed_at TEXT NOT NULL,
          expires_at TEXT,
          UNIQUE(resource_type, resource_id, token)
        )
    """,
    "claims_active": """
        CREATE UNIQUE INDEX IF NOT EXISTS claims_active
          ON claims(resource_type, resource_id)
          WHERE state = 'active'
    """,
    "agent_health": """
        CREATE TABLE IF NOT EXISTS agent_health (
          agent_id TEXT PRIMARY KEY,
          last_seen TEXT NOT NULL,
          status TEXT NOT NULL,
          source TEXT NOT NULL DEFAULT 'tick',
          detail_json TEXT,
          stale_after INTEGER NOT NULL DEFAULT 900
        )
    """,
    "messages": """
        CREATE TABLE IF NOT EXISTS messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts TEXT NOT NULL,
          from_agent TEXT NOT NULL,
          to_agent TEXT NOT NULL,
          msg_type TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          consumed_at TEXT
        )
    """,
    # schema-only: 承接 a2a-messages.jsonl 的字段 (from/to/type/payload/consumed),
    # shadow 阶段不接数据流 (grill Q11 裁定), warning 阶段再挂双写.
    "shadow_events": """
        CREATE TABLE IF NOT EXISTS shadow_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts TEXT NOT NULL,
          kind TEXT NOT NULL,
          resource_type TEXT,
          resource_id TEXT,
          detail_json TEXT
        )
    """,
}

MIGRATIONS: dict[int, list[str]] = {
    1: [SCHEMA_V1[k] for k in ("claims", "claims_active", "agent_health", "messages", "shadow_events")],
}


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ensure_ready() -> Path:
    """懒初始化: 建目录/DB/表, 跑版本迁移. 幂等, 任何入口先调这个."""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        _migrate(conn, str(path))
        conn.execute("COMMIT")
        return path
    finally:
        conn.close()


# ── claims: 原子认领 / 释放 / fencing ────────────────────────────────


def claim_resource(
    resource_type: str,
    resource_id: str,
    owner: str,
    ttl_hours: float = 24.0,
) -> Claim | None:
    """原子认领: BEGIN IMMEDIATE 事务内 'MAX(token)+1 WHERE 无 active claim'.

    已被 active claim 占据 → 返回 None (不抛); DB 故障 → 抛
    CoordinationStoreError, 由 shadow 挂点捕获落事件.
    """
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        now = _utc_now()
        expires_hint = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(time.time() + ttl_hours * 3600),
        )
        conn.execute(
            "UPDATE claims SET state='expired' "
            "WHERE resource_type=? AND resource_id=? AND state='active' "
            "AND expires_at IS NOT NULL AND expires_at<=?",
            (resource_type, resource_id, now),
        )
        active = conn.execute(
            "SELECT owner, token, claimed_at FROM claims "
            "WHERE resource_type=? AND resource_id=? AND state='active'",
            (resource_type, resource_id),
        ).fetchone()
        if active is not None:
            if active["owner"] == owner:
                # same-owner 幂等重取 (T1-05A drift 修复): 文件锁允许同 session
                # 重取 (reused: true), 镜像同语义 — 顺延 TTL 返回既有 claim,
                # token 不变 (不产生 mirror_drift 噪音, 不使旧 token 失效)
                conn.execute(
                    "UPDATE claims SET expires_at=? "
                    "WHERE resource_type=? AND resource_id=? AND state='active'",
                    (expires_hint, resource_type, resource_id),
                )
                conn.execute("COMMIT")
                return Claim(
                    resource_type=resource_type, resource_id=resource_id,
                    owner=owner, token=active["token"],
                    claimed_at=active["claimed_at"], expires_at=expires_hint,
                )
            conn.execute("ROLLBACK")
            return None
        token = (conn.execute(
            "SELECT COALESCE(MAX(token), 0) + 1 FROM claims WHERE resource_type=? AND resource_id=?",
            (resource_type, resource_id),
        ).fetchone()[0])
        conn.execute(
            "INSERT INTO claims (resource_type, resource_id, owner, token, state, claimed_at, expires_at) "
            "VALUES (?, ?, ?, ?, 'active', ?, ?)",
            (resource_type, resource_id, owner, token, now, expires_hint),
        )
        conn.execute("COMMIT")
        return Claim(
            resource_type=resource_type, resource_id=resource_id,
            owner=owner, token=token, claimed_at=now, expires_at=expires_hint,
        )
    finally:
        conn.close()


def active_claim(resource_type: str, resource_id: str) -> Claim | None:
    """当前 active claim (无则 None). 供复用判定与 status 用."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT owner, token, claimed_at, expires_at FROM claims "
            "WHERE resource_type=? AND resource_id=? AND state='active'",
            (resource_type, resource_id),
        ).fetchone()
        if row is None:
            return None
        return Claim(
            resource_type=resource_type, resource_id=resource_id,
            owner=row["owner"], token=row["token"],
            claimed_at=row["claimed_at"], expires_at=row["expires_at"],
        )
    finally:
        conn.close()


def release_resource(resource_type: str, resource_id: str, owner: str, token: int | None = None) -> bool:
    """对称释放: owner 匹配才释放 (state→released, 行保留作 token 历史)."""
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT id, owner, token FROM claims "
            "WHERE resource_type=? AND resource_id=? AND state='active'",
            (resource_type, resource_id),
        ).fetchone()
        if row is None or row["owner"] != owner or (token is not None and row["token"] != token):
            conn.execute("ROLLBACK")
            return False
        conn.execute(
            "UPDATE claims SET state='released' WHERE id=?", (row["id"],)
        )
        conn.execute("COMMIT")
        return True
    finally:
        conn.close()


def current_token(resource_type: str, resource_id: str) -> int:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT MAX(token) FROM claims WHERE resource_type=? AND resource_id=?",
            (resource_type, resource_id),
        ).fetchone()
        return row[0] or 0
    finally:
        conn.close()


def check_fencing(
    resource_type: str,
    resource_id: str,
    owner: str,
    local_token: int,
) -> Verdict:
    """仅 active + owner/token 精确匹配 + 未过期的 claim 通过 fencing."""
    conn = _connect()
    try:
        latest = conn.execute(
            "SELECT owner, token, state, expires_at FROM claims "
            "WHERE resource_type=? AND resource_id=? ORDER BY token DESC LIMIT 1",
            (resource_type, resource_id),
        ).fetchone()
        active = conn.execute(
            "SELECT owner, token, state, expires_at FROM claims "
            "WHERE resource_type=? AND resource_id=? AND state='active'",
            (resource_type, resource_id),
        ).fetchone()
    finally:
        conn.close()
    current = latest["token"] if latest is not None else None
    if active is None:
        state = latest["state"] if latest is not None else "missing"
        return Verdict(False, f"claim is {state}, not active", current, local_token)
    if active["expires_at"] and active["expires_at"] <= _utc_now():
        return Verdict(False, f"active claim expired at {active['expires_at']}", current, local_token)
    if active["owner"] != owner:
        return Verdict(False, f"owner mismatch: active={active['owner']} local={owner}", current, local_token)
    if active["token"] != local_token:
        return Verdict(False, f"token mismatch: active={active['token']} local={local_token}", current, local_token)
    return Verdict(True, "active owner and token match", current, local_token)


# ── agent_health: 心跳 (tick 源) ─────────────────────────────────────


def heartbeat(agent_id: str, status: str, source: str = "tick", detail: dict | None = None) -> None:
    """upsert 一行心跳. 心跳失败不炸调用方 (tick 主流程 F14 错误隔离)."""
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO agent_health (agent_id, last_seen, status, source, detail_json, stale_after) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(agent_id) DO UPDATE SET last_seen=excluded.last_seen, "
            "status=excluded.status, source=excluded.source, detail_json=excluded.detail_json",
            (agent_id, _utc_now(), status, source,
             json.dumps(detail, ensure_ascii=False) if detail else None,
             STALE_AFTER_TICKS * 300),  # tick 5min × 3
        )
    finally:
        conn.close()


def stale_agents(now_ts: float | None = None) -> list[dict]:
    """列出超过 stale_after 未心跳的 agent (供 status/观察用)."""
    now_ts = now_ts if now_ts is not None else time.time()
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT agent_id, last_seen, stale_after FROM agent_health"
        ).fetchall()
    finally:
        conn.close()
    out: list[dict] = []
    for r in rows:
        # timegm: last_seen 是 UTC 字符串, 必须按 UTC 解 (mktime 会按本地时区错位)
        seen = calendar.timegm(time.strptime(r["last_seen"], "%Y-%m-%dT%H:%M:%SZ"))
        if now_ts - seen > r["stale_after"]:
            out.append({"agent_id": r["agent_id"], "last_seen": r["last_seen"]})
    return out


# ── shadow_events: 观察 + 备份记录 ───────────────────────────────────


def emit_shadow_event(
    kind: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict | None = None,
) -> bool:
    """shadow 事件落库. 事件写入本身失败 → 尽力 stderr, 不抛 (观察面不反噬主流程)."""
    try:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO shadow_events (ts, kind, resource_type, resource_id, detail_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (_utc_now(), kind, resource_type, resource_id,
                 json.dumps(detail, ensure_ascii=False) if detail else None),
            )
            return True
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — 观察面尽力而为
        print(f"[coordination] shadow event drop: {kind}: {exc}", file=__import__('sys').stderr)
        return False


# ── 备份 / 完整性 ────────────────────────────────────────────────────


def integrity_check() -> str:
    conn = _connect()
    try:
        return conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()


def _backup_with_connection(
    conn: sqlite3.Connection,
    path: Path,
    *,
    max_age_h: float,
    keep: int,
) -> Path | None:
    """用既有连接执行备份，避免 store access → backup → store access 递归."""
    stamp = path.parent / f"{path.name}.last-backup"
    lock_path = path.parent / f"{path.name}.backup.lock"
    with lock_path.open("a+") as lock_fh:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        now = time.time()
        if stamp.exists() and now - stamp.stat().st_mtime < max_age_h * 3600:
            return None
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise CoordinationStoreError(f"integrity_check={integrity}", db_path=str(path))
        for i in range(keep - 1, 0, -1):
            src = path.parent / f"{path.name}.bak.{i}"
            dst = path.parent / f"{path.name}.bak.{i + 1}"
            if src.exists():
                src.replace(dst)
        backup = path.parent / f"{path.name}.bak.1"
        dest = sqlite3.connect(str(backup))
        try:
            conn.backup(dest)
        finally:
            dest.close()
        stamp.touch()
        conn.execute(
            "INSERT INTO shadow_events (ts, kind, detail_json) VALUES (?, 'backup_ok', ?)",
            (_utc_now(), json.dumps({"backup": str(backup)}, ensure_ascii=False)),
        )
        return backup


def maybe_backup(max_age_h: float = 24.0, keep: int = 3) -> Path | None:
    """时间戳兜底备份；普通 store access 也会安全调用同一非递归实现."""
    path = db_path()
    conn = _connect(automatic_backup=False)
    try:
        return _backup_with_connection(
            conn, path, max_age_h=max_age_h, keep=keep
        )
    finally:
        conn.close()


# ── status 快照 (CLI/测试用) ────────────────────────────────────────


def snapshot() -> dict:
    """只读快照: claims/agent_health/messages + shadow 事件计数."""
    conn = _connect()
    try:
        claims = [dict(r) for r in conn.execute(
            "SELECT resource_type, resource_id, owner, token, state, claimed_at, expires_at "
            "FROM claims ORDER BY resource_type, resource_id"
        )]
        health = []
        for row in conn.execute(
            "SELECT agent_id, last_seen, status, source, stale_after, detail_json "
            "FROM agent_health ORDER BY agent_id"
        ):
            item = dict(row)
            detail_raw = item.pop("detail_json", None)
            try:
                detail = json.loads(detail_raw) if detail_raw else {}
            except (TypeError, json.JSONDecodeError):
                detail = {}
            attestation = detail.get("runtime_attestation")
            if isinstance(attestation, dict):
                item["runtime_attestation"] = attestation
            health.append(item)
        messages = [dict(r) for r in conn.execute(
            "SELECT id, ts, from_agent, to_agent, msg_type, consumed_at FROM messages ORDER BY id DESC LIMIT 20"
        )]
        events = {r[0]: r[1] for r in conn.execute(
            "SELECT kind, COUNT(*) FROM shadow_events GROUP BY kind"
        )}
    finally:
        conn.close()
    return {
        "db_path": str(db_path()),
        "schema_version": SCHEMA_VERSION,
        "claims": claims,
        "agent_health": health,
        "messages": messages,
        "shadow_events": events,
        "stale_agents": stale_agents(),
    }


def _main() -> int:
    """薄 CLI 壳: crontab 日备入口 (runbook §4 引用)."""
    import argparse

    ap = argparse.ArgumentParser(description="coordination store maintenance")
    ap.add_argument("--backup", action="store_true", help="integrity check + backup + 轮转")
    ap.add_argument("--status", action="store_true", help="JSON 快照")
    args = ap.parse_args()
    if args.backup:
        ensure_ready()
        bak = maybe_backup(max_age_h=0)  # cron 显式触发, 强制备份
        print(json.dumps({"backup": str(bak), "integrity": integrity_check()}))
        return 0
    if args.status:
        print(json.dumps(snapshot(), indent=2, ensure_ascii=False))
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
