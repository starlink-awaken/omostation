"""Pure, additive validation for the optional Portfolio v2 Ledger contract.

BET-Y1Q4-T1-04 (spec: docs/superpowers/specs/2026-09-03-w0-portfolio-v2-schema-compatibility-design.md)

Contract shape (additive top level):

    meta + vision + objectives + campaigns + milestones + bets

A legacy v1 Ledger has none of the v2 top-level entities (no ``vision`` key),
so every v2 check is skipped and the existing ``bets`` list parses unchanged.
When the v2 surface is present, entity identity, cross-references, metric
shape, enums, timestamps, and boolean policy fields are validated and produce
typed errors/warnings.  Validation is a pure function: it never mutates the
input mapping and performs no filesystem writes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# Spec §7 error contract — typed codes used across the ledger CLI.
PORTFOLIO_SCHEMA_INVALID = "PORTFOLIO_SCHEMA_INVALID"
OBJECTIVE_REF_MISSING = "OBJECTIVE_REF_MISSING"
KR_REF_MISSING = "KR_REF_MISSING"
META_TOTAL_BETS_DRIFT = "META_TOTAL_BETS_DRIFT"

# Spec §3: required v2 fields for a non-terminal v2 BET.
REQUIRED_V2_BINDING_FIELDS = ("campaign_ref", "objective_refs", "kr_refs")

# A valid ISO-8601 date or datetime (subset actually used by the ledger).
_ISO8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}"
    r"(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$"
)


@dataclass(frozen=True)
class PortfolioValidationResult:
    """Typed Portfolio v2 findings; validation never mutates its input."""

    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


def _is_iso8601(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if _ISO8601_RE.fullmatch(value) is None:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _collect_entity_ids(
    entities: Any,
    *,
    kind: str,
    errors: list[str],
) -> set[str]:
    """Validate an entity list's identity and return the set of IDs.

    Missing/invalid/duplicate IDs append typed errors; the returned set holds
    the IDs that were well-formed so references can be checked against it.
    """
    seen: set[str] = set()
    if entities is None:
        return seen
    if not isinstance(entities, list):
        errors.append(f"{PORTFOLIO_SCHEMA_INVALID}: {kind} must be a list")
        return seen
    for index, entity in enumerate(entities):
        if not isinstance(entity, dict) or not isinstance(entity.get("id"), str):
            errors.append(f"{kind.upper()}_ID_INVALID: entry {index}")
            continue
        entity_id = entity["id"]
        if entity_id in seen:
            errors.append(f"{kind.upper()}_ID_DUPLICATE: {entity_id}")
        seen.add(entity_id)
    return seen


def _validate_metric_shapes(
    bet: dict[str, Any],
    *,
    bet_id: str,
    errors: list[str],
) -> None:
    """Validate metric shape for a v2 BET's hypothesis baseline/target."""
    metric = bet.get("hypothesis_metric")
    if metric is None:
        return
    if not isinstance(metric, dict):
        errors.append(f"{PORTFOLIO_SCHEMA_INVALID}: {bet_id} hypothesis_metric must be a mapping")
        return
    for field in ("baseline", "target"):
        value = metric.get(field)
        if value is not None and not isinstance(value, (int, float)):
            errors.append(f"METRIC_SHAPE_INVALID: {bet_id} -> hypothesis_metric.{field} must be numeric")


def _validate_bet_type(bet: dict[str, Any], *, bet_id: str, errors: list[str]) -> None:
    """Validate the bet_type enum (spec §3)."""
    bet_type = bet.get("bet_type")
    if bet_type is None:
        return
    if not isinstance(bet_type, str) or not bet_type.strip():
        errors.append(f"BET_TYPE_INVALID: {bet_id} bet_type must be a non-empty string")


def _validate_policy_bool(bet: dict[str, Any], *, bet_id: str, errors: list[str]) -> None:
    """Validate boolean policy fields on a v2 BET."""
    for field in ("value_indicator_policy", "replacement_policy"):
        value = bet.get(field)
        if value is not None and not isinstance(value, bool):
            errors.append(f"POLICY_BOOLEAN_INVALID: {bet_id} -> {field} must be boolean")


def _validate_timestamp(bet: dict[str, Any], *, bet_id: str, errors: list[str]) -> None:
    """Validate ISO-8601 timestamp fields on a v2 BET."""
    for field in ("effective_at", "review_before"):
        value = bet.get(field)
        if value is not None and not _is_iso8601(value):
            errors.append(f"TIMESTAMP_INVALID: {bet_id} -> {field} must be ISO-8601")


