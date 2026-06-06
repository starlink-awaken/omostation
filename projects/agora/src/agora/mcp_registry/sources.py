"""External source discovery for MCP tools — GitHub + central registry."""

import asyncio
import json
import os
from typing import Any

import httpx
import structlog

from agora.mcp_registry.evaluator import QualityScorer  # type: ignore[import-not-found]

logger = structlog.get_logger(__name__)

_DEFAULT_REGISTRY_URL = "https://raw.githubusercontent.com/starlink-awaken/mcp-registry/main/registry.json"
_GITHUB_API = "https://api.github.com"


def _github_token() -> str | None:
    return os.environ.get("GITHUB_TOKEN")


async def search_github(
    query: str = "mcp-server",
    min_stars: int = 0,
    max_results: int = 30,
) -> list[dict[str, Any]]:
    """Search GitHub for MCP repositories.

    Args:
        query: GitHub topic/search query.
        min_stars: Minimum star count filter.
        max_results: Maximum results (capped at 100 per GitHub API).

    Returns:
        List of tool dicts with standardized fields.
    """
    url = f"{_GITHUB_API}/search/repositories?q=topic:{query}&sort=stars&order=desc&per_page={min(max_results, 100)}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = _github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=15.0)
    except httpx.HTTPError as e:
        logger.error("github_search_failed", query=query, error=str(e))
        return []

    if resp.status_code != 200:
        logger.warning(
            "github_search_non_200",
            query=query,
            status=resp.status_code,
        )
        return []

    data = resp.json()
    items = data.get("items", [])
    results: list[dict[str, Any]] = []

    for item in items:
        stars = item.get("stargazers_count", 0)
        if stars < min_stars:
            continue

        language = item.get("language", "") or ""
        topics = item.get("topics", []) or []
        if language.lower() == "python" or "python" in topics:
            tool_type = "python"
        elif language.lower() in ("javascript", "typescript", "js", "ts") or any(
            t in topics for t in ("javascript", "typescript", "node", "nodejs")
        ):
            tool_type = "node"
        else:
            tool_type = "unknown"

        results.append(
            {
                "name": item.get("full_name", ""),
                "description": item.get("description") or "",
                "repo_url": item.get("html_url", ""),
                "tool_type": tool_type,
                "stars": stars,
                "source": "github",
                "version": "",
                "tags": topics,
                "metadata": {
                    "full_name": item.get("full_name", ""),
                    "language": language,
                    "updated_at": item.get("updated_at", ""),
                    "open_issues": item.get("open_issues_count", 0),
                    "license": item.get("license", {}).get("spdx_id", "") if item.get("license") else "",
                },
            }
        )

    logger.info("github_search_complete", query=query, results=len(results))
    return results


async def search_registry(
    registry_url: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch MCP tools from the central registry JSON.

    Supports http://, https://, file:// URLs, and local file paths.

    Args:
        registry_url: URL/path to the registry JSON. Defaults to the project registry.

    Returns:
        List of tool dicts with standardized fields.
    """
    url = registry_url or _DEFAULT_REGISTRY_URL

    # Handle local file paths (file:// prefix or bare path)
    if url.startswith("file://"):
        filepath = url[len("file://") :]
        try:
            with open(filepath) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error("registry_local_file_failed", path=filepath, error=str(e))
            return []
    elif not url.startswith(("http://", "https://")):
        # Assume it's a local file path
        try:
            with open(url) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error("registry_local_file_failed", path=url, error=str(e))
            return []
    else:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=15.0)
        except httpx.HTTPError as e:
            logger.error("registry_fetch_failed", url=url, error=str(e))
            return []

        if resp.status_code != 200:
            logger.warning("registry_fetch_non_200", url=url, status=resp.status_code)
            return []

        try:
            data = resp.json()
        except Exception as e:
            logger.error("registry_parse_failed", url=url, error=str(e))
            return []

    services = data if isinstance(data, list) else data.get("services", [])

    results: list[dict[str, Any]] = []
    for svc in services:
        if not isinstance(svc, dict):
            continue
        tags = svc.get("tags", []) or []
        metadata = svc.get("metadata", {}) or {}
        metadata["verified"] = svc.get("verified", metadata.get("verified", False))

        results.append(
            {
                "name": svc.get("name", ""),
                "description": svc.get("description") or "",
                "repo_url": svc.get("repo_url") or svc.get("repository", ""),
                "tool_type": svc.get("tool_type", ""),
                "stars": svc.get("stars", 0),
                "source": "registry",
                "version": svc.get("version", ""),
                "tags": tags if isinstance(tags, list) else [],
                "metadata": metadata,
            }
        )

    logger.info("registry_fetch_complete", url=url, results=len(results))
    return results


async def search_all(
    query: str = "mcp-server",
    sources: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Search all specified sources concurrently and return merged, scored results.

    Args:
        query: Search query string.
        sources: List of source names (e.g. ["github", "registry"]). Defaults to all.

    Returns:
        Deduplicated, scored, sorted list of tool dicts.
    """
    if sources is None:
        sources = ["github", "registry"]

    source_map: dict[str, Any] = {
        "github": lambda: search_github(query),
        "registry": search_registry,
    }

    tasks = [source_map[source_name]() for source_name in sources if source_name in source_map]
    if not tasks:
        logger.warning("search_all_no_valid_sources", sources=sources)
        return []

    gathered = await asyncio.gather(*tasks, return_exceptions=True)

    # Merge results: first seen by name wins
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for result in gathered:
        if isinstance(result, Exception):
            logger.error("search_all_source_error", error=str(result))
            continue
        for item in result:
            name = item.get("name", "")
            if name and name not in seen:
                seen.add(name)
                merged.append(item)

    # Score and sort
    for item in merged:
        item["quality_score"] = QualityScorer.evaluate(item)
    merged.sort(key=lambda x: x.get("quality_score", 0), reverse=True)

    logger.info(
        "search_all_complete",
        query=query,
        sources=sources,
        total=len(merged),
    )
    return merged
