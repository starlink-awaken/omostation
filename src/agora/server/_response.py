"""响应工具与共享常量 — 用于 MCP 工具接口的标准化响应格式。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# ── 响应格式 ─────────────────────────────────────────────────────

FORMAT_VERSION = "agora-v1"


def _ok(data: dict) -> dict:
    """返回标准成功响应。data 中应包含 format_version 字段。"""
    return {"status": "ok", **data}


# ── 大响应保护 (阶段3) ────────────────────────────────────────
# 超过该大小的 result 会被截断 + 标记, 避免客户端 json.loads 崩溃
# (meta/discover 11KB+ 含 control char 曾崩解析器)
MAX_RESULT_CHARS = 10_000


def _safe_result(result: Any, max_chars: int = MAX_RESULT_CHARS) -> dict:
    """对大 result 做 JSON 安全处理: 截断 + 标记 + 长度.

    Returns: {result, truncated, result_chars} — 超过 max_chars 时
    截断并标记 truncated=True (客户端可据此分页或忽略).
    """
    import json as _json

    try:
        s = _json.dumps(result, ensure_ascii=False)
        total = len(s)
        truncated = total > max_chars
        if truncated:
            # 截断为合法 JSON (保留结构头)
            cut = s[:max_chars]
            return {
                "result": _json.loads(cut) if _try_parse(cut) else result,
                "truncated": True,
                "result_chars": total,
                "truncated_length": max_chars,
            }
        return {"result": result, "truncated": False, "result_chars": total}
    except Exception:  # defensive: 序列化失败原样返回
        return {"result": result, "truncated": False, "result_chars": 0}


def _try_parse(s: str) -> Any | None:
    """尝试解析 JSON, 失败返回 None."""
    import json as _json

    try:
        return _json.loads(s)
    except Exception:  # noqa: BLE001
        return None


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
    except Exception:  # defensive fallback
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
