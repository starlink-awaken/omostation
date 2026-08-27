"""Eidos integration — data validation via eidos KnowledgeCard schemas.

All connector output is validated against eidos KnowledgeCard/Fact/OntologyNode
schemas before being returned to callers.
"""

from __future__ import annotations

from typing import Any


class EidosAdapter:
    """Validate connector data against eidos schemas.

    Uses eidos Validator when available; skips validation when not installed.
    Validation is non-blocking: failed items are logged but not dropped.
    Registry and validator are cached after first use.
    """

    def __init__(self) -> None:
        self._eidos_available = self._check_eidos()
        self._registry = None
        self._validator = None

    def _check_eidos(self) -> bool:
        try:
            import eidos

            return True
        except ImportError:
            return False

    def _ensure_validator(self) -> Any:
        """Lazy-init and cache eidos registry + validator."""
        if self._validator is None and self._eidos_available:
            from eidos.core.validator import Validator
            from eidos.registry import create_registry

            self._registry = create_registry()
            self._validator = Validator(self._registry)
        return self._validator

    def _validate(self, data: dict[str, Any], schema_type: str, strict: bool = False) -> dict[str, Any]:
        """Validate data against an eidos schema type.

        Returns {"is_valid": bool, "errors": list[str]}.
        When eidos is not installed, returns is_valid=True with a warning.
        """
        validator = self._ensure_validator()
        if validator is None:
            return {"is_valid": True, "errors": ["eidos not installed — validation skipped"]}

        try:
            result = validator.validate_object(schema_type, data, strict=strict)
            return {
                "is_valid": result.is_valid,
                "errors": [e.message for e in result.errors],
            }
        except Exception as e:
            return {"is_valid": False, "errors": [f"Validation error: {e}"]}

    def validate_knowledge_card(self, data: dict[str, Any], strict: bool = False) -> dict[str, Any]:
        """Validate data as an eidos KnowledgeCard."""
        return self._validate(data, "KnowledgeCard", strict)

    def validate_fact(self, data: dict[str, Any], strict: bool = False) -> dict[str, Any]:
        """Validate data as an eidos Fact."""
        return self._validate(data, "Fact", strict)

    def validate_ontology_node(self, data: dict[str, Any], strict: bool = False) -> dict[str, Any]:
        """Validate data as an eidos OntologyNode."""
        return self._validate(data, "OntologyNode", strict)

    def is_eidos_available(self) -> bool:
        return self._eidos_available

    def status(self) -> dict[str, Any]:
        """Report adapter status."""
        return {
            "eidos_available": self._eidos_available,
        }
