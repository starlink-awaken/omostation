"""Kronos 内容提取器 — 多级 fallback 链：Ollama LLM → 规则提取 → 默认值。

Pipeline:
  raw_text → Ollama 提取 → 规则提取 → 结构化 JSON → 返回
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from typing import Any, NotRequired, TypedDict, cast

# extract_with_ollama moved to this module

logger = logging.getLogger("kronos.extractor")


class EntitiesResult(TypedDict):
    """实体提取结果"""

    persons: list[str]
    concepts: list[str]
    organizations: list[str]


class ExtractedResult(TypedDict):
    """结构化提取结果"""

    title: str
    summary: str
    key_points: list[str]
    entities: dict[str, list[str]]
    content_type: str
    importance: str
    tags: list[str]
    quotes: NotRequired[list[str]]
    _fallback: NotRequired[str]
    fallback_reason: NotRequired[str | None]


class ErrorResult(TypedDict):
    """错误结果"""

    error: str
    raw: NotRequired[str]


# ── Ollama 可用性缓存 ──

_OLLAMA_AVAILABLE: bool | None = None


def check_ollama(timeout: float = 3.0) -> bool:
    """检查本地 Ollama 是否可用，带缓存"""
    global _OLLAMA_AVAILABLE
    try:
        import httpx

        resp = httpx.get("http://localhost:11434/api/tags", timeout=timeout)
        _OLLAMA_AVAILABLE = resp.status_code == 200
        if _OLLAMA_AVAILABLE:
            logger.info("Ollama detected at http://localhost:11434")
        return _OLLAMA_AVAILABLE
    except Exception:
        _OLLAMA_AVAILABLE = False
        return False


def _detect_content_type(text: str) -> str:
    """规则判断内容类型"""
    text_lower = text.lower()

    # 论文特征
    paper_keywords = [
        r"doi\s*:",
        r"arxiv",
        r"abstract",
        r"introduction",
        r"methodology",
        r"experiment",
        r"conclusion",
        r"references?",
        r"ieee",
        r"acm\b",
    ]
    paper_score = sum(1 for kw in paper_keywords if re.search(kw, text_lower))
    if paper_score >= 3:
        return "论文"

    # 快讯/新闻特征
    news_keywords = [r"据.*报道", r"记者", r"据悉", r"快讯", r"日.*电"]
    if any(re.search(kw, text_lower) for kw in news_keywords):
        return "快讯"

    # 技术文档特征
    tech_keywords = [
        r"api",
        r"function",
        r"class\b",
        r"method",
        r"parameter",
        r"config",
        r"install",
        r"usage",
        r"example",
        r"tutorial",
        r"documentation",
    ]
    tech_score = sum(1 for kw in tech_keywords if re.search(kw, text_lower))
    if tech_score >= 3:
        return "技术文档"

    return "文章"


def _extract_title(text: str) -> str:
    """规则提取标题"""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    # 优先取 # 开头
    for line in lines:
        m = re.match(r"^#{1,4}\s+(.+)$", line)
        if m:
            return m.group(1).strip()

    # 其次取第一个非空短行（≤80 字符）
    for line in lines:
        if 5 <= len(line) <= 80:
            return line

    # 最后截取前 60 字符
    text_clean = re.sub(r"\s+", " ", text).strip()
    return text_clean[:60] + "..." if len(text_clean) > 60 else text_clean


def _extract_summary(text: str) -> str:
    """规则提取摘要 — 取前 2-3 句"""
    sentences = re.split(r"(?<=[。！？.!?])\s*", text)
    meaningful = [s.strip() for s in sentences if len(s.strip()) > 10]
    summary = " ".join(meaningful[:2])
    return summary[:150] + "..." if len(summary) > 150 else summary


def _extract_key_points(text: str) -> list[str]:
    """规则提取要点 — 找列表项"""
    points = []

    # 找 bullet/数字列表
    for line in text.split("\n"):
        line = line.strip()
        m = re.match(r"^[\-\*\•]\s+(.+)$", line)
        if m:
            points.append(m.group(1).strip()[:50])
            continue
        m = re.match(r"^\d+[\.\)、]\s+(.+)$", line)
        if m:
            points.append(m.group(1).strip()[:50])

    # 找关键句（包含"是|指|表示|意味着"等定义性词）
    if not points:
        sentences = re.split(r"(?<=[。！？.!?])\s*", text)
        for s in sentences[:5]:
            s = s.strip()
            if any(kw in s for kw in ["是", "指", "表示", "意味着", "定义", "关键", "核心"]):
                if len(s) > 10:
                    points.append(s[:50])
                    if len(points) >= 3:
                        break

    return points[:5] if points else ["提取失败 — 请切换 LLM 模式"]


def _extract_entities(text: str) -> EntitiesResult:
    """规则提取实体 — 专有名词启发式"""
    persons = set()
    concepts = set()
    organizations = set()

    # 中文人名启发式（2-4 字，常见姓氏开头）
    name_pattern = re.findall(
        r"((?:欧阳|司马|诸葛|上官|夏侯|慕容|司徒|司空|尉迟|东方|独孤"
        r"|南宫|长孙|宇文|轩辕)"
        r"|"
        r"([李王张刘陈杨赵黄周吴徐孙马胡朱郭何罗高"
        r"林郑梁谢唐许冯宋韩邓彭曹曾田]"
        r"[^\s，。、；：？！,\.;:\?\!]{1,3}))",
        text,
    )
    for m in name_pattern:
        # m is a tuple from two groups; take whichever is non-empty
        n = m[0] or m[1]
        if 2 <= len(n) <= 4:
            persons.add(n)

    # 组织名（公司/机构后缀）
    org_pattern = re.findall(r"([^\s，。、；：？！]{2,}(?:公司|集团|机构|组织|大学|学院|研究院|局|会))", text)
    for o in org_pattern:
        organizations.add(o.strip())

    # 核心概念（引号包裹的词组）
    concept_pattern = re.findall(r"[「『]([^」』]{2,20})[」』]", text)
    for c in concept_pattern:
        concepts.add(c)

    return {
        "persons": list(persons)[:5],
        "concepts": list(concepts)[:5],
        "organizations": list(organizations)[:3],
    }


def extract_with_rules(text: str) -> ExtractedResult:
    """纯规则提取结构化信息 — 零 LLM 依赖"""
    return {
        "title": _extract_title(text),
        "summary": _extract_summary(text),
        "key_points": _extract_key_points(text),
        "entities": cast("dict[str, list[str]]", _extract_entities(text)),
        "content_type": _detect_content_type(text),
        "importance": "medium",
        "tags": [],
        "_fallback": "rules",
    }


def extract(text: str, model: str | None = None) -> ExtractedResult:
    """多级 fallback 提取链：Ollama LLM → 规则提取 → 默认值

    Args:
        text: 原始文本内容
        model: 可选 Ollama 模型名，None 时自动检测

    Returns:
        结构化 dict，包含 _fallback 和 fallback_reason 键标记提取来源和原因
    """
    # 第 1 级：LLM 提取
    if text.strip():
        result = extract_with_ollama(text, model)
        if "error" not in result:
            result["_fallback"] = "llm"
            result["fallback_reason"] = None
            logger.info("LLM extraction succeeded")
            return result
        error_msg = result.get("error", "unknown error")
        logger.warning("LLM extraction failed: %s, falling back to rules", error_msg)
    else:
        logger.warning("Empty text provided to extract()")
        return _default_result("empty text")

    # 第 2 级：规则提取
    logger.info("Falling back to rule-based extraction")
    rules_result = extract_with_rules(text)
    rules_result["fallback_reason"] = f"LLM extraction failed: {error_msg}, fell back to rule-based extraction"
    return rules_result


def _default_result(reason: str = "unknown") -> ExtractedResult:
    return {
        "title": "未命名",
        "summary": "",
        "key_points": [],
        "entities": {},
        "quotes": [],
        "content_type": "文章",
        "importance": "medium",
        "tags": [],
        "_fallback": "default",
        "fallback_reason": f"Default fallback triggered: {reason}",
    }


class ExtractedContent:
    """提取结果的结构化封装"""

    def __init__(self, raw: Mapping[str, Any]):
        self.title = raw.get("title", "未命名")
        self.summary = raw.get("summary", "")
        self.key_points = raw.get("key_points", [])
        self.entities = raw.get("entities", {})
        self.quotes = raw.get("quotes", [])
        self.content_type = raw.get("content_type", "文章")
        self.importance = raw.get("importance", "medium")
        self.tags = raw.get("tags", [])

    @property
    def is_valid(self) -> bool:
        return bool(self.title) and bool(self.summary)

    def to_markdown(self, source_url: str, source_label: str) -> str:
        """转 Obsidian 可读 Markdown"""
        lines = []
        lines.append("---")
        lines.append(f'title: "{self.title}"')
        lines.append("tags:")
        for t in self.tags:
            lines.append(f"  - {t}")
        lines.append(f"  - importance/{self.importance}")
        lines.append("  - pipeline/kronos-auto")
        lines.append("created: 2026-05-23")
        lines.append(f'source_url: "{source_url}"')
        lines.append(f"source: {source_label}")
        lines.append("---")
        lines.append("")
        lines.append(f"# {self.title}")
        lines.append("")
        lines.append(f"> {self.summary}")
        lines.append("")
        if self.key_points:
            lines.append("## 要点")
            for p in self.key_points:
                lines.append(f"- {p}")
            lines.append("")
        if self.quotes:
            lines.append("## 摘录")
            for q in self.quotes:
                lines.append(f"> {q}")
            lines.append("")
        if self.entities:
            parts = []
            if self.entities.get("concepts"):
                parts.append(f"概念: {'; '.join(self.entities['concepts'][:5])}")
            if self.entities.get("persons"):
                parts.append(f"人物: {'; '.join(self.entities['persons'][:5])}")
            if parts:
                lines.append("## 实体")
                for p in parts:
                    lines.append(f"- {p}")
                lines.append("")
        lines.append("---")
        lines.append("*Kronos 自动处理*")
        return "\n".join(lines)


# ── Ollama 集成（从 fetch_router 移入） ──

_DEFAULT_OLLAMA_MODEL: str | None = None


def _detect_ollama_model() -> str:
    """检测 Ollama 中可用的最佳模型"""
    global _DEFAULT_OLLAMA_MODEL
    if _DEFAULT_OLLAMA_MODEL:
        return _DEFAULT_OLLAMA_MODEL
    try:
        import httpx

        resp = httpx.get("http://localhost:11434/api/tags", timeout=3)
        if resp.status_code == 200:
            resp_data: dict[str, Any] = resp.json()
            models = resp_data.get("models", [])
            preferred = ["qwen3.5:4b", "qwen3.5:9b", "qwen3-coder-next", "gemma4:e2b", "llama3.2:3b"]
            for name in preferred:
                for m in models:
                    if m.get("name", "").startswith(name):
                        model_name: str = m["name"]
                        _DEFAULT_OLLAMA_MODEL = model_name
                        return model_name
            if models:
                first_model: str = models[0]["name"]
                _DEFAULT_OLLAMA_MODEL = first_model
                return first_model
    except Exception:
        pass
    return "qwen2.5:7b"


# omlx 默认 model (Apple Silicon MLX server :8000, aetherforge 统一网关的本地 Provider).
# 替代 Ollama 推理. aetherforge SSOT 网关跨包 (kairon 不依赖 aetherforge) 待 BOS RPC 工程化,
# 当前 kronos 直连 omlx :8000 (OpenAI 兼容), omlx 即 aetherforge 路由的 local engine.
_DEFAULT_OMLX_MODEL = "mythos-fast"


def call_ollama(prompt: str, model: str | None = None, system_prompt: str | None = None) -> str:
    """调用本地 LLM (优先 omlx :8000 OpenAI 兼容, fallback Ollama).

    omlx = Apple Silicon MLX server (aetherforge 统一网关的本地 Provider, 替代 Ollama 推理).
    Ollama 保留 fallback (过渡). aetherforge SSOT 网关 (run_generate) 跨包待 BOS RPC 工程化.
    """
    # 优先 omlx :8000 (OpenAI 兼容 /v1/chat/completions)
    try:
        import httpx

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        resp = httpx.post(
            os.environ.get("LLM_GATEWAY_URL", "http://100.96.126.35:4000") + "/v1/chat/completions",
            json={"model": model or _DEFAULT_OMLX_MODEL, "messages": messages, "stream": False},
            timeout=120,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        pass  # omlx 不可用, fallback Ollama

    # fallback Ollama (旧逻辑, 过渡保留)
    if model is None:
        model = _detect_ollama_model()
    payload: dict = {"model": model, "prompt": prompt, "stream": False}
    if system_prompt:
        payload["system"] = system_prompt
    try:
        import httpx

        resp = httpx.post(OLLAMA_GENERATE_URL, json=payload, timeout=120)
        if resp.status_code != 200:
            return f"[Ollama HTTP {resp.status_code}: {resp.text[:200]}"
        resp_data: dict[str, Any] = resp.json()
        response_text: str = resp_data.get("response", "")
        return response_text
    except ImportError:
        return "[Ollama 需要 httpx: pip install httpx]"
    except Exception as e:
        return f"[Ollama error: {e}]"


def extract_with_ollama(text: str, model: str | None = None) -> ExtractedResult | ErrorResult:
    """用本地模型提取结构化内容"""
    if model is None:
        model = _detect_ollama_model()
    system = "你是一个内容分析助手。从输入文本中提取结构化信息，只输出 JSON。"
    prompt = f"""从以下内容中提取结构化信息，输出纯 JSON（不要 markdown 代码块）：
{{
  "title": "标题",
  "summary": "一句话概括",
  "key_points": ["要点1", "要点2", "要点3"],
  "entities": {{"persons": ["人名"], "concepts": ["核心概念"], "organizations": ["组织名"]}},
  "content_type": "文章|论文|快讯",
  "importance": "high|medium|low"
}}

内容：
{text[:8000]}
"""
    response = call_ollama(prompt, model, system)
    if response.startswith("[Ollama"):
        return {"error": response}
    try:
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            result: ExtractedResult | ErrorResult = json.loads(json_match.group())
            return result
        return {"error": "模型返回非 JSON 格式", "raw": response[:300]}
    except Exception as e:
        return {"error": str(e), "raw": response[:200]}
