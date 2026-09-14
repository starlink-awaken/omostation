"""Tests for OpenAICompatibleClient."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestOpenAICompatibleClient:
    """Tests for the LLM client."""

    @pytest.mark.asyncio
    async def test_generate_mock(self):
        """Test generate() with mocked HTTP response."""
        from minerva.llm.client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://localhost:11434/v1",
            model="qwen3:30b-a3b",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Hello, world!"}}]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await client.generate(
                system="You are helpful.",
                prompt="Say hello",
                temperature=0.1,
            )

        assert result == "Hello, world!"
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0].endswith("/chat/completions")
        payload = call_args[1]["json"]
        assert payload["model"] == "qwen3:30b-a3b"
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"
        assert payload["temperature"] == 0.1

    @pytest.mark.asyncio
    async def test_generate_no_system(self):
        """Test generate() without system prompt."""
        from minerva.llm.client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://localhost:11434/v1",
            model="qwen3:30b-a3b",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "OK"}}]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await client.generate(system=None, prompt="test")

        assert result == "OK"
        payload = mock_post.call_args[1]["json"]
        # When system is None, only user message should be present
        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_generate_http_error(self):
        """Test generate() propagates HTTP errors."""
        import httpx
        from minerva.llm.client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://localhost:11434/v1",
            model="qwen3:30b-a3b",
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=MagicMock(status_code=500)
            )
            with pytest.raises(httpx.HTTPStatusError):
                await client.generate(system=None, prompt="test")

    @pytest.mark.asyncio
    async def test_generate_timeout(self):
        """Test generate() propagates timeout errors."""
        import httpx
        from minerva.llm.client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://localhost:11434/v1",
            model="qwen3:30b-a3b",
            timeout=5,
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Request timeout")
            with pytest.raises(httpx.TimeoutException):
                await client.generate(system=None, prompt="test")

    @pytest.mark.asyncio
    async def test_generate_missing_choices(self):
        """Test generate() handles response with no choices gracefully."""
        from minerva.llm.client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://localhost:11434/v1",
            model="qwen3:30b-a3b",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": []}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises((IndexError, KeyError)):
                await client.generate(system=None, prompt="test")

    @pytest.mark.asyncio
    async def test_generate_custom_params(self):
        """Test generate() sends custom temperature and max_tokens."""
        from minerva.llm.client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://localhost:11434/v1",
            model="qwen3:30b-a3b",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Cold"}}]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await client.generate(
                system="Be brief.",
                prompt="test",
                temperature=0.1,
                max_tokens=100,
            )

        assert result == "Cold"
        payload = mock_post.call_args[1]["json"]
        assert payload["temperature"] == 0.1
        assert payload["max_tokens"] == 100

    @pytest.mark.asyncio
    async def test_generate_auth_header(self):
        """Test generate() sends Authorization header when api_key is set."""
        from minerva.llm.client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="https://api.deepseek.com",
            model="deepseek-v4-pro",
            api_key="sk-test-key-123",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Auth OK"}}]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await client.generate(system=None, prompt="test")

        assert result == "Auth OK"
        headers = mock_post.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer sk-test-key-123"
