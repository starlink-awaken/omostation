"""统一知识摄取管线 (P0-2).

任意外部知识源 → 统一摄取 → kos 知识中枢 (markdown + Mem0 双写)。

统一入口:
  ingest_any(source)  — 自动识别 URL / 文本 / 文件, 分派到对应摄取路径
  ingest_url(url)     — URL → kronos.fetch_router 四级降级抓取 → kos.ingest_text
  ingest_text(text)   — 文本直达 kos.ingest_text
  ingest_file(path)   — 文件 → 读取 → kos.ingest_text

设计原则 (对齐 llm-router 哲学):
  1. 抓取走降级链 (Jina Reader → native HTTP → scrapling → MCP)
  2. 每级失败打印原因, 不静默
  3. kos 入库失败降级跳过, 不阻塞调用方
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("kronos.ingest_pipeline")


def ingest_any(source: str) -> dict[str, Any]:
    """统一入口: 自动识别 source 类型并分派。"""
    if source.startswith(("http://", "https://")):
        return ingest_url(source)
    if source.startswith(("~/", "/", "./", "../")) or "." in source.split("/")[-1]:
        try:
            from pathlib import Path

            p = Path(source).expanduser()
            if p.exists() and p.is_file():
                return ingest_file(str(p))
        except OSError:
            pass
    return ingest_text(source)


# P2: 抓取策略表 — 按 URL 类型选择默认抓取路径 (可被 INGEST_FETCH_STRATEGY 环境变量覆盖)
FETCH_STRATEGY_TABLE = {
    "wikipedia": "jina",
    "github": "native",
    "arxiv": "jina",
    "youtube": "jina",
    "pdf": "native",
    "default": "auto",  # auto = jina → native → scrapling → MCP 四级降级
}


def _pick_fetch_strategy(url: str) -> str:
    """按 URL 域名/后缀选默认策略 (P2 固化)。"""
    import os

    override = os.environ.get("INGEST_FETCH_STRATEGY")
    if override:
        return override
    lowered = url.lower()
    for key, strategy in FETCH_STRATEGY_TABLE.items():
        if key == "default":
            continue
        if key == "pdf" and lowered.endswith(".pdf"):
            return strategy
        if key != "pdf" and key in lowered:
            return strategy
    return FETCH_STRATEGY_TABLE["default"]


def ingest_url(url: str) -> dict[str, Any]:
    """URL 摄取: 复用 kronos.fetch_router 四级降级抓取 → kos 入库。"""
    strategy = _pick_fetch_strategy(url)
    logger.info(f"抓取策略: {strategy} for {url[:60]}")
    try:
        from kronos.fetch_router import build_jina_plan, _try_jina_reader, _try_native_http

        # 先探测抓取策略
        try:
            plan = build_jina_plan(url)
            content = _try_jina_reader(url, timeout=30)
            if not content:
                content = _try_native_http(url, timeout=30)
            if not content and plan:
                logger.info("Jina/native 均失败, 尝试 scrapling")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"fetch_router 探测失败: {exc}")
            content = _try_native_http(url, timeout=30)

        if not content:
            return {"ingested": None, "type": "url", "url": url, "error": "抓取失败(四级降级均不可用)"}

        # 去 HTML 标签, 取纯文本
        import re

        text = re.sub(r"<[^>]+>", " ", content)
        text = re.sub(r"\s+", " ", text).strip()[:20000]
        title = url.split("/")[-1][:60] or url
        return _to_kos(text, title, {"source": "url", "url": url})
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"URL 摄取失败: {exc}")
        return {"ingested": None, "type": "url", "url": url, "error": str(exc)}


def ingest_text(text: str, title: str | None = None) -> dict[str, Any]:
    """文本摄取: 直达 kos.ingest_text (markdown + Mem0 双写)。"""
    return _to_kos(text, title, {"source": "text"})


def ingest_file(path: str) -> dict[str, Any]:
    """文件摄取: 读取本地文件 → kos 入库。"""
    try:
        from pathlib import Path

        p = Path(path).expanduser()
        text = p.read_text(encoding="utf-8", errors="replace")
        return _to_kos(text, p.name, {"source": "file", "path": str(p)})
    except OSError as exc:
        return {"ingested": None, "type": "file", "path": path, "error": str(exc)}


def _validate_input(text: str, title: str) -> dict[str, str] | None:
    """结构化校验门禁 (P1-1): 入库前校验, 不合法返回错误 dict。"""
    if not text or not text.strip():
        return {"error": "文本为空"}
    if len(text.strip()) < 10:
        return {"error": f"文本过短 ({len(text.strip())} 字符, 需 ≥10)"}
    if len(text) > 100_000:
        return {"error": f"文本超长 ({len(text)} 字符, 上限 100k)"}
    if not title or not title.strip():
        return {"error": "标题为空"}
    return None


def _to_kos(text: str, title: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """核心入库: 校验门禁 → kos.ingest_text, 失败降级不阻塞。"""
    invalid = _validate_input(text, title)
    if invalid:
        logger.warning(f"校验未过 (跳过入库): {invalid}")
        return {"ingested": None, "type": metadata.get("source", "text"), "title": title, **invalid}
    final_title = (title or text[:50]).strip()
    try:
        from kos.ingest import ingest_text as kos_ingest

        result = kos_ingest(text, title=final_title)
        result["metadata"] = metadata
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"kos 入库失败 (降级跳过): {exc}")
        return {"ingested": None, "type": metadata.get("source", "text"), "title": title, "error": str(exc)}


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        r = ingest_any(sys.argv[1])
        print(f"摄取结果: {r}")
