"""FeatureGate — 三层参数控制中枢

控制粒度：
  层级1：环境变量 AGORA_ENABLE_GROUPS / AGORA_DISABLE_GROUPS / ...
  层级2：配置文件 feature_groups / bos_domains
  层级3：运行时 CLI (agora feature enable/disable)

设计原则：
  - 向后兼容：没有 feature_gates 配置时行为不变
  - env > 配置 > 默认值
  - 分组可嵌套（一个服务可属多个组）
  - BOS 域独立控制
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ── 默认 BOS 域定义 ──────────────────────────────────────────────
DEFAULT_BOS_DOMAINS: dict[str, dict[str, Any]] = {
    "memory": {"enabled": True, "description": "记忆域 — kos/kronos/gbrain"},
    "analysis": {"enabled": True, "description": "分析域 — minerva/ontoderive/codeanalyze/iris"},
    "governance": {"enabled": True, "description": "治理域 — omo/metaos/sot-bridge"},
    "capability": {"enabled": True, "description": "能力域 — forge/agent-runtime"},
    "persona": {"enabled": False, "description": "人格域 — sot-bridge-persona"},
    "meta": {"enabled": True, "description": "元域 — 系统元数据"},
    "ecos": {"enabled": True, "description": "协议域 — L0 协议层"},
    "agora": {"enabled": True, "description": "织层域 — 服务网格"},
}

# ── 默认 feature groups ──────────────────────────────────────────
DEFAULT_FEATURE_GROUPS: dict[str, dict[str, Any]] = {
    "L0": {"enabled": True, "services": ["ecos"], "description": "L0 协议层"},
    "I0": {"enabled": True, "services": [], "description": "I0 织层（Agora 自身）"},
    "L2-engine": {
        "enabled": True,
        "services": [
            "kos", "eidos", "minerva", "kronos", "ontoderive",
            "codeanalyze", "iris", "sophia", "gbrain",
        ],
        "description": "L2 引擎面 — 知识工程包",
    },
    "L2-governance": {
        "enabled": True,
        "services": ["omo", "metaos"],
        "description": "L2 治理面 — OMO/MetaOS",
    },
    "L4": {"enabled": True, "services": ["l4-kernel", "cockpit-cards"], "description": "L4 自我层"},
    "runtime": {"enabled": True, "services": ["runtime", "agent-runtime"], "description": "L1 运行时"},
    "external": {
        "enabled": False,
        "services": [
            "docker-mcp-gateway", "serena", "gitnexus",
            "chrome-devtools-mcp", "mcp-server-sqlite",
            "mcp-server-apple-events", "claude-mcp-serve",
            "codex-mcp-server", "zai-mcp-server",
        ],
        "description": "外部工具（npm/docker/homebrew）",
    },
    "model-driven": {
        "enabled": True,
        "services": ["model-driven"],
        "description": "模型驱动开发",
    },
    "compute": {
        "enabled": True,
        "services": ["compute-mesh", "llm-gateway", "aetherforge"],
        "description": "算力与网关层",
    },
}

# ── 层 → 组名映射（给 AGORA_ENABLE_LAYERS 用） ────────────────
LAYER_TO_GROUPS: dict[str, list[str]] = {
    "L0": ["L0"],
    "I0": ["I0"],
    "L1": ["runtime"],
    "L2": ["L2-engine", "L2-governance", "model-driven"],
    "L4": ["L4"],
    "XL": ["compute", "external"],
}

# ── 来源 → 组名映射（给 AGORA_ENABLE_SOURCES 用） ─────────────
SOURCE_TO_GROUPS: dict[str, list[str]] = {
    "local": ["L4", "L0", "model-driven", "compute", "runtime"],
    "kairon": ["L2-engine", "L2-governance"],
    "npm": ["external"],
    "docker": ["external"],
    "homebrew": ["external"],
    "aetherforge": ["compute"],
}


class FeatureGate:
    """单体 Feature Gate — 集中管理所有功能开关。

    自动从 ~/.agora/agora-proxy-services.json 加载 feature_groups,
    并读取环境变量覆盖。
    """

    _instance: FeatureGate | None = None

    def __init__(self, config_path: str | Path | None = None):
        self._config_path: Path | None = None
        self._groups: dict[str, dict[str, Any]] = {}
        self._domains: dict[str, dict[str, Any]] = {}
        self._loaded = False

        if config_path:
            self._config_path = Path(config_path)

    # ── 单例 ──────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls, config_path: str | Path | None = None) -> FeatureGate:
        if cls._instance is None:
            cls._instance = cls(config_path)
        elif config_path and cls._instance._config_path is None:
            cls._instance._config_path = Path(config_path)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    # ── 加载 ──────────────────────────────────────────────────────

    def load(self, config_data: dict[str, Any] | None = None) -> None:
        """从配置数据或配置文件中加载 feature_groups 和 bos_domains。"""
        if self._loaded:
            return

        if config_data is not None:
            self._load_from_dict(config_data)
            self._loaded = True
            return

        # 从文件加载
        config_path = self._resolve_config_path()
        if config_path and config_path.exists():
            try:
                raw = json.loads(config_path.read_text(encoding="utf-8"))
                self._load_from_dict(raw)
                self._loaded = True
                logger.info("feature_gate_loaded", path=str(config_path))
                return
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("feature_gate_load_failed", error=str(e))

        # 回退默认值
        self._load_from_dict({})
        self._loaded = True
        logger.info("feature_gate_using_defaults")

    def _load_from_dict(self, data: dict[str, Any]) -> None:
        """从配置 dict 加载。"""
        raw_groups = data.get("feature_groups", {})
        raw_domains = data.get("bos_domains", {})

        # 合并默认值（用户配置覆盖默认）
        self._groups = dict(DEFAULT_FEATURE_GROUPS)
        self._groups.update(raw_groups)

        self._domains = dict(DEFAULT_BOS_DOMAINS)
        self._domains.update(raw_domains)

    def _resolve_config_path(self) -> Path | None:
        """定位配置文件。"""
        if self._config_path and self._config_path.exists():
            return self._config_path
        data_dir = os.environ.get("AGORA_DATA_DIR", "")
        if data_dir:
            candidate = Path(data_dir) / "agora-proxy-services.json"
            if candidate.exists():
                return candidate
        default = Path.home() / ".agora" / "agora-proxy-services.json"
        if default.exists():
            return default
        return None

    def reload(self) -> None:
        """强制重载配置。"""
        self._loaded = False
        self.load()

    # ── 持久化 ────────────────────────────────────────────────────

    def save(self) -> bool:
        """将当前 groups/domains 写回配置文件。"""
        config_path = self._resolve_config_path()
        if not config_path:
            logger.warning("feature_gate_save_no_config")
            return False

        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw = {}

        raw["feature_groups"] = self._groups
        raw["bos_domains"] = self._domains
        config_path.write_text(
            json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("feature_gate_saved", path=str(config_path))
        return True

    # ── 环境变量覆盖 ──────────────────────────────────────────────

    def _parse_env_list(self, env_name: str) -> list[str]:
        """解析形如 `L0,L2,external` 的环境变量。"""
        val = os.environ.get(env_name, "")
        if not val:
            return []
        return [v.strip() for v in val.split(",") if v.strip()]

    def _env_force_enabled_groups(self) -> set[str] | None:
        """AGORA_ENABLE_GROUPS — 非空时只启用这些组。None = 不覆盖。"""
        groups = self._parse_env_list("AGORA_ENABLE_GROUPS")
        if not groups:
            # 兼容旧名
            groups = self._parse_env_list("AGORA_ENABLE_GROUPS")
        return set(groups) if groups else None

    def _env_force_disabled_groups(self) -> set[str]:
        """AGORA_DISABLE_GROUPS — 强制禁用的组。"""
        return set(self._parse_env_list("AGORA_DISABLE_GROUPS"))

    def _env_force_enabled_layers(self) -> set[str] | None:
        """AGORA_ENABLE_LAYERS — 转换层名为组名。"""
        layers = self._parse_env_list("AGORA_ENABLE_LAYERS")
        if not layers:
            return None
        groups: set[str] = set()
        for layer in layers:
            mapped = LAYER_TO_GROUPS.get(layer.upper(), [])
            groups.update(mapped)
        return groups

    def _env_force_enabled_domains(self) -> set[str] | None:
        """AGORA_ENABLE_DOMAINS — 非空时只启用这些域。"""
        domains = self._parse_env_list("AGORA_ENABLE_DOMAINS")
        return set(domains) if domains else None

    def _env_force_disabled_domains(self) -> set[str]:
        """AGORA_DISABLE_DOMAINS — 强制禁用的域。"""
        return set(self._parse_env_list("AGORA_DISABLE_DOMAINS"))

    # ── 服务筛选 ──────────────────────────────────────────────────

    def _get_groups_for_service(self, service_name: str) -> list[str]:
        """返回服务所属的所有组名。"""
        groups = []
        for gname, gconf in self._groups.items():
            svcs = gconf.get("services", [])
            # 精确匹配和通配符匹配
            for pattern in svcs:
                if pattern == service_name:
                    groups.append(gname)
                    break
                # 通配符: 不实现完整的 fnmatch，只支持简单后缀匹配
                if pattern.endswith("*") and service_name.startswith(pattern[:-1]):
                    groups.append(gname)
                    break
        return groups

    def is_service_enabled(self, service_name: str, service_config: dict[str, Any] | None = None) -> bool:
        """判断单个服务是否启用。

        优先级:
          1. AGORA_ENABLE_GROUPS/LAYERS → 白名单模式
          2. AGORA_DISABLE_GROUPS
          3. feature_groups 配置
          4. 服务自身的 enabled 标记（向后兼容）
        """
        self.load()

        # 步骤1：白名单模式
        force_enabled = self._env_force_enabled_groups()
        if force_enabled is None:
            force_enabled = self._env_force_enabled_layers()

        if force_enabled is not None:
            groups = self._get_groups_for_service(service_name)
            # 如果在白名单组中 → 启用
            if any(g in force_enabled for g in groups):
                return True
            # 不在任何白名单组 → 除非服务自身 enabled 且不属于任何组
            if not groups:
                # 没分组的服务只在白名单为空时启用（不太可能）
                return False
            return False

        # 步骤2：禁用组
        force_disabled = self._env_force_disabled_groups()
        if force_disabled:
            groups = self._get_groups_for_service(service_name)
            if any(g in force_disabled for g in groups):
                return False

        # 步骤3：feature_groups 配置
        groups = self._get_groups_for_service(service_name)
        if groups:
            # 至少一个组启用才启用
            return any(self._groups.get(g, {}).get("enabled", True) for g in groups)

        # 步骤4：服务自身 enabled 标记
        if service_config:
            return service_config.get("enabled", True)
        return True

    def filter_services(self, services: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """从服务列表中筛选出启用的。"""
        result = []
        for svc in services:
            name = svc.get("name", "")
            if name and self.is_service_enabled(name, svc):
                result.append(svc)
        return result

    # ── BOS 域控制 ────────────────────────────────────────────────

    def is_bos_domain_enabled(self, domain: str) -> bool:
        """判断 BOS 域是否启用。

        优先级:
          1. AGORA_ENABLE_DOMAINS → 白名单
          2. AGORA_DISABLE_DOMAINS
          3. AGORA_DISABLE_BOS (禁用所有 BOS)
          4. bos_domains 配置
        """
        self.load()

        # 快速全球禁用
        if os.environ.get("AGORA_ENABLE_BOS", "true").lower() in ("0", "false", "no"):
            return False

        # 白名单
        force_enabled = self._env_force_enabled_domains()
        if force_enabled is not None:
            return domain in force_enabled

        # 禁用列表
        force_disabled = self._env_force_disabled_domains()
        if domain in force_disabled:
            return False

        # 配置
        domain_cfg = self._domains.get(domain, {})
        return domain_cfg.get("enabled", True)

    def filter_bos_domains(self, domains: list[str] | None = None) -> list[str]:
        """返回当前启用的 BOS 域列表。"""
        self.load()
        all_domains = domains or list(self._domains.keys())
        return [d for d in all_domains if self.is_bos_domain_enabled(d)]

    # ── 运行时修改 ────────────────────────────────────────────────

    def set_group_enabled(self, group_name: str, enabled: bool) -> bool:
        """设置组的启用状态。返回 True 表示修改成功。"""
        self.load()
        if group_name not in self._groups:
            return False
        self._groups[group_name]["enabled"] = enabled
        self.save()
        return True

    def set_domain_enabled(self, domain: str, enabled: bool) -> bool:
        """设置 BOS 域的启用状态。"""
        self.load()
        if domain not in self._domains:
            self._domains[domain] = {"enabled": enabled, "description": ""}
        self._domains[domain]["enabled"] = enabled
        self.save()
        return True

    # ── 状态查询 ──────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """返回完整的 FeatureGate 状态（用于 CLI）。"""
        self.load()

        # 计算各服务的启用状态摘要
        all_services: dict[str, list[str]] = {}
        service_groups: dict[str, list[str]] = {}
        for gname, gconf in self._groups.items():
            for svc in gconf.get("services", []):
                if svc not in service_groups:
                    service_groups[svc] = []
                service_groups[svc].append(gname)

        groups_status: dict[str, dict[str, Any]] = {}
        for gname, gconf in self._groups.items():
            groups_status[gname] = {
                "enabled": gconf.get("enabled", True),
                "description": gconf.get("description", ""),
                "service_count": len(gconf.get("services", [])),
            }

        domains_status: dict[str, dict[str, Any]] = {}
        for dname, dconf in self._domains.items():
            domains_status[dname] = {
                "enabled": dconf.get("enabled", True),
                "description": dconf.get("description", ""),
            }

        # 环境变量生效情况
        env_overrides = {
            "AGORA_ENABLE_GROUPS": os.environ.get("AGORA_ENABLE_GROUPS", ""),
            "AGORA_DISABLE_GROUPS": os.environ.get("AGORA_DISABLE_GROUPS", ""),
            "AGORA_ENABLE_LAYERS": os.environ.get("AGORA_ENABLE_LAYERS", ""),
            "AGORA_ENABLE_DOMAINS": os.environ.get("AGORA_ENABLE_DOMAINS", ""),
            "AGORA_DISABLE_DOMAINS": os.environ.get("AGORA_DISABLE_DOMAINS", ""),
            "AGORA_ENABLE_BOS": os.environ.get("AGORA_ENABLE_BOS", ""),
        }
        active_env = {k: v for k, v in env_overrides.items() if v}

        return {
            "version": 1,
            "groups": groups_status,
            "domains": domains_status,
            "env_overrides": active_env,
            "config_path": str(self._resolve_config_path()) if self._resolve_config_path() else "N/A",
        }
