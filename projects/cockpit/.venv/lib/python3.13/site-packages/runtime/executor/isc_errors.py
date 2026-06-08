"""ISC error system -- migrated from agentmesh engine/isc/errors.ts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Shared types (ported inline from types.ts to avoid circular deps)
# ---------------------------------------------------------------------------

@dataclass
class SourceLocation:
    start: int = 0
    end: int = 0
    start_line: int | None = None
    start_column: int | None = None
    end_line: int | None = None
    end_column: int | None = None


@dataclass
class Diagnostic:
    severity: str  # 'error' | 'warning' | 'info'
    code: str
    message: str
    location: SourceLocation | None = None
    suggestion: str | None = None


# ---------------------------------------------------------------------------
# Base error
# ---------------------------------------------------------------------------

class ISCError(Exception):
    """Base ISC error with code, location, and suggestion metadata."""

    def __init__(
        self,
        code: str,
        message: str,
        location: SourceLocation | None = None,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.location = location
        self.suggestion = suggestion

    def to_diagnostic(self) -> Diagnostic:
        return Diagnostic(
            severity="error",
            code=self.code,
            message=str(self.args[0]) if self.args else "",
            location=self.location,
            suggestion=self.suggestion,
        )


# ---------------------------------------------------------------------------
# Lexer errors
# ---------------------------------------------------------------------------

class ISCLexerError(ISCError):
    def __init__(
        self, message: str, position: int, suggestion: str | None = None
    ) -> None:
        super().__init__(
            "ISC_LEXER_ERROR",
            message,
            SourceLocation(start=position, end=position + 1),
            suggestion,
        )


class ISCInvalidCharacterError(ISCLexerError):
    def __init__(self, char: str, position: int) -> None:
        super().__init__(
            f"Invalid character '{char}' at position {position}",
            position,
            "Remove the invalid character or check for typos in the expression.",
        )


class ISCUnterminatedStringError(ISCLexerError):
    def __init__(self, position: int, quote: str) -> None:
        super().__init__(
            f"Unterminated string literal starting at position {position}",
            position,
            f"Add a closing '{quote}' to complete the string.",
        )


class ISCInvalidNumberError(ISCLexerError):
    def __init__(self, value: str, position: int) -> None:
        super().__init__(
            f"Invalid number format '{value}' at position {position}",
            position,
            "Check the number format and remove any invalid characters.",
        )


# ---------------------------------------------------------------------------
# Parser errors
# ---------------------------------------------------------------------------

class ISCParserError(ISCError):
    def __init__(
        self,
        message: str,
        location: SourceLocation,
        suggestion: str | None = None,
    ) -> None:
        super().__init__("ISC_PARSER_ERROR", message, location, suggestion)


class ISCMismatchedParenthesisError(ISCParserError):
    def __init__(self, expected: str, position: int) -> None:
        if expected in ("(", "["):
            message = f"Missing opening '{expected}'"
        else:
            message = f"Missing closing '{expected}'"
        super().__init__(
            message,
            SourceLocation(start=position, end=position + 1),
            f"Add the missing '{expected}' to balance the expression.",
        )


class ISCUnexpectedTokenError(ISCParserError):
    def __init__(self, expected: str, got: str, position: int) -> None:
        super().__init__(
            f"Expected {expected}, but got '{got}'",
            SourceLocation(start=position, end=position + 1),
            "Check the expression syntax and ensure correct operator usage.",
        )


class ISCEmptyExpressionError(ISCParserError):
    def __init__(self) -> None:
        super().__init__(
            "Empty expression",
            SourceLocation(start=0, end=0),
            "Provide a valid expression to evaluate.",
        )


class ISCInvalidOperatorError(ISCParserError):
    def __init__(self, operator: str, position: int) -> None:
        super().__init__(
            f"Invalid use of operator '{operator}'",
            SourceLocation(start=position, end=position + len(operator)),
            "Check that the operator has valid operands on both sides.",
        )


# ---------------------------------------------------------------------------
# Evaluation errors
# ---------------------------------------------------------------------------

class ISCEvaluationError(ISCError):
    def __init__(
        self,
        message: str,
        location: SourceLocation | None = None,
        suggestion: str | None = None,
    ) -> None:
        super().__init__("ISC_EVALUATION_ERROR", message, location, suggestion)


class ISCUndefinedVariableError(ISCEvaluationError):
    def __init__(self, variable_name: str, location: SourceLocation | None = None) -> None:
        super().__init__(
            f"Undefined variable '{variable_name}'",
            location,
            f"Define '{variable_name}' in the evaluation context or check for typos.",
        )


class ISCTypeError(ISCEvaluationError):
    def __init__(
        self,
        operation: str,
        expected_type: str,
        actual_value: Any,
        location: SourceLocation | None = None,
    ) -> None:
        actual_type = "null" if actual_value is None else type(actual_value).__name__
        super().__init__(
            f"Type error in {operation}: expected {expected_type}, got {actual_type}",
            location,
            f"Ensure the operand is of type {expected_type}.",
        )


class ISCDivisionByZeroError(ISCEvaluationError):
    def __init__(self, location: SourceLocation | None = None) -> None:
        super().__init__(
            "Division by zero",
            location,
            "Check the divisor to ensure it is not zero.",
        )


class ISCPropertyAccessError(ISCEvaluationError):
    def __init__(
        self, obj: Any, property_name: str, location: SourceLocation | None = None
    ) -> None:
        obj_type = "null" if obj is None else type(obj).__name__
        super().__init__(
            f"Cannot access property '{property_name}' on {obj_type}",
            location,
            f"Ensure the object has the property '{property_name}' or check for null/undefined values.",
        )


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

class ISCValidationError(ISCError):
    def __init__(
        self,
        message: str,
        path: str | None = None,
        location: SourceLocation | None = None,
    ) -> None:
        super().__init__("ISC_VALIDATION_ERROR", message, location)
        self.path = path


class ISCInvalidExpressionError(ISCValidationError):
    def __init__(self, expression: str, reason: str) -> None:
        super().__init__(
            f"Invalid expression '{expression}': {reason}",
            location=SourceLocation(start=0, end=len(expression)),
        )


class ISCCircularDependencyError(ISCValidationError):
    def __init__(self, path: list[str]) -> None:
        super().__init__(
            f"Circular dependency detected: {' -> '.join(path)}",
            path=" -> ".join(path),
        )


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def create_diagnostic(
    severity: str,
    code: str,
    message: str,
    location: SourceLocation | None = None,
    suggestion: str | None = None,
) -> Diagnostic:
    return Diagnostic(severity, code, message, location, suggestion)


def format_location(location: SourceLocation) -> str:
    if location.start_line is not None:
        return f"line {location.start_line}, column {location.start_column}"
    return f"position {location.start}"


def format_error(error: ISCError, source: str | None = None) -> str:
    parts = [f"[{error.code}] {error.args[0] if error.args else ''}"]
    if error.location:
        parts.append(f" at {format_location(error.location)}")
        if source:
            segment = source[error.location.start : error.location.end]
            if segment:
                parts.append(f"\n  {segment}")
    if error.suggestion:
        parts.append(f"\n  Suggestion: {error.suggestion}")
    return "".join(parts)


def is_isc_error(error: Any) -> bool:
    return isinstance(error, ISCError)


def errors_to_diagnostics(errors: list[object]) -> list[Diagnostic]:
    return [e.to_diagnostic() for e in errors if isinstance(e, ISCError)]
