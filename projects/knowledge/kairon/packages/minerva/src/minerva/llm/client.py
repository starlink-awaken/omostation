"""OpenAI-compatible LLM client — single interface for Ollama (local) and DeepSeek (cloud)."""

from __future__ import annotations

from typing import cast

import httpx


class OpenAICompatibleClient:
    """Thin wrapper around OpenAI-compatible /v1/chat/completions endpoint.

    Works with: Ollama (localhost:11434/v1), DeepSeek (api.deepseek.com/v1),
    LM Studio (localhost:1234/v1), and any OpenAI-compatible provider.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str = "ollama",
        model: str = "qwen3.6:35b-a3b-coding-nvfp4",
        timeout: int = 120,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def _http(self) -> httpx.AsyncClient:
        """Lazy-initialized HTTP client with connection pooling."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Send chat completion request. Returns raw text response.

        Args:
            prompt: User prompt
            system: System prompt (optional, None to omit)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens in response

        Returns:
            Raw text from the model's response

        Raises:
            httpx.HTTPError: On network or HTTP failures
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        resp = await self._http.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return cast("str", data["choices"][0]["message"]["content"])
