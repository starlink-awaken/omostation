"""Agora Identity CA — 身份凭证签发与验证 (Phase 9 / T123)。"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from pathlib import Path

from agora.persistence_db import _get_db  # type: ignore[import-not-found]

CA_DB_PATH = Path.home() / ".kos" / "identity.db"


class IdentityCA:
    """Local CA — 签发/吊销/验证身份凭证。"""

    def __init__(
        self, db_path: str | None = None, ca_id: str = "ca:agora.starlink.local"
    ):
        self._db_path = db_path or str(CA_DB_PATH)
        self.ca_id = ca_id
        self._ensure_schema()

    def _ensure_schema(self):
        conn = _get_db(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS identities (
                subject_id TEXT PRIMARY KEY,
                subject_type TEXT NOT NULL,
                issuer TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                expires_at TEXT DEFAULT '',
                proof_ref TEXT NOT NULL,
                proof_type TEXT DEFAULT 'hmac',
                tenant TEXT DEFAULT '',
                revoked INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ca_keys (
                key_id TEXT PRIMARY KEY,
                secret_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            )
        """)
        conn.commit()

    def init_ca(self) -> str:
        """初始化 CA 密钥。返回公钥引用。"""
        conn = _get_db(self._db_path)
        key_id = "key:" + secrets.token_hex(8)
        raw_secret = secrets.token_hex(32)
        salt = os.urandom(16)
        key_hash = hashlib.pbkdf2_hmac("sha256", raw_secret.encode(), salt, 6000)
        secret_hash = salt.hex() + ":" + key_hash.hex()
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn.execute(
            "INSERT OR REPLACE INTO ca_keys (key_id, secret_hash, created_at) VALUES (?, ?, ?)",
            (key_id, secret_hash, ts),
        )
        conn.commit()
        return f"hmac:{key_id}"

    def issue_identity(
        self,
        subject_id: str,
        subject_type: str,
        tenant: str = "",
        expires_days: int = 365,
    ) -> dict:
        """签发身份凭证。"""
        conn = _get_db(self._db_path)
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        expires = ""
        if expires_days > 0:
            expires = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ",
                time.gmtime(time.time() + expires_days * 86400),
            )

        # Generate HMAC proof with salted PBKDF2
        raw = secrets.token_hex(16)
        salt = os.urandom(16)
        proof_hash = hashlib.pbkdf2_hmac("sha256", raw.encode(), salt, 6000)
        proof_ref = f"hmac:{salt.hex()}:{proof_hash.hex()[:16]}"

        conn.execute(
            """INSERT OR REPLACE INTO identities
               (subject_id, subject_type, issuer, issued_at, expires_at,
                proof_ref, proof_type, tenant)
               VALUES (?, ?, ?, ?, ?, ?, 'hmac', ?)""",
            (subject_id, subject_type, self.ca_id, now, expires, proof_ref, tenant),
        )
        conn.commit()

        return {
            "subject_id": subject_id,
            "subject_type": subject_type,
            "issuer": self.ca_id,
            "issued_at": now,
            "expires_at": expires,
            "proof_ref": proof_ref,
            "proof_type": "hmac",
            "proof_secret": raw,  # Show once!
            "tenant": tenant,
        }

    def verify_identity(self, subject_id: str, proof_secret: str = "") -> dict:
        """验证身份凭证有效性。"""
        conn = _get_db(self._db_path)
        row = conn.execute(
            "SELECT * FROM identities WHERE subject_id = ? AND revoked = 0",
            (subject_id,),
        ).fetchone()
        if not row:
            return {"valid": False, "reason": "not_found"}

        cols = [
            "subject_id",
            "subject_type",
            "issuer",
            "issued_at",
            "expires_at",
            "proof_ref",
            "proof_type",
            "tenant",
            "revoked",
        ]
        d = dict(zip(cols, row, strict=True))

        now_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if d["expires_at"] and d["expires_at"] < now_ts:
            return {"valid": False, "reason": "expired"}

        if proof_secret:
            parts = d["proof_ref"].split(":")
            if len(parts) >= 3 and parts[1]:
                # New format: hmac:salt:hash_prefix
                try:
                    salt = bytes.fromhex(parts[1])
                    expected_prefix = hashlib.pbkdf2_hmac(
                        "sha256", proof_secret.encode(), salt, 6000
                    ).hex()[:16]
                    if expected_prefix != parts[2]:
                        return {"valid": False, "reason": "proof_mismatch"}
                except (ValueError, IndexError):
                    return {"valid": False, "reason": "proof_mismatch"}
            else:
                # Legacy format: hmac:hash_prefix
                expected_hash = hashlib.sha256(proof_secret.encode()).hexdigest()
                if not d["proof_ref"].endswith(expected_hash[:16]):
                    return {"valid": False, "reason": "proof_mismatch"}

        return {"valid": True, "identity": d}

    def revoke_identity(self, subject_id: str) -> bool:
        """吊销身份凭证。"""
        conn = _get_db(self._db_path)
        conn.execute(
            "UPDATE identities SET revoked = 1 WHERE subject_id = ?",
            (subject_id,),
        )
        conn.commit()
        return True

    def list_identities(self, tenant: str = "") -> list[dict]:
        """列举身份凭证。"""
        conn = _get_db(self._db_path)
        cols = [
            "subject_id",
            "subject_type",
            "issuer",
            "issued_at",
            "expires_at",
            "tenant",
            "revoked",
        ]
        if tenant:
            rows = conn.execute(
                "SELECT subject_id, subject_type, issuer, issued_at, expires_at, tenant, revoked FROM identities WHERE tenant = ?",
                (tenant,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT subject_id, subject_type, issuer, issued_at, expires_at, tenant, revoked FROM identities",
            ).fetchall()
        return [dict(zip(cols, r, strict=True)) for r in rows]


def send_jsonrpc(data):
    import sys

    sys.stdout.write(__import__("json").dumps(data, ensure_ascii=False) + chr(10))
    sys.stdout.flush()


def run_mcp_stdio():
    import sys

    line = sys.stdin.readline()
    if not line:
        return
    msg = json.loads(line)
    if msg.get("method") != "initialize":
        return
    send_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": msg["id"],
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "identity-ca", "version": "1.0.0"},
                "capabilities": {"tools": {}},
            },
        }
    )
    sys.stdin.readline()
    ca = IdentityCA()
    ca.init_ca()
    while True:
        line = sys.stdin.readline()
        if not line:
            return
        msg = json.loads(line)
        if msg.get("method") == "tools/list":
            send_jsonrpc(
                {
                    "jsonrpc": "2.0",
                    "id": msg["id"],
                    "result": {
                        "tools": [
                            {
                                "name": "identity.issue",
                                "description": "签发身份凭证",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "subject_id": {"type": "string"},
                                        "subject_type": {
                                            "type": "string",
                                            "enum": ["user", "agent", "org", "node"],
                                        },
                                        "tenant": {"type": "string"},
                                        "expires_days": {
                                            "type": "integer",
                                            "default": 365,
                                        },
                                    },
                                    "required": ["subject_id", "subject_type"],
                                },
                            },
                            {
                                "name": "identity.verify",
                                "description": "验证身份凭证",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"subject_id": {"type": "string"}},
                                    "required": ["subject_id"],
                                },
                            },
                            {
                                "name": "identity.revoke",
                                "description": "冒销身份凭证",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"subject_id": {"type": "string"}},
                                    "required": ["subject_id"],
                                },
                            },
                            {
                                "name": "identity.list",
                                "description": "列出所有凭证",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"tenant": {"type": "string"}},
                                },
                            },
                        ]
                    },
                }
            )
        elif msg.get("method") == "tools/call":
            p = msg.get("params", {})
            tn = p.get("name", "")
            a = p.get("arguments", {})
            handlers = {
                "identity.issue": lambda a=a: ca.issue_identity(**a),
                "identity.verify": lambda a=a: ca.verify_identity(**a),
                "identity.revoke": lambda a=a: ca.revoke_identity(**a),
                "identity.list": lambda a=a: ca.list_identities(a.get("tenant", "")),
            }
            h = handlers.get(tn)
            if h:
                try:
                    r = h()
                    send_jsonrpc(
                        {
                            "jsonrpc": "2.0",
                            "id": msg["id"],
                            "result": {
                                "content": [{"type": "text", "text": json.dumps(r)}]
                            },
                        }
                    )
                except Exception as e:
                    send_jsonrpc(
                        {
                            "jsonrpc": "2.0",
                            "id": msg["id"],
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps({"error": str(e)}),
                                    }
                                ]
                            },
                        }
                    )


if __name__ == "__main__":
    run_mcp_stdio()
