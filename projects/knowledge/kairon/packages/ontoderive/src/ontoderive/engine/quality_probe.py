from __future__ import annotations

#!/usr/bin/env python3
"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Quality Probe ≡ Module
# 内涵 ≝ {Quality, Probe}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, QualityProbe)}
# 功能 ⊢ {Quality_Probe, Init_Quality, Validate_Probe}
# =============================================================================

# ---
# Type: Module
# Status: ACTIVE
# Layer: L3
# ---
"""
Quality Probe - 文档质量探针

功能:
- Frontmatter 完整性检查
- 命名规范检查
- 形式化摘要检查
- AI Context 检查
- 综合评分计算

Usage:
    python3 -m organs.D_Logos.organs.quality_probe --check docs/README.md
    python3 -m organs.D_Logos.organs.quality_probe --scan docs/ --output report.json
"""


import argparse
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

_log = logging.getLogger(__name__)


class Severity(Enum):
    """问题严重程度"""

    CRITICAL = "critical"  # 阻断级
    MAJOR = "major"  # 严重级
    MINOR = "minor"  # 轻微级
    INFO = "info"  # 提示级


@dataclass
class QualityIssue:
    """质量问题"""

    file_path: Path
    check_type: str
    severity: Severity
    message: str
    suggestion: str
    line_number: int | None = None
    auto_fixable: bool = False
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "file_path": str(self.file_path),
            "check_type": self.check_type,
            "severity": self.severity.value,
            "message": self.message,
            "suggestion": self.suggestion,
            "line_number": self.line_number,
            "auto_fixable": self.auto_fixable,
            "context": self.context,
        }


@dataclass
class ScanResult:
    """扫描结果"""

    file_path: Path
    issues: list[QualityIssue]
    score: float
    scan_duration_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "file_path": str(self.file_path),
            "issues_count": len(self.issues),
            "issues": [i.to_dict() for i in self.issues],
            "score": self.score,
            "scan_duration_ms": self.scan_duration_ms,
            "timestamp": self.timestamp,
        }


