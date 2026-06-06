from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    SYX001_UNEXPECTED_TOKEN = "SYX001"  # noqa: S105
    SYX002_MISSING_TOKEN = "SYX002"  # noqa: S105
    SYX003_INVALID_SYNTAX = "SYX003"
    LEX101_UNCLOSED_STRING = "LEX101"
    LEX102_INVALID_ESCAPE = "LEX102"
    LEX103_INVALID_NUMBER = "LEX103"
    LEX104_UNSUPPORTED_CHARACTER = "LEX104"
    TYP201_TYPE_MISMATCH = "TYP201"
    TYP202_UNKNOWN_TYPE = "TYP202"
    SEM301_UNDEFINED_SYMBOL = "SEM301"
    SEM302_DUPLICATE_DECLARATION = "SEM302"
    SEM303_CIRCULAR_DEPENDENCY = "SEM303"
    COM401_CODE_GENERATION_FAILED = "COM401"
    RUN501_EXECUTION_FAILED = "RUN501"
    RUN502_TIMEOUT = "RUN502"
    RUN506_STACK_DEPTH_EXCEEDED = "RUN506"
    IO701_FILE_NOT_FOUND = "IO701"


class ErrorSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class SourceLocation:
    file: str = "<unknown>"
    line: int = 1
    column: int = 1
    length: int | None = None
    snippet: str | None = None


@dataclass
class FixSuggestion:
    message: str = ""
    action: str = "replace"
    location: SourceLocation | None = None
    replacement: str = ""
    priority: int = 5


class DSLError(Exception):
    def __init__(
        self,
        code: ErrorCode = ErrorCode.RUN501_EXECUTION_FAILED,
        message: str = "",
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        loc: SourceLocation | None = None,
        context: dict[str, Any] | None = None,
        caused_by: DSLError | None = None,
    ):
        self.code = code
        self.severity = severity
        self.loc = loc or SourceLocation()
        self.context = context or {}
        self.caused_by = caused_by
        self.suggestions: list[FixSuggestion] = []
        super().__init__(message)

    def add_suggestion(self, suggestion: FixSuggestion) -> DSLError:
        self.suggestions.append(suggestion)
        return self

    def is_error(self) -> bool:
        return self.severity == ErrorSeverity.ERROR

    def is_warning(self) -> bool:
        return self.severity == ErrorSeverity.WARNING

    def to_short_string(self) -> str:
        return f"[{self.code}] {self.args[0] if self.args else ''} at {self.loc.file}:{self.loc.line}:{self.loc.column}"


class SyntaxError_(DSLError):  # noqa: N801, N818
    def __init__(
        self,
        code: ErrorCode = ErrorCode.SYX003_INVALID_SYNTAX,
        message: str = "",
        loc: SourceLocation | None = None,
        context: dict[str, Any] | None = None,
        caused_by: DSLError | None = None,
    ):
        super().__init__(code, message, ErrorSeverity.ERROR, loc, context, caused_by)

    @staticmethod
    def unexpected_token(
        unexpected: str, expected: list[str], loc: SourceLocation
    ) -> SyntaxError_:
        msg = f"Unexpected token '{unexpected}', expected {' or '.join(expected)}"
        err = SyntaxError_(ErrorCode.SYX001_UNEXPECTED_TOKEN, msg, ErrorSeverity.ERROR, loc)  # type: ignore[arg-type]
        err.add_suggestion(
            FixSuggestion(
                message=f"Replace '{unexpected}' with one of: {' or '.join(expected)}",
                action="replace",
                location=loc,
                priority=10,
            )
        )
        return err

    @staticmethod
    def missing_token(missing: str, loc: SourceLocation) -> SyntaxError_:
        err = SyntaxError_(
            ErrorCode.SYX002_MISSING_TOKEN, f"Missing '{missing}'", loc
        )
        err.add_suggestion(
            FixSuggestion(
                message=f"Add '{missing}' at this position",
                action="insert",
                location=loc,
                priority=10,
            )
        )
        return err


class LexicalError(DSLError):
    @staticmethod
    def unclosed_string(loc: SourceLocation) -> LexicalError:
        err = LexicalError(
            ErrorCode.LEX101_UNCLOSED_STRING,
            "Unclosed string literal",
            ErrorSeverity.ERROR,
            loc,
        )
        err.add_suggestion(
            FixSuggestion(
                message='Add closing quote (" or \')',
                action="insert",
                location=loc,
                priority=10,
            )
        )
        return err

    @staticmethod
    def invalid_escape(escape: str, loc: SourceLocation) -> LexicalError:
        return LexicalError(
            ErrorCode.LEX102_INVALID_ESCAPE,
            f"Invalid escape sequence '{escape}'",
            ErrorSeverity.ERROR,
            loc,
        )


