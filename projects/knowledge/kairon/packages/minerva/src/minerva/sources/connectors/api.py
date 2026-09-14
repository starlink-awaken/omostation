from __future__ import annotations

"""
Extracted from SharedBrain D_Harvest → minerva.

---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# Api ≡ API
# 内涵 ≝ {Api}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Api)}
# 功能 ⊢ {Init_Api, Execute_Api, Validate_Api}
# =============================================================================

# ---
# domain: D-Harvest
# layer: organ
# status: active
# ---

"""
API Source Connector - Fetches content from REST APIs
Implements adaptive fetching with authentication, headers, pagination, and error handling

Performance optimization: HTTP connection pool reuse
"""
import asyncio
import hashlib
from dataclasses import dataclass
from typing import Any

import httpx
from minerva.sources.connectors import ISourceConnector, RawContent


# 共享的HTTP客户端池 - 这个SB连接池避免重复创建TCP连接
class HTTPClientPool:
    """
    共享的HTTP客户端池管理器（API版本）

    按配置哈希缓存httpx.AsyncClient实例，避免重复创建连接池。
    支持自定义headers和认证配置的连接池管理。
    """

    _pool: dict[str, httpx.AsyncClient] = {}

    @classmethod
    def get_client(cls, config: ApiSourceConfig) -> httpx.AsyncClient:
        """
        获取或创建共享的HTTP客户端

        Args:
            config: ApiSourceConfig 实例

        Returns:
            httpx.AsyncClient: 共享的异步HTTP客户端
        """
        # 生成配置哈希作为缓存键 - 包含headers以支持不同认证配置
        headers_str = str(sorted(config.headers.items())) if config.headers else ""
        config_hash = hashlib.md5(f"{config.url}:{config.timeout}:{config.method}:{headers_str}".encode()).hexdigest()  # noqa: S324

        if config_hash not in cls._pool:
            # 创建新客户端并缓存
            client = httpx.AsyncClient(
                timeout=config.timeout,
                follow_redirects=True,
                headers=dict(config.headers) if config.headers else None,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
            cls._pool[config_hash] = client

        return cls._pool[config_hash]

    @classmethod
    async def close_all(cls) -> None:
        """关闭所有缓存的客户端 - 用于清理资源"""
        for client in cls._pool.values():
            await client.aclose()
        cls._pool.clear()


@dataclass
class ApiSourceConfig:
    """API source configuration"""

    url: str
    method: str = "GET"  # GET, POST, etc.
    headers: dict[str, str] | None = None
    params: dict[str, Any] | None = None
    json_body: dict[str, Any] | None = None
    timeout: float = 10.0
    max_retries: int = 3
    retry_delay: float = 1.0
    max_size: int = 10_000_000  # 10MB limit

    # 认证配置
    auth_type: str = "none"  # none, bearer, basic, api_key
    auth_token: str | None = None  # For bearer token
    api_key: str | None = None  # For API key
    api_key_header: str = "X-API-Key"  # Default header name for API key
    username: str | None = None  # For basic auth
    password: str | None = None  # For basic auth

    # 分页配置
    pagination_type: str = "none"  # none, query, header, link, cursor
    pagination_param: str = "page"  # Query parameter for page number
    pagination_limit: int = 100  # Maximum items per page
    max_pages: int = 10  # Maximum pages to fetch

    def __post_init__(self) -> None:
        """Initialize defaults for mutable fields"""
        if self.headers is None:
            self.headers = {}
        if self.params is None:
            self.params = {}


class ApiSourceConnector(ISourceConnector):
    """Fetches API content with adaptive error handling and pagination support"""

    def __init__(self, config: ApiSourceConfig) -> None:
        self.config = config

    async def fetch(self) -> RawContent:
        """Fetch content from configured API endpoint with retry logic"""
        last_error: Exception | None = None

        # 使用共享的HTTP客户端池 - 这个SB优化避免重复创建TCP连接
        client = HTTPClientPool.get_client(self.config)

        for attempt in range(self.config.max_retries):
            try:
                # 构建请求headers
                headers = dict(self.config.headers or {})
                headers = self._add_auth_headers(headers)

                # 构建请求参数
                params = dict(self.config.params or {})

                # 处理分页
                if self.config.pagination_type == "none":
                    response = await self._make_request(
                        client, self.config.url, self.config.method, params, self.config.json_body
                    )
                    data = await self._process_response(response)
                else:
                    # 处理分页请求
                    data = await self._fetch_paginated(client, params)

                # 将数据转换为字符串
                import json

                content_str = json.dumps(data, ensure_ascii=False, indent=2)
                content_bytes = content_str.encode("utf-8")

                # Check content size
                if len(content_bytes) > self.config.max_size:
                    raise ValueError(f"Content too large: {len(content_bytes)} > {self.config.max_size}")

                return RawContent(
                    uri=self.config.url,
                    data=content_bytes,
                    content_type="application/json",
                    metadata={
                        "status_code": 200,
                        "content_length": len(content_bytes),
                        "attempt": attempt + 1,
                        "pagination_type": self.config.pagination_type,
                        "auth_type": self.config.auth_type,
                    },
                )

            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (2**attempt))
                continue

            except httpx.HTTPStatusError as e:
                # Don't retry client errors (4xx)
                if e.response.status_code < 500:
                    raise
                last_error = e
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (2**attempt))
                continue

            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (2**attempt))
                continue

        # All retries exhausted
        raise ConnectionError(
            f"Failed to fetch {self.config.url} after {self.config.max_retries} attempts"
        ) from last_error

    def _add_auth_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """Add authentication headers based on auth_type"""
        if self.config.auth_type == "bearer" and self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"
        elif self.config.auth_type == "api_key" and self.config.api_key:
            headers[self.config.api_key_header] = self.config.api_key
        elif self.config.auth_type == "basic" and self.config.username and self.config.password:
            # Basic auth will be handled by httpx
            pass  # httpx will handle basic auth via auth parameter

        return headers

    async def _make_request(
        self,
        client: httpx.AsyncClient,
        url: str,
        method: str,
        params: dict | None,
        json_body: dict | None,
    ) -> httpx.Response:
        """Make a single HTTP request"""
        # Handle basic auth
        auth = None
        if self.config.auth_type == "basic" and self.config.username and self.config.password:
            auth = (self.config.username, self.config.password)

        if method.upper() == "GET":
            response = await client.get(url, params=params, auth=auth)
        elif method.upper() == "POST":
            response = await client.post(url, params=params, json=json_body, auth=auth)  # type: ignore[arg-type]
        elif method.upper() == "PUT":
            response = await client.put(url, params=params, json=json_body, auth=auth)  # type: ignore[arg-type]
        elif method.upper() == "DELETE":
            response = await client.delete(url, params=params, auth=auth)  # type: ignore[arg-type]
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        return response

    async def _process_response(self, response: httpx.Response) -> Any:
        """Process API response and return data"""

        content_type = response.headers.get("content-type", "")

        if "application/json" in content_type:
            return response.json()
        else:
            # For non-JSON responses, return text
            return {"text": response.text}

    async def _fetch_paginated(self, client: httpx.AsyncClient, initial_params: dict) -> Any:
        """Fetch paginated data"""

        if self.config.pagination_type == "query":
            return await self._fetch_query_pagination(client, initial_params)
        elif self.config.pagination_type == "cursor":
            return await self._fetch_cursor_pagination(client, initial_params)
        elif self.config.pagination_type == "link":
            return await self._fetch_link_pagination(client, initial_params)
        else:
            raise ValueError(f"Unsupported pagination type: {self.config.pagination_type}")

    async def _fetch_query_pagination(self, client: httpx.AsyncClient, initial_params: dict) -> list:
        """Fetch data using query parameter pagination (e.g., ?page=1, ?page=2)"""
        all_items: list[Any] = []

        for page in range(1, self.config.max_pages + 1):
            params = dict(initial_params)
            params[self.config.pagination_param] = page
            params["limit"] = self.config.pagination_limit

            response = await self._make_request(
                client, self.config.url, self.config.method, params, self.config.json_body
            )

            data: Any = await self._process_response(response)

            # Handle different response structures
            if isinstance(data, list):
                items = data
                if not items:  # Empty page = no more data
                    break
                all_items.extend(items)
            elif isinstance(data, dict):
                # Try common keys for paginated responses
                items = data.get("items", data.get("results", data.get("data", []))) or []
                if not items:
                    break
                all_items.extend(items)

                # Check if there are more pages
                if len(items) < self.config.pagination_limit:
                    break
            else:
                break

        return all_items

    async def _fetch_cursor_pagination(self, client: httpx.AsyncClient, initial_params: dict) -> list:
        """Fetch data using cursor-based pagination"""
        all_items: list[Any] = []
        cursor = None

        for _ in range(self.config.max_pages):
            params = dict(initial_params)
            if cursor:
                params["cursor"] = cursor
            params["limit"] = self.config.pagination_limit

            response = await self._make_request(
                client, self.config.url, self.config.method, params, self.config.json_body
            )

            data: Any = await self._process_response(response)

            # Handle different response structures
            if isinstance(data, dict):
                items = data.get("items", data.get("results", data.get("data", []))) or []
                if not items:
                    break
                all_items.extend(items)

                # Get next cursor
                cursor = data.get("next_cursor", data.get("cursor"))
                if not cursor:
                    break
            else:
                break

        return all_items

    async def _fetch_link_pagination(self, client: httpx.AsyncClient, initial_params: dict) -> list:
        """Fetch data using Link header pagination (GitHub style)"""
        all_items: list[Any] = []
        url = self.config.url

        for _ in range(self.config.max_pages):
            response = await client.get(url, params=initial_params)
            response.raise_for_status()

            data: Any = await self._process_response(response)

            # Handle different response structures
            if isinstance(data, list):
                items = data
                if not items:
                    break
                all_items.extend(items)
            elif isinstance(data, dict):
                items = data.get("items", data.get("results", data.get("data", []))) or []
                if not items:
                    break
                all_items.extend(items)

            # Get next page from Link header
            link_header = response.headers.get("Link", "")
            if 'rel="next"' not in link_header:
                break

            # Extract next URL from Link header
            import re

            next_match = re.search(r'<([^>]+)>; rel="next"', link_header)
            if not next_match:
                break

            url = next_match.group(1)

        return all_items

    async def health_check(self) -> bool:
        """Check if the API source is accessible"""
        try:
            # 使用共享的HTTP客户端池 - 这个SB优化避免重复创建TCP连接
            client = HTTPClientPool.get_client(self.config)
            headers = self._add_auth_headers({})

            # Try HEAD request first
            try:
                response = await client.head(self.config.url, headers=headers)
                return response.status_code < 500
            except Exception:
                # Fall back to GET with minimal data
                params = dict(self.config.params or {})
                # Limit to 1 item for health check
                if self.config.pagination_type != "none":
                    params["limit"] = 1

                response = await client.get(self.config.url, params=params, headers=headers)
                return response.status_code < 500
        except Exception:
            return False

    async def close(self) -> None:
        """Close the shared HTTP client pool and release resources."""
        await HTTPClientPool.close_all()

    @property
    def source_id(self) -> str:
        """Return source identifier"""
        # Generate source ID from URL
        from hashlib import sha256

        url_hash = sha256(self.config.url.encode()).hexdigest()[:16]
        return f"api_{url_hash}"
