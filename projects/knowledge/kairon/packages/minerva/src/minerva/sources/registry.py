from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Registry ≡ Module
# 内涵 ≝ {Registry}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Registry)}
# 功能 ⊢ {Init_Registry, Execute_Registry, Validate_Registry}
# =============================================================================

# ---
# domain: D-Harvest
# layer: organ
# status: active
# ---

"""
数据源注册表
"""
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class DataSource:
    """数据源配置"""

    source_id: str
    type: str  # "web", "api", "document", "code"
    connector_class: str  # Python 类路径
    extractor_class: str
    schedule: str  # Cron 表达式
    enabled: bool = True
    credentials_ref: str | None = None
    health_check_url: str | None = None
    metadata: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)


class SourceRegistry:
    """数据源注册表"""

    def __init__(self, config_path: str = "organs/D-Harvest/sources/config/") -> None:
        self.config_path = Path(config_path)
        self.sources: dict[str, DataSource] = {}
        self._load_sources()

    def _load_sources(self) -> None:
        """从YAML配置文件加载数据源"""
        config_file = self.config_path / "sources.yaml"
        if config_file.exists():
            with open(config_file, encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            for source_data in config_data.get("sources", []):
                source = DataSource(**source_data)
                self.sources[source.source_id] = source
        else:
            # 创建默认配置文件
            self._create_default_config(config_file)

    def _create_default_config(self, config_file: Path) -> None:
        """创建默认配置文件"""
        default_config = {
            "sources": [
                {
                    "source_id": "example-web",
                    "type": "web",
                    "enabled": False,
                    "connector_class": "organs.D_Harvest.sources.connectors.web:WebSourceConnector",
                    "extractor_class": "organs.D_Harvest.extractors.html:HtmlContentExtractor",
                    "schedule": "0 */1 * * *",
                    "config": {"url": "https://example.com", "max_items": 30},
                    "metadata": {"category": "example", "priority": "low"},
                }
            ]
        }

        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)

    def register_source(self, source: DataSource) -> None:
        """注册新数据源"""
        self.sources[source.source_id] = source

    def get_source(self, source_id: str) -> DataSource | None:
        """获取数据源配置"""
        return self.sources.get(source_id)

    async def get_healthy_sources(self) -> list[DataSource]:
        """获取所有健康的数据源"""
        healthy = []
        for s in self.sources.values():
            if s.enabled:
                if await self._check_health(s):
                    healthy.append(s)
        return healthy

    async def _check_health(self, source: DataSource) -> bool:
        """健康检查"""
        if not source.health_check_url:
            return True

        try:
            import httpx

            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(source.health_check_url)
                return resp.status_code == 200
        except Exception:
            return False