class TypeError_(DSLError):  # noqa: N801, N818
    def __init__(
        self,
        code: ErrorCode = ErrorCode.TYP201_TYPE_MISMATCH,
        message: str = "",
        loc: SourceLocation | None = None,
        expected_type: str = "",
        actual_type: str = "",
        context: dict[str, Any] | None = None,
    ):
        self.expected_type = expected_type
        self.actual_type = actual_type
        super().__init__(code, message, ErrorSeverity.ERROR, loc, context)

    @staticmethod
    def type_mismatch(
        expected: str, actual: str, loc: SourceLocation
    ) -> TypeError_:
        err = TypeError_(
            ErrorCode.TYP201_TYPE_MISMATCH,
            f"Type mismatch: expected '{expected}', got '{actual}'",
            loc,
            expected,
            actual,
        )
        err.add_suggestion(
            FixSuggestion(
                message=f"Change the type to {expected}",
                action="replace",
                location=loc,
                priority=8,
            )
        )
        return err


class SemanticError(DSLError):
    @staticmethod
    def undefined_symbol(symbol: str, loc: SourceLocation) -> SemanticError:
        err = SemanticError(
            ErrorCode.SEM301_UNDEFINED_SYMBOL,
            f"Undefined symbol: '{symbol}'",
            ErrorSeverity.ERROR,
            loc,
        )
        err.add_suggestion(
            FixSuggestion(
                message=f"Declare or import '{symbol}' before use",
                priority=9,
            )
        )
        return err

    @staticmethod
    def duplicate_declaration(
        symbol: str, first_loc: SourceLocation, loc: SourceLocation
    ) -> SemanticError:
        return SemanticError(
            ErrorCode.SEM302_DUPLICATE_DECLARATION,
            f"Duplicate declaration of '{symbol}'. First declared at {first_loc.line}:{first_loc.column}",
            loc,  # type: ignore[arg-type]
            {"first_declaration": first_loc},  # type: ignore[arg-type]
        )

    @staticmethod
    def circular_dependency(cycle: list[str], loc: SourceLocation) -> SemanticError:
        return SemanticError(
            ErrorCode.SEM303_CIRCULAR_DEPENDENCY,
            f"Circular dependency detected: {' -> '.join(cycle)}",
            loc,  # type: ignore[arg-type]
            {"cycle": cycle},  # type: ignore[arg-type]
        )


class RuntimeError_(DSLError):  # noqa: N801, N818
    @staticmethod
    def execution_failed(reason: str, loc: SourceLocation) -> RuntimeError_:
        return RuntimeError_(
            ErrorCode.RUN501_EXECUTION_FAILED,
            f"Execution failed: {reason}",
            ErrorSeverity.ERROR,
            loc,
        )

    @staticmethod
    def stack_depth_exceeded(
        current_depth: int, max_depth: int,
        loc: SourceLocation | None = None,
    ) -> RuntimeError_:
        loc = loc or SourceLocation()
        return RuntimeError_(
            ErrorCode.RUN506_STACK_DEPTH_EXCEEDED,
            f"Stack depth exceeded: {current_depth} >= {max_depth}",
            loc,  # type: ignore[arg-type]
            {"current_depth": current_depth, "max_depth": max_depth},  # type: ignore[arg-type]
        )


class ErrorCollector:
    def __init__(self) -> None:
        self._errors: list[DSLError] = []
        self._warnings: list[DSLError] = []

    def add_error(self, error: DSLError) -> None:
        if error.is_warning():
            self._warnings.append(error)
        else:
            self._errors.append(error)

    def add_errors(self, errors: list[DSLError]) -> None:
        for e in errors:
            self.add_error(e)

    def get_errors(self) -> list[DSLError]:
        return list(self._errors)

    def get_warnings(self) -> list[DSLError]:
        return list(self._warnings)

    def has_errors(self) -> bool:
        return len(self._errors) > 0

    def has_warnings(self) -> bool:
        return len(self._warnings) > 0

    @property
    def error_count(self) -> int:
        return len(self._errors)

    @property
    def warning_count(self) -> int:
        return len(self._warnings)

    def clear(self) -> None:
        self._errors.clear()
        self._warnings.clear()


class ErrorRecoveryManager:
    def __init__(self, max_attempts: int = 10) -> None:
        self._max_attempts = max_attempts
        self._attempts = 0

    def try_recover(self, _error: dict[str, Any]) -> bool:
        if self._attempts >= self._max_attempts:
            return False
        self._attempts += 1
        return False

    def reset(self) -> None:
        self._attempts = 0

    def can_recover(self) -> bool:
        return self._attempts < self._max_attempts


def create_source_location(
    file: str, line: int, column: int, length: int | None = None
) -> SourceLocation:
    return SourceLocation(file=file, line=line, column=column, length=length)


def format_source_location(loc: SourceLocation) -> str:
    return f"{loc.file}:{loc.line}:{loc.column}"
