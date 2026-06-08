"""AWS Bedrock provider — Claude, Llama, Mistral via AWS Bedrock Runtime.

Environment variables:
    AWS_ACCESS_KEY_ID:       AWS access key.
    AWS_SECRET_ACCESS_KEY:   AWS secret key.
    AWS_REGION:              AWS region (default ``us-east-1``).
    AWS_BEDROCK_MODEL_ID:    Default model ID (default ``anthropic.claude-3-sonnet-20240229``).

Uses ``boto3`` for API calls.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from ..provider import LLMProvider, LLMRequest, LLMResponse

_log = logging.getLogger(__name__)

_DEFAULT_REGION = "us-east-1"
_DEFAULT_MODEL = "anthropic.claude-3-sonnet-20240229"

# Bedrock model IDs by provider
_KNOWN_MODELS = [
    "anthropic.claude-3-sonnet-20240229",
    "anthropic.claude-3-haiku-20240307",
    "anthropic.claude-3-opus-20240229",
    "anthropic.claude-3-5-sonnet-20240620",
    "meta.llama3-70b-instruct-v1:0",
    "meta.llama3-8b-instruct-v1:0",
    "mistral.mistral-large-2402-v1:0",
    "mistral.mixtral-8x7b-instruct-v0:1",
    "amazon.titan-text-premier-v1:0",
    "cohere.command-r-plus-v1:0",
]


class BedrockProvider(LLMProvider):
    """AWS Bedrock provider via ``boto3``."""

    @property
    def provider_name(self) -> str:
        return "bedrock"

    def available_models(self) -> list[str]:
        return list(_KNOWN_MODELS)

    def __init__(
        self,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        region: str | None = None,
        model_id: str | None = None,
    ) -> None:
        super().__init__()
        self._aws_key = aws_access_key_id or os.environ.get("AWS_ACCESS_KEY_ID", "")
        self._aws_secret = aws_secret_access_key or os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        self._region = region or os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", _DEFAULT_REGION))
        self._model_id = model_id or os.environ.get("AWS_BEDROCK_MODEL_ID", _DEFAULT_MODEL)
        self.default_model = self._model_id
        self._runtime: Any | None = None

    def is_available(self) -> bool:
        if not self._aws_key or not self._aws_secret:
            return False
        try:
            import boto3  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_runtime(self) -> Any:
        if self._runtime is None:
            import boto3
            session = boto3.Session(
                aws_access_key_id=self._aws_key,
                aws_secret_access_key=self._aws_secret,
                region_name=self._region,
            )
            self._runtime = session.client("bedrock-runtime")
        return self._runtime

    def _build_body(self, request: LLMRequest) -> bytes:
        """Build the request body based on model provider."""
        model = request.model or self.default_model
        prompt = request.prompt

        if model.startswith("anthropic.claude"):
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            if request.system_prompt:
                body["system"] = request.system_prompt
        elif model.startswith("meta.llama"):
            body = {
                "prompt": f"<|begin_of_text|>{'<|start_header_id|>system<|end_header_id|>' + request.system_prompt + '<|eot_id|>' if request.system_prompt else ''}<|start_header_id|>user<|end_header_id|>{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>",
                "max_gen_len": request.max_tokens,
                "temperature": request.temperature,
            }
        else:
            body = {
                "prompt": prompt,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
            }
            if request.system_prompt:
                body["system"] = request.system_prompt
        return json.dumps(body).encode("utf-8")

    def _parse_response(self, response: dict, model: str) -> LLMResponse:
        """Parse Bedrock response based on model provider."""
        body = json.loads(response["body"].read())
        content = ""
        input_tokens = 0
        output_tokens = 0

        if model.startswith("anthropic.claude"):
            content = body.get("content", [{}])[0].get("text", "")
            input_tokens = body.get("usage", {}).get("input_tokens", 0)
            output_tokens = body.get("usage", {}).get("output_tokens", 0)
        elif model.startswith("meta.llama"):
            content = body.get("generation", "")
            input_tokens = body.get("prompt_token_count", 0)
            output_tokens = body.get("generation_token_count", 0)
        else:
            content = body.get("results", [{}])[0].get("outputText", "") if "results" in body else body.get("completion", "")

        return LLMResponse(
            content=content,
            provider="bedrock",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.default_model
        body = self._build_body(request)
        client = self._get_runtime()

        try:
            import boto3  # noqa: F401
            response = client.invoke_model(
                modelId=model,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            return self._parse_response(response, model)
        except Exception as e:
            _log.error("Bedrock generate failed: %s", e)
            raise

    def complete(self, request: LLMRequest) -> LLMResponse:
        return self._sync_complete(request)

    def _sync_complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.default_model
        body = self._build_body(request)
        client = self._get_runtime()

        try:
            response = client.invoke_model(
                modelId=model,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            return self._parse_response(response, model)
        except Exception as e:
            _log.error("Bedrock complete failed: %s", e)
            raise
