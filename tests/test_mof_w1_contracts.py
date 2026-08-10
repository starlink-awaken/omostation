"""Focused tests for the W1-01 M2 strict-contract schemas.

Covers EventEnvelope, Signal, Commitment, Episode, and enhanced Outcome:
- YAML envelope (m2_type / version / created / section key)
- M3 anchors (BehavioralElement / GovernanceElement.Policy / StructuralElement)
- validator-supported field types only (string/int/number/bool/enum/list/map/ref)
- strict Python validation rules (compile as Python; no null / implies / .size)
- schema_version explicit version field present in every contract
- explicit relationship fields present and non-ambiguous
- rejection of missing relationships (source_event_ref, from_signal_ref, etc.)
- rejection of ambiguous relationships (empty strings, empty lists)
- valid instances pass all rules
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

M2_DIR = Path(__file__).resolve().parents[1] / "src" / "ecos" / "ssot" / "mof" / "m2"

SUPPORTED_TYPES = {"string", "int", "number", "bool", "enum", "list", "map", "ref", "date", "datetime"}
FORBIDDEN_RULE_FRAGMENTS = ("null", "implies", ".size")
SEMVER = r"^\d+\.\d+\.\d+$"

SCHEMAS = ["event_envelope", "signal", "commitment", "episode", "outcome"]


# ── helpers ──


def _load(name: str) -> dict:
    path = M2_DIR / f"{name}.yaml"
    assert path.is_file(), f"missing M2 schema: {path}"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _body(data: dict) -> dict:
    m2_type = data["m2_type"]
    for key in (m2_type, m2_type[0].lower() + m2_type[1:], m2_type.lower()):
        if isinstance(data.get(key), dict):
            return data[key]
    raise AssertionError(f"no schema body section for m2_type={m2_type}")


def _all_declared_types(node: object) -> list[str]:
    """Recursively collect every declared field `type:` in the schema body."""
    out: list[str] = []
    if isinstance(node, dict):
        t = node.get("type")
        if isinstance(t, str):
            out.append(t)
        for value in node.values():
            out.extend(_all_declared_types(value))
    elif isinstance(node, list):
        for value in node:
            out.extend(_all_declared_types(value))
    return out


def _rules(body: dict) -> list[dict]:
    rules = body.get("validationRules") or []
    assert rules, "schema must declare validationRules"
    return rules


def _rule_exprs(body: dict) -> list[str]:
    return [rule["rule"] for rule in _rules(body)]


def _find_rule(body: dict, fragment: str) -> str:
    for rule in _rules(body):
        if fragment in rule["rule"]:
            return rule["rule"]
    raise AssertionError(f"no validation rule containing {fragment!r}")


class _SafeLocals(dict):
    """Dict that returns None for any missing key — so bare-name references to
    absent optional fields evaluate to None instead of raising NameError."""

    def __missing__(self, key: str):  # noqa: D401
        return None


def _evaluate_rules(exprs: list[str], instance: dict) -> dict[str, bool]:
    """Evaluate strict-Python rules with the instance dict as locals.

    Missing fields resolve to None (like JS undefined), so rules like
    ``source_ref is not None`` correctly yield False when the field is absent.
    Builtins (``len``, ``str`` …) are injected into the locals dict so that
    ``_SafeLocals.__missing__`` does not shadow them with None.
    """
    safe_locals = _SafeLocals(instance)
    safe_locals["len"] = len
    results: dict[str, bool] = {}
    for expr in exprs:
        compiled = compile(expr, "<rule>", "eval")
        results[expr] = bool(eval(compiled, {"len": len}, safe_locals))
    return results


# ── envelope ──


@pytest.mark.parametrize("name", SCHEMAS)
def test_envelope(name: str) -> None:
    data = _load(name)
    assert data["m2_type"], "m2_type required"
    assert isinstance(data["version"], str) and re.match(SEMVER, data["version"]), (
        "version must be semver"
    )
    assert str(data["created"]).startswith("20"), "created must be ISO-8601 datetime"
    body = _body(data)
    assert body["m3_parent"], "m3_parent required"
    assert body["description"], "description required"
    assert body["stateMachine"], "stateMachine required"
    assert body["requiredProperties"], "requiredProperties required"


# ── M3 anchors ──


def test_m3_anchors() -> None:
    assert _body(_load("event_envelope"))["m3_parent"] == "BehavioralElement"
    assert _body(_load("signal"))["m3_parent"] == "BehavioralElement"
    assert _body(_load("commitment"))["m3_parent"] == "GovernanceElement.Policy"
    assert _body(_load("episode"))["m3_parent"] == "StructuralElement"
    assert _body(_load("outcome"))["m3_parent"] == "StructuralElement.Artifact"


# ── field types ──


@pytest.mark.parametrize("name", SCHEMAS)
def test_only_validator_supported_types(name: str) -> None:
    body = _body(_load(name))
    types = set(_all_declared_types(body))
    unsupported = types - SUPPORTED_TYPES
    assert not unsupported, f"{name} uses unsupported types: {sorted(unsupported)}"


# ── validation rules: strict Python ──


@pytest.mark.parametrize("name", SCHEMAS)
def test_validation_rules_are_strict_python(name: str) -> None:
    body = _body(_load(name))
    for expr in _rule_exprs(body):
        for forbidden in FORBIDDEN_RULE_FRAGMENTS:
            assert forbidden not in expr, (
                f"{name} rule contains forbidden {forbidden!r}: {expr!r}"
            )
        compile(expr, f"<rule:{name}>", "eval")  # SyntaxError propagates


# ── schema_version field present in every contract ──


@pytest.mark.parametrize("name", SCHEMAS)
def test_schema_version_required_field(name: str) -> None:
    body = _body(_load(name))
    req = body.get("requiredProperties") or {}
    assert "schema_version" in req, f"{name} must have schema_version in requiredProperties"
    sv = req["schema_version"]
    assert sv.get("type") == "string", f"{name} schema_version must be string type"
    assert "pattern" in sv, f"{name} schema_version must have a pattern constraint"


# ── EventEnvelope ──


def _event_envelope_rules() -> list[str]:
    return _rule_exprs(_body(_load("event_envelope")))


def _valid_event_envelope() -> dict:
    return {
        "event_id": "evt-001-abcd",
        "schema_version": "event-envelope/v1",
        "source_ref": "agent://worker-01",
        "emitted_at": "2026-08-10T10:00:00+08:00",
        "payload": {"type": "test", "value": 42},
    }


def test_event_envelope_valid_passes_all_rules() -> None:
    results = _evaluate_rules(_event_envelope_rules(), _valid_event_envelope())
    failures = [expr for expr, ok in results.items() if not ok]
    assert not failures, f"valid EventEnvelope failed rules: {failures}"


def test_event_envelope_missing_source_ref_rejected() -> None:
    """Missing source_ref (relationship field) must be rejected."""
    instance = _valid_event_envelope()
    del instance["source_ref"]
    results = _evaluate_rules(_event_envelope_rules(), instance)
    src_rule = next(r for r in results if "source_ref" in r)
    assert results[src_rule] is False, "missing source_ref must fail validation"


def test_event_envelope_empty_source_ref_rejected() -> None:
    """Empty string source_ref (ambiguous provenance) must be rejected."""
    instance = _valid_event_envelope()
    instance["source_ref"] = ""
    results = _evaluate_rules(_event_envelope_rules(), instance)
    src_rule = next(r for r in results if "source_ref" in r and "!=" in r)
    assert results[src_rule] is False, "empty source_ref must fail (ambiguous provenance)"


# ── Signal ──


def _signal_rules() -> list[str]:
    return _rule_exprs(_body(_load("signal")))


def _valid_signal() -> dict:
    return {
        "signal_id": "sig-001-efgh",
        "schema_version": "signal/v1",
        "source_event_ref": "evt-001-abcd",
        "detected_at": "2026-08-10T10:01:00+08:00",
        "pattern": "threshold_breach",
    }


def test_signal_valid_passes_all_rules() -> None:
    results = _evaluate_rules(_signal_rules(), _valid_signal())
    failures = [expr for expr, ok in results.items() if not ok]
    assert not failures, f"valid Signal failed rules: {failures}"


def test_signal_missing_source_event_ref_rejected() -> None:
    """Missing source_event_ref (core relationship) must be rejected."""
    instance = _valid_signal()
    del instance["source_event_ref"]
    results = _evaluate_rules(_signal_rules(), instance)
    ref_rule = next(r for r in results if "source_event_ref" in r)
    assert results[ref_rule] is False, "missing source_event_ref must fail"


def test_signal_empty_source_event_ref_rejected() -> None:
    """Empty string source_event_ref (ambiguous provenance) must be rejected."""
    instance = _valid_signal()
    instance["source_event_ref"] = ""
    results = _evaluate_rules(_signal_rules(), instance)
    ref_rule = next(r for r in results if "source_event_ref" in r and "!=" in r)
    assert results[ref_rule] is False, "empty source_event_ref must fail (ambiguous provenance)"


# ── Commitment ──


def _commitment_rules() -> list[str]:
    return _rule_exprs(_body(_load("commitment")))


def _valid_commitment() -> dict:
    return {
        "commitment_id": "cmt-001-ijkl",
        "schema_version": "commitment/v1",
        "from_signal_ref": "sig-001-efgh",
        "promise": "Fix scene-card-check within 4h",
        "created_at": "2026-08-10T10:02:00+08:00",
    }


def test_commitment_valid_passes_all_rules() -> None:
    results = _evaluate_rules(_commitment_rules(), _valid_commitment())
    failures = [expr for expr, ok in results.items() if not ok]
    assert not failures, f"valid Commitment failed rules: {failures}"


def test_commitment_missing_from_signal_ref_rejected() -> None:
    """Missing from_signal_ref (core relationship) must be rejected."""
    instance = _valid_commitment()
    del instance["from_signal_ref"]
    results = _evaluate_rules(_commitment_rules(), instance)
    ref_rule = next(r for r in results if "from_signal_ref" in r)
    assert results[ref_rule] is False, "missing from_signal_ref must fail"


def test_commitment_empty_from_signal_ref_rejected() -> None:
    """Empty string from_signal_ref (ambiguous provenance) must be rejected."""
    instance = _valid_commitment()
    instance["from_signal_ref"] = ""
    results = _evaluate_rules(_commitment_rules(), instance)
    ref_rule = next(r for r in results if "from_signal_ref" in r and "!=" in r)
    assert results[ref_rule] is False, "empty from_signal_ref must fail (ambiguous provenance)"


# ── Episode ──


def _episode_rules() -> list[str]:
    return _rule_exprs(_body(_load("episode")))


def _valid_episode() -> dict:
    return {
        "episode_id": "epi-001-mnop",
        "schema_version": "episode/v1",
        "contains_event_refs": ["evt-001-abcd", "evt-002-qrst"],
        "opened_at": "2026-08-10T10:00:00+08:00",
    }


def test_episode_valid_passes_all_rules() -> None:
    results = _evaluate_rules(_episode_rules(), _valid_episode())
    failures = [expr for expr, ok in results.items() if not ok]
    assert not failures, f"valid Episode failed rules: {failures}"


def test_episode_missing_contains_event_refs_rejected() -> None:
    """Missing contains_event_refs (core relationship) must be rejected."""
    instance = _valid_episode()
    del instance["contains_event_refs"]
    results = _evaluate_rules(_episode_rules(), instance)
    refs_rule = next(r for r in results if "contains_event_refs" in r)
    assert results[refs_rule] is False, "missing contains_event_refs must fail"


def test_episode_empty_contains_event_refs_rejected() -> None:
    """Empty list contains_event_refs (ambiguous membership) must be rejected."""
    instance = _valid_episode()
    instance["contains_event_refs"] = []
    results = _evaluate_rules(_episode_rules(), instance)
    refs_rule = next(r for r in results if "contains_event_refs" in r)
    assert results[refs_rule] is False, "empty contains_event_refs must fail (ambiguous membership)"


# ── Outcome (enhanced v1.1.0) ──


def test_outcome_version_bumped() -> None:
    """Outcome must be v1.1.0 (enhanced with schema_version + from_commitment_ref)."""
    data = _load("outcome")
    assert data["version"] == "1.1.0", f"Outcome version expected 1.1.0, got {data['version']}"


def test_outcome_has_schema_version_required() -> None:
    body = _body(_load("outcome"))
    req = body.get("requiredProperties") or {}
    assert "schema_version" in req, "Outcome must have schema_version in requiredProperties"


def test_outcome_has_from_commitment_ref_optional() -> None:
    body = _body(_load("outcome"))
    opt = body.get("optionalProperties") or {}
    assert "from_commitment_ref" in opt, (
        "Outcome must have from_commitment_ref in optionalProperties"
    )


def _outcome_rules() -> list[str]:
    return _rule_exprs(_body(_load("outcome")))


def _valid_outcome() -> dict:
    return {
        "outcome": "scene-card-check 修复完成",
        "schema_version": "outcome/v1",
        "from_action": "ACTION-2026-08-10-001",
    }


def test_outcome_valid_without_commitment_ref_passes() -> None:
    """Valid Outcome without from_commitment_ref (backward compat) must pass."""
    results = _evaluate_rules(_outcome_rules(), _valid_outcome())
    failures = [expr for expr, ok in results.items() if not ok]
    assert not failures, f"valid Outcome (no commitment) failed rules: {failures}"


def test_outcome_empty_from_commitment_ref_rejected() -> None:
    """Empty string from_commitment_ref (ambiguous provenance) must be rejected."""
    instance = _valid_outcome()
    instance["from_commitment_ref"] = ""
    results = _evaluate_rules(_outcome_rules(), instance)
    ref_rule = next(r for r in results if "from_commitment_ref" in r)
    assert results[ref_rule] is False, "empty from_commitment_ref must fail (ambiguous provenance)"


def test_outcome_valid_with_commitment_ref_passes() -> None:
    """Valid Outcome with non-empty from_commitment_ref must pass."""
    instance = _valid_outcome()
    instance["from_commitment_ref"] = "cmt-001-ijkl"
    results = _evaluate_rules(_outcome_rules(), instance)
    failures = [expr for expr, ok in results.items() if not ok]
    assert not failures, f"valid Outcome (with commitment) failed rules: {failures}"


# ── relationConstraints present ──


@pytest.mark.parametrize("name", SCHEMAS)
def test_relation_constraints_present(name: str) -> None:
    """Every W1-01 contract must declare relationConstraints (explicit relationships)."""
    body = _body(_load(name))
    assert body.get("relationConstraints"), (
        f"{name} must declare relationConstraints for explicit relationships"
    )
