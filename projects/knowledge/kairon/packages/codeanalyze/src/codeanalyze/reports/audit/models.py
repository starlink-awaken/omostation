"""Audit data models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AuditGroup:
    """One cross-validation check group."""

    name: str
    checks: list[dict] = field(default_factory=list)
    passed: int = 0
    failed: int = 0

    def add_check(self, label: str, passed: bool, detail: str = "") -> None:
        self.checks.append({"label": label, "passed": passed, "detail": detail})
        if passed:
            self.passed += 1
        else:
            self.failed += 1

    @property
    def score(self) -> str:
        total = self.passed + self.failed
        return f"{self.passed}/{total}" if total else "0/0"


@dataclass
class AuditReport:
    """Full audit result across all check groups."""

    groups: list[AuditGroup] = field(default_factory=list)
    total_checks: int = 0
    total_passed: int = 0
    total_failed: int = 0

    def add_group(self, group: AuditGroup) -> None:
        self.groups.append(group)
        self.total_checks += group.passed + group.failed
        self.total_passed += group.passed
        self.total_failed += group.failed

    @property
    def score(self) -> float:
        return self.total_passed / self.total_checks * 100 if self.total_checks else 0

    def to_markdown(self) -> str:
        from datetime import datetime

        lines = [
            "# 知识审计报告",
            f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## 概览",
            f"- 检查组: {len(self.groups)}",
            f"- 检查项: {self.total_checks}",
            f"- 通过: {self.total_passed} ({self.score:.0f}%)",
            f"- 未通过: {self.total_failed}",
            "",
        ]
        for group in self.groups:
            lines.append(f"## {group.name}")
            lines.append(f"**通过率: {group.score}**")
            lines.append("")
            for c in group.checks:
                icon = "✅" if c["passed"] else "❌"
                lines.append(f"- {icon} {c['label']}")
                if c["detail"]:
                    lines.append(f"  _{c['detail']}_")
            lines.append("")
        return "\n".join(lines)
