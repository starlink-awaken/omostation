"""Contract lifecycle management (agentmesh engine contract-manager.ts migration)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

ContractStatus = Literal["draft", "active", "deprecated", "broken"]
ViolationSeverity = Literal["error", "warning"]
ChangeType = Literal["added", "removed", "modified"]
SUPPORTED_TYPES = frozenset({"string", "number", "boolean", "object", "array", "any"})


@dataclass
class ContractField:
    name: str
    type: str
    required: bool
    description: str = ""


@dataclass
class ContractDefinition:
    id: str
    name: str
    version: str
    status: ContractStatus
    provider: str
    consumers: list[str]
    fields: list[ContractField]
    description: str
    created_at: float
    updated_at: float


@dataclass
class ContractViolation:
    field: str; expected: str; actual: str; severity: ViolationSeverity; message: str  # noqa: E702


@dataclass
class ContractValidationResult:
    contract_id: str; valid: bool  # noqa: E702
    errors: list[ContractViolation] = field(default_factory=list)
    warnings: list[ContractViolation] = field(default_factory=list)
    checked_at: float = 0.0


@dataclass
class ContractChange:
    type: ChangeType; field: str; details: str; breaking: bool  # noqa: E702


@dataclass
class ContractChangeRecord:
    contract_id: str; from_version: str; to_version: str  # noqa: E702
    changes: list[ContractChange]; timestamp: float  # noqa: E702


class ContractManager:
    """Interface contract lifecycle — definition, validation, version comparison."""

    def __init__(self) -> None:
        self._contracts: dict[str, ContractDefinition] = {}
        self._change_history: list[ContractChangeRecord] = []

    def define_contract(self, name: str, version: str, provider: str, fields: list[ContractField], description: str = "", consumers: list[str] | None = None) -> ContractDefinition:
        now = time.time()
        c = ContractDefinition(id=str(uuid.uuid4()), name=name, version=version, status="draft", provider=provider, consumers=list(consumers or []), fields=fields, description=description, created_at=now, updated_at=now)
        self._contracts[c.id] = c; return c  # noqa: E702

    def get_contract(self, cid: str) -> ContractDefinition | None:
        return self._contracts.get(cid)

    def list_contracts(self, status: ContractStatus | None = None) -> list[ContractDefinition]:
        return list(self._contracts.values()) if status is None else [c for c in self._contracts.values() if c.status == status]

    def validate_payload(self, cid: str, payload: dict[str, Any]) -> ContractValidationResult:
        c = self._get(cid); errors, warnings = [], []  # noqa: E702
        for f in c.fields:
            v = payload.get(f.name)
            if v is None and f.required:
                errors.append(ContractViolation(field=f.name, expected=f.type, actual="null", severity="error", message=f"Required field '{f.name}' is missing"))
            elif v is not None and f.type != "any":
                actual = type(v).__name__
                if actual == "int": actual = "number"  # noqa: E701
                if actual != f.type:
                    errors.append(ContractViolation(field=f.name, expected=f.type, actual=actual, severity="error", message=f"Expected {f.type} got {actual}"))
        known = {f.name for f in c.fields}
        for k in payload:
            if k not in known and payload[k] is not None:
                warnings.append(ContractViolation(field=k, expected="not defined", actual="unknown", severity="warning", message=f"Unknown field '{k}'"))
        return ContractValidationResult(contract_id=cid, valid=len(errors) == 0, errors=errors, warnings=warnings, checked_at=time.time())

    def compare_versions(self, cid: str, new_fields: list[ContractField]) -> ContractChangeRecord:
        old = self._get(cid); old_map = {f.name: f for f in old.fields}; new_map = {f.name: f for f in new_fields}; changes = []  # noqa: E702
        for name, cf in old_map.items():
            if name not in new_map:
                changes.append(ContractChange(type="removed", field=name, details=f"'{name}' removed", breaking=cf.required))
        for name, nf in new_map.items():
            cf = old_map.get(name)  # type: ignore[assignment]
            if cf is None:
                changes.append(ContractChange(type="added", field=name, details=f"'{name}' added", breaking=nf.required))
            elif cf.type != nf.type or cf.required != nf.required:
                changes.append(ContractChange(type="modified", field=name, details=f"'{name}' changed", breaking=cf.type != nf.type))
        record = ContractChangeRecord(contract_id=cid, from_version=old.version, to_version="", changes=changes, timestamp=time.time())
        self._change_history.append(record); return record  # noqa: E702

    def get_consistency_report(self) -> dict[str, Any]:
        active = sum(1 for c in self._contracts.values() if c.status == "active")
        broken = sum(1 for c in self._contracts.values() if c.status == "broken")
        return {"total": len(self._contracts), "active": active, "broken": broken, "consistency": 100 if active + broken == 0 else round(active / (active + broken) * 100)}

    def _get(self, cid: str) -> ContractDefinition:
        c = self._contracts.get(cid)
        if c is None: raise ValueError(f"Contract not found: {cid}")  # noqa: E701
        return c
