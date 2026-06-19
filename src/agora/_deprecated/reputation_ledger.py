from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Prime'
Layer: L3
Summary: 'ReputationLedger: Tracks node reliability and manages swarm handshakes.'
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Reputation Ledger ≡ Module
# 内涵 ≝ {Reputation, Ledger}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, ReputationLedger)}
# 功能 ⊢ {Reputation_Ledger, Init_Reputation, Validate_Ledger}
# =============================================================================

import logging  # noqa: E402
import sqlite3  # noqa: E402
from typing import Any  # noqa: E402

from nucleus.Z_Microkernel.facades.path_resolver_facade import get_path_resolver  # type: ignore[import-not-found]  # noqa: E402

_log = logging.getLogger(__name__)
_DEFAULT_ROLE = "General"


class ReputationLedger:
    """
    [TRK-034] 声誉账本 (ReputationLedger)
    负责追踪 Swarm 节点的行为表现，管理 P2P 信任基础。
    """

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            self.db_path = get_path_resolver().resolve_db("gateway", "reputation.db")
        else:
            self.db_path = db_path

        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """初始化声誉表。"""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS node_reputation (
                    node_id TEXT PRIMARY KEY,
                    score REAL DEFAULT 0.0,
                    role TEXT DEFAULT 'General',
                    last_action TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self._ensure_role_column(conn)
            conn.commit()

    def _ensure_role_column(self, conn: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(node_reputation)").fetchall()
        }
        if "role" in columns:
            return

        conn.execute(
            f"ALTER TABLE node_reputation ADD COLUMN role TEXT DEFAULT '{_DEFAULT_ROLE}'"
        )

    def get_score(self, node_id: str) -> float:
        """获取节点的当前声誉分。"""
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT score FROM node_reputation WHERE node_id = ?", (node_id,)
                ).fetchone()
                return row["score"] if row else 0.0
        except sqlite3.Error as e:
            _log.error("❌ [Reputation] Failed to get score: %s", e)
            return 0.0

    def update_score(self, node_id: str, delta: float, reason: str = "") -> bool:
        """更新节点声誉分。"""
        try:
            with self._get_conn() as conn:
                # 检查是否存在
                row = conn.execute(
                    "SELECT score FROM node_reputation WHERE node_id = ?", (node_id,)
                ).fetchone()
                if not row:
                    conn.execute(
                        "INSERT INTO node_reputation (node_id, score, last_action) VALUES (?, ?, ?)",
                        (node_id, delta, reason),
                    )
                else:
                    new_score = row["score"] + delta
                    conn.execute(
                        "UPDATE node_reputation SET score = ?, last_action = ?, updated_at = CURRENT_TIMESTAMP WHERE node_id = ?",
                        (new_score, reason, node_id),
                    )
                conn.commit()
            _log.info("📊 [Reputation] Updated %s: %+.2f (%s)", node_id, delta, reason)
            return True
        except sqlite3.Error as e:
            _log.error("❌ [Reputation] Failed to update score: %s", e)
            return False

    def assign_role(self, node_id: str, role: str) -> bool:
        """[TRK-042] 为节点分配特定的专业角色（如 SecurityAudit）。"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO node_reputation (node_id, role, last_action)
                    VALUES (?, ?, ?)
                    ON CONFLICT(node_id) DO UPDATE SET
                        role = excluded.role,
                        last_action = excluded.last_action,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (node_id, role, f"Assigned role {role}"),
                )
                conn.commit()
            _log.info("🏷️ [Reputation] Node %s assigned role: %s", node_id, role)
            return True
        except sqlite3.Error as e:
            _log.error("❌ [Reputation] Failed to assign role: %s", e)
            return False

    def get_top_experts(self, role: str, count: int = 3) -> list[dict[str, Any]]:
        """[TRK-042] 获取指定领域声誉最高的前 N 个专家。"""
        if count <= 0:
            return []

        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT node_id, score, role
                    FROM node_reputation
                    WHERE role = ?
                    ORDER BY score DESC, updated_at DESC
                    LIMIT ?
                    """,
                    (role, count),
                ).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            _log.error("❌ [Reputation] Failed to get experts: %s", e)
            return []

    def verify_handshake(self, node_id: str, challenge: str, signature: str) -> bool:
        """
        验证节点握手。
        Phase 3 简化版：目前仅验证签名格式并初始化声誉。
        """
        if not signature or signature == "":
            return False

        # 模拟验证逻辑
        is_valid = signature == "valid-sig"

        if is_valid:
            # 初始化新节点
            if self.get_score(node_id) == 0.0:
                self.update_score(node_id, 0.0, "Initial handshake")
            _log.info("🤝 [Reputation] Handshake verified for node: %s", node_id)

        return is_valid

    def sync_with_peer(self, peer_id: str, peer_table: dict[str, float]) -> None:
        """
        与邻居同步声誉表，使用加权平均算法。
        NewScore = LocalScore * 0.6 + PeerScore * 0.4
        """
        _log.info("📡 [Reputation] Syncing reputation table with peer: %s", peer_id)

        for node_id, peer_score in peer_table.items():
            local_score = self.get_score(node_id)

            # 计算加权分
            # 这里的逻辑是：我们信任自己的观察 (60%)，但也参考邻居的意见 (40%)
            consensus_score = (local_score * 0.6) + (peer_score * 0.4)

            # 更新到数据库
            self._set_absolute_score(node_id, consensus_score, f"Sync from {peer_id}")

    def _set_absolute_score(self, node_id: str, score: float, reason: str) -> None:
        """内部方法：直接设置绝对分值。"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO node_reputation (node_id, score, last_action) VALUES (?, ?, ?) "
                    "ON CONFLICT(node_id) DO UPDATE SET score = EXCLUDED.score, last_action = EXCLUDED.last_action, updated_at = CURRENT_TIMESTAMP",
                    (node_id, score, reason),
                )
                conn.commit()
        except sqlite3.Error as e:
            _log.error("❌ [Reputation] Failed to set absolute score: %s", e)
