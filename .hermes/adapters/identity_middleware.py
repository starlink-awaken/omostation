"""Identity Middleware — Hermes MCP 调用时注入身份凭证 (Phase 9 / T124)。"""

from __future__ import annotations

import json
from pathlib import Path

IDENTITY_CACHE = Path.home() / ".kos" / "identities.json"


def load_identity(subject_id: str = "agent:hermes") -> dict:
    """从缓存文件或默认值加载身份信息。"""
    if IDENTITY_CACHE.exists():
        return json.loads(IDENTITY_CACHE.read_text())
    return {
        "subject_id": subject_id,
        "subject_type": "agent",
        "issuer": "ca:agora.starlink.local",
        "tenant": "starlink-core",
    }


def inject_identity_header(headers: dict | None = None) -> dict:
    """在 HTTP 头中注入身份凭证。"""
    identity = load_identity()
    headers = headers or {}
    headers["X-Identity-Subject"] = identity.get("subject_id", "")
    headers["X-Identity-Tenant"] = identity.get("tenant", "")
    headers["X-Identity-Issuer"] = identity.get("issuer", "")
    return headers


def extract_identity_from_headers(headers: dict) -> dict:
    """从 HTTP 头中提取身份信息。"""
    return {
        "subject_id": headers.get("X-Identity-Subject", ""),
        "subject_type": headers.get("X-Identity-Type", "user"),
        "issuer": headers.get("X-Identity-Issuer", ""),
        "tenant": headers.get("X-Identity-Tenant", ""),
    }
