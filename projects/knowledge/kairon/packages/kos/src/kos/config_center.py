#!/usr/bin/env python3
# ruff: noqa
"""
KOS Config Center — 配置中心统一管理

统一管理系统配置，替代分散的环境变量和代码默认值。

Usage:
    kos config get embedding.model
    kos config set embedding.model BAAI/bge-base-zh-v1.5
    kos config list
    kos config validate
    kos config diff
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# 配置文件路径
CONFIG_PATH = Path.home() / ".kos" / "config.json"

# 默认配置
DEFAULT_CONFIG = {
    "embedding": {
        "model": "BAAI/bge-small-zh-v1.5",
        "backend": "auto",  # auto, omlx, st
        "batch_size": 128,
        "chunk_size": 1024,
        "chunk_overlap": 128,
    },
    "search": {
        "default_mode": "hybrid",
        "default_limit": 10,
        "cache_enabled": True,
        "cache_ttl_l1": 300,
        "cache_ttl_l2": 3600,
    },
    "indexing": {
        "auto_incremental": True,
        "incremental_interval": 300,
        "watch_filesystem": False,
        "poll_interval": 60,
    },
    "monitoring": {
        "enabled": True,
        "health_check_interval": 600,
        "alert_on_index_drift": True,
        "alert_on_high_latency": True,
        "latency_threshold_ms": 500,
    },
    "mcp": {
        "version": "1.0",
        "require_confirmation_l2": True,
    },
    "api": {
        "omlx_url": "http://100.96.126.35:4000",
        "omlx_api_key": "123456",
        "omlx_embed_model": "embed",
    },
}

# 配置描述 (用于帮助)
CONFIG_DESCRIPTIONS = {
    "embedding.model": "嵌入模型名称",
    "embedding.backend": "嵌入后端 (auto/omlx/st)",
    "embedding.batch_size": "嵌入批次大小",
    "embedding.chunk_size": "文档切片大小 (字符)",
    "embedding.chunk_overlap": "切片重叠大小 (字符)",
    "search.default_mode": "默认检索模式",
    "search.default_limit": "默认最大结果数",
    "search.cache_enabled": "是否启用缓存",
    "search.cache_ttl_l1": "L1 缓存 TTL (秒)",
    "search.cache_ttl_l2": "L2 缓存 TTL (秒)",
    "indexing.auto_incremental": "是否自动增量索引",
    "indexing.incremental_interval": "增量索引间隔 (秒)",
    "indexing.watch_filesystem": "是否监控文件系统",
    "indexing.poll_interval": "文件监控轮询间隔 (秒)",
    "monitoring.enabled": "是否启用监控",
    "monitoring.health_check_interval": "健康检查间隔 (秒)",
    "monitoring.alert_on_index_drift": "索引漂移告警",
    "monitoring.alert_on_high_latency": "高延迟告警",
    "monitoring.latency_threshold_ms": "延迟阈值 (ms)",
    "mcp.version": "MCP 协议版本",
    "mcp.require_confirmation_l2": "L2 操作需确认",
    "api.omlx_url": "omlx 网关地址",
    "api.omlx_api_key": "omlx API Key",
    "api.omlx_embed_model": "omlx 嵌入模型名",
}


class ConfigCenter:
    """配置中心。"""

    def __init__(self):
        self._config = None

    @property
    def config(self) -> dict:
        if self._config is None:
            self._config = self._load()
        return self._config

    def _load(self) -> dict:
        """加载配置 (默认 + 用户覆盖)."""
        config = self._deep_copy(DEFAULT_CONFIG)

        if CONFIG_PATH.exists():
            try:
                user_config = json.loads(CONFIG_PATH.read_text())
                config = self._deep_merge(config, user_config)
            except (json.JSONDecodeError, IOError):
                pass

        return config

    def save(self):
        """保存配置到文件。"""
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(self.config, ensure_ascii=False, indent=2))

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值。

        Args:
            key: 配置键 (如 "embedding.model")。
            default: 默认值。

        Returns:
            配置值，不存在返回 default。
        """
        parts = key.split(".")
        value = self.config
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value

    def set(self, key: str, value: Any):
        """设置配置值。

        Args:
            key: 配置键。
            value: 配置值。
        """
        parts = key.split(".")
        config = self.config
        for part in parts[:-1]:
            if part not in config:
                config[part] = {}
            config = config[part]
        config[parts[-1]] = value

    def list(self) -> dict:
        """列出所有配置。"""
        return self.config

    def validate(self) -> dict[str, Any]:
        """验证配置正确性。"""
        errors = []
        warnings = []

        # 检查必需字段
        if not self.get("embedding.model"):
            errors.append("embedding.model 不能为空")

        # 检查模型是否有效
        from kos.semantic import EMBED_MODEL_REGISTRY

        model = self.get("embedding.model")
        if model and model not in EMBED_MODEL_REGISTRY:
            warnings.append(f"模型 '{model}' 不在注册表中")

        # 检查数值范围
        if self.get("search.default_limit", 0) <= 0:
            errors.append("search.default_limit 必须 > 0")
        if self.get("embedding.batch_size", 0) <= 0:
            errors.append("embedding.batch_size 必须 > 0")

        # 检查 URL
        omlx_url = self.get("api.omlx_url")
        if omlx_url and not omlx_url.startswith("http"):
            warnings.append("api.omlx_url 格式异常")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def diff(self) -> dict[str, Any]:
        """对比当前配置与默认配置。"""
        changes = {}

        def compare(default: dict, current: dict, prefix: str = ""):
            for key in set(list(default.keys()) + list(current.keys())):
                full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
                if key in default and key in current:
                    if isinstance(default[key], dict) and isinstance(current[key], dict):
                        compare(default[key], current[key], full_key)
                    elif default[key] != current[key]:
                        changes[full_key] = {
                            "default": default[key],
                            "current": current[key],
                            "description": CONFIG_DESCRIPTIONS.get(full_key, ""),
                        }
                elif key in default:
                    changes[full_key] = {
                        "default": default[key],
                        "current": None,
                        "description": CONFIG_DESCRIPTIONS.get(full_key, ""),
                    }
                else:
                    changes[full_key] = {
                        "default": None,
                        "current": current[key],
                        "description": CONFIG_DESCRIPTIONS.get(full_key, ""),
                    }

        compare(DEFAULT_CONFIG, self.config)
        return changes

    @staticmethod
    def _deep_copy(d: dict) -> dict:
        return json.loads(json.dumps(d))

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        result = ConfigCenter._deep_copy(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigCenter._deep_merge(result[key], value)
            else:
                result[key] = value
        return result


# ── CLI 入口 ──────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="KOS Config Center")
    sub = parser.add_subparsers(dest="command")

    # Get
    p_get = sub.add_parser("get", help="Get config value")
    p_get.add_argument("key", help="Config key (e.g., embedding.model)")

    # Set
    p_set = sub.add_parser("set", help="Set config value")
    p_set.add_argument("key", help="Config key")
    p_set.add_argument("value", help="Config value")
    p_set.add_argument("--no-save", action="store_true", help="Don't save to file")

    # List
    sub.add_parser("list", help="List all config")

    # Validate
    sub.add_parser("validate", help="Validate config")

    # Diff
    sub.add_parser("diff", help="Show diff vs defaults")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    center = ConfigCenter()

    if args.command == "get":
        value = center.get(args.key)
        if value is not None:
            print(json.dumps(value, ensure_ascii=False))
        else:
            print(f"Key not found: {args.key}")

    elif args.command == "set":
        # Try to parse as JSON, fallback to string
        try:
            parsed = json.loads(args.value)
        except json.JSONDecodeError:
            parsed = args.value
        center.set(args.key, parsed)
        if not args.no_save:
            center.save()
        print(f"Set {args.key} = {json.dumps(parsed, ensure_ascii=False)}")

    elif args.command == "list":
        print(json.dumps(center.list(), ensure_ascii=False, indent=2))

    elif args.command == "validate":
        result = center.validate()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "diff":
        changes = center.diff()
        if changes:
            print("Changes from defaults:")
            for key, info in changes.items():
                desc = f" ({info['description']})" if info["description"] else ""
                print(f"  {key}{desc}")
                print(f"    default: {info['default']}")
                print(f"    current: {info['current']}")
        else:
            print("No changes from defaults")


if __name__ == "__main__":
    main()
