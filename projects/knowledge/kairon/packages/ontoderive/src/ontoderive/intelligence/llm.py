"""
OntoDerive LLM增强层 — 零依赖降级 + 本地模型增强
===================================================
默认使用规则引擎（零依赖），当LLM可用时自动增强推导质量。
支持的LLM后端：ollama(本地), openai API, anthropic API
"""

from __future__ import annotations

import os
from typing import Any

from .providers import BACKENDS, BaseProvider, detect_backend


class LLMEnhancer:
    """LLM增强器 — 失败时静默降级为规则引擎

    自动检测顺序:
    1. ollama CLI → 模型列表 | 要求: ollama 已安装
    2. 本地API → OpenAI兼容端点 | 要求: ONTODERIVE_LLM_URL 或 localhost:11434
    3. OPENAI_API_KEY → openai 后端
    4. ANTHROPIC_API_KEY → anthropic 后端
    """

    def __init__(self, backend: Any = "auto", model: Any = None, base_url: Any = None) -> None:
        if backend == "auto":
            backend = os.environ.get("ONTODERIVE_LLM_BACKEND", "auto")
        if backend == "auto":
            backend_name, auto_model = detect_backend()
            self.backend = backend_name
            if auto_model and not model:
                model = auto_model
        else:
            self.backend = backend

        self.model = model or os.environ.get("LLM_MODEL") or os.environ.get("ONTODERIVE_LLM_MODEL", "")
        self.base_url = base_url or os.environ.get("LLM_BASE_URL") or os.environ.get("ONTODERIVE_LLM_URL", "")
        self._provider = self._build_provider()
        self.available = self._provider.probe()

    def _build_provider(self) -> BaseProvider:
        cls = BACKENDS.get(self.backend)
        if cls is None:
            return BACKENDS["none"]()
        return cls(model=self.model, base_url=self.base_url)

    def _call(self, prompt: Any, system: Any = "", temperature: Any = 0.3) -> Any:
        if not self.available:
            return None
        try:
            return self._provider.call(prompt, system, temperature)
        except Exception as e:
            import sys

            print(f"[llm] 调用失败: {e}", file=sys.stderr)
            return None

    # ── 三个增强入口 ──

    def enhance_derivation_hints(self, facts_summary: Any, inferences_text: Any, existing_hints: Any) -> Any:
        """增强推导提示：LLM读取推论全文，生成洞察"""
        if not self.available or self.backend == "none":
            return existing_hints
        prompt = f"""分析以下推论，给出1-2条推导建议。每条20字以内。只输出建议，一行一条。

事实: {facts_summary}
推论:
{inferences_text[:1500]}"""
        result = self._call(prompt, "你是知识工程分析专家。简洁输出。", 0.3)
        if result:
            lines = [
                line.strip("- 1234567890.*# ") for line in result.split("\n") if line.strip() and len(line.strip()) > 4
            ]
            return existing_hints + lines[:2]
        return existing_hints

    def detect_contradictions(self, inference_a: Any, inference_b: Any, shared_facts: Any) -> Any:
        """语义矛盾检测：LLM判断两个推论是否真正矛盾"""
        if not self.available or self.backend == "none":
            return None
        prompt = f"""判断以下两个推论是否存在实质性矛盾。仅回答YES或NO。

推论A: {inference_a[:200]}
推论B: {inference_b[:200]}
共享事实: {shared_facts}

是否存在矛盾？(YES/NO):"""
        result = self._call(prompt, "仅回答YES或NO。", 0.1)
        return result and "YES" in result.upper()

    def smart_match_tools(self, goal: Any, context: Any, tools_descriptions: Any) -> Any:
        """智能工具匹配：LLM替代TF-IDF做语义匹配"""
        if not self.available or self.backend == "none":
            return None
        tools_text = "\n".join(
            f"- {t['id']}: {t['name']} — {t.get('description', '')[:60]}" for t in tools_descriptions[:30]
        )
        prompt = f"""分析目标并从工具列表中选出最合适的3个工具ID。

目标: {goal}
上下文: {context}

工具列表:
{tools_text}

只输出3个工具ID，用逗号分隔（如 M-001, S-003, T-001）:"""
        result = self._call(prompt, "只输出工具ID，逗号分隔。", 0.1)
        if result:
            ids = [x.strip() for x in result.split(",")[:3]]
            return ids
        return None


# 模块级单例
_enhancer: LLMEnhancer | None = None


def get_enhancer(force: Any = False) -> Any:
    global _enhancer
    if _enhancer is None or force:
        _enhancer = LLMEnhancer()
    return _enhancer
