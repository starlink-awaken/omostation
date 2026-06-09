"""
SSOT Kernel — engine.py
========================
数据驱动的规则引擎核心。

引擎不直接调用 Python 函数，而是：
1. 从领域配置加载规则（rules.yaml）
2. 按规则中声明的 pattern 查找对应的模式处理器
3. 调用模式处理器的 evaluate() 方法
4. 聚合结果

扩展机制：用户可在 ~/.ssot/checkers/ 下注册自定义模式处理器。
"""

from __future__ import annotations

import datetime
import importlib
import inspect
import pkgutil
from pathlib import Path

from .meta_model import DomainConfig, Rule
from .patterns.base import (
    BaseChecker,
    BasePattern,
    CheckResult,
    DependencyValidator,
    DerivationReport,
)


class CheckerRegistry:
    """规则模式注册表。

    引擎启动时自动发现以下来源的模式处理器：
    1. 内置模式（ssot_kernel/patterns/ 中的 BasePattern 子类）
    2. 用户自定义模式（~/.ssot/checkers/ 中的 BasePattern 子类）
    3. 注册表中手动注册的模式
    """

    def __init__(self):
        self._patterns: dict[str, BasePattern] = {}

    def discover_builtin(self):
        """自动发现 ssot_kernel.patterns 中的内置模式"""
        from . import patterns as pkg

        for _importer, modname, _ispkg in pkgutil.walk_packages(
            pkg.__path__, prefix=f"{pkg.__name__}."
        ):
            try:
                mod = importlib.import_module(modname)
                for _name, obj in inspect.getmembers(mod, inspect.isclass):
                    if (
                        issubclass(obj, BasePattern)
                        and not inspect.isabstract(obj)
                        and obj is not BasePattern
                        and obj is not BaseChecker
                    ):
                        instance = obj()
                        self._patterns[instance.pattern_name] = instance
            except Exception:
                # 静默跳过加载失败的模块
                pass

    def discover_user_patterns(self, paths: list[Path] | None = None):
        """发现用户自定义模式"""
        if paths is None:
            default_path = Path.home() / ".ssot" / "checkers"
            paths = [default_path] if default_path.exists() else []

        for p in paths:
            if not p.exists():
                continue
            _path_inserted = False
            if str(p.parent) not in __import__("sys").path:
                __import__("sys").path.insert(0, str(p.parent))
                _path_inserted = True

            for py_file in sorted(p.glob("*.py")):
                if py_file.name.startswith("_"):
                    continue
                try:
                    mod_name = py_file.stem
                    mod = importlib.import_module(mod_name)
                    for _name, obj in inspect.getmembers(mod, inspect.isclass):
                        if (
                            issubclass(obj, BasePattern)
                            and not inspect.isabstract(obj)
                            and obj is not BasePattern
                            and obj is not BaseChecker
                        ):
                            instance = obj()
                            if instance.pattern_name not in self._patterns:
                                self._patterns[instance.pattern_name] = instance
                except Exception:
                    pass

    def register(self, name: str, pattern: BasePattern):
        """手动注册一个模式处理器"""
        self._patterns[name] = pattern

    def get(self, name: str) -> BasePattern | None:
        return self._patterns.get(name)

    def list_patterns(self) -> list[str]:
        return list(self._patterns.keys())


class RuleEngine:
    """数据驱动的规则引擎。

    用法：
        engine = RuleEngine()
        report = engine.execute(domain_config)
    """

    def __init__(self):
        self.registry = CheckerRegistry()
        self.registry.discover_builtin()
        self.registry.discover_user_patterns()

    def execute(
        self,
        domain: DomainConfig,
        rules: list[Rule] | None = None,
        rounds: int = 1,
        context: dict | None = None,
    ) -> DerivationReport:
        """执行规则引擎。

        Args:
            domain: 领域配置
            rules: 要执行的规则列表（默认使用 domain.rules）
            rounds: 多轮迭代次数
            context: 执行上下文

        Returns:
            DerivationReport: 完整推导报告
        """
        if rules is None:
            rules = domain.rules

        report = DerivationReport(
            engine_version="2.0",
            executed_at=datetime.datetime.now().isoformat(),
            domain_name=domain.domain.get("name", "unknown"),
        )

        all_results = []
        for round_num in range(1, rounds + 1):
            round_context = {
                "round": round_num,
                "total_rounds": rounds,
                **(context or {}),
            }

            for rule in rules:
                # P0 fix: 依赖前置校验
                dep_checker = DependencyValidator(domain)
                dep_result = dep_checker.validate_rule(rule)
                if dep_result is not None:
                    all_results.append(dep_result)
                    continue

                pattern = self.registry.get(rule.pattern)
                if pattern is None:
                    result = CheckResult(
                        protocol_id=rule.id,
                        name=rule.name or rule.id,
                        passed=True,
                        severity="WARN",
                        details=[f"⚠️ 未知规则模式: {rule.pattern}，跳过"],
                    )
                else:
                    try:
                        result = pattern.evaluate(rule, domain, round_context)
                    except Exception as e:
                        result = CheckResult(
                            protocol_id=rule.id,
                            name=rule.name or rule.id,
                            passed=False,
                            severity="ERROR",
                            details=[f"❌ 执行异常: {e}"],
                        )
                all_results.append(result)

        report.results = all_results
        report.total_rules = len(all_results)
        report.passed = sum(1 for r in all_results if r.passed)
        report.blocker = sum(
            1 for r in all_results if not r.passed and r.severity == "BLOCKER"
        )
        report.error = sum(
            1 for r in all_results if not r.passed and r.severity == "ERROR"
        )
        report.warn = sum(
            1 for r in all_results if not r.passed and r.severity == "WARN"
        )
        report.all_passed = report.blocker == 0 and report.error == 0

        return report
