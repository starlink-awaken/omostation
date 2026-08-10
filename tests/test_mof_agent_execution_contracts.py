"""Focused tests for the M2 execution-contract schemas.

Covers WorkPacket + CompletionManifest:
- YAML envelope (m2_type / version / created / section key)
- M3 anchors (BehavioralElement.Process / StructuralElement.Artifact)
- validator-supported field types only (string/int/number/bool/enum/list/map/ref)
- strict Python validation rules (compile as Python; no null / implies / .size)
- structured_report evidence type in both schemas
- R0 empty write-surface rule
- CompletionManifest 4-state lifecycle (candidate/blocked/failed/archived)
- required non-negative surface_delta.files/loc
- rule evaluation against valid and violating instances
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

M2_DIR = Path(__file__).resolve().parents[1] / "src" / "ecos" / "ssot" / "mof" / "m2"

SUPPORTED_TYPES = {"string", "int", "number", "bool", "enum", "list", "map", "ref"}
FORBIDDEN_RULE_FRAGMENTS = ("null", "implies", ".size")
SEMVER = r"^\d+\.\d+\.\d+$"

SCHEMAS = ["work_packet", "completion_manifest"]


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


def _evaluate_rules(exprs: list[str], instance: dict) -> dict[str, bool]:
    """Evaluate strict-Python rules with the instance dict as locals."""
    results: dict[str, bool] = {}
    for expr in exprs:
        compiled = compile(expr, "<rule>", "eval")
        results[expr] = bool(eval(compiled, {"len": len}, instance))
    return results


# ── envelope ──


@pytest.mark.parametrize("name", SCHEMAS)
def test_envelope(name: str) -> None:
    data = _load(name)
    assert data["m2_type"], "m2_type required"
    assert isinstance(data["version"], str) and re.match(SEMVER, data["version"]), (
        "version must be semver"
    )
    assert str(data["created"]).startswith(
        "20"
    ), "created must be ISO-8601 datetime"
    body = _body(data)
    assert body["m3_parent"], "m3_parent required"
    assert body["description"], "description required"
    assert body["stateMachine"], "stateMachine required"
    assert body["requiredProperties"], "requiredProperties required"


# ── M3 anchors ──


def test_m3_anchors() -> None:
    assert _body(_load("work_packet"))["m3_parent"] == "BehavioralElement.Process"
    assert (
        _body(_load("completion_manifest"))["m3_parent"]
        == "StructuralElement.Artifact"
    )


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


# ── WorkPacket semantics ──


def _workpacket_rules() -> list[str]:
    return _rule_exprs(_body(_load("work_packet")))


def _valid_r1_instance() -> dict:
    return {
        "packet_id": "WP-W1-01-001",
        "schema_version": "work-packet/v1",
        "blueprint_ref": "blueprint://digital-twin/v1#W1",
        "wave": "W1",
        "bet_id": "BET-Y1Q1-T1-06",
        "strategic_outcome": "门禁诚实阻断未就绪卡",
        "objective": "修复 scene-card-check",
        "why_now": "假绿污染后续判断",
        "status": "active",
        "authority": {
            "strategist": "codex-strategic-director",
            "human_gate": False,
            "risk_level": "R1",
            "autonomy_level": "A2",
        },
        "scope": {
            "read_surfaces": ["Makefile"],
            "write_surfaces": ["Makefile"],
            "non_goals": ["不新增顶层治理规则"],
        },
        "dependencies": {
            "required_packets": [],
            "required_services": [],
            "required_decisions": [],
        },
        "acceptance": {
            "done_when": [
                {
                    "id": "AC1",
                    "assertion": "任一卡失败时返回非零",
                    "evidence_type": "structured_report",
                }
            ],
            "verify_commands": [["make", "scene-card-check"]],
        },
        "budgets": {
            "appetite_hours": 4,
            "max_elapsed_hours": 6,
            "max_changed_files": 3,
            "max_new_files": 1,
            "max_new_top_level_components": 0,
        },
        "rollback": {
            "strategy": "revert in isolated worktree",
            "data_migration": False,
        },
        "circuit_breaker": {"when": ["超时"], "action": "stop_and_escalate"},
        "assignment": {
            "executor_class": "small-code-worker",
            "verifier_class": "independent-readonly-verifier",
            "same_model_verification_allowed": False,
            "expires_at": "2026-08-10T12:00:00Z",
        },
    }


def test_workpacket_valid_r1_passes_all_rules() -> None:
    results = _evaluate_rules(_workpacket_rules(), _valid_r1_instance())
    failures = [expr for expr, ok in results.items() if not ok]
    assert not failures, f"valid R1 instance failed rules: {failures}"


def test_workpacket_structured_report_evidence_type() -> None:
    body = _body(_load("work_packet"))
    done_when = body["requiredProperties"]["acceptance"]["properties"]["done_when"]
    items = done_when["items"]
    assert items["type"] == "map"
    evidence_values = items["properties"]["evidence_type"]["values"]
    assert "structured_report" in evidence_values


def test_workpacket_r0_empty_write_surface_rule() -> None:
    body = _body(_load("work_packet"))
    rule = _find_rule(body, "scope.get('write_surfaces') != []")  # the R0 rule
    assert "R0" in rule and "write_surfaces" in rule

    base = _valid_r1_instance()
    # R0 with non-empty write_surfaces → rule must fail (False)
    r0_violation = dict(base, authority={**base["authority"], "risk_level": "R0"})
    r0_violation["scope"] = {
        "read_surfaces": [],
        "write_surfaces": ["Makefile"],
        "non_goals": [],
    }
    r0_violation["budgets"] = {
        "appetite_hours": 4,
        "max_elapsed_hours": 6,
        "max_changed_files": 0,
        "max_new_files": 0,
        "max_new_top_level_components": 0,
    }
    assert _evaluate_rules([rule], r0_violation)[rule] is False

    # R0 with empty write_surfaces → rule passes (True)
    r0_clean = dict(r0_violation)
    r0_clean["scope"] = {
        "read_surfaces": [],
        "write_surfaces": [],
        "non_goals": [],
    }
    assert _evaluate_rules([rule], r0_clean)[rule] is True


def test_workpacket_r2_requires_independent_verification() -> None:
    body = _body(_load("work_packet"))
    rule = _find_rule(body, "same_model_verification_allowed")
    base = _valid_r1_instance()
    r2_self_verify = dict(base)
    r2_self_verify["authority"] = {**base["authority"], "risk_level": "R2"}
    r2_self_verify["assignment"] = {
        **base["assignment"],
        "same_model_verification_allowed": True,
    }
    assert _evaluate_rules([rule], r2_self_verify)[rule] is False


# ── CompletionManifest semantics ──


def _manifest_rules() -> list[str]:
    return _rule_exprs(_body(_load("completion_manifest")))


def _valid_candidate_instance() -> dict:
    return {
        "packet_id": "WP-W1-01-001",
        "packet_hash": "sha256:" + "a" * 64,
        "assignment_id": "ASG-W1-01",
        "agent_id": "agent-1",
        "status": "candidate",
        "changed_paths": ["Makefile"],
        "claims": [
            {
                "acceptance_id": "AC1",
                "assertion": "任一卡失败时返回非零",
                "evidence_refs": ["evidence://ac1"],
            }
        ],
        "checks": [
            {
                "command": ["make", "scene-card-check"],
                "returncode": 0,
                "stdout_hash": "sha256:" + "b" * 64,
            }
        ],
        "recommended_next": "verify",
        "surface_delta": {"files": 1, "loc": 20},
    }


def test_manifest_four_state_lifecycle() -> None:
    body = _body(_load("completion_manifest"))
    sm = set(body["stateMachine"].keys())
    assert sm == {"candidate", "blocked", "failed", "archived"}
    assert body["stateMachine"]["archived"]["transitions"] == []
    # status enum mirrors the 4 states and excludes 'done' (Agent cannot self-close)
    status_spec = body["requiredProperties"]["status"]
    assert status_spec["type"] == "enum"
    assert set(status_spec["values"]) == {"candidate", "blocked", "failed", "archived"}


def test_manifest_structured_report_evidence_type() -> None:
    body = _body(_load("completion_manifest"))
    evidence = body["optionalProperties"]["evidence"]["items"]["properties"]["type"]
    assert "structured_report" in evidence["values"]


def test_manifest_surface_delta_required_non_negative() -> None:
    body = _body(_load("completion_manifest"))
    surface_delta = body["requiredProperties"]["surface_delta"]
    assert surface_delta["type"] == "map"
    assert set(surface_delta.get("required", [])) == {"files", "loc"}
    assert surface_delta["properties"]["files"]["type"] == "int"
    assert surface_delta["properties"]["loc"]["type"] == "int"

    files_rule = _find_rule(body, "surface_delta.get('files'")
    loc_rule = _find_rule(body, "surface_delta.get('loc'")
    assert ">= 0" in files_rule and ">= 0" in loc_rule

    negative = _valid_candidate_instance()
    negative["surface_delta"] = {"files": -1, "loc": -1}
    results = _evaluate_rules([files_rule, loc_rule], negative)
    assert results[files_rule] is False
    assert results[loc_rule] is False


def test_manifest_valid_candidate_passes_all_rules() -> None:
    results = _evaluate_rules(_manifest_rules(), _valid_candidate_instance())
    failures = [expr for expr, ok in results.items() if not ok]
    assert not failures, f"valid candidate instance failed rules: {failures}"


def test_manifest_no_done_status_and_verify_routing() -> None:
    rules = _manifest_rules()

    done_instance = _valid_candidate_instance()
    done_instance["status"] = "done"
    status_rule = _find_rule(_body(_load("completion_manifest")), "status in")
    assert _evaluate_rules([status_rule], done_instance)[status_rule] is False

    revise_instance = _valid_candidate_instance()
    revise_instance["recommended_next"] = "revise"
    routing_rule = next(r for r in rules if "recommended_next" in r)
    assert _evaluate_rules([routing_rule], revise_instance)[routing_rule] is False
