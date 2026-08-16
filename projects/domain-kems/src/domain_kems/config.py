#!/usr/bin/env python3
"""
Config — 统一配置管理
三层优先级：环境变量 > 配置文件 > 默认值
"""

from pathlib import Path
from typing import Dict, Optional
import os
import json


class DomainConfig:
    """域配置管理"""

    # 默认域配置
    DEFAULT_DOMAINS = {
        "卫健委": {
            "path": "~/Documents/@工作文档/卫健委",
            "bos_uri": "bos://analysis/health_commission/",
            "type": "document",
            "tier": 1,
        },
        "规自委": {
            "path": "~/Documents/@工作文档/规自委",
            "bos_uri": "bos://analysis/land_planning/",
            "type": "document",
            "tier": 1,
        },
        "国转中心": {
            "path": "~/Documents/@工作文档/国转中心",
            "bos_uri": "bos://analysis/transformation/",
            "type": "document",
            "tier": 1,
        },
        "合同法规": {
            "path": "~/Documents/@工作文档/合同法规",
            "bos_uri": "bos://analysis/contract_law/",
            "type": "document",
            "tier": 1,
        },
    }

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path.home() / ".domain" / "config.yaml"
        self._config = self._load()

    def _load(self) -> dict:
        """加载配置（优先级：环境变量 > 配置文件 > 默认值）"""
        config = {"domains": self.DEFAULT_DOMAINS.copy()}

        # 从配置文件加载
        if self.config_path.exists():
            try:
                import yaml
                file_config = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
                if file_config and "domains" in file_config:
                    config["domains"].update(file_config["domains"])
            except ImportError:
                pass  # YAML 未安装时使用 JSON
            except Exception:
                pass

        # 环境变量覆盖
        for domain_id in self.DEFAULT_DOMAINS:
            env_key = f"DOMAIN_ROOT_{domain_id.upper()}"
            env_val = os.environ.get(env_key)
            if env_val:
                config["domains"][domain_id]["path"] = env_val

        return config

    def get_domain(self, name: str) -> Optional[dict]:
        """获取域配置"""
        return self._config.get("domains", {}).get(name)

    def get_path(self, name: str) -> Optional[Path]:
        """获取域路径"""
        domain = self.get_domain(name)
        if domain:
            return Path(domain["path"]).expanduser()
        return None

    def get_bos_uri(self, name: str) -> Optional[str]:
        """获取域 BOS URI"""
        domain = self.get_domain(name)
        if domain:
            return domain.get("bos_uri")
        return None

    def list_domains(self) -> Dict[str, dict]:
        """列出所有域"""
        return self._config.get("domains", {})


if __name__ == "__main__":
    config = DomainConfig()
    for name, domain in config.list_domains().items():
        path = config.get_path(name)
        exists = path.exists() if path else False
        print(f"{name}: {domain['path']} {'✅' if exists else '❌'}")
