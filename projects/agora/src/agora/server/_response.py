"""响应工具与共享常量 — 用于 MCP 工具接口的标准化响应格式。"""

from __future__ import annotations

from pathlib import Path

# ── 响应格式 ─────────────────────────────────────────────────────

FORMAT_VERSION = "agora-v1"


def _ok(data: dict) -> dict:
    """返回标准成功响应。data 中应包含 format_version 字段。"""
    return {"status": "ok", **data}


def _error(msg: str) -> dict:
    """返回标准错误响应（内建 format_version）。"""
    return {"status": "error", "error": msg, "format_version": FORMAT_VERSION}


# ── 缓存 TTL 配置 ──────────────────────────────────────────────
# 从 agora-bos-rates.yaml 读取每前缀的 cache_ttl，无配置时默认 30s。

_RATES_CACHE_TTL: dict[str, int] = {}


def _load_cache_ttl_config() -> None:
    """加载缓存 TTL 配置。"""
    global _RATES_CACHE_TTL
    rates_path = Path(__file__).parent.parent / "agora-bos-rates.yaml"
    if not rates_path.exists():
        return
    import yaml

    try:
        rates = yaml.safe_load(open(rates_path))
        _RATES_CACHE_TTL = {}
        for route in rates.get("routes", []):
            prefix = route["prefix"]
            ttl = route.get("cache_ttl", 30)
            _RATES_CACHE_TTL[prefix] = ttl
    except Exception:
        _RATES_CACHE_TTL = {}


def _get_cache_ttl(uri: str) -> int:
    """按 URI 前缀获取缓存 TTL (最长前缀匹配，无匹配默认 30s)."""
    if not _RATES_CACHE_TTL:
        _load_cache_ttl_config()
    best_len = -1
    best_ttl = 30
    for prefix, ttl in _RATES_CACHE_TTL.items():
        if uri.startswith(prefix) and len(prefix) > best_len:
            best_len = len(prefix)
            best_ttl = ttl
    return best_ttl


# NOTE: _ok/_error 定义当前与 agora.response_helpers 略有不同（此处内建 format_version）。
# 待 God Module 拆分完成后可统一使用 response_helpers 版本。
