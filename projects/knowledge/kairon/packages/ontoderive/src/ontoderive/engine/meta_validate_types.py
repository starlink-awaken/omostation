from __future__ import annotations

"""Meta Validate Types — 验证类型定义

定义元验证系统中使用的所有数据模型、枚举和类型：
- ValidationStatus, FalsePositiveType, FalseNegativeType
- ConfidenceScore, FalsePositive, FalseNegative
- GroundTruth, BenchmarkResult, ValidationVerification
- DocType, ValidationIssueSeverity, ValidationIssue
"""

import enum
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ValidationStatus(Enum):
    """验证状态"""

    UNVALIDATED = "unvalidated"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    PARTIAL = "partial"


class FalsePositiveType(Enum):
    """误报类型"""

    OVER_STRICT = "over_strict"
    PATTERN_MISMATCH = "pattern_mismatch"
    CONTEXT_MISSING = "context_missing"
    FALSE_ALARM = "false_alarm"


class FalseNegativeType(Enum):
    """漏报类型"""

    OVER_LENIENT = "over_lenient"
    PATTERN_MISSING = "pattern_missing"
    EDGE_CASE = "edge_case"
    SILENT_FAILURE = "silent_failure"


@dataclass
class ConfidenceScore:
    """置信度分数"""

    score: float
    precision: float
    recall: float
    f1_score: float
    benchmark_pass_rate: float
    factors: dict[str, float] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"ConfidenceScore(score={self.score:.3f}, precision={self.precision:.3f}, recall={self.recall:.3f})"


@dataclass
class FalsePositive:
    """误报"""

    id: str
    declaration_name: str
    issue_type: FalsePositiveType
    description: str
    original_alignment_issue_id: str
    root_cause: str
    suggestion: str
    detected_at: float = field(default_factory=time.time)


@dataclass
class FalseNegative:
    """漏报"""

    id: str
    declaration_name: str
    issue_type: FalseNegativeType
    description: str
    expected_issue: str
    root_cause: str
    suggestion: str
    detected_at: float = field(default_factory=time.time)


@dataclass
class GroundTruth:
    """基准真值"""

    id: str
    project: str
    version: str
    timestamp: float
    files: dict[str, Any]
    expected_alignment: dict[str, Any]
    source: str

    @classmethod
    def create_from_audit(
        cls,
        project: str,
        version: str,
        files: dict[str, Any],
        expected_alignment: dict[str, Any],
    ) -> GroundTruth:
        """从人工审核创建基准真值"""
        return cls(
            id=f"GT-{int(time.time())}",
            project=project,
            version=version,
            timestamp=time.time(),
            files=files,
            expected_alignment=expected_alignment,
            source="human_audit",
        )


@dataclass
class BenchmarkResult:
    """基准测试结果"""

    suite_name: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    pass_rate: float
    details: list[dict[str, Any]]
    duration: float


@dataclass
class ValidationVerification:
    """验证验证结果"""

    id: str
    alignment_report_id: str
    status: ValidationStatus
    confidence: ConfidenceScore
    false_positives: list[FalsePositive]
    false_negatives: list[FalseNegative]
    verified_at: float = field(default_factory=time.time)
    notes: str = ""


class DocType(enum.Enum):
    """Doc taxonomy as per the docs governance standard."""

    STATE = "State"
    REFERENCE = "Reference"
    PROCESS = "Process"
    INTERNAL = "Internal"
    INDEX = "Index"
    LAW = "Law"
    CONTEXT = "context"


class ValidationIssueSeverity(Enum):
    """Severity levels for doc-governance validation issues."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ValidationIssue:
    """A single doc-governance validation finding."""

    severity: ValidationIssueSeverity
    message: str
    doc_path: Path | None = None
    field_name: str | None = None
