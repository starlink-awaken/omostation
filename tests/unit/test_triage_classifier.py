"""Unit tests for TriageClassifier and intent complexity tiering."""

from __future__ import annotations

from omlxc.dataplane.triage import ComplexityTier, TriageClassifier
from omlxc.domain.protocols import ChatMessage


def test_triage_explicit_thinking_and_hints() -> None:
    classifier = TriageClassifier()

    # Explicit thinking
    res1 = classifier.classify(thinking_requested=True)
    assert res1.tier == ComplexityTier.REASONING

    # DeepSeek R1 model hint
    res2 = classifier.classify(model_hint="deepseek-r1-distill-qwen-32b")
    assert res2.tier == ComplexityTier.REASONING


def test_triage_token_thresholds() -> None:
    classifier = TriageClassifier(fast_token_threshold=100, reasoning_token_threshold=2000)

    # Large context tokens
    res_large = classifier.classify(context_tokens=3500)
    assert res_large.tier == ComplexityTier.REASONING

    # Short simple query
    msg = (ChatMessage(role="user", content="fix typo in variable name"),)
    res_fast = classifier.classify(messages=msg, context_tokens=50)
    assert res_fast.tier == ComplexityTier.FAST


def test_triage_keywords_and_code_blocks() -> None:
    classifier = TriageClassifier()

    # Keyword match: refactor architecture
    msg1 = (
        ChatMessage(role="user", content="Please refactor architecture of the data plane."),
    )
    res1 = classifier.classify(messages=msg1, context_tokens=500)
    assert res1.tier == ComplexityTier.REASONING

    # Multiple code blocks
    content_multi_code = (
        "Review these:\n```python\na=1\n```\n```python\nb=2\n```\n```python\nc=3\n```"
    )
    msg2 = (ChatMessage(role="user", content=content_multi_code),)
    res2 = classifier.classify(messages=msg2, context_tokens=800)
    assert res2.tier == ComplexityTier.REASONING

    # Standard fallback
    msg3 = (
        ChatMessage(
            role="user", content="Write a python function to fetch weather data from API."
        ),
    )
    res3 = classifier.classify(messages=msg3, context_tokens=400)
    assert res3.tier == ComplexityTier.STANDARD
