"""Cockpit 统一认证模块 — API key 管理 + FastAPI 认证依赖.

可选认证模式:
  COCKPIT_AUTH_REQUIRED=true  → 所有 /api/* 路由需要 API key
  COCKPIT_AUTH_REQUIRED=false → 允许匿名访问 (默认, 向后兼容)

Key 来源 (优先级高→低):
  1. COCKPIT_API_KEY env var → master key (scopes=["admin"])
  2. config/api_keys.yaml → 多 key 配置

请求认证方式 (二选一):
  - X-Api-Key: <key>
  - Authorization: Bearer <key>
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

_AUTH_REQUIRED = os.environ.get("COCKPIT_AUTH_REQUIRED", "false").lower() in ("true", "1", "yes")
_API_KEY_ENV = "COCKPIT_API_KEY"
_KEYS_FILE_ENV = "COCKPIT_KEYS_FILE"
_DEFAULT_KEYS_FILE = Path(__file__).resolve().parents[2] / "config" / "api_keys.yaml"


@dataclass(frozen=True)
class ApiKeyInfo:
    name: str
    scopes: list[str] = field(default_factory=lambda: ["read"])


def load_api_keys() -> dict[str, ApiKeyInfo]:
    """加载 API keys: env var + 可选 YAML 文件."""
    keys: dict[str, ApiKeyInfo] = {}

    env_key = os.environ.get(_API_KEY_ENV, "")
    if env_key:
        keys[env_key] = ApiKeyInfo(name="admin", scopes=["admin"])

    keys_file = Path(os.environ.get(_KEYS_FILE_ENV, str(_DEFAULT_KEYS_FILE)))
    if keys_file.exists():
        try:
            data = yaml.safe_load(keys_file.read_text(encoding="utf-8"))
            for entry in (data or {}).get("keys", []):
                k = entry.get("key", "")
                if k and k != "your-secret-key-here":
                    keys[k] = ApiKeyInfo(
                        name=entry.get("name", "unnamed"),
                        scopes=entry.get("scopes", ["read"]),
                    )
        except (OSError, yaml.YAMLError):
            pass

    return keys


@lru_cache(maxsize=1)
def _cached_keys() -> dict[str, ApiKeyInfo]:
    return load_api_keys()


def reload_api_keys() -> dict[str, ApiKeyInfo]:
    """清除缓存并重新加载 keys (用于测试或热更新)."""
    _cached_keys.cache_clear()
    return _cached_keys()


def _extract_key_from_headers(headers: dict[str, str]) -> str | None:
    """从请求头提取 API key: X-Api-Key 或 Authorization: Bearer."""
    api_key = headers.get("x-api-key")
    if api_key:
        return api_key

    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()

    return None


def verify_api_key(headers: dict[str, str]) -> ApiKeyInfo | None:
    """验证 API key. 返 ApiKeyInfo 或 None (匿名). 失败 raise ValueError."""
    if not _AUTH_REQUIRED:
        key = _extract_key_from_headers(headers)
        if key:
            keys = _cached_keys()
            for stored, info in keys.items():
                if hmac.compare_digest(key, stored):
                    return info
        return None

    key = _extract_key_from_headers(headers)
    if not key:
        raise ValueError("Missing API key")

    keys = _cached_keys()
    for stored, info in keys.items():
        if hmac.compare_digest(key, stored):
            return info

    raise ValueError("Invalid API key")


def is_auth_required() -> bool:
    return _AUTH_REQUIRED


def get_subservice_token() -> str:
    """获取出站调用子服务的 token (复用 master key 或独立 JWT)."""
    return os.environ.get("COCKPIT_JWT_TOKEN", os.environ.get(_API_KEY_ENV, ""))
