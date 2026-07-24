"""治理检查器注册表 — 动态加载和执行 X1-X4 检查器"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from ecos.l0.governance import (
    CheckResult,
    CheckSeverity,
    CheckStatus,
    GovernanceCheck,
)


@dataclass
class CheckerRegistration:
    """检查器注册信息"""

    id: str
    dimension: str
    name: str
    description: str
    module: str
    class_name: str
    type: str = "python"
    severity: str = "medium"
    enabled: bool = True
    schedule: str = "on-demand"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionConfig:
    """执行配置"""

    parallel: bool = True
    max_workers: int = 4
    timeout_seconds: int = 300
    retry_enabled: bool = True
    max_retries: int = 2
    backoff_seconds: int = 5


class GovernanceRegistry:
    """治理检查器注册表"""

    def __init__(self, registry_path: str | Path | None = None):
        self.registry_path = Path(registry_path) if registry_path else None
        self.checkers: list[CheckerRegistration] = []
        self.execution_config = ExecutionConfig()
        self._loaded = False

    def load(self) -> None:
        """加载注册表"""
        if self.registry_path and self.registry_path.exists():
            with open(self.registry_path) as f:
                data = yaml.safe_load(f) or {}

            # 加载检查器
            for checker_data in data.get("checkers", []):
                registration = CheckerRegistration(
                    id=checker_data["id"],
                    dimension=checker_data["dimension"],
                    name=checker_data["name"],
                    description=checker_data["description"],
                    module=checker_data["module"],
                    class_name=checker_data["class"],
                    type=checker_data.get("type", "python"),
                    severity=checker_data.get("severity", "medium"),
                    enabled=checker_data.get("enabled", True),
                    schedule=checker_data.get("schedule", "on-demand"),
                )
                self.checkers.append(registration)

            # 加载执行配置
            exec_config = data.get("execution", {})
            self.execution_config = ExecutionConfig(
                parallel=exec_config.get("parallel", True),
                max_workers=exec_config.get("max_workers", 4),
                timeout_seconds=exec_config.get("timeout_seconds", 300),
            )

            self._loaded = True

    def get_checker(self, checker_id: str) -> Optional[CheckerRegistration]:
        """获取检查器注册信息"""
        for checker in self.checkers:
            if checker.id == checker_id:
                return checker
        return None

    def get_by_dimension(self, dimension: str) -> list[CheckerRegistration]:
        """按维度获取检查器"""
        return [c for c in self.checkers if c.dimension == dimension and c.enabled]

    def get_enabled(self) -> list[CheckerRegistration]:
        """获取所有启用的检查器"""
        return [c for c in self.checkers if c.enabled]

    def instantiate_checker(
        self, registration: CheckerRegistration, repo_root: str | Path
    ) -> GovernanceCheck:
        """实例化检查器"""
        module = importlib.import_module(registration.module)
        checker_class = getattr(module, registration.class_name)
        return checker_class(repo_root)

    def run_check(self, checker_id: str, repo_root: str | Path) -> CheckResult:
        """运行单个检查"""
        registration = self.get_checker(checker_id)
        if not registration:
            return CheckResult(
                check_id=checker_id,
                dimension="unknown",
                status=CheckStatus.FAIL,
                message=f"检查器 {checker_id} 未注册",
                severity=CheckSeverity.HIGH,
            )

        if not registration.enabled:
            return CheckResult(
                check_id=checker_id,
                dimension=registration.dimension,
                status=CheckStatus.SKIP,
                message=f"检查器 {checker_id} 已禁用",
            )

        try:
            checker = self.instantiate_checker(registration, repo_root)
            return checker.execute()
        except Exception as e:  # defensive fallback
            return CheckResult(
                check_id=checker_id,
                dimension=registration.dimension,
                status=CheckStatus.FAIL,
                message=f"执行失败: {e}",
                severity=CheckSeverity.HIGH,
            )

    def run_dimension(self, dimension: str, repo_root: str | Path) -> list[CheckResult]:
        """运行指定维度的所有检查"""
        checkers = self.get_by_dimension(dimension)
        return [self.run_check(c.id, repo_root) for c in checkers]

    def run_all(self, repo_root: str | Path) -> list[CheckResult]:
        """运行所有启用的检查"""
        checkers = self.get_enabled()
        return [self.run_check(c.id, repo_root) for c in checkers]

    def to_dict(self) -> dict[str, Any]:
        """导出注册表"""
        return {
            "checkers": [
                {
                    "id": c.id,
                    "dimension": c.dimension,
                    "name": c.name,
                    "description": c.description,
                    "enabled": c.enabled,
                    "schedule": c.schedule,
                }
                for c in self.checkers
            ]
        }
