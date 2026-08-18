from __future__ import annotations

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
# Perception Validation ≡ Module
# 内涵 ≝ {Perception, Validation}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, PerceptionValidation)}
# 功能 ⊢ {Perception_Validation, Init_Perception, Validate_Validation}
# =============================================================================

# ---
# domain: D-Intelligence
# layer: organ
# status: active
# ---

import logging
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)


@dataclass
class PerceptionInput:
    input_id: str
    source: str
    data: dict
    timestamp: float
    confidence: float = 1.0


@dataclass
class ValidationResult:
    input_id: str
    valid: bool
    issues: list[str] = field(default_factory=list)
    adjusted_confidence: float = 1.0


class PerceptionValidation:
    """Validates perception inputs and tracks source trustworthiness."""

    def __init__(self) -> None:
        super().__init__()
        self._validators: dict[str, Callable] = {}
        self._pass_count: dict[str, int] = defaultdict(int)
        self._fail_count: dict[str, int] = defaultdict(int)
        self._rejection_reasons: dict[str, int] = defaultdict(int)

    def register_validator(self, source: str, validator_fn: Callable) -> None:
        self._validators[source] = validator_fn

    def validate(self, inp: PerceptionInput) -> ValidationResult:
        if inp.timestamp > time.time():
            self._fail_count[inp.source] += 1
            reason = "Perception timestamp is in the future"
            self._rejection_reasons[reason] += 1
            return ValidationResult(
                input_id=inp.input_id,
                valid=False,
                issues=[reason],
                adjusted_confidence=0.0,
            )

        validator = self._validators.get(inp.source)
        if validator is None:
            self._fail_count[inp.source] += 1
            reason = f"No validator registered for source '{inp.source}'"
            self._rejection_reasons[reason] += 1
            return ValidationResult(
                input_id=inp.input_id,
                valid=False,
                issues=[reason],
                adjusted_confidence=0.0,
            )
        try:
            issues = validator(inp)
            if not isinstance(issues, list):
                issues = []
        except (ValueError, TypeError, AttributeError, RuntimeError) as exc:
            issues = [f"Validator error: {exc}"]

        valid = len(issues) == 0
        if valid:
            self._pass_count[inp.source] += 1
        else:
            self._fail_count[inp.source] += 1
            for issue in issues:
                self._rejection_reasons[issue] += 1

        adjusted = self.adjust_confidence(inp) if valid else 0.0
        return ValidationResult(
            input_id=inp.input_id,
            valid=valid,
            issues=issues,
            adjusted_confidence=adjusted,
        )

    def validate_batch(self, inputs: list[PerceptionInput]) -> list[ValidationResult]:
        return [self.validate(inp) for inp in inputs]

    def get_trusted_sources(self) -> list[str]:
        trusted: list[str] = []
        all_sources = set(self._pass_count.keys()) | set(self._fail_count.keys())
        for source in all_sources:
            total = self._pass_count[source] + self._fail_count[source]
            if total > 0 and (self._pass_count[source] / total) > 0.9:
                trusted.append(source)
        return sorted(trusted)

    def get_source_stats(self, source: str) -> dict:
        passed = self._pass_count[source]
        failed = self._fail_count[source]
        total = passed + failed
        return {
            "source": source,
            "passed": passed,
            "failed": failed,
            "total": total,
            "pass_rate": passed / total if total > 0 else 0.0,
        }

    def adjust_confidence(self, inp: PerceptionInput) -> float:
        stats = self.get_source_stats(inp.source)
        pass_rate = stats["pass_rate"]
        if stats["total"] == 0:
            return inp.confidence
        return inp.confidence * (0.5 + 0.5 * pass_rate)

    def get_rejection_reasons(self) -> dict[str, int]:
        return dict(self._rejection_reasons)
