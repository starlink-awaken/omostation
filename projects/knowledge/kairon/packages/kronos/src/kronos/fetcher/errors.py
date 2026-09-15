"""Fetch error handling — error classification and response validation."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kronos.fetch_router import FetchResult  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)


FETCH_ERROR_TABLE: dict[str, dict[str, str]] = {
    "403_forbidden": {
        "pattern": "403|Forbidden",
        "cause": "目标服务器拒绝访问(反爬/IP封禁)",
        "action": "自动降级到 L0b Jina / L4 CloakBrowser",
        "user_msg": "目标网站拒绝访问,已自动切换抓取方式",
    },
    "timeout": {
        "pattern": "timeout|TimeoutError",
        "cause": "连接超时",
        "action": "尝试更短的超时 + 重试 1 次",
        "user_msg": "连接超时,已自动重试",
    },
    "dns_failure": {
        "pattern": "NameResolutionError|getaddrinfo",
        "cause": "DNS 解析失败",
        "action": "跳过该 URL,标记为无效链接",
        "user_msg": "域名无法解析,已跳过",
    },
    "empty_response": {
        "pattern": "No readable content|empty.*response",
        "cause": "服务器返回空内容",
        "action": "尝试用 Jina Reader 重新获取",
        "user_msg": "返回空内容,正在尝试备用方式",
    },
    "robots_blocked": {
        "pattern": "robots.txt|blocked by robots",
        "cause": "被 robots.txt 禁止抓取",
        "action": "使用 CloakBrowser 浏览器渲染绕过",
        "user_msg": "网站禁止自动抓取,使用浏览器模式重试",
    },
    "ssl_error": {
        "pattern": "SSLError|certificate verify",
        "cause": "SSL 证书错误",
        "action": "跳过 SSL 验证重试",
        "user_msg": "SSL 证书异常,已尝试绕过",
    },
}


def diagnose_fetch_error(error: Exception) -> dict[str, str]:
    """诊断抓取错误原因,返回处理建议"""
    err_str = str(error)
    for err_code, info in FETCH_ERROR_TABLE.items():
        if re.search(info["pattern"], err_str, re.IGNORECASE):
            return {"code": err_code, "cause": info["cause"], "action": info["action"], "user_msg": info["user_msg"]}
    return {
        "code": "unknown",
        "cause": str(error)[:100],
        "action": "尝试下一层 fallback",
        "user_msg": "未知错误,尝试降级",
    }


# ── 图片处理(对齐 WPS content-digest 规范) ──────────

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}


def extract_image_urls(html: str) -> list[str]:
    """从 HTML 中提取图片 URL"""
    urls = []
    for src_attr in ["src", "data-src", "data-original"]:
        for m in re.finditer(rf'{src_attr}\s*=\s*["\']([^"\']+)["\']', html):
            url = m.group(1)
            if any(url.lower().endswith(ext) for ext in IMAGE_EXTENSIONS):
                urls.append(url)
    return list(set(urls))


def is_image_url(url: str) -> bool:
    if any(url.lower().endswith(ext) for ext in IMAGE_EXTENSIONS):
        return True
    return bool(re.search(r"images?/|\.(jpg|jpeg|png|gif|webp)\b", url.lower()))


def _validate_url(url: str) -> str | None:
    """校验 URL 协议,拒绝不安全协议."""
    if url.startswith("file://"):
        return "file:// 协议被拒绝(可能读取本地文件)"
    if url.startswith("javascript:"):
        return "javascript: 协议被拒绝"
    if url.startswith("data:"):
        return "data: 协议被拒绝"
    if not url.startswith(("http://", "https://")):
        return f"不支持的协议: {url[:20]}"
    return None


def execute_fetch(url: str, timeout: int = 15) -> FetchResult:
    """
    执行自动抓取,依次尝试所有 HTTP 层,最后尝试浏览器层.

    Args:
        url: 目标 URL
        timeout: 每层超时秒数

    Returns:
      {"ok": true, "content": "...", "text": "...", "markdown": "...",
       "method": "native_http|jina_reader|cloakbrowser|...", "title": "..."}
    """
    # URL 协议校验
    url_err = _validate_url(url)
    if url_err:
        return {"ok": False, "error": url_err, "method": "validation"}
    # 延迟导入避免循环: fetch_router → fetcher.errors → fetch_router
    from kronos.fetch_router import (
        _extract_title,
        _html_to_markdown,
        _strip_html,
        _try_cloakbrowser,
        _try_jina_reader,
        _try_native_http,
        _try_playwright,
        _try_scrapling_fetch,
    )

    methods = [
        ("native_http", lambda: _try_native_http(url, timeout)),
        ("scrapling", lambda: _try_scrapling_fetch(url, timeout)),
        ("jina_reader", lambda: _try_jina_reader(url, timeout)),
        ("cloakbrowser", lambda: _try_cloakbrowser(url)),
        ("playwright", lambda: _try_playwright(url)),
    ]

    for method_name, fetcher in methods:
        try:
            content = fetcher()
            if content and not _is_error_page(content):
                return {
                    "ok": True,
                    "content": content,
                    "text": _strip_html(content),
                    "markdown": _html_to_markdown(content),
                    "method": method_name,
                    "title": _extract_title(content),
                }
        except Exception as e:
            logger.warning("fetch method %s failed for %s: %s", method_name, url, e)
            continue

    # 全部失败 → 出方案链
    from kronos.fetch_router import execute_fallback_chain

    chain = execute_fallback_chain(url)
    return {"ok": False, "plan": chain, "error": "所有方法均失败"}


def _is_error_page(content: str) -> bool:
    """检测抓取结果是否为错误页而非真实内容"""
    if len(content) < 500:
        return True
    error_signals = [
        '"error"',
        '"code":403',
        '"code":40362',
        '"code":429',
        "请求存在异常",
        "访问被限制",
        "暂时限制",
        "访问异常",
        "Verify you are human",
        "请开启JavaScript",
        "Just a moment...",
        "Checking your browser",
    ]
    for sig in error_signals:
        if sig in content[:2000]:
            return True
    return False
