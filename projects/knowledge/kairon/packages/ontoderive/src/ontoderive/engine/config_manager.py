from __future__ import annotations

"""Configuration Manager - 配置管理器

统一管理所有治理模块的配置，支持：
- YAML 配置文件加载
- 环境变量覆盖
- 配置验证
- 热重载

Usage:
    config = GovernanceConfig.load()
    threshold = config.quality.pass_threshold
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

_log = logging.getLogger(__name__)


@dataclass
class QualityConfig:
    """Quality Probe 配置"""

    weights: dict[str, int] = field(default_factory=lambda: {"critical": 15, "major": 10, "minor": 5, "info": 1})
    pass_threshold: float = 85.0
    warning_threshold: float = 70.0
    required_fields: dict[str, list[str]] = field(
        default_factory=lambda: {
            "markdown": ["Type", "Status", "Version", "Owner", "Authority"],
            "python": ["Type", "Status"],
        }
    )
    alternative_fields: dict[str, list[str]] = field(
        default_factory=lambda: {
            "Version": ["Updated", "Created"],
            "Owner": ["Author", "Maintainer"],
        }
    )
    enabled_checks: list[str] = field(default_factory=lambda: ["frontmatter", "naming", "formal_summary", "ai_context"])
    naming_pattern: str = r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$"


@dataclass
class AutoFixConfig:
    """Auto-Fix Engine 配置"""

    dry_run_by_default: bool = True
    backup_before_fix: bool = True
    backup_dir: str = ".backup/auto-fix"
    enabled_strategies: list[str] = field(default_factory=lambda: ["frontmatter", "formal_summary", "ai_context"])
    default_values: dict[str, str] = field(
        default_factory=lambda: {"Status": "ACTIVE", "Version": "1.0.0", "Owner": "@Unassigned"}
    )
    skip_patterns: list[str] = field(default_factory=list)


@dataclass
class MetaValidateConfig:
    """Meta-Validate 配置"""

    sample_size: int = 30
    min_sample_size: int = 10
    max_sample_size: int = 100
    thresholds: dict[str, float] = field(
        default_factory=lambda: {
            "accuracy": 0.85,
            "precision": 0.80,
            "recall": 0.80,
            "max_false_positive_rate": 0.10,
            "max_false_negative_rate": 0.15,
        }
    )


@dataclass
class AuthorityGraphConfig:
    """Authority Graph 配置"""

    detect_cycles: bool = True
    detect_orphans: bool = True
    detect_broken_links: bool = True
    max_depth: int = 10
    influence_weights: dict[str, float] = field(default_factory=lambda: {"referenced_by": 2.0, "references": 1.0})


@dataclass
class BenchmarkConfig:
    """Benchmark Suite 配置"""

    history_retention: int = 100
    data_dir: str = "analysis/analysis/logs/benchmarks"
    performance: dict[str, float] = field(default_factory=lambda: {"min_scan_speed": 1000.0, "max_scan_time": 500.0})
    alerts: dict[str, Any] = field(
        default_factory=lambda: {
            "on_score_regression": True,
            "regression_threshold": -5.0,
            "on_pass_rate_drop": True,
            "pass_rate_drop_threshold": -10.0,
        }
    )


@dataclass
class GovernanceConfig:
    """统一的治理配置"""

    version: str = "2.0"
    quality: QualityConfig = field(default_factory=QualityConfig)
    auto_fix: AutoFixConfig = field(default_factory=AutoFixConfig)
    meta_validate: MetaValidateConfig = field(default_factory=MetaValidateConfig)
    authority_graph: AuthorityGraphConfig = field(default_factory=AuthorityGraphConfig)
    benchmark: BenchmarkConfig = field(default_factory=BenchmarkConfig)

    # 文件路径
    _config_path: Path | None = field(default=None, repr=False)

    @classmethod
    def load(cls, config_path: str | None = None) -> GovernanceConfig:
        """从 YAML 文件加载配置

        搜索顺序:
        1. 指定的 config_path
        2. .governance-config.yaml (当前目录)
        3. ~/.governance-config.yaml (家目录)
        4. 默认配置
        """
        if yaml is None:
            _log.warning("PyYAML not available, using default configuration")
            return cls()

        # 确定配置文件路径
        paths_to_try = []

        if config_path:
            paths_to_try.append(Path(config_path))

        # 当前目录
        paths_to_try.append(Path.cwd() / ".governance-config.yaml")

        # 家目录
        home = Path.home()
        paths_to_try.append(home / ".governance-config.yaml")

        # 项目根目录（向上查找）
        current = Path.cwd()
        for _ in range(5):
            paths_to_try.append(current / ".governance-config.yaml")
            current = current.parent

        # 查找第一个存在的配置文件
        config_file = None
        for path in paths_to_try:
            if path.exists():
                config_file = path
                break

        if config_file is None:
            _log.info("No configuration file found, using defaults")
            return cls()

        _log.info(f"Loading configuration from {config_file}")

        try:
            with open(config_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not isinstance(data, dict):
                _log.error(f"Invalid configuration format in {config_file}")
                return cls()

            return cls._from_dict(data, config_file)

        except yaml.YAMLError as e:
            _log.error(f"Failed to parse configuration: {e}")
            return cls()
        except (OSError, TypeError, ValueError) as e:
            _log.error(f"Failed to load configuration: {e}")
            return cls()

    @classmethod
    def _from_dict(cls, data: dict, config_path: Path | None = None) -> GovernanceConfig:
        """从字典构建配置对象"""
        config = cls(_config_path=config_path)

        # 版本
        if "version" in data:
            config.version = data["version"]

        # Quality
        if "quality" in data:
            q = data["quality"]
            if "weights" in q:
                config.quality.weights.update(q["weights"])
            if "pass_threshold" in q:
                config.quality.pass_threshold = q["pass_threshold"]
            if "warning_threshold" in q:
                config.quality.warning_threshold = q["warning_threshold"]
            if "required_fields" in q:
                config.quality.required_fields.update(q["required_fields"])
            if "alternative_fields" in q:
                config.quality.alternative_fields.update(q["alternative_fields"])
            if "enabled_checks" in q:
                config.quality.enabled_checks = q["enabled_checks"]
            if "naming" in q and "pattern" in q["naming"]:
                config.quality.naming_pattern = q["naming"]["pattern"]

        # Auto-Fix
        if "auto_fix" in data:
            af = data["auto_fix"]
            if "dry_run_by_default" in af:
                config.auto_fix.dry_run_by_default = af["dry_run_by_default"]
            if "backup_before_fix" in af:
                config.auto_fix.backup_before_fix = af["backup_before_fix"]
            if "backup_dir" in af:
                config.auto_fix.backup_dir = af["backup_dir"]
            if "enabled_strategies" in af:
                config.auto_fix.enabled_strategies = af["enabled_strategies"]
            if "default_values" in af:
                config.auto_fix.default_values.update(af["default_values"])
            if "skip_patterns" in af:
                config.auto_fix.skip_patterns = af["skip_patterns"]

        # Meta-Validate
        if "meta_validate" in data:
            mv = data["meta_validate"]
            if "sample_size" in mv:
                config.meta_validate.sample_size = mv["sample_size"]
            if "thresholds" in mv:
                config.meta_validate.thresholds.update(mv["thresholds"])

        # Authority Graph
        if "authority_graph" in data:
            ag = data["authority_graph"]
            if "detect_cycles" in ag:
                config.authority_graph.detect_cycles = ag["detect_cycles"]
            if "max_depth" in ag:
                config.authority_graph.max_depth = ag["max_depth"]
            if "influence_weights" in ag:
                config.authority_graph.influence_weights.update(ag["influence_weights"])

        # Benchmark
        if "benchmark" in data:
            b = data["benchmark"]
            if "history_retention" in b:
                config.benchmark.history_retention = b["history_retention"]
            if "data_dir" in b:
                config.benchmark.data_dir = b["data_dir"]

        # 应用环境变量覆盖
        config._apply_env_overrides()

        return config

    def _apply_env_overrides(self) -> None:
        """应用环境变量覆盖配置

        环境变量命名规则: GOVERNANCE_<SECTION>_<KEY>
        例如：GOVERNANCE_QUALITY_PASS_THRESHOLD=90
        """

        # Quality
        if "GOVERNANCE_QUALITY_PASS_THRESHOLD" in os.environ:
            try:
                self.quality.pass_threshold = float(os.environ["GOVERNANCE_QUALITY_PASS_THRESHOLD"])
            except ValueError:
                pass

        if "GOVERNANCE_QUALITY_VERBOSE" in os.environ:
            import logging

            logging.getLogger().setLevel(logging.DEBUG)

        # Auto-Fix
        if "GOVERNANCE_AUTO_FIX_DRY_RUN" in os.environ:
            val = os.environ["GOVERNANCE_AUTO_FIX_DRY_RUN"].lower()
            self.auto_fix.dry_run_by_default = val in ("true", "1", "yes")

    def validate(self) -> list[str]:
        """验证配置有效性

        Returns:
            警告信息列表（空列表表示配置有效）
        """
        warnings = []

        # 检查阈值合理性
        if self.quality.pass_threshold < 0 or self.quality.pass_threshold > 100:
            warnings.append(f"Invalid pass_threshold: {self.quality.pass_threshold} (should be 0-100)")

        if self.quality.warning_threshold >= self.quality.pass_threshold:
            warnings.append(
                f"warning_threshold ({self.quality.warning_threshold}) should be < pass_threshold ({self.quality.pass_threshold})"
            )

        # 检查样本大小
        if self.meta_validate.sample_size < self.meta_validate.min_sample_size:
            warnings.append(
                f"sample_size ({self.meta_validate.sample_size}) should be >= min_sample_size ({self.meta_validate.min_sample_size})"
            )

        # 检查权重
        for key, value in self.quality.weights.items():
            if value < 0:
                warnings.append(f"Negative weight for {key}: {value}")

        return warnings

    def to_dict(self) -> dict:
        """将配置转换为字典"""
        return {
            "version": self.version,
            "quality": {
                "pass_threshold": self.quality.pass_threshold,
                "weights": self.quality.weights,
                "enabled_checks": self.quality.enabled_checks,
            },
            "auto_fix": {
                "dry_run_by_default": self.auto_fix.dry_run_by_default,
                "enabled_strategies": self.auto_fix.enabled_strategies,
            },
            "meta_validate": {
                "sample_size": self.meta_validate.sample_size,
                "thresholds": self.meta_validate.thresholds,
            },
            "benchmark": {
                "history_retention": self.benchmark.history_retention,
                "data_dir": self.benchmark.data_dir,
            },
        }


# 全局配置实例（单例模式）
_global_config: GovernanceConfig | None = None


def get_config(reload: bool = False) -> GovernanceConfig:
    """获取全局配置实例

    Args:
        reload: 是否强制重新加载配置

    Returns:
        GovernanceConfig 实例
    """
    global _global_config

    if _global_config is None or reload:
        _global_config = GovernanceConfig.load()

        # 验证配置
        warnings = _global_config.validate()
        for warning in warnings:
            _log.warning(f"Configuration warning: {warning}")

    return _global_config


if __name__ == "__main__":
    # 测试配置加载
    import json

    config = get_config(reload=True)
    print("Loaded Configuration:")
    print(json.dumps(config.to_dict(), indent=2))

    warnings = config.validate()
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  ⚠️  {w}")
    else:
        print("\n✅ Configuration is valid")
