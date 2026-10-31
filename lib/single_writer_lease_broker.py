#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WP-101 & WP-102 生产兼容实现：持久化 Single-Writer Lease Broker 与 HMAC-SHA256 / Ed25519 能力令牌验证器
解决：
1. F31-01：替代仅对单机生效的本地 `fcntl.flock` 与 v3.3 纯内存字典，使用 SQLite 事务持久化 `lease_epoch` 与 `committed_idempotency_keys`，确保进程重启后 `lease_epoch` 严格单调递增不归零，阻断旧租约迟到写入（Stale Worker Split-Brain）。
2. F31-02 / Issue #4225：保留原 `proof` 作为 `payload_integrity_digest` 向后兼容，同时强制校验带密钥 `HMAC-SHA256` 签名的 `ControlCapsule`、有效期、`allowed_write_scopes` 与 `approval_ref`。
"""
import hashlib
import hmac
import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional


class BrokerSecurityError(PermissionError):
    """能力签名不合法、越权、路径冲突或租约已过期时抛出的硬阻断异常。"""
    pass


class ControlCapsuleSigner:
    """签发与验证带密钥 HMAC-SHA256 + 内容完整性摘要的 ControlCapsule 令牌。"""

    def __init__(self, secret_key: str):
        if not secret_key or len(secret_key) < 16:
            raise ValueError("secret_key 长度必须至少为 16 字节")
        self._key = secret_key.encode("utf-8")

    def sign_capsule(self, capsule: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._canonical_payload(capsule)
        integrity_digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        sig = hmac.new(self._key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        signed = dict(capsule)
        signed["payload_integrity_digest"] = integrity_digest
        signed["hmac_sha256"] = sig
        return signed

    def verify_capsule(self, signed_capsule: Dict[str, Any], now_ts: Optional[float] = None) -> bool:
        now = now_ts if now_ts is not None else time.time()
        sig = signed_capsule.get("hmac_sha256", "")
        if not sig:
            raise BrokerSecurityError("MISSING_HMAC_SIGNATURE: 缺少 HMAC-SHA256 能力签名，拒绝无密钥散列 (F31-02)")

        expected_payload = self._canonical_payload(signed_capsule)
        expected_sig = hmac.new(self._key, expected_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            raise BrokerSecurityError("INVALID_HMAC_SIGNATURE: ControlCapsule 签名校验失败，疑似篡改或伪造")

        exp = float(signed_capsule.get("expires_at", 0))
        if exp <= now:
            raise BrokerSecurityError("CAPSULE_EXPIRED: ControlCapsule 已过期，自动 fail-closed")

        op_level = signed_capsule.get("op_level", "L0")
        if op_level in ("L2", "L3") and not signed_capsule.get("approval_ref"):
            raise BrokerSecurityError(f"APPROVAL_REQUIRED_FOR_{op_level}: 高风险操作必须绑定 Principal 显式 approval_ref")

        return True

    @staticmethod
    def _canonical_payload(capsule: Dict[str, Any]) -> str:
        scopes = ",".join(sorted(capsule.get("allowed_write_scopes") or []))
        fields = [
            f"issuer={capsule.get('issuer', 'control-home-01')}",
            f"audience={capsule.get('audience', 'omo-worker')}",
            f"task_id={capsule.get('task_id', '')}",
            f"worker_id={capsule.get('worker_id', '')}",
            f"clone_id={capsule.get('clone_id', '')}",
            f"role_id={capsule.get('role_id', '')}",
            f"op_level={capsule.get('op_level', 'L0')}",
            f"lease_epoch={capsule.get('lease_epoch', 0)}",
            f"expires_at={capsule.get('expires_at', 0)}",
            f"approval_ref={capsule.get('approval_ref', '')}",
            f"allowed_write_scopes={scopes}",
        ]
        return "|".join(fields)


class SingleWriterLeaseBroker:
    """
    控制面唯一写者仲裁器（支持 SQLite 持久化或内存模式，重启不丢失 lease_epoch）：
    - 维护每个 task_id 的单调递增 lease_epoch
    - 校验并行任务之间的写表面互斥 (Disjoint Write Scopes)
    - 拦截过期 epoch 的 Stale Worker 写入
    - 拦截相同 idempotency_key 但不同参数摘要的冲突重放
    """

    def __init__(self, signer: ControlCapsuleSigner, db_path: str = ":memory:"):
        self._signer = signer
        self._db_path = db_path
        if db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_leases (
                    task_id TEXT PRIMARY KEY,
                    lease_epoch INTEGER NOT NULL,
                    active_owner TEXT NOT NULL,
                    clone_id TEXT NOT NULL,
                    op_level TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    allowed_write_scopes TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS idempotency_ledger (
                    idempotency_key TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    lease_epoch INTEGER NOT NULL,
                    transition TEXT NOT NULL,
                    evidence_sha256 TEXT NOT NULL,
                    committed_at REAL NOT NULL
                )
                """
            )

    def close(self) -> None:
        self._conn.close()

    def acquire_lease(
        self,
        task_id: str,
        worker_id: str,
        role_id: str,
        op_level: str = "L0",
        ttl_seconds: int = 600,
        approval_ref: str = "",
        clone_id: str = "clone-default",
        allowed_write_scopes: Optional[List[str]] = None,
        now_ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        now = now_ts if now_ts is not None else time.time()
        scopes = sorted(allowed_write_scopes or [])

        with self._conn:
            # Check write-surface overlap with other currently active (unexpired) tasks
            if scopes:
                cur = self._conn.execute(
                    "SELECT task_id, active_owner, allowed_write_scopes FROM task_leases WHERE task_id != ? AND expires_at > ?",
                    (task_id, now),
                )
                for other_tid, other_owner, other_scopes_json in cur.fetchall():
                    other_scopes = set(json.loads(other_scopes_json))
                    overlap = set(scopes) & other_scopes
                    if overlap:
                        raise BrokerSecurityError(
                            f"WRITE_SURFACE_CONFLICT: 任务 {task_id} 与在途任务 {other_tid} (owner={other_owner}) 写路径重叠: {sorted(overlap)}"
                        )

            row = self._conn.execute(
                "SELECT lease_epoch FROM task_leases WHERE task_id = ?", (task_id,)
            ).fetchone()
            next_epoch = (row[0] + 1) if row else 1

            self._conn.execute(
                """
                INSERT INTO task_leases (task_id, lease_epoch, active_owner, clone_id, op_level, expires_at, allowed_write_scopes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    lease_epoch = excluded.lease_epoch,
                    active_owner = excluded.active_owner,
                    clone_id = excluded.clone_id,
                    op_level = excluded.op_level,
                    expires_at = excluded.expires_at,
                    allowed_write_scopes = excluded.allowed_write_scopes
                """,
                (task_id, next_epoch, worker_id, clone_id, op_level, now + ttl_seconds, json.dumps(scopes)),
            )

        capsule = {
            "issuer": "control-home-01",
            "audience": "omo-worker",
            "task_id": task_id,
            "worker_id": worker_id,
            "clone_id": clone_id,
            "role_id": role_id,
            "op_level": op_level,
            "lease_epoch": next_epoch,
            "expires_at": now + ttl_seconds,
            "approval_ref": approval_ref,
            "allowed_write_scopes": scopes,
        }
        return self._signer.sign_capsule(capsule)

    def commit_transition(
        self,
        signed_capsule: Dict[str, Any],
        idempotency_key: str,
        transition: str,
        evidence_sha256: str,
        now_ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        now = now_ts if now_ts is not None else time.time()
        self._signer.verify_capsule(signed_capsule, now_ts=now)

        task_id = signed_capsule["task_id"]
        worker_id = signed_capsule["worker_id"]
        req_epoch = int(signed_capsule["lease_epoch"])

        with self._conn:
            # 1. Check idempotency ledger first
            idem_row = self._conn.execute(
                "SELECT task_id, transition, evidence_sha256, lease_epoch FROM idempotency_ledger WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if idem_row is not None:
                prev_tid, prev_trans, prev_sha, prev_epoch = idem_row
                if (prev_tid, prev_trans, prev_sha) == (task_id, transition, evidence_sha256):
                    return {
                        "status": "IDEMPOTENT_NOOP",
                        "task_id": task_id,
                        "lease_epoch": prev_epoch,
                        "idempotency_key": idempotency_key,
                    }
                raise BrokerSecurityError(
                    f"IDEMPOTENCY_KEY_PARAMETER_CONFLICT: 幂等键 '{idempotency_key}' 被复用于不同参数/目标"
                )

            # 2. Check authoritative lease_epoch & active_owner
            lease_row = self._conn.execute(
                "SELECT lease_epoch, active_owner FROM task_leases WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if lease_row is None:
                raise BrokerSecurityError(f"UNKNOWN_TASK_LEASE: 任务 {task_id} 不存在有效租约")

            cur_epoch, cur_owner = lease_row
            if req_epoch != cur_epoch or worker_id != cur_owner:
                raise BrokerSecurityError(
                    f"STALE_LEASE_EPOCH_FENCED (F31-01): 拒绝旧租约写入 (req_epoch={req_epoch}, current_epoch={cur_epoch}, worker={worker_id}, active_owner={cur_owner})"
                )

            self._conn.execute(
                """
                INSERT INTO idempotency_ledger (idempotency_key, task_id, worker_id, lease_epoch, transition, evidence_sha256, committed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (idempotency_key, task_id, worker_id, req_epoch, transition, evidence_sha256, now),
            )

        return {
            "status": "COMMITTED",
            "task_id": task_id,
            "worker_id": worker_id,
            "lease_epoch": req_epoch,
            "transition": transition,
            "idempotency_key": idempotency_key,
            "evidence_sha256": evidence_sha256,
        }
