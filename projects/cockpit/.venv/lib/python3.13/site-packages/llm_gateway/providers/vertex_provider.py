"""Google Vertex AI provider — Gemini 2.5/2.0/1.5 via google-genai SDK.

Environment variables:
    GOOGLE_CLOUD_PROJECT:    GCP project ID.
    GOOGLE_CLOUD_LOCATION:   GCP location (default ``us-central1``).
    GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON (optional).

Can also use ``GOOGLE_API_KEY`` for simple API key auth (gemini only).
Uses the ``google-genai`` SDK for Vertex AI or ``google-generativeai`` for API key auth.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from ..provider import LLMProvider, LLMRequest, LLMResponse

_log = logging.getLogger(__name__)

_DEFAULT_LOCATION = "us-central1"
_DEFAULT_MODEL = "gemini-2.5-flash-001"

_KNOWN_MODELS = [
    "gemini-2.5-flash-001",
    "gemini-2.5-pro-001",
    "gemini-2.0-flash-001",
    "gemini-1.5-flash-001",
    "gemini-1.5-pro-001",
    "gemini-2.0-flash-lite-001",
]


class VertexAIProvider(LLMProvider):
    """Google Vertex AI provider (Gemini models)."""

    @property
    def provider_name(self) -> str:
        return "vertex"

    def available_models(self) -> list[str]:
        return list(_KNOWN_MODELS)

    def __init__(
        self,
        project: str | None = None,
        location: str | None = None,
        model_id: str | None = None,
        api_key: str | None = None,
    ) -> None:
        super().__init__()
        self._project = project or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        self._location = location or os.environ.get("GOOGLE_CLOUD_LOCATION", _DEFAULT_LOCATION)
        self._model_id = model_id or _DEFAULT_MODEL
        self._api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        self.default_model = self._model_id
        self._client: Any | None = None
        self._use_api_key = bool(self._api_key and not self._project)

    def is_available(self) -> bool:
        has_project = bool(self._project) or bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""))
        has_api_key = bool(self._api_key)
        if not has_project and not has_api_key:
            return False
        try:
            if self._use_api_key:
                import google.generativeai  # noqa: F401
            else:
                import vertexai  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        if self._use_api_key:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            self._client = genai.GenerativeModel(self._model_id)
        else:
            import vertexai
            vertexai.init(project=self._project, location=self._location)
            from vertexai.generative_models import GenerativeModel
            self._client = GenerativeModel(self._model_id)
        return self._client

    def _generate_content(self, request: LLMRequest) -> Any:
        """Generate content using the appropriate SDK."""
        client = self._get_client()
        contents = [request.prompt]

        gen_kwargs = {
            "max_output_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.system_prompt:
            gen_kwargs["system_instruction"] = request.system_prompt

        if self._use_api_key:
            # google-generativeai SDK
            response = client.generate_content(
                contents,
                generation_config=gen_kwargs,
            )
            return response
        else:
            # vertexai SDK
            response = client.generate_content(
                contents,
                generation_config=gen_kwargs,
            )
            return response

    async def generate(self, request: LLMRequest) -> LLMResponse:
        try:
            response = self._generate_content(request)
            return self._parse_response(response, request)
        except Exception as e:
            _log.error("Vertex AI generate failed: %s", e)
            raise

    def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            response = self._generate_content(request)
            return self._parse_response(response, request)
        except Exception as e:
            _log.error("Vertex AI complete failed: %s", e)
            raise

    def _parse_response(self, response: Any, request: LLMRequest) -> LLMResponse:
        model = request.model or self.default_model

        if self._use_api_key:
            # google-generativeai SDK response
            try:
                content = response.text
            except (ValueError, AttributeError):
                content = str(response)
            usage = getattr(response, "usage_metadata", None)
            input_tokens = usage.prompt_token_count if usage else 0
            output_tokens = usage.candidates_token_count if usage else 0
        else:
            # vertexai SDK response
            try:
                content = response.text
            except (ValueError, AttributeError):
                content = str(response)
            usage = getattr(response, "usage_metadata", None)
            input_tokens = usage.prompt_token_count if usage else 0
            output_tokens = usage.candidates_token_count if usage else 0

        return LLMResponse(
            content=content,
            provider="vertex",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    # is_available() defined above
