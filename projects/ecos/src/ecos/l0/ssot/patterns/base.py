"""
SSOT Kernel — patterns/base.py
规则模式基类：所有内置模式 + 用户自定义 checker 都继承此类。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..meta_model import DomainConfig, Rule


@dataclass
class CheckResult:
    """一条规则的检查结果"""

    protocol_id: str  # 对应 spec 中的 id
    name: str  # 规则名称
    passed: bool  # 是否通过
    severity: str = "WARN"  # BLOCKER / ERROR / WARN
    details: list[str] = field(default_factory=list)
    fixes: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class DerivationReport:
    """一次推导执行的完整报告"""

    engine_version: str = "2.0"
    executed_at: str = ""
    domain_name: str = ""
    total_rules: int = 0
    passed: int = 0
    blocker: int = 0
    error: int = 0
    warn: int = 0
    results: list[CheckResult] = field(default_factory=list)
    all_passed: bool = True

    @property
    def summary_line(self) -> str:
        return f"✅ {self.passed} passed / 🔴 {self.blocker} blocker / 🟠 {self.error} error / 🟡 {self.warn} warn"


class BasePattern(ABC):
    """规则模式基类。

    所有内置模式（矛盾推导/理论匹配/IP联动/一致性/能力缺失）和用户自定义 checker
    都继承此类。引擎通过 `evaluate()` 接口统一调度。
    """

    @property
    @abstractmethod
    def pattern_name(self) -> str:
        """模式标识符，对应 rules.yaml 中的 pattern 字段"""
        ...

    @abstractmethod
    def evaluate(
        self, rule: Rule, domain: DomainConfig, context: dict[str, Any] | None = None
    ) -> CheckResult:
        """执行规则检查，返回结构化的检查结果。

        Args:
            rule: 从领域配置加载的规则定义
            domain: 全量领域数据
            context: 可选的执行上下文（如轮次号、历史结果）
        """
        ...


class DependencyValidator:
    """依赖前置校验器——在规则执行前检查所有引用的实体/事实是否存在。

    P0 修复：防止规则因依赖缺失而静默失败。
    扫描 rules.yaml 中所有 condition 的条件表达式，提取引用的 ID，
    在领域配置中确认它们确实存在。不存在的标记为 ERROR 并阻止规则执行。
    """

    def __init__(self, domain: DomainConfig):
        self.domain = domain

    def validate_rule(self, rule: Rule) -> CheckResult | None:
        """检查一条规则的所有前置条件是否引用了真实存在的实体/事实。

        Returns:
            如果有缺失依赖，返回 CheckResult(severity=BLOCKER)
            否则返回 None（规则可以继续执行）
        """
        import re

        missing: list[str] = []
        for premise in getattr(rule, "premises", []):
            cond = premise.get("condition", "")

            # 提取 fact_ratio("DAT-ID", "DAT-ID") 中的 ID
            for m in re.finditer(r'fact_ratio\("([^"]+)",\s*"([^"]+)"\)', cond):
                for ref_id in (m.group(1), m.group(2)):
                    if (
                        not self._entity_exists(ref_id)
                        and not self._fact_exists(ref_id)
                        and ref_id not in missing
                    ):
                        missing.append(ref_id)

            # 提取 entity_attr("ORG-ID", ...) 中的 ID
            for m in re.finditer(r'entity_attr\("([^"]+)"', cond):
                ref_id = m.group(1)
                if not self._entity_exists(ref_id) and ref_id not in missing:
                    missing.append(ref_id)

            # 提取 entity_exists("PREFIX", ...) 中的前缀
            for m in re.finditer(r'entity_exists\("([^"]+)"', cond):
                prefix = m.group(1)
                if not self._prefix_exists(prefix) and f"前缀{prefix}" not in missing:
                    missing.append(f"前缀{prefix}")

        if missing:
            return CheckResult(
                protocol_id=f"{getattr(rule, 'id', 'UNKNOWN')}-depcheck",
                name=f"依赖检查: {getattr(rule, 'name', rule.id)}",
                passed=False,
                severity="BLOCKER",
                details=[
                    f"❌ 规则引用的实体/事实不存在: {', '.join(missing)}",
                    f"   规则: {rule.id} ({rule.name})",
                    "   修复: 补充缺失的实体/事实，或修正引用 ID",
                ],
                fixes=[f"添加缺失实体: {m}" for m in missing],
            )
        return None

    def _entity_exists(self, eid: str) -> bool:
        return self.domain.find_entity(eid) is not None

    def _fact_exists(self, fid: str) -> bool:
        return self.domain.find_fact(fid) is not None

    def _prefix_exists(self, prefix: str) -> bool:
        return any(e.id.startswith(prefix) for e in self.domain.entities)


class BaseChecker(BasePattern):
    """规约检查器的基类（checker 是一种特殊的 pattern）。

    与 BasePattern 的区别：checker 不产生新推论，只检查已有实体是否符合约束。
    """

    ...