def validate_portfolio(ledger: dict[str, Any], *, strict: bool) -> PortfolioValidationResult:
    """Validate the optional Portfolio v2 surface without filesystem writes.

    A legacy Ledger has no portfolio top-level entities yet, so compatibility
    mode accepts it unchanged.  Strict enforcement is intentionally deferred to
    the separately authorized ``meta.total_bets`` repair and W0 self-binding.
    """
    if not isinstance(ledger, dict):
        return PortfolioValidationResult(errors=("PORTFOLIO_SCHEMA_INVALID: ledger must be a mapping",))
    warnings: list[str] = []
    errors: list[str] = []

    meta = ledger.get("meta")
    bets = ledger.get("bets")
    if isinstance(meta, dict) and isinstance(meta.get("total_bets"), int) and isinstance(bets, list):
        declared = meta["total_bets"]
        actual = len(bets)
        if declared != actual:
            finding = f"{META_TOTAL_BETS_DRIFT}: declared={declared} actual={actual}"
            if strict:
                errors.append(finding)
            else:
                warnings.append(finding)

    # Compatibility gate: a legacy v1 Ledger has no v2 top-level entities.
    contract_enabled = "vision" in ledger
    if not contract_enabled:
        return PortfolioValidationResult(errors=tuple(errors), warnings=tuple(warnings))

    # Vision (single entity) identity.
    vision = ledger.get("vision")
    if not isinstance(vision, dict) or not isinstance(vision.get("id"), str):
        errors.append("VISION_ID_INVALID: vision must be a mapping with an id")
    vision_id = vision.get("id") if isinstance(vision, dict) else None

    # Objectives and their key results.
    objectives = ledger.get("objectives")
    if not isinstance(objectives, list):
        errors.append(f"{PORTFOLIO_SCHEMA_INVALID}: objectives must be a list")
        objectives = []
    objective_ids = _collect_entity_ids(objectives, kind="objective", errors=errors)
    key_result_ids: set[str] = set()
    for objective in objectives:
        if not isinstance(objective, dict) or not isinstance(objective.get("id"), str):
            continue
        objective_id = objective["id"]
        key_results = objective.get("key_results")
        if key_results is None:
            continue
        if not isinstance(key_results, list):
            errors.append(f"KEY_RESULTS_INVALID: {objective_id}")
            continue
        for key_result in key_results:
            if not isinstance(key_result, dict) or not isinstance(key_result.get("id"), str):
                errors.append(f"KR_ID_INVALID: {objective_id} -> entry")
                continue
            key_result_ids.add(key_result["id"])

    # Campaigns and milestones identity + objective cross-references.
    campaigns = ledger.get("campaigns")
    if not isinstance(campaigns, list):
        errors.append(f"{PORTFOLIO_SCHEMA_INVALID}: campaigns must be a list")
        campaigns = []
    campaign_ids = _collect_entity_ids(campaigns, kind="campaign", errors=errors)
    for campaign in campaigns:
        if not isinstance(campaign, dict) or not isinstance(campaign.get("id"), str):
            continue
        campaign_id = campaign["id"]
        refs = campaign.get("objective_refs", [])
        if not isinstance(refs, list):
            errors.append(f"OBJECTIVE_REFS_INVALID: {campaign_id}")
            continue
        for ref in refs:
            if ref not in objective_ids:
                errors.append(f"{OBJECTIVE_REF_MISSING}: {campaign_id} -> {ref}")

    milestones = ledger.get("milestones")
    if not isinstance(milestones, list):
        errors.append(f"{PORTFOLIO_SCHEMA_INVALID}: milestones must be a list")
        milestones = []
    _collect_entity_ids(milestones, kind="milestone", errors=errors)

    # Bets identity + portfolio binding cross-references.
    if not isinstance(bets, list):
        errors.append(f"{PORTFOLIO_SCHEMA_INVALID}: bets must be a list")
        bets = []
    bet_ids = _collect_entity_ids(bets, kind="bet", errors=errors)
    for bet in bets:
        if not isinstance(bet, dict):
            continue
        bet_id = str(bet.get("id") or "<unknown>")
        binding = bet.get("portfolio_binding")
        if not isinstance(binding, dict):
            continue
        schema_state = binding.get("schema_state")
        # Spec §4: only an explicit bootstrap_unenforced declaration is not
        # enforcement evidence.  A binding with no schema_state is treated as a
        # plain v2 bet and is subject to required-field enforcement.
        enforced = schema_state != "bootstrap_unenforced"
        is_terminal = bet.get("status") in {"done", "failed"}
        if enforced and not is_terminal:
            for field in REQUIRED_V2_BINDING_FIELDS:
                if field not in binding:
                    errors.append(f"PORTFOLIO_BINDING_FIELD_MISSING: {bet_id} -> {field}")

        campaign_ref = binding.get("campaign_ref")
        if campaign_ref is not None and campaign_ref not in campaign_ids:
            errors.append(f"CAMPAIGN_REF_MISSING: {bet_id} -> {campaign_ref}")

        objective_refs = binding.get("objective_refs")
        if not isinstance(objective_refs, list):
            if objective_refs is not None:
                errors.append(f"OBJECTIVE_REFS_INVALID: {bet_id}")
        else:
            for ref in objective_refs:
                if ref not in objective_ids:
                    errors.append(f"{OBJECTIVE_REF_MISSING}: {bet_id} -> {ref}")

        kr_refs = binding.get("kr_refs")
        if not isinstance(kr_refs, list):
            if kr_refs is not None:
                errors.append(f"KR_REFS_INVALID: {bet_id}")
        else:
            for ref in kr_refs:
                if ref not in key_result_ids:
                    errors.append(f"{KR_REF_MISSING}: {bet_id} -> {ref}")

        parent_bet = binding.get("parent_bet")
        if parent_bet is not None and parent_bet not in bet_ids:
            errors.append(f"PARENT_BET_MISSING: {bet_id} -> {parent_bet}")

        _validate_metric_shapes(bet, bet_id=bet_id, errors=errors)
        _validate_bet_type(bet, bet_id=bet_id, errors=errors)
        _validate_policy_bool(bet, bet_id=bet_id, errors=errors)
        _validate_timestamp(bet, bet_id=bet_id, errors=errors)

    return PortfolioValidationResult(errors=tuple(errors), warnings=tuple(warnings))
