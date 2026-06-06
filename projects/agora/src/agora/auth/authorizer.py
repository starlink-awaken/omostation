"""Agora Authorizer — 在路由前校验 CapabilityGrant (Phase 9 / T126)。"""

from __future__ import annotations

import json
import time
from pathlib import Path

from agora.persistence_db import _get_db  # type: ignore[import-not-found]

GRANTS_DB = Path.home() / ".kos" / "grants.db"

# 全局门禁 — 指定强制授权的工具列表
ENFORCE_TOOLS = ["collab.*"]  # 默认只对此类工具强制授权
# 空列表 = 全部 pass-through
# ["*"] = 全部强制


def set_enforce_tools(tools: list[str]) -> None:
    """设置强制授权的工具列表。"""
    global ENFORCE_TOOLS
    ENFORCE_TOOLS = tools


def is_enforced(tool: str) -> bool:
    """判断某工具是否强制授权。"""
    if not ENFORCE_TOOLS:
        return False
    if "*" in ENFORCE_TOOLS:
        return True
    for pattern in ENFORCE_TOOLS:
        if pattern.endswith("*") and tool.startswith(pattern.rstrip("*")):
            return True
        if pattern == tool:
            return True
    return False


class Authorizer:
    """CapabilityGrant 授权中间件 — 创建/校验/吊销/列举 grant。"""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or str(GRANTS_DB)
        self._ensure_schema()

    def _ensure_schema(self):
        conn = _get_db(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS grants (
                grant_id TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                capability TEXT NOT NULL,
                resource_scope TEXT DEFAULT '',
                constraints TEXT DEFAULT '{}',
                issued_by TEXT DEFAULT '',
                issued_at TEXT NOT NULL,
                revoked INTEGER DEFAULT 0,
                revoked_at TEXT DEFAULT '',
                call_count INTEGER DEFAULT 0,
                total_cost REAL DEFAULT 0.0
            )
        """)
        conn.commit()

    def create_grant(
        self,
        subject: str,
        capability: str,
        resource_scope: str = "",
        constraints: dict | None = None,
        issued_by: str = "ca:agora.starlink.local",
    ) -> dict:
        """创建一条新的 CapabilityGrant。"""
        import secrets

        conn = _get_db(self._db_path)
        grant_id = f"grant:{secrets.token_hex(8)}"
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn.execute(
            "INSERT INTO grants (grant_id, subject, capability, resource_scope, constraints, issued_by, issued_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (grant_id, subject, capability, resource_scope, json.dumps(constraints or {}), issued_by, ts),
        )
        conn.commit()
        return {"grant_id": grant_id, "subject": subject, "capability": capability}

    def check_call(self, subject: str, tool: str, cost: float = 0) -> dict:
        """路由前校验。返回 allowed / denied + reason。"""
        conn = _get_db(self._db_path)

        # 找匹配的 grant（未吊销）
        rows = conn.execute(
            "SELECT * FROM grants WHERE subject = ? AND revoked = 0",
            (subject,),
        ).fetchall()

        cols = [
            "grant_id",
            "subject",
            "capability",
            "resource_scope",
            "constraints",
            "issued_by",
            "issued_at",
            "revoked",
            "revoked_at",
            "call_count",
            "total_cost",
        ]
        applicable = []
        for row in rows:
            g = dict(zip(cols, row, strict=True))
            g["constraints"] = json.loads(g["constraints"])

            # 通配符 capability 匹配
            cap = g["capability"]
            if cap == "*" or cap == tool or (cap.endswith(".*") and tool.startswith(cap[:-2])):
                applicable.append(g)

        if not applicable:
            return {"allowed": False, "reason": f"No grant for {subject} to call {tool}"}

        # 检查约束
        now_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        for g in applicable:
            cons = g["constraints"]
            if cons.get("expire_at") and cons["expire_at"] < now_ts:
                continue
            if cons.get("max_calls") and g["call_count"] >= cons["max_calls"]:
                continue
            if cons.get("max_cost_usd") and g["total_cost"] >= cons["max_cost_usd"]:
                continue

            # 更新计数器
            conn.execute(
                "UPDATE grants SET call_count = call_count + 1, total_cost = total_cost + ? WHERE grant_id = ?",
                (cost, g["grant_id"]),
            )
            conn.commit()
            return {"allowed": True, "grant_id": g["grant_id"]}

        return {"allowed": False, "reason": "All applicable grants exceeded constraints"}

    def revoke_grant(self, grant_id: str) -> bool:
        """吊销指定的 grant。"""
        conn = _get_db(self._db_path)
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn.execute(
            "UPDATE grants SET revoked = 1, revoked_at = ? WHERE grant_id = ?",
            (ts, grant_id),
        )
        conn.commit()
        return True

    def list_grants(self, subject: str = "") -> list[dict]:
        """列举全部或指定 subject 的 grant。"""
        conn = _get_db(self._db_path)
        cols = [
            "grant_id",
            "subject",
            "capability",
            "resource_scope",
            "constraints",
            "issued_by",
            "issued_at",
            "revoked",
            "revoked_at",
            "call_count",
            "total_cost",
        ]
        if subject:
            rows = conn.execute(
                "SELECT * FROM grants WHERE subject = ?",
                (subject,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM grants").fetchall()

        result = []
        for row in rows:
            d = dict(zip(cols, row, strict=True))
            d["constraints"] = json.loads(d["constraints"])
            result.append(d)
        return result


def authorize_middleware(subject: str, tool: str, cost: float = 0, db_path: str | None = None) -> dict:
    """在路由前调用的门禁中间件。

    当工具不在 ENFORCE_TOOLS 中时，仅记录日志（pass-through）。
    """
    az = Authorizer(db_path=db_path)
    r = az.check_call(subject, tool, cost)
    if not r["allowed"] and is_enforced(tool):
        return r  # 真正拒绝
    if not r["allowed"]:
        r["_note"] = f"pass-through (would deny {subject}→{tool})"
    return r
