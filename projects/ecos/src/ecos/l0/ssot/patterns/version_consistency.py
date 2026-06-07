"""
SSOT Kernel — patterns/version_consistency.py
Schema 版本一致性校验模式 (L1-1: 契约版本化)

检查规则：
1. 所有注册的 Schema 必须具有符合 SemVer (MAJOR.MINOR.PATCH) 的版本号
2. 跨项目声明的依赖版本约束必须满足当前注册表版本
3. 过期版本（>= 2 MAJOR behind）应输出 deprecation warning
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..meta_model import DomainConfig
from .base import BasePattern, CheckResult

if TYPE_CHECKING:
    from ..meta_model import Rule


SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


class VersionConsistencyPattern(BasePattern):
    """Schema 版本一致性校验模式。

    遍历领域配置中所有受管的 Schema 注册条目，
    检查版本号是否符合 SemVer 规范，以及是否满足依赖的版本约束。
    """

    @property
    def pattern_name(self) -> str:
        return "version_consistency"

    def evaluate(self, rule: Rule, domain: DomainConfig, context: dict | None = None) -> CheckResult:
        rule_id = rule.id
        rule_name = rule.name or rule_id

        issues = []
        schema_registry = rule.params.get("schema_registry", [])
        dep_constraints = rule.params.get("dependency_constraints", {})
        current_major = rule.params.get("current_major", 1)

        # 1. 检查每个 Schema 的版本号是否符合 SemVer
        for entry in schema_registry:
            schema_name = entry.get("name", "unknown")
            version = entry.get("version", "")
            status = entry.get("status", "active")

            if not SEMVER_RE.match(version):
                issues.append(
                    {
                        "schema": schema_name,
                        "version": version,
                        "issue": f"版本号不符合 SemVer: '{version}' (应为 MAJOR.MINOR.PATCH)",
                    }
                )
                continue

            # 2. 检查过期版本 (>= 2 MAJOR behind)
            try:
                major = int(version.split(".")[0])
            except (ValueError, IndexError):
                issues.append(
                    {
                        "schema": schema_name,
                        "version": version,
                        "issue": "无法解析 MAJOR 版本号",
                    }
                )
                continue

            major_diff = current_major - major
            if major_diff >= 3 and status != "deprecated":
                issues.append(
                    {
                        "schema": schema_name,
                        "version": version,
                        "issue": f"版本 v{version} 已落后 {major_diff} 个 MAJOR, 应标记为 deprecated 或删除",
                    }
                )
            elif major_diff >= 2:
                issues.append(
                    {
                        "schema": schema_name,
                        "version": version,
                        "issue": f"版本 v{version} 已落后 {major_diff} 个 MAJOR, 请输出 deprecation_warning",
                    }
                )

        # 3. 检查跨项目依赖约束
        for dep_name, constraint in dep_constraints.items():
            entry = None
            for e in schema_registry:
                if e.get("name") == dep_name:
                    entry = e
                    break
            if entry is None:
                issues.append(
                    {
                        "schema": dep_name,
                        "issue": f"依赖 '{dep_name}' 在注册表中不存在",
                    }
                )
                continue

            dep_version = entry.get("version", "0.0.0")
            if not self._version_satisfies(dep_version, constraint):
                issues.append(
                    {
                        "schema": dep_name,
                        "version": dep_version,
                        "constraint": constraint,
                        "issue": f"版本 v{dep_version} 不满足依赖约束 '{constraint}'",
                    }
                )

        if issues:
            details = [f"⚠️ {rule_name}: {len(issues)} 个版本一致性问题"]
            for item in issues[:10]:
                schema = item.get("schema", "?")
                issue = item.get("issue", "?")
                details.append(f"  ├─ {schema}: {issue}")
            return CheckResult(
                protocol_id=rule_id,
                name=rule_name,
                passed=False,
                severity="ERROR",
                details=details,
                fixes=["更新版本号以符合 SemVer", "标记过期版本为 deprecated", "更新依赖约束以匹配当前版本"],
                meta={"issues": issues},
            )
        else:
            return CheckResult(
                protocol_id=rule_id,
                name=rule_name,
                passed=True,
                details=[f"✅ {rule_name}: 所有 Schema 版本一致"],
                meta={"issues": []},
            )

    @staticmethod
    def _version_satisfies(version: str, constraint: str) -> bool:
        """检查 version 是否满足 SemVer 约束字符串（如 '>=1.0.0 <2.0.0'）。

        当前支持简单比较：>=X.Y.Z, <X.Y.Z, >=X.Y.Z <X.Y.Z
        """
        try:
            parts = constraint.strip().split()
            v_parts = [int(x) for x in version.split(".")]

            for part in parts:
                if part.startswith(">="):
                    min_v = [int(x) for x in part[2:].split(".")]
                    # 逐段比较
                    if tuple(v_parts) < tuple(min_v):
                        return False
                elif part.startswith("<="):
                    max_v = [int(x) for x in part[2:].split(".")]
                    if tuple(v_parts) > tuple(max_v):
                        return False
                elif part.startswith(">"):
                    min_v = [int(x) for x in part[1:].split(".")]
                    if tuple(v_parts) <= tuple(min_v):
                        return False
                elif part.startswith("<"):
                    max_v = [int(x) for x in part[1:].split(".")]
                    if tuple(v_parts) >= tuple(max_v):
                        return False
                elif part.startswith("=="):
                    eq_v = [int(x) for x in part[2:].split(".")]
                    if tuple(v_parts) != tuple(eq_v):
                        return False
            return True
        except (ValueError, IndexError):
            return False