class QualityProbe:
    """质量探针"""

    def __init__(self, config_path: str | None = None) -> None:
        self.config = self._load_config(config_path)
        self.checks = {
            "frontmatter": self._check_frontmatter,
            "naming": self._check_naming,
            "formal_summary": self._check_formal_summary,
            "ai_context": self._check_ai_context,
        }

    def scan(self, path: Path, check_types: list[str] | None = None) -> ScanResult:
        """扫描单个文档"""
        start_time = time.time()
        issues = []

        if check_types is None:
            check_types = list(self.checks.keys())

        for check_type in check_types:
            check_func = self.checks.get(check_type)
            if not check_func:
                _log.warning(f"Unknown check type: {check_type}")
                continue

            found_issues = check_func(path)
            issues.extend(found_issues)

        score = self.calculate_score(issues)
        duration_ms = (time.time() - start_time) * 1000

        return ScanResult(file_path=path, issues=issues, score=score, scan_duration_ms=duration_ms)

    def scan_directory(
        self, dir_path: Path, pattern: str = "**/*.md", exclude_patterns: list[str] | None = None
    ) -> list[ScanResult]:
        """扫描目录"""
        results = []

        all_files = list(dir_path.glob(pattern))
        _log.info(f"Found {len(all_files)} markdown files")

        for i, file_path in enumerate(all_files, 1):
            # 跳过排除模式
            if exclude_patterns:
                skip = any(re.match(pat, str(file_path)) for pat in exclude_patterns)
                if skip:
                    continue

            if i % 50 == 0:
                _log.info(f"Scanning {i}/{len(all_files)}: {file_path}")

            result = self.scan(file_path)
            results.append(result)

        return results

    def _check_frontmatter(self, path: Path) -> list[QualityIssue]:
        """检查 YAML Frontmatter"""
        issues = []
        content = path.read_text(encoding="utf-8")

        # 解析 frontmatter (更宽松的模式，允许前导空白)
        match = re.search(r"(?:^|\n)---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)

        if not match:
            issues.append(
                QualityIssue(
                    file_path=path,
                    check_type="frontmatter",
                    severity=Severity.CRITICAL,
                    message="Missing YAML frontmatter",
                    suggestion="Add YAML frontmatter with required fields: Type, Status, Version, Owner, Authority",
                    auto_fixable=True,
                    context={"missing": "entire_frontmatter"},
                )
            )
            return issues

        # 尝试解析 YAML
        fm = {}
        if yaml:
            try:
                fm_raw = match.group(1)
                # 快速检查：如果包含 Markdown 标题或粗体标记（不在引号内），可能是无效的 frontmatter
                # 注意：YAML 字符串值可以包含 [ ] 等字符，所以只检测明显的 Markdown 格式
                has_markdown_headers = bool(re.search(r"^\s*#+\s*\w", fm_raw, re.MULTILINE))  # ## Header
                has_markdown_bold = bool(re.search(r"\*\*[^*]+\*\*", fm_raw))  # **bold**

                if has_markdown_headers or has_markdown_bold:
                    issues.append(
                        QualityIssue(
                            file_path=path,
                            check_type="frontmatter",
                            severity=Severity.CRITICAL,
                            message="Invalid frontmatter format (contains Markdown)",
                            suggestion="Frontmatter must be valid YAML, not Markdown content",
                            auto_fixable=False,
                            context={"format_error": True},
                        )
                    )
                    return issues

                fm = yaml.safe_load(fm_raw)

                # yaml.safe_load 可能返回字符串而不是字典
                if not isinstance(fm, dict):
                    issues.append(
                        QualityIssue(
                            file_path=path,
                            check_type="frontmatter",
                            severity=Severity.CRITICAL,
                            message="Invalid YAML frontmatter structure",
                            suggestion="Frontmatter must be a YAML mapping (key: value)",
                            auto_fixable=False,
                            context={"structure_error": True},
                        )
                    )
                    return issues

            except yaml.YAMLError as e:
                issues.append(
                    QualityIssue(
                        file_path=path,
                        check_type="frontmatter",
                        severity=Severity.CRITICAL,
                        message=f"Invalid YAML syntax: {str(e)[:100]}",
                        suggestion="Fix YAML syntax errors",
                        auto_fixable=False,
                        context={"yaml_error": str(e)},
                    )
                )
                return issues
        else:
            _log.warning("PyYAML not available, skipping deep frontmatter validation")
            return issues

        # 检查必需字段
        required_fields = ["Type", "Status", "Version", "Owner", "Authority"]
        for fld in required_fields:
            if fld not in fm:
                # 检查是否有替代字段
                alternatives = {
                    "Version": ["Updated", "Create"],  # Version 可用 Updated 替代
                    "Owner": ["Author", "Maintainer"],  # Owner 可用 Author 替代
                }

                has_alternative = any(alt in fm for alt in alternatives.get(fld, []))

                if not has_alternative:
                    issues.append(
                        QualityIssue(
                            file_path=path,
                            check_type="frontmatter",
                            severity=Severity.MAJOR if fld in ["Type", "Authority"] else Severity.MINOR,
                            message=f"Missing required field: {fld}",
                            suggestion=f'Add "{fld}" to frontmatter',
                            auto_fixable=True,
                            context={"missing_field": fld},
                        )
                    )

        # 检查自动生成元数据
        owner = fm.get("Owner", "")
        constraint = str(fm.get("Constraint", ""))

        if owner == "@Sisyphus" or "AUTO_ADDED_METADATA" in constraint:
            issues.append(
                QualityIssue(
                    file_path=path,
                    check_type="frontmatter",
                    severity=Severity.MAJOR,
                    message="Auto-generated metadata detected",
                    suggestion="Replace @Sisyphus with real owner and remove AUTO_ADDED_METADATA constraint",
                    auto_fixable=False,
                    context={"auto_generated": True},
                )
            )

        # 检查 Status 有效性
        valid_statuses = [
            "ACTIVE",
            "DRAFT",
            "DEPRECATED",
            "ARCHIVED",
            "RESERVE",
            "FUTURE_VISION",
            "PRODUCTION_READY",
        ]
        status = fm.get("Status", "")
        if status and status not in valid_statuses:
            issues.append(
                QualityIssue(
                    file_path=path,
                    check_type="frontmatter",
                    severity=Severity.MINOR,
                    message=f"Invalid status value: {status}",
                    suggestion=f"Use one of: {', '.join(valid_statuses)}",
                    auto_fixable=True,
                    context={"invalid_status": status},
                )
            )

        return issues

    def _check_naming(self, path: Path) -> list[QualityIssue]:
        """检查命名规范"""
        issues = []
        filename = path.name
        rel_path = str(path)

        # 检查大写字母（除了特定情况）
        if re.search(r"[A-Z]", filename):
            allowed_patterns = ["README", "ADR-", "RFC-", "API", "EU", "BOS", "LLM", "DAO"]
            if not any(pattern in filename for pattern in allowed_patterns):
                issues.append(
                    QualityIssue(
                        file_path=path,
                        check_type="naming",
                        severity=Severity.MINOR,
                        message=f"Uppercase letters in filename: {filename}",
                        suggestion="Use kebab-case (lowercase with hyphens)",
                        auto_fixable=True,
                        context={"current_name": filename},
                    )
                )

        # 检查下划线（排除 __pycache__ 等）
        if "_" in filename and not filename.startswith("__"):
            issues.append(
                QualityIssue(
                    file_path=path,
                    check_type="naming",
                    severity=Severity.MINOR,
                    message=f"Underscores in filename: {filename}",
                    suggestion="Use hyphens instead of underscores",
                    auto_fixable=True,
                    context={"current_name": filename},
                )
            )

        # 检查 Process 文档日期前缀
        if "25-implementation" in rel_path or "milestones" in rel_path:
            if not re.match(r"^\d{8}-", filename) and filename != "README.md":
                issues.append(
                    QualityIssue(
                        file_path=path,
                        check_type="naming",
                        severity=Severity.MINOR,
                        message="Process document missing date prefix",
                        suggestion="Add YYYYMMDD- prefix (e.g., 20260317-feature.md)",
                        auto_fixable=True,
                        context={"needs_date_prefix": True},
                    )
                )

        # 检查全大写文件名（严重违规）
        if filename.isupper() and filename.endswith(".md"):
            issues.append(
                QualityIssue(
                    file_path=path,
                    check_type="naming",
                    severity=Severity.MAJOR,
                    message=f"All-uppercase filename: {filename}",
                    suggestion="Convert to lowercase with kebab-case",
                    auto_fixable=True,
                    context={"severe_violation": True},
                )
            )

        return issues

    def _check_formal_summary(self, path: Path) -> list[QualityIssue]:
        """检查形式化摘要"""
        issues = []
        content = path.read_text(encoding="utf-8")

        # 检查是否存在形式化摘要章节
        patterns = [
            r"## 0\. 形式化摘要 ≝",
            r"## 0\. 形式化摘要",
            r"## Formal Summary",
        ]

        has_summary = any(re.search(pattern, content) for pattern in patterns)

        if not has_summary:
            # 检查是否有 logic 代码块作为替代
            has_logic_block = "```logic" in content

            issues.append(
                QualityIssue(
                    file_path=path,
                    check_type="formal_summary",
                    severity=Severity.MAJOR if "20-architecture" in str(path) else Severity.MINOR,
                    message="Missing formal summary section",
                    suggestion='Add "## 0. 形式化摘要 ≝" section with ```logic block',
                    auto_fixable=True,
                    context={"has_logic_block": has_logic_block},
                )
            )

        # 检查形式化摘要的质量
        if has_summary:
            # 检查是否包含 Define 语句
            if "Define(" not in content:
                issues.append(
                    QualityIssue(
                        file_path=path,
                        check_type="formal_summary",
                        severity=Severity.INFO,
                        message="Formal summary lacks Define statements",
                        suggestion="Add Define(Goal), Define(Scope), etc.",
                        auto_fixable=False,
                    )
                )

        return issues

    def _check_ai_context(self, path: Path) -> list[QualityIssue]:
        """检查 AI Semantic Context"""
        issues = []
        content = path.read_text(encoding="utf-8")

        patterns = [
            r"## 🤖 AI Semantic Context",
            r"## AI Semantic Context",
            r"## 🤖AI Semantic Context",
            r"> \*\*AI 指引\*\*",
        ]

        has_context = any(re.search(pattern, content) for pattern in patterns)

        if not has_context:
            issues.append(
                QualityIssue(
                    file_path=path,
                    check_type="ai_context",
                    severity=Severity.MINOR,
                    message="Missing AI Semantic Context section",
                    suggestion='Add "## 🤖 AI Semantic Context" section with usage guidelines',
                    auto_fixable=True,
                    context={},
                )
            )

        return issues

    def calculate_score(self, issues: list[QualityIssue]) -> float:
        """计算质量评分 (0-100)"""
        if not issues:
            return 100.0

        severity_weights = {
            Severity.CRITICAL: 30,
            Severity.MAJOR: 15,
            Severity.MINOR: 5,
            Severity.INFO: 1,
        }

        total_penalty = sum(severity_weights[i.severity] for i in issues)
        score = max(0, 100 - total_penalty)

        return round(score, 2)

    def _load_config(self, config_path: str | None) -> dict[str, Any]:
        """加载配置文件"""
        default_config = {
            "threshold": 0.85,
            "auto_fix_enabled": True,
            "checks": ["frontmatter", "naming", "formal_summary", "ai_context"],
            "exclude_patterns": [
                r"\.git/",
                r"__pycache__/",
                r"\.venv/",
                r"node_modules/",
            ],
            "severity_weights": {
                Severity.CRITICAL.value: 30,
                Severity.MAJOR.value: 15,
                Severity.MINOR.value: 5,
                Severity.INFO.value: 1,
            },
        }

        if config_path and Path(config_path).exists():
            with open(config_path) as f:
                loaded = json.load(f)
                default_config.update(loaded)

        return default_config


def main() -> None:
    """CLI 入口"""
    parser = argparse.ArgumentParser(description="Quality Probe - Document Quality Scanner")
    parser.add_argument("path", type=str, help="File or directory to scan")
    parser.add_argument(
        "--check",
        nargs="+",
        choices=["frontmatter", "naming", "formal_summary", "ai_context"],
        default=["frontmatter", "naming", "formal_summary", "ai_context"],
        help="Checks to run",
    )
    parser.add_argument("--output", type=str, help="Output JSON file")
    parser.add_argument("--config", type=str, help="Config file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--threshold", type=float, default=85.0, help="Minimum acceptable score")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    probe = QualityProbe(config_path=args.config)
    path = Path(args.path)

    if path.is_file():
        result = probe.scan(path, check_types=args.check)
        results = [result]
    elif path.is_dir():
        results = probe.scan_directory(path, pattern="**/*.md")
    else:
        print(f"Error: {path} does not exist")
        sys.exit(1)

    # 输出结果
    total_issues = sum(len(r.issues) for r in results)
    avg_score = sum(r.score for r in results) / len(results) if results else 0

    print(f"\n{'=' * 60}")
    print("SCAN COMPLETE")
    print(f"{'=' * 60}")
    print(f"Files scanned: {len(results)}")
    print(f"Total issues: {total_issues}")
    print(f"Average score: {avg_score:.2f}/100")
    print(f"Threshold: {args.threshold}")

    if avg_score < args.threshold:
        print("\n❌ FAILED: Score below threshold!")
        sys.exit(1)
    else:
        print("\n✅ PASSED: Score meets threshold")

    # 保存详细报告
    if args.output:
        output_data = {
            "scan_timestamp": datetime.now().isoformat(),
            "files_scanned": len(results),
            "total_issues": total_issues,
            "average_score": avg_score,
            "results": [r.to_dict() for r in results],
        }

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)

        print(f"\nDetailed report saved to: {output_path}")


if __name__ == "__main__":
    main()
