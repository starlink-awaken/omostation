"""LLM Provider 接口 + 后端实现 — 可插拔"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, cast


def _standard_llm_provider() -> str:
    return os.environ.get("LLM_PROVIDER", "").strip().lower()


def _standard_llm_api_key() -> str | None:
    value = os.environ.get("LLM_API_KEY", "").strip()
    return value or None


class BaseProvider(ABC):
    """LLM provider 抽象基类"""

    def __init__(self, model: str = "", base_url: str = "") -> None:
        self.model = model
        self.base_url = base_url

    @abstractmethod
    def call(self, prompt: str, system: str = "", temperature: float = 0.3) -> str | None: ...

    @abstractmethod
    def probe(self) -> bool: ...


class OllamaProvider(BaseProvider):
    def call(self, prompt: Any, system: Any = "", temperature: Any = 0.3) -> Any:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        try:
            r = subprocess.run(
                ["ollama", "run", self.model, full_prompt],
                capture_output=True,
                text=True,
                timeout=15,
            )
            return r.stdout.strip() if r.returncode == 0 else None
        except (FileNotFoundError, subprocess.TimeoutExpired, TimeoutError):
            return None

    def probe(self) -> Any:
        if not self.model:
            # auto-select
            self.model = _auto_select_ollama_model()
            return bool(self.model)
        try:
            models = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=3)
            return models.returncode == 0 and self.model in models.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False


def _auto_select_ollama_model() -> str:
    """从已安装的 ollama 模型中选一个优先级高的"""
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=3)
        if r.returncode != 0:
            return ""
        models = r.stdout
        for m in ["qwen3.5:4b", "qwen2.5:7b", "qwen2.5:3b", "gemma4:e2b", "qwen2.5:1.5b", "llama3.2:3b"]:
            if m in models:
                return m
        first = models.strip().split("\n")[1] if "\n" in models else ""
        return first.split()[0] if first else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


class OpenAIProvider(BaseProvider):
    def call(self, prompt: Any, system: Any = "", temperature: Any = 0.3) -> Any:
        try:
            from openai import OpenAI

            client_kwargs = {}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
            api_key = _standard_llm_api_key() or os.environ.get("OPENAI_API_KEY")
            if api_key:
                client_kwargs["api_key"] = api_key
            elif self.base_url:
                client_kwargs["api_key"] = "litellm"

            client = OpenAI(**cast("Any", client_kwargs))
            resp = client.chat.completions.create(
                model=self.model or os.environ.get("ONTODERIVE_LLM_MODEL", "gpt-4o-mini"),
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=500,
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"[llm] OpenAI调用失败: {e}", file=sys.stderr)
            return None

    def probe(self) -> Any:
        return bool(_standard_llm_api_key() or os.environ.get("OPENAI_API_KEY") or self.base_url)


class AnthropicProvider(BaseProvider):
    def call(self, prompt: Any, system: Any = "", temperature: Any = 0.3) -> Any:
        try:
            import anthropic  # type: ignore[reportMissingImports]

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if _standard_llm_provider() == "anthropic":
                api_key = _standard_llm_api_key() or api_key
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model=self.model or os.environ.get("ONTODERIVE_LLM_MODEL", "claude-sonnet-4-20250514"),
                system=system or None,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=temperature,
            )
            return resp.content[0].text if resp.content else None
        except Exception as e:
            print(f"[llm] Anthropic调用失败: {e}", file=sys.stderr)
            return None

    def probe(self) -> Any:
        return bool(
            os.environ.get("ANTHROPIC_API_KEY") or (_standard_llm_provider() == "anthropic" and _standard_llm_api_key())
        )


class LocalProvider(BaseProvider):
    """本地 OpenAI 兼容 API (ollama/lmstudio 等)"""

    def call(self, prompt: Any, system: Any = "", temperature: Any = 0.3) -> Any:
        payload = {"model": self.model, "input": prompt}
        if system:
            payload["system_prompt"] = system
        try:
            req = urllib.request.Request(  # noqa: S310
                self.base_url or os.environ.get("ONTODERIVE_LLM_URL", "http://localhost:11434"),
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
                data = json.loads(resp.read())
            for item in data.get("output", []):
                if item.get("type") == "message":
                    return item.get("content", "").strip()
            return None
        except (json.JSONDecodeError, OSError, ValueError) as e:
            print(f"[llm] 本地API调用失败: {e}", file=sys.stderr)
            return None

    def probe(self) -> bool:
        return True  # connection already verified during detection


class NoneProvider(BaseProvider):
    """空实现 — 静默降级"""

    def call(self, prompt: Any, system: Any = "", temperature: Any = 0.3) -> None:
        return None

    def probe(self) -> bool:
        return False


# 后端注册表
BACKENDS: dict[str, type[BaseProvider]] = {
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "local": LocalProvider,
    "none": NoneProvider,
}


def detect_backend() -> tuple[str, str]:
    """自动检测可用的LLM后端, 返回 (backend_name, model)"""
    standard_provider = _standard_llm_provider()
    standard_model = os.environ.get("LLM_MODEL", "").strip()
    if standard_provider == "ollama":
        return "ollama", standard_model
    if standard_provider in {"litellm", "openai", "openrouter", "deepseek", "siliconflow"}:
        return "openai", standard_model
    if standard_provider == "anthropic":
        return "anthropic", standard_model
    # 1) ollama
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            model = _auto_select_ollama_model()
            return "ollama", model
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    # 2) 本地API
    url = os.environ.get("ONTODERIVE_LLM_URL", "http://localhost:11434")
    try:
        req = urllib.request.Request(url, method="GET")  # noqa: S310
        with urllib.request.urlopen(req, timeout=3):  # noqa: S310
            return "local", ""
    except OSError:
        pass
    # 3) openai key
    if os.environ.get("OPENAI_API_KEY"):
        return "openai", ""
    # 4) anthropic key
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic", ""
    return "none", ""


# ── 向后兼容 ──────────────────────────────────────────
# 新代码优先使用 llm-gateway；若独立 CLI 环境没有安装该包，则回退到本地抽象基类。
try:
    from llm_gateway import provider  # noqa: F401  # type: ignore[reportMissingImports]
except ImportError:
    pass
