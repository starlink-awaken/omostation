"""Tests for Memory Spine knowledge deduplication."""

from unittest.mock import AsyncMock, patch

import pytest

from agora.mcp.bos_resolver import _memory_all_search


@pytest.mark.asyncio
async def test_memory_all_search_deduplicates_snippets():
    """Identical snippets from different sources should be collapsed."""

    async def _fake_resolve(uri, args, proxy_manager=None):
        if "kos" in uri:
            return {
                "result": [
                    {"id": "k1", "snippet": "shared knowledge snippet", "score": 0.9},
                    {"id": "k2", "snippet": "unique kos snippet", "score": 0.8},
                ]
            }
        if "gbrain" in uri:
            return {
                "result": {
                    "results": [
                        {
                            "id": "g1",
                            "snippet": "shared knowledge snippet",
                            "score": 0.85,
                        },
                        {"id": "g2", "snippet": "unique gbrain snippet", "score": 0.75},
                    ]
                }
            }
        if "vault" in uri:
            return {
                "result": [
                    {"id": "v1", "snippet": "shared knowledge snippet", "score": 0.7}
                ]
            }
        return {"result": []}

    with patch(
        "agora.mcp.bos_resolver.resolve_bos_uri", new_callable=AsyncMock
    ) as mock_resolve:
        mock_resolve.side_effect = _fake_resolve
        result = await _memory_all_search({"query": "knowledge", "limit": 10})

    assert result["status"] == "ok"
    snippets = [r["snippet"] for r in result["result"]]
    # The shared snippet appears in all three backends but must only be returned once.
    assert snippets.count("shared knowledge snippet") == 1
    assert "unique kos snippet" in snippets
    assert "unique gbrain snippet" in snippets
