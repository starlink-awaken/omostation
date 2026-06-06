"""Quality evaluation engine for MCP tools."""

from datetime import UTC, datetime


class QualityScorer:
    """Composite quality scorer based on stars, freshness, version, usage, and verification."""

    WEIGHTS: dict[str, float] = {
        "stars": 0.20,
        "freshness": 0.15,
        "version": 0.15,
        "local_usage": 0.25,
        "success_rate": 0.15,
        "verified": 0.10,
    }

    @staticmethod
    def normalize_stars(stars: int) -> float:
        if stars >= 5000:
            return 1.0
        if stars >= 1000:
            return 0.9
        if stars >= 500:
            return 0.8
        if stars >= 100:
            return 0.6
        if stars >= 10:
            return 0.4
        if stars >= 1:
            return 0.2
        return 0.0

    @staticmethod
    def normalize_freshness(updated_at: str | None) -> float:
        if not updated_at:
            return 0.5
        try:
            dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            days = (datetime.now(UTC) - dt).days
        except (ValueError, TypeError):
            return 0.5
        if days <= 30:
            return 1.0
        if days <= 90:
            return 0.9
        if days <= 180:
            return 0.7
        if days <= 365:
            return 0.5
        return 0.2

    @staticmethod
    def normalize_version(version: str | None) -> float:
        if not version:
            return 0.3
        if version.startswith("v"):
            version = version[1:]
        parts = version.split(".")
        if len(parts) >= 3:
            return 1.0
        if len(parts) >= 2:
            return 0.7
        return 0.4

    @staticmethod
    def normalize_local_usage(usage_count: int) -> float:
        if usage_count >= 100:
            return 1.0
        if usage_count >= 50:
            return 0.9
        if usage_count >= 20:
            return 0.7
        if usage_count >= 10:
            return 0.5
        if usage_count >= 3:
            return 0.3
        if usage_count >= 1:
            return 0.1
        return 0.0

    @staticmethod
    def evaluate(tool_info: dict) -> float:
        """Calculate composite quality score (0.0-1.0)."""
        stars = QualityScorer.normalize_stars(tool_info.get("stars", 0))
        freshness = QualityScorer.normalize_freshness((tool_info.get("metadata") or {}).get("updated_at"))
        version = QualityScorer.normalize_version(tool_info.get("version", ""))
        local_usage = QualityScorer.normalize_local_usage(tool_info.get("usage_count", 0))
        success_rate = tool_info.get("success_rate", 0.5)
        verified = 1.0 if (tool_info.get("metadata") or {}).get("verified") else 0.0

        w = QualityScorer.WEIGHTS
        raw = (
            w["stars"] * stars
            + w["freshness"] * freshness
            + w["version"] * version
            + w["local_usage"] * local_usage
            + w["success_rate"] * success_rate
            + w["verified"] * verified
        )

        # Recency decay
        last_used = tool_info.get("last_used")
        if last_used:
            try:
                lt = datetime.fromisoformat(last_used.replace("Z", "+00:00"))
                days_idle = (datetime.now(UTC) - lt).days
                if days_idle > 30:
                    raw *= 0.8
            except (ValueError, TypeError):
                pass

        return round(raw, 4)

    @classmethod
    def evaluate_batch(cls, tools: list[dict]) -> list[dict]:
        """Score and sort a list of tool dicts in place."""
        for t in tools:
            t["quality_score"] = cls.evaluate(t)
        tools.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
        return tools
