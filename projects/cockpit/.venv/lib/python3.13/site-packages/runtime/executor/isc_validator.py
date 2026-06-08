"""ISC validator -- migrated from agentmesh engine/isc/validator.ts."""

from __future__ import annotations

import re
import time
from typing import Any

from .isc_parser import ISCParser

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

class ValidationError:
    def __init__(
        self,
        path: str,
        message: str,
        code: str | None = None,
        expected: str | None = None,
        actual: Any = None,
    ) -> None:
        self.path = path
        self.message = message
        self.code = code
        self.expected = expected
        self.actual = actual


class ValidationResult:
    def __init__(
        self,
        valid: bool,
        errors: list[ValidationError] | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        self.valid = valid
        self.errors = errors or []
        self.warnings = warnings or []


class ValidationReport:
    def __init__(
        self,
        gate_name: str = "",
        is_valid: bool = False,
        criteria_count: int = 0,
        mandatory_count: int = 0,
        optional_count: int = 0,
        errors: list[ValidationError] | None = None,
        warnings: list[str] | None = None,
        variables: list[str] | None = None,
        validated_at: int = 0,
    ) -> None:
        self.gate_name = gate_name
        self.is_valid = is_valid
        self.criteria_count = criteria_count
        self.mandatory_count = mandatory_count
        self.optional_count = optional_count
        self.errors = errors or []
        self.warnings = warnings or []
        self.variables = variables or []
        self.validated_at = validated_at


# ---------------------------------------------------------------------------
# Conversion rules (natural language -> ISC)
# ---------------------------------------------------------------------------

class _ConversionRule:
    def __init__(self, pattern: str, template_fn) -> None:
        self.pattern = re.compile(pattern)
        self.template_fn = template_fn


_CONVERSION_RULES: list[_ConversionRule] = [
    _ConversionRule(
        r"(?:Test\s+)?coverage\s*(>=|<=|>|<|==|!=)\s*(\d+)%",
        lambda m: f"coverage {m.group(1)} {m.group(2)}%",
    ),
    _ConversionRule(
        r"(?:Code\s+)?duplication\s*(>=|<=|>|<|==|!=)\s*(\d+)%",
        lambda m: f"duplication {m.group(1)} {m.group(2)}%",
    ),
    _ConversionRule(
        r"P95\s+latency\s*(<=|<)\s*(\d+)ms?",
        lambda m: f"p95_latency {m.group(1)} {m.group(2)}",
    ),
    _ConversionRule(
        r"Cyclomatic\s+complexity\s*(<=|<)\s*(\d+)",
        lambda m: f"complexity {m.group(1)} {m.group(2)}",
    ),
    _ConversionRule(
        r"No\s+(?:lint\s+)?errors",
        lambda _: "errors == 0",
    ),
    _ConversionRule(
        r"no\s+(\w+(?:\s+\w+)*)",
        lambda m: f"{m.group(1).lower().replace(' ', '_')} == 0",
    ),
    _ConversionRule(
        r"all\s+(\w+(?:\s+\w+)*)\s+(\w+(?:\s+\w+)*)",
        lambda m: f"{m.group(1).lower().replace(' ', '_')} == true",
    ),
    _ConversionRule(
        r"maximum\s+(\w+(?:\s+\w+)*)\s*(<=|<)\s*(\d+)",
        lambda m: f"{m.group(1).lower().replace(' ', '_')} {m.group(2)} {m.group(3)}",
    ),
    _ConversionRule(
        r"minimum\s+(\w+(?:\s+\w+)*)\s*(>=|>)\s*(\d+)",
        lambda m: f"{m.group(1).lower().replace(' ', '_')} {m.group(2)} {m.group(3)}",
    ),
    _ConversionRule(
        r".+",
        lambda m: m.group(0).lower().replace(" ", "_"),
    ),
]


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class ISCValidator:
    """Validates ISC expressions and quality gate configurations."""

    def __init__(self) -> None:
        self._parser = ISCParser()

    # Expression validation ------------------------------------------------

    def validate_expression(self, expression: str) -> ValidationResult:
        errors: list[ValidationError] = []
        warnings: list[str] = []
        try:
            ast = self._parser.parse(expression)
            if not ast:
                errors.append(
                    ValidationError("$", "Expression parsed to empty AST", "EMPTY_AST")
                )
                return ValidationResult(False, errors, warnings)
            variables = self.extract_variables(expression)
            if not variables:
                warnings.append(
                    "Expression contains no variables - this may be a constant value"
                )
            return ValidationResult(True, [], warnings)
        except Exception as exc:
            errors.append(
                ValidationError("$", str(exc), "PARSE_ERROR")
            )
            return ValidationResult(False, errors, warnings)

    def extract_variables(self, expression: str) -> list[str]:
        try:
            ast = self._parser.parse(expression)
            return self._extract_vars_from_ast(ast)
        except Exception:
            return []

    def _extract_vars_from_ast(self, node: dict[str, Any]) -> list[str]:
        vars_set: set[str] = set()

        def traverse(n: dict[str, Any]) -> None:
            t = n.get("type", "")
            if t == "Identifier":
                vars_set.add(n["name"])
            elif t == "Member":
                obj_vars = _extract_raw(n.get("object", {}))
                if obj_vars:
                    vars_set.add(f"{obj_vars[0]}.{n['property']}")
            elif t in ("Comparison", "Logical", "Unary"):
                if "left" in n:
                    traverse(n["left"])
                if "right" in n:
                    traverse(n["right"])
                if "argument" in n:
                    traverse(n["argument"])

        traverse(node)
        return list(vars_set)

    def check_undefined_variables(
        self, criterion: dict[str, Any]
    ) -> list[str]:
        actual_vars = self.extract_variables(criterion.get("expression", ""))
        expected_vars = criterion.get("expected_variables", [])
        return [v for v in actual_vars if v not in expected_vars]

    def validate_variables(self, criterion: dict[str, Any]) -> ValidationResult:
        errors: list[ValidationError] = []
        warnings: list[str] = []
        actual_vars = self.extract_variables(criterion.get("expression", ""))
        expected_vars = criterion.get("expected_variables", [])
        for var_name in actual_vars:
            if var_name not in expected_vars:
                warnings.append(
                    f"Variable '{var_name}' is not in expected_variables list"
                )
        for var_name in expected_vars:
            if var_name not in actual_vars:
                warnings.append(
                    f"Expected variable '{var_name}' is not used in expression"
                )
        return ValidationResult(len(errors) == 0, errors, warnings)

    # Quality gate validation ---------------------------------------------

    def validate_quality_gate(self, gate: dict[str, Any]) -> ValidationResult:
        errors: list[ValidationError] = []
        warnings: list[str] = []

        name = gate.get("name")
        if not name or not isinstance(name, str):
            errors.append(
                ValidationError("name", "Quality gate must have a valid name", "MISSING_NAME")
            )

        valid_phases = ["init", "research", "decision", "execution", "feedback", "delivery"]
        phase = gate.get("phase")
        if not phase or phase not in valid_phases:
            errors.append(
                ValidationError(
                    "phase",
                    f"Invalid phase '{phase}'. Must be one of: {', '.join(valid_phases)}",
                    "INVALID_PHASE",
                    ", ".join(valid_phases),
                )
            )

        criteria = gate.get("criteria")
        if not isinstance(criteria, list):
            errors.append(
                ValidationError("criteria", "Criteria must be an array", "INVALID_CRITERIA_TYPE")
            )
            return ValidationResult(False, errors, warnings)

        if not criteria:
            warnings.append("Quality gate has no criteria")

        for i, crit in enumerate(criteria):
            result = self.validate_criterion(crit)
            for e in result.errors:
                e.path = f"criteria[{i}].{e.path}"
                errors.append(e)
            warnings.extend(result.warnings)

        return ValidationResult(len(errors) == 0, errors, warnings)

    def validate_criterion(self, criterion: dict[str, Any] | str) -> ValidationResult:
        errors: list[ValidationError] = []
        warnings: list[str] = []

        if isinstance(criterion, str):
            warnings.append(
                f'legacy natural language format detected: "{criterion}". '
                "Consider migrating to ISC format."
            )
            return ValidationResult(True, [], warnings)

        if not criterion.get("id"):
            errors.append(ValidationError("id", "Criterion must have an id", "MISSING_ID"))
        if not criterion.get("name"):
            errors.append(ValidationError("name", "Criterion must have a name", "MISSING_NAME"))
        if not criterion.get("expression"):
            errors.append(
                ValidationError("expression", "Criterion must have an expression", "MISSING_EXPRESSION")
            )
        else:
            expr_result = self.validate_expression(criterion["expression"])
            if not expr_result.valid:
                for e in expr_result.errors:
                    e.path = f"expression.{e.path}"
                    errors.append(e)
            warnings.extend(expr_result.warnings)
        if not isinstance(criterion.get("mandatory"), bool):
            errors.append(
                ValidationError(
                    "mandatory",
                    "Criterion must specify mandatory as boolean",
                    "MISSING_MANDATORY",
                )
            )
        return ValidationResult(len(errors) == 0, errors, warnings)

    # Legacy migration ----------------------------------------------------

    def convert_legacy_expression(self, natural: str) -> str:
        normalized = natural.strip()
        for rule in _CONVERSION_RULES:
            m = rule.pattern.match(normalized)
            if m:
                return rule.template_fn(m)
        return normalized

    def migrate_legacy_criteria(
        self, legacy_criteria: list[str], base_id: str | None = None
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for idx, crit in enumerate(legacy_criteria):
            expr = self.convert_legacy_expression(crit)
            result.append({
                "id": f"{base_id}-{idx}" if base_id else f"criterion-{idx}",
                "name": crit,
                "expression": expr,
                "mandatory": True,
            })
        return result

    # Report generation ---------------------------------------------------

    def generate_validation_report(self, gate: dict[str, Any]) -> ValidationReport:
        validation = self.validate_quality_gate(gate)
        all_vars: set[str] = set()
        for crit in gate.get("criteria", []):
            if isinstance(crit, dict) and crit.get("expression"):
                for v in self.extract_variables(crit["expression"]):
                    all_vars.add(v)

        mandatory = sum(
            1 for c in gate.get("criteria", [])
            if isinstance(c, dict) and c.get("mandatory")
        )
        optional = sum(
            1 for c in gate.get("criteria", [])
            if isinstance(c, dict) and not c.get("mandatory")
        )
        return ValidationReport(
            gate_name=gate.get("name", ""),
            is_valid=validation.valid,
            criteria_count=len(gate.get("criteria", [])),
            mandatory_count=mandatory,
            optional_count=optional,
            errors=validation.errors,
            warnings=validation.warnings,
            variables=sorted(all_vars),
            validated_at=int(time.time() * 1000),
        )

    def generate_validation_summary(self, report: ValidationReport) -> str:
        lines = [
            f'# Validation Report for "{report.gate_name}"',
            "",
            f"Status: {'VALID' if report.is_valid else 'INVALID'}",
            f"Criteria: {report.criteria_count} total "
            f"({report.mandatory_count} mandatory, {report.optional_count} optional)",
        ]
        if report.variables:
            lines.append(f"Variables: {', '.join(report.variables)}")
        if report.errors:
            lines.extend(["", "## Errors:"])
            for err in report.errors:
                lines.append(f"  - [{err.path}] {err.message}")
        if report.warnings:
            lines.extend(["", "## Warnings:"])
            for w in report.warnings:
                lines.append(f"  - {w}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_raw(node: dict[str, Any]) -> list[str]:
    if node.get("type") == "Identifier":
        return [node["name"]]
    return []


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_isc_validator() -> ISCValidator:
    return ISCValidator()
