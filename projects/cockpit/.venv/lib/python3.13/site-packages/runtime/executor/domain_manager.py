"""Domain schema definition, loading, metrics, and registry.

Migrated from agentmesh engine: domain-schema.ts, domain-metrics.ts,
domain-loader.ts, domain-registry.ts.

Provides domain configuration schema validation, archetype-specific
success metrics, domain configuration loading with default merging,
and a registry for shared boilerplate defaults.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

# ============================================================
# Constants
# ============================================================

Archetype = Literal[
    "software-dev", "creative-writing", "visual-production",
    "document-processing", "data-science", "custom",
]
ComplexityLevel = Literal["simple", "standard", "advanced", "enterprise"]
Phase = Literal["init", "research", "decision", "execution", "feedback", "delivery"]
RiskLevel = Literal["low", "medium", "high", "critical"]
MetricDirection = Literal["higher-is-better", "lower-is-better"]
MetricUnit = str

MINIMUM_PASS_SCORE = 70.0

_METRIC_DIR_MAP: dict[str, int] = {"low": 1, "medium": 2, "high": 3, "critical": 4}
_ACTION_PRIORITY: dict[str, int] = {
    "pause": 5, "rollback": 4, "scale": 3, "alert": 2, "ignore": 1,
}

ARCHETYPE_TO_DIR: dict[str, str | None] = {
    "software-dev": "software",
    "creative-writing": "creative-writing",
    "visual-production": "visual-production",
    "document-processing": "document-processing",
    "data-science": "data-science",
    "custom": None,
}


# ============================================================
# Schema Types
# ============================================================

@dataclass
class ValidationError:
    message: str
    path: str
    value: Any = None
    expected: str | None = None


@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class Schema:
    type: str
    required: bool = False
    default: Any = None
    enum: list[Any] | None = None
    min: float | None = None
    max: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    properties: dict[str, Schema] | None = None
    items: Schema | None = None
    additional_properties: bool | None = None


# ============================================================
# Domain Config Types
# ============================================================

@dataclass
class QualityGateCriterion:
    id: str
    name: str
    description: str = ""
    expression: str = ""
    threshold: float | None = None
    unit: str | None = None
    mandatory: bool = True
    expected_variables: list[str] = field(default_factory=list)


@dataclass
class QualityGate:
    name: str
    phase: Phase
    criteria: list[QualityGateCriterion]
    mandatory: bool = True
    description: str = ""
    config_file: str | None = None


@dataclass
class DomainDefaults:
    complexity: ComplexityLevel = "standard"
    token_budget: int = 100_000
    max_concurrent_agents: int = 3


@dataclass
class DomainConfig:
    name: str
    description: str
    archetype: Archetype
    version: str
    phase_prompts: dict[str, str] = field(default_factory=dict)
    defaults: DomainDefaults = field(default_factory=DomainDefaults)
    quality_gates: list[QualityGate] = field(default_factory=list)


# ============================================================
# Metric Types
# ============================================================

@dataclass
class MetricDefinition:
    name: str
    description: str
    unit: MetricUnit
    target: float
    weight: float
    direction: MetricDirection


@dataclass
class MetricMeasurement:
    metric_name: str
    value: float
    timestamp: float
    passed: bool
    details: str | None = None


@dataclass
class DomainMetricProfile:
    archetype: Archetype
    metrics: list[MetricDefinition]


@dataclass
class QualityReport:
    project_id: str
    archetype: Archetype
    generated_at: float
    overall_score: float
    passed: bool
    metrics: list[dict[str, Any]]
    summary: str


# ============================================================
# Schema Validator
# ============================================================

_DOMAIN_SCHEMA: Schema = Schema(
    type="object",
    required=True,
    properties={
        "name": Schema(type="string", required=True, min_length=1, max_length=100),
        "description": Schema(type="string", required=True, min_length=10, max_length=500),
        "archetype": Schema(
            type="string", required=True,
            enum=["software-dev", "creative-writing", "visual-production",
                  "document-processing", "data-science", "custom"],
        ),
        "version": Schema(type="string", required=True, pattern=r"^\d+\.\d+\.\d+(-[a-z0-9.]+)?$"),
    },
    additional_properties=True,
)


def validate_schema(value: Any, schema: Schema, path: str = "$") -> ValidationResult:
    """Validate a value against a schema definition."""
    errors: list[ValidationError] = []
    warnings: list[str] = []

    if schema.required and value is None:
        errors.append(ValidationError("Required field is missing", path, expected=schema.type))
        return ValidationResult(valid=False, errors=errors, warnings=warnings)

    if value is None:
        return ValidationResult(valid=True, errors=[], warnings=warnings)

    # Type check
    if not _check_type(value, schema.type):
        errors.append(ValidationError(
            f"Expected {schema.type}, got {type(value).__name__}", path, value, schema.type,
        ))
        return ValidationResult(valid=False, errors=errors, warnings=warnings)

    # String validations
    if schema.type == "string" and isinstance(value, str):
        if schema.min_length is not None and len(value) < schema.min_length:
            errors.append(ValidationError(
                f"Minimum length is {schema.min_length}, got {len(value)}", path, value,
            ))
        if schema.max_length is not None and len(value) > schema.max_length:
            errors.append(ValidationError(
                f"Maximum length is {schema.max_length}, got {len(value)}", path, value,
            ))
        if schema.pattern and not re.match(schema.pattern, value):
            errors.append(ValidationError("Value does not match required pattern", path, value))

    # Number validations
    if schema.type == "number" and isinstance(value, (int, float)):
        if schema.min is not None and value < schema.min:
            errors.append(ValidationError(f"Minimum value is {schema.min}, got {value}", path, value))
        if schema.max is not None and value > schema.max:
            errors.append(ValidationError(f"Maximum value is {schema.max}, got {value}", path, value))

    # Enum validation
    if schema.enum is not None and value not in schema.enum:
        errors.append(ValidationError(
            f"Value must be one of: {', '.join(str(e) for e in schema.enum)}", path, value,
        ))

    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


def _check_type(value: Any, type_name: str) -> bool:
    mapping = {
        "string": lambda v: isinstance(v, str),
        "number": lambda v: isinstance(v, (int, float)) and not (isinstance(v, float) and v != v),
        "boolean": lambda v: isinstance(v, bool),
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "null": lambda v: v is None,
    }
    return mapping.get(type_name, lambda v: True)(value)


# ============================================================
# Domain Loader
# ============================================================

def build_default_profiles() -> dict[Archetype, DomainMetricProfile]:
    """Build default metric profiles for all supported archetypes."""
    profiles: dict[Archetype, DomainMetricProfile] = {}

    profiles["software-dev"] = DomainMetricProfile(
        archetype="software-dev",
        metrics=[
            MetricDefinition("code_coverage", "Percentage of code covered by tests", "percentage", 80, 0.25, "higher-is-better"),
            MetricDefinition("bug_density", "Bugs per thousand lines of code", "ratio", 0.5, 0.2, "lower-is-better"),
            MetricDefinition("api_consistency", "API endpoints following design standards", "percentage", 100, 0.15, "higher-is-better"),
            MetricDefinition("deploy_success", "Deployment success rate", "percentage", 99, 0.2, "higher-is-better"),
            MetricDefinition("test_pass_rate", "Percentage of tests passing", "percentage", 95, 0.2, "higher-is-better"),
        ],
    )

    profiles["creative-writing"] = DomainMetricProfile(
        archetype="creative-writing",
        metrics=[
            MetricDefinition("plot_coherence", "Logical consistency and flow (1-10)", "score", 8, 0.25, "higher-is-better"),
            MetricDefinition("character_consistency", "Consistency of character behavior (1-10)", "score", 9, 0.25, "higher-is-better"),
            MetricDefinition("reader_retention", "Estimated reader engagement", "percentage", 80, 0.2, "higher-is-better"),
            MetricDefinition("style_unity", "Writing style consistency (1-10)", "score", 7, 0.15, "higher-is-better"),
            MetricDefinition("pacing_score", "Narrative pacing quality (1-10)", "score", 7, 0.15, "higher-is-better"),
        ],
    )

    profiles["visual-production"] = DomainMetricProfile(
        archetype="visual-production",
        metrics=[
            MetricDefinition("art_consistency", "Visual style consistency (1-10)", "score", 9, 0.3, "higher-is-better"),
            MetricDefinition("narrative_flow", "Visual storytelling flow (1-10)", "score", 8, 0.25, "higher-is-better"),
            MetricDefinition("visual_impact", "Overall visual impact (1-10)", "score", 8, 0.25, "higher-is-better"),
            MetricDefinition("style_unity", "Coherence of artistic style (1-10)", "score", 8, 0.2, "higher-is-better"),
        ],
    )

    profiles["document-processing"] = DomainMetricProfile(
        archetype="document-processing",
        metrics=[
            MetricDefinition("content_accuracy", "Accuracy of extracted/generated content", "percentage", 99, 0.3, "higher-is-better"),
            MetricDefinition("format_compliance", "Adherence to output format standards", "percentage", 100, 0.25, "higher-is-better"),
            MetricDefinition("terminology_consistency", "Terminology consistency across documents", "percentage", 95, 0.2, "higher-is-better"),
            MetricDefinition("audit_completeness", "Completeness of audit trail", "percentage", 100, 0.25, "higher-is-better"),
        ],
    )

    profiles["custom"] = DomainMetricProfile(
        archetype="custom",
        metrics=[
            MetricDefinition("delivery_completeness", "Percentage of deliverables completed", "percentage", 90, 0.6, "higher-is-better"),
            MetricDefinition("quality_score", "Overall quality assessment (1-10)", "score", 7, 0.4, "higher-is-better"),
        ],
    )

    return profiles


def _evaluate_pass_fail(value: float, target: float, direction: MetricDirection) -> bool:
    if direction == "higher-is-better":
        return value >= target
    return value <= target


def _normalize_score(value: float, target: float, direction: MetricDirection) -> float:
    """Normalize a metric value to a 0--100 score."""
    if direction == "higher-is-better":
        if target == 0:
            return 100.0 if value >= 0 else 0.0
        return min(100.0, (value / target) * 100.0)
    # lower-is-better
    if target == 0:
        return 100.0 if value == 0 else max(0.0, 100.0 - value * 100.0)
    ratio = value / target
    if ratio <= 1:
        return 100.0
    return max(0.0, (2.0 - ratio) * 100.0)


def _build_summary(
    archetype: Archetype, score: float, passed: int, failed: int, not_measured: int, total: int,
) -> str:
    measured = passed + failed
    parts = [f"Quality report for archetype \"{archetype}\": overall score {score:.1f}/100."]
    if measured == 0:
        parts.append(f"No metrics have been measured yet (0/{total}).")
    else:
        parts.append(f"{measured}/{total} metrics measured: {passed} passed, {failed} failed.")
    if not_measured > 0 and measured > 0:
        parts.append(f"{not_measured} metric(s) still awaiting measurement.")
    parts.append("Status: PASSED." if score >= MINIMUM_PASS_SCORE else "Status: FAILED.")
    return " ".join(parts)


# ============================================================
# DomainRegistry
# ============================================================

class DomainRegistry:
    """Provides default values for domain configurations to reduce boilerplate."""

    def __init__(
        self,
        base_defaults: DomainDefaults | None = None,
    ) -> None:
        self._base_defaults = base_defaults or DomainDefaults()

    def get_effective_config(self, partial: dict[str, Any]) -> DomainConfig:
        """Merge a partial domain config with registry defaults."""
        defaults = self._base_defaults
        user_defaults = partial.get("defaults", {})
        if isinstance(user_defaults, dict) and user_defaults:
            defaults = DomainDefaults(
                complexity=user_defaults.get("complexity", defaults.complexity),
                token_budget=user_defaults.get("token_budget", defaults.token_budget),
                max_concurrent_agents=user_defaults.get("max_concurrent_agents", defaults.max_concurrent_agents),
            )

        return DomainConfig(
            name=partial.get("name", ""),
            description=partial.get("description", ""),
            archetype=partial.get("archetype", "custom"),
            version=partial.get("version", "1.0.0"),
            phase_prompts=partial.get("phase_prompts", {}),
            defaults=defaults,
            quality_gates=_parse_quality_gates(partial.get("quality_gates", [])),
        )


def _parse_quality_gates(gates: Any) -> list[QualityGate]:
    if not isinstance(gates, list):
        return []
    result: list[QualityGate] = []
    for g in gates:
        if not isinstance(g, dict):
            continue
        raw_criteria = g.get("criteria", [])
        criteria = []
        for i, c in enumerate(raw_criteria):
            if isinstance(c, str):
                criteria.append(QualityGateCriterion(
                    id=f"criterion-{len(result)}-{i}",
                    name=c, description=c, expression=c,
                ))
            elif isinstance(c, dict):
                criteria.append(QualityGateCriterion(
                    id=c.get("id", str(uuid.uuid4())),
                    name=c.get("name", ""),
                    description=c.get("description", ""),
                    expression=c.get("expression", c.get("pass_condition", "")),  # type: ignore[arg-type]
                    threshold=c.get("threshold"),
                    unit=c.get("unit"),
                    mandatory=c.get("mandatory", True),
                ))
        result.append(QualityGate(
            name=g.get("name", ""),
            phase=g.get("phase", "execution"),
            criteria=criteria,
            mandatory=g.get("mandatory", True),
            description=g.get("description", ""),
            config_file=g.get("config_file"),
        ))
    return result


# ============================================================
# DomainMetrics (Quality Assessment)
# ============================================================

class DomainMetrics:
    """Domain-specific success criteria tracking and quality report generation."""

    def __init__(self) -> None:
        self._profiles: dict[Archetype, DomainMetricProfile] = build_default_profiles()
        self._measurements: dict[str, dict[str, list[MetricMeasurement]]] = {}

    # -- Profile Management --

    def get_profile(self, archetype: Archetype) -> DomainMetricProfile | None:
        return self._profiles.get(archetype)

    def set_profile(self, archetype: Archetype, metrics: list[MetricDefinition]) -> None:
        self._profiles[archetype] = DomainMetricProfile(archetype=archetype, metrics=list(metrics))

    def add_metric(self, archetype: Archetype, metric: MetricDefinition) -> None:
        profile = self._profiles.get(archetype)
        if profile:
            profile.metrics.append(MetricDefinition(**vars(metric)))
        else:
            self._profiles[archetype] = DomainMetricProfile(archetype=archetype, metrics=[MetricDefinition(**vars(metric))])

    # -- Measurement Recording --

    def record_measurement(
        self, project_id: str, metric_name: str, value: float, details: str | None = None,
    ) -> MetricMeasurement:
        passed = False
        for profile in self._profiles.values():
            for m in profile.metrics:
                if m.name == metric_name:
                    passed = _evaluate_pass_fail(value, m.target, m.direction)
                    break
        measurement = MetricMeasurement(
            metric_name=metric_name, value=value, timestamp=time.time(), passed=passed, details=details,
        )
        self._measurements.setdefault(project_id, {}).setdefault(metric_name, []).append(measurement)
        return measurement

    def get_measurements(self, project_id: str, metric_name: str | None = None) -> list[MetricMeasurement]:
        project_map = self._measurements.get(project_id)
        if not project_map:
            return []
        if metric_name:
            return project_map.get(metric_name, [])
        result: list[MetricMeasurement] = []
        for ms in project_map.values():
            result.extend(ms)
        return result

    def get_latest_measurement(self, project_id: str, metric_name: str) -> MetricMeasurement | None:
        measurements = self.get_measurements(project_id, metric_name)
        return measurements[-1] if measurements else None

    def generate_report(self, project_id: str, archetype: Archetype) -> QualityReport:
        profile = self._profiles.get(archetype)
        definitions = profile.metrics if profile else []

        report_metrics: list[dict[str, Any]] = []
        weighted_sum = 0.0
        total_weight = 0.0

        for d in definitions:
            latest = self.get_latest_measurement(project_id, d.name)
            if latest is None:
                report_metrics.append({"definition": d, "measurement": None, "status": "not-measured"})
                continue
            passed = _evaluate_pass_fail(latest.value, d.target, d.direction)
            report_metrics.append({"definition": d, "measurement": latest, "status": "passed" if passed else "failed"})
            score = _normalize_score(latest.value, d.target, d.direction)
            weighted_sum += score * d.weight
            total_weight += d.weight

        overall = weighted_sum / total_weight if total_weight > 0 else 0.0
        passed_count = sum(1 for m in report_metrics if m["status"] == "passed")
        failed_count = sum(1 for m in report_metrics if m["status"] == "failed")
        not_measured = sum(1 for m in report_metrics if m["status"] == "not-measured")

        return QualityReport(
            project_id=project_id,
            archetype=archetype,
            generated_at=time.time(),
            overall_score=overall,
            passed=overall >= MINIMUM_PASS_SCORE,
            metrics=report_metrics,
            summary=_build_summary(archetype, overall, passed_count, failed_count, not_measured, len(definitions)),
        )

    def clear_measurements(self, project_id: str) -> None:
        self._measurements.pop(project_id, None)

    def reset(self) -> None:
        self._measurements.clear()
        self._profiles = build_default_profiles()
