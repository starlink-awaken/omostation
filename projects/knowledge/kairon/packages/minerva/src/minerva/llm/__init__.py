"""Minerva LLM client module."""

from minerva.llm.client import (
    OpenAICompatibleClient as _OriginalOpenAICompatibleClient,  # noqa: F401
)

__all__ = ["OpenAICompatibleClient"]
