"""ISC expression evaluator -- migrated from agentmesh engine/isc/evaluator.ts."""

from __future__ import annotations

from typing import Any

from .isc_errors import (
    ISCEvaluationError,
    ISCPropertyAccessError,
    ISCTypeError,
    ISCUndefinedVariableError,
)

# ---------------------------------------------------------------------------
# AST types (ported inline)
# ---------------------------------------------------------------------------

type ISCNode = (
    dict[str, Any]  # duck-typed AST node with "type" key
)


# ---------------------------------------------------------------------------
# Type conversion helpers
# ---------------------------------------------------------------------------

def _to_number(value: Any) -> int | float:
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            pass
    if isinstance(value, bool):
        return 1 if value else 0
    raise ISCTypeError("number conversion", "number", value)


def _to_string(value: Any) -> str:
    if value is None:
        return "null"
    return str(value)


def _to_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        lower = value.lower().strip()
        return lower in ("true", "yes", "1") or bool(value)
    return False


def _get_value_type(value: Any) -> str:
    if value is None:
        return "null"
    t = type(value).__name__
    if t in ("str", "int", "float", "bool"):
        return t
    return "object"


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class ISCEvaluator:
    """Evaluates ISC expression ASTs against a variable context."""

    def evaluate(self, expr: ISCNode, context: dict[str, Any] | None = None) -> bool | int | float | str:
        """Evaluate expression and return primitive result."""
        ctx = context or {}
        try:
            return self._eval(expr, ctx)
        except ISCEvaluationError:
            raise
        except Exception as exc:
            raise ISCEvaluationError(
                f"Unexpected error during evaluation: {exc}"
            ) from exc

    def evaluate_to_boolean(self, expr: ISCNode, context: dict[str, Any] | None = None) -> bool:
        return _to_boolean(self.evaluate(expr, context))

    def evaluate_detailed(self, expr: ISCNode, context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = context or {}
        try:
            value = self.evaluate(expr, ctx)
            return {"success": True, "value": value}
        except ISCEvaluationError as exc:
            return {"success": False, "error": str(exc)}

    # Internal dispatch --------------------------------------------------

    def _eval(self, expr: ISCNode, context: dict[str, Any]) -> Any:
        node_type = expr.get("type", "")
        if node_type == "Identifier":
            return self._eval_identifier(expr, context)
        if node_type == "Literal":
            return expr["value"]
        if node_type == "Comparison":
            return self._eval_comparison(expr, context)
        if node_type == "Logical":
            return self._eval_logical(expr, context)
        if node_type == "Unary":
            return self._eval_unary(expr, context)
        if node_type == "Member":
            return self._eval_member(expr, context)
        raise ISCEvaluationError(f"Unknown expression type: {node_type}")

    def _eval_identifier(self, expr: ISCNode, context: dict[str, Any]) -> Any:
        name: str = expr["name"]
        if name not in context:
            raise ISCUndefinedVariableError(name)
        return context[name]

    def _eval_comparison(self, expr: ISCNode, context: dict[str, Any]) -> bool:
        left = self._eval(expr["left"], context)
        right = self._eval(expr["right"], context)
        op: str = expr["operator"]

        # Normalize percentage comparisons
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            if left < 1 and right > 1:
                right = right / 100
            elif right < 1 and left > 1:
                left = left / 100

        if op == "==":
            return self._compare_equal(left, right)
        if op == "!=":
            return not self._compare_equal(left, right)
        if op == ">":
            return self._compare_greater(left, right)
        if op == ">=":
            return self._compare_greater(left, right) or self._compare_equal(left, right)
        if op == "<":
            return self._compare_less(left, right)
        if op == "<=":
            return self._compare_less(left, right) or self._compare_equal(left, right)
        raise ISCEvaluationError(f"Unknown comparison operator: {op}")

    def _eval_logical(self, expr: ISCNode, context: dict[str, Any]) -> bool:
        left = _to_boolean(self._eval(expr["left"], context))
        op: str = expr["operator"]
        if op == "&&" and not left:
            return False
        if op == "||" and left:
            return True
        right = _to_boolean(self._eval(expr["right"], context))
        return (left and right) if op == "&&" else (left or right)

    def _eval_unary(self, expr: ISCNode, context: dict[str, Any]) -> bool:
        arg = _to_boolean(self._eval(expr["argument"], context))
        op: str = expr["operator"]
        if op == "!":
            return not arg
        raise ISCEvaluationError(f"Unknown unary operator: {op}")

    def _eval_member(self, expr: ISCNode, context: dict[str, Any]) -> Any:
        obj = self._eval(expr["object"], context)
        if obj is None or not isinstance(obj, dict):
            raise ISCPropertyAccessError(obj, expr["property"])
        prop: str = expr["property"]
        if prop not in obj:
            obj_name = expr["object"].get("name", "...") if expr["object"].get("type") == "Identifier" else "..."
            raise ISCUndefinedVariableError(f"{obj_name}.{prop}")
        return obj[prop]

    # Comparison helpers -------------------------------------------------

    @staticmethod
    def _compare_equal(left: Any, right: Any) -> bool:
        if left is right or left == right:
            return True
        lt = _get_value_type(left)
        rt = _get_value_type(right)
        if (lt in ("int", "float") and rt == "str") or (lt == "str" and rt in ("int", "float")):
            try:
                return _to_number(left) == _to_number(right)
            except ISCTypeError:
                return False
        if lt == "bool" or rt == "bool":
            return _to_boolean(left) == _to_boolean(right)
        return False

    @staticmethod
    def _compare_greater(left: Any, right: Any) -> bool:
        return _to_number(left) > _to_number(right)

    @staticmethod
    def _compare_less(left: Any, right: Any) -> bool:
        return _to_number(left) < _to_number(right)


# ---------------------------------------------------------------------------
# Batch evaluation
# ---------------------------------------------------------------------------

def evaluate_batch(
    expressions: list[ISCNode],
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    evaluator = ISCEvaluator()
    return [evaluator.evaluate_detailed(expr, context) for expr in expressions]


def evaluate_all_or_nothing(
    expressions: list[ISCNode],
    context: dict[str, Any],
) -> dict[str, Any]:
    evaluator = ISCEvaluator()
    for expr in expressions:
        result = evaluator.evaluate_detailed(expr, context)
        if not result["success"]:
            return result
    return {"success": True}
