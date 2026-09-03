"""Pure, additive validation for the optional Portfolio v2 Ledger contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PortfolioValidationResult:
    """Typed Portfolio v2 findings; validation never mutates its input."""

    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_portfolio(ledger: dict[str, Any], *, strict: bool) -> PortfolioValidationResult:
    """Validate the optional Portfolio v2 surface without filesystem writes.

    A legacy Ledger has no portfolio top-level entities yet, so compatibility
    mode accepts it unchanged. Strict enforcement is intentionally deferred to
    the separately authorized `meta.total_bets` repair and W0 self-binding.
    """
    if not isinstance(ledger, dict):
        return PortfolioValidationResult(errors=("PORTFOLIO_SCHEMA_INVALID: ledger must be a mapping",))
    warnings: list[str] = []
    objectives = ledger.get("objectives")
    errors: list[str] = []
    meta = ledger.get("meta")
    bets = ledger.get("bets")
    if isinstance(meta, dict) and isinstance(meta.get("total_bets"), int) and isinstance(bets, list):
        declared = meta["total_bets"]
        actual = len(bets)
        if declared != actual:
            finding = f"META_TOTAL_BETS_DRIFT: declared={declared} actual={actual}"
            if strict:
                errors.append(finding)
            else:
                warnings.append(finding)

    if objectives is None:
        return PortfolioValidationResult(errors=tuple(errors), warnings=tuple(warnings))
    if not isinstance(objectives, list):
        return PortfolioValidationResult(
            errors=tuple([*errors, "PORTFOLIO_SCHEMA_INVALID: objectives must be a list"]),
            warnings=tuple(warnings),
        )

    seen: set[str] = set()
    key_result_ids: set[str] = set()
    for objective in objectives:
        if not isinstance(objective, dict) or not isinstance(objective.get("id"), str):
            errors.append("OBJECTIVE_ID_INVALID")
            continue
        objective_id = objective["id"]
        if objective_id in seen:
            errors.append(f"OBJECTIVE_ID_DUPLICATE: {objective_id}")
        seen.add(objective_id)
        key_results = objective.get("key_results", [])
        if not isinstance(key_results, list):
            errors.append(f"KEY_RESULTS_INVALID: {objective_id}")
            continue
        for key_result in key_results:
            if not isinstance(key_result, dict) or not isinstance(key_result.get("id"), str):
                errors.append(f"KR_ID_INVALID: {objective_id}")
                continue
            key_result_ids.add(key_result["id"])

    contract_enabled = "vision" in ledger
    bets = ledger.get("bets", [])
    if not isinstance(bets, list):
        errors.append("PORTFOLIO_SCHEMA_INVALID: bets must be a list")
    else:
        for bet in bets:
            if not isinstance(bet, dict):
                errors.append("BET_INVALID")
                continue
            binding = bet.get("portfolio_binding")
            if not isinstance(binding, dict):
                continue
            bet_id = str(bet.get("id") or "<unknown>")
            if contract_enabled and bet.get("status") not in {"done", "failed"}:
                for field in ("campaign_ref", "objective_refs", "kr_refs"):
                    if field not in binding:
                        errors.append(f"PORTFOLIO_BINDING_FIELD_MISSING: {bet_id} -> {field}")
            kr_refs = binding.get("kr_refs", [])
            if not isinstance(kr_refs, list):
                errors.append(f"KR_REFS_INVALID: {bet_id}")
                continue
            for kr_ref in kr_refs:
                if not isinstance(kr_ref, str) or kr_ref not in key_result_ids:
                    errors.append(f"KR_REF_MISSING: {bet_id} -> {kr_ref}")
    return PortfolioValidationResult(errors=tuple(errors), warnings=tuple(warnings))
