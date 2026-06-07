"""
SSOT Kernel — reporter.py
==========================
报告生成器。将 DerivationReport 输出为多种格式。
"""

from __future__ import annotations

import datetime
import json

from .patterns.base import DerivationReport


class Reporter:
    """报告生成器"""

    @staticmethod
    def to_markdown(report: DerivationReport) -> str:
        """生成 Markdown 格式报告"""
        lines = []
        lines.append("---")
        lines.append("title: SSOT 推导报告")
        lines.append(f"executed_at: {report.executed_at}")
        lines.append(f"engine_version: {report.engine_version}")
        lines.append(f"domain: {report.domain_name}")
        lines.append(f"total_rules: {report.total_rules}")
        lines.append(f"blockers: {report.blocker}")
        lines.append(f"errors: {report.error}")
        lines.append(f"warnings: {report.warn}")
        lines.append("---")
        lines.append("")
        lines.append("# SSOT 推导报告")
        lines.append("")
        lines.append("## 执行摘要")
        lines.append("")
        lines.append("| 项目 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 领域 | {report.domain_name} |")
        lines.append(f"| 执行时间 | {report.executed_at} |")
        lines.append(f"| 引擎版本 | {report.engine_version} |")
        lines.append(f"| 规则总数 | {report.total_rules} |")
        lines.append(f"| 通过 | {report.passed} |")
        lines.append(f"| 🔴 BLOCKER | {report.blocker} |")
        lines.append(f"| 🟠 ERROR | {report.error} |")
        lines.append(f"| 🟡 WARN | {report.warn} |")
        lines.append("")
        lines.append(f"**总评**: {'✅ 全部通过' if report.all_passed else '⚠️ 有待处理缺口'}")
        lines.append("")

        for result in report.results:
            icon = (
                "✅"
                if result.passed
                else ("🔴" if result.severity == "BLOCKER" else "🟠" if result.severity == "ERROR" else "🟡")
            )
            lines.append(f"### {icon} {result.protocol_id}: {result.name}")
            lines.append(f"- **状态**: {'通过' if result.passed else '未通过'} | **严重度**: {result.severity}")
            for d in result.details:
                lines.append(f"- {d}")
            if not result.passed and result.fixes:
                for f in result.fixes:
                    lines.append(f"- 🔧 {f}")
            lines.append("")

        lines.append(f"*报告自动生成于 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}*")
        return "\n".join(lines)

    @staticmethod
    def to_json(report: DerivationReport) -> str:
        """生成 JSON 格式报告"""
        data = {
            "engine_version": report.engine_version,
            "executed_at": report.executed_at,
            "domain_name": report.domain_name,
            "summary": {
                "total": report.total_rules,
                "passed": report.passed,
                "blocker": report.blocker,
                "error": report.error,
                "warn": report.warn,
                "all_passed": report.all_passed,
            },
            "results": [
                {
                    "protocol_id": r.protocol_id,
                    "name": r.name,
                    "passed": r.passed,
                    "severity": r.severity,
                    "details": r.details,
                    "fixes": r.fixes,
                }
                for r in report.results
            ],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    @staticmethod
    def summary_line(report: DerivationReport) -> str:
        """一行摘要"""
        return (
            f"[{report.domain_name}] "
            f"✅ {report.passed}/{report.total_rules} passed | "
            f"🔴{report.blocker} 🟠{report.error} 🟡{report.warn}"
        )
