"""Minerva LLM client module."""

from minerva.llm.client import (
    OpenAICompatibleClient as _OriginalOpenAICompatibleClient,
)

__all__ = ["OpenAICompatibleClient"]
