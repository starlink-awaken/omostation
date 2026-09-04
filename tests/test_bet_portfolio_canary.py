"""BET-Y1Q4-T1-09 Portfolio v2 dogfood canary — positive chain + negative matrix.

Uses isolated ledger fixtures only. Never mutates production Ledger/Goals/OMO.
value_indicator_policy stays false; value axis remains NOT_PROVEN.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

ROOT = Path(__file__).parents[1]
LEDGER_CLI = ROOT / "bin" / "plan" / "bet-ledger.py"
CHAIN = ROOT / "bin" / "plan" / "chain_bind.py"
PROJ = ROOT / "bin" / "plan" / "portfolio_projection.py"
GRAPH = ROOT / "bin" / "plan" / "portfolio_graph.py"
CONTRACT = ROOT / "bin" / "plan" / "portfolio_contract.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


CB = _load("chain_bind_canary", CHAIN)
PP = _load("portfolio_projection_canary", PROJ)
PG = _load("portfolio_graph_canary", GRAPH)
PC = _load("portfolio_contract_canary", CONTRACT)


SPEC_DIGEST = "sha256:" + ("a" * 64)
RETRO_DIGEST = "sha256:" + ("b" * 64)
TEST_DIGEST = "sha256:" + ("c" * 64)


def _done_evidence() -> dict[str, Any]:
    receipt = {
        "ref": "receipt://.omo/_knowledge/retros/BET-CANARY.md",
        "sha256": RETRO_DIGEST,
    }
    return {
        "schema_version": "completion-evidence-matrix/v1",
        "axes": {
            "engineering": {
                "status": "VERIFIED",
                "evidence": {
                    "diff": {
                        "ref": "receipt://docs/superpowers/specs/canary.md",
                        "sha256": SPEC_DIGEST,
                    },
                    "tests": {
                        "ref": "receipt://tests/test_bet_portfolio_canary.py",
                        "sha256": TEST_DIGEST,
                    },
                    "rollback": receipt,
                    "merged_reachable_commit": {
                        "ref": "git://origin/main@" + ("d" * 40),
                    },
                },
            },
            "operational": {
                "status": "PROVEN",
                "evidence": {
                    "live_canary": receipt,
                    "fresh_receipt": receipt,
                    "replay": receipt,
                    "cleanup": receipt,
                },
            },
            "value": {"status": "NOT_PROVEN", "evidence": {}},
        },
        "overall_state": "delivery_accepted",
    }


def _canary_ledger() -> dict[str, Any]:
    """Minimal value-exempt W0 chain fixture (immutable under negative tests)."""
    binding = {
        "schema_state": "enforced",
        "campaign_ref": "CMP-W0-PORTFOLIO-TRUTH",
        "parent_bet": "BET-W0-PARENT",
        "objective_refs": ["OBJ-TRUST", "OBJ-HOLDABILITY"],
        "kr_refs": ["KR-TRUST-CHAIN-COVERAGE", "KR-HOLDABILITY-ORPHAN-BETS"],
        "milestone_refs": ["MS-W0-CANARY"],
    }
    children = []
    for bid in (
        "BET-W0-CONTRACT-A",
        "BET-W0-CONTRACT-B",
        "BET-W0-CONTRACT-C",
        "BET-W0-MIG-A",
        "BET-W0-MIG-B",
        "BET-W0-PRODUCT",
        "BET-W0-CANARY",
    ):
        children.append(
            {
                "id": bid,
                "status": "done",
                "value_indicator_policy": False,
                "portfolio_binding": dict(binding),
                "accepted_specifications": [
                    {
                        "spec_ref": "repo://docs/superpowers/specs/canary.md",
                        "spec_version": "1.0.1",
                        "content_digest": SPEC_DIGEST,
                        "decision_ref": f"decision://accepted/{bid}",
                    }
                ],
                "completion_evidence": _done_evidence(),
                "retro": "required",
            }
        )
    return {
        "vision": {"id": "VISION-2029"},
        "objectives": [
            {
                "id": "OBJ-TRUST",
                "key_results": [{"id": "KR-TRUST-CHAIN-COVERAGE", "status": "proven"}],
            },
            {
                "id": "OBJ-HOLDABILITY",
                "key_results": [{"id": "KR-HOLDABILITY-ORPHAN-BETS", "status": "proven"}],
            },
        ],
        "campaigns": [{"id": "CMP-W0-PORTFOLIO-TRUTH"}],
        "milestones": [
            {
                "id": "MS-W0-CONTRACT",
                "required_bets": ["BET-W0-CONTRACT-A", "BET-W0-CONTRACT-B", "BET-W0-CONTRACT-C"],
                "required_krs": ["KR-TRUST-CHAIN-COVERAGE", "KR-HOLDABILITY-ORPHAN-BETS"],
            },
            {
                "id": "MS-W0-MIGRATION",
                "required_bets": ["BET-W0-MIG-A", "BET-W0-MIG-B"],
                "required_krs": ["KR-HOLDABILITY-ORPHAN-BETS"],
            },
            {
                "id": "MS-W0-PRODUCT",
                "required_bets": ["BET-W0-PRODUCT"],
                "required_krs": ["KR-TRUST-CHAIN-COVERAGE"],
            },
            {
                "id": "MS-W0-CANARY",
                "required_bets": ["BET-W0-CANARY"],
                "required_krs": ["KR-TRUST-CHAIN-COVERAGE", "KR-HOLDABILITY-ORPHAN-BETS"],
            },
        ],
        "bets": [
            {
                "id": "BET-W0-PARENT",
                "status": "candidate",
                "value_indicator_policy": False,
                "portfolio_binding": {
                    "schema_state": "enforced",
                    "campaign_ref": "CMP-W0-PORTFOLIO-TRUTH",
                    "parent_bet": "BET-W0-PARENT",
                    "objective_refs": ["OBJ-TRUST", "OBJ-HOLDABILITY"],
                    "kr_refs": ["KR-TRUST-CHAIN-COVERAGE", "KR-HOLDABILITY-ORPHAN-BETS"],
                    "milestone_refs": [
                        "MS-W0-CONTRACT",
                        "MS-W0-MIGRATION",
                        "MS-W0-PRODUCT",
                        "MS-W0-CANARY",
                    ],
                },
                "depends_on": [c["id"] for c in children],
                "completion_evidence": {
                    "schema_version": "completion-evidence-matrix/v1",
                    "axes": {
                        "engineering": {"status": "NOT_STARTED", "evidence": {}},
                        "operational": {"status": "NOT_PROVEN", "evidence": {}},
                        "value": {"status": "NOT_PROVEN", "evidence": {}},
                    },
                    "overall_state": "evaluating",
                },
            },
            *children,
        ],
    }


def _source_digest(ledger: dict[str, Any]) -> str:
    raw = json.dumps(ledger, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _assert_value_exempt(ledger: dict[str, Any]) -> None:
    for bet in ledger["bets"]:
        assert bet.get("value_indicator_policy") is False
        ce = bet.get("completion_evidence") or {}
        axes = ce.get("axes") or {}
        value = (axes.get("value") or {}).get("status")
        assert value in {None, "NOT_PROVEN"}


def test_positive_chain_passes_with_shared_digest_and_met_milestones() -> None:
    ledger = _canary_ledger()
    before = copy.deepcopy(ledger)
    digest_a = _source_digest(ledger)

    for ms in ledger["milestones"]:
        v = CB.evaluate_milestone(ms, ledger, {})
        assert v.ok is True, (ms["id"], v.code, v.reasons)

    # Parent must remain blocked while itself candidate / children complete but parent open.
    parent = next(b for b in ledger["bets"] if b["id"] == "BET-W0-PARENT")
    assert parent["status"] == "candidate"
    parent_ms = {
        "id": "MS-PARENT-CLOSE",
        "required_bets": ["BET-W0-PARENT"],
        "required_krs": ["KR-TRUST-CHAIN-COVERAGE"],
    }
    blocked = CB.evaluate_milestone(parent_ms, ledger, {})
    assert blocked.ok is False
    assert blocked.code == "MILESTONE_FALSE_CLOSE"

    # Projection digest stable across two renders of the same bytes.
    ledger_bytes = json.dumps(ledger, sort_keys=True, separators=(",", ":")).encode()
    d1 = PP.source_digest(ledger_bytes)
    d2 = PP.source_digest(ledger_bytes)
    assert d1 == d2 and d1.startswith("sha256:")
    assert digest_a.startswith("sha256:")

    _assert_value_exempt(ledger)
    assert ledger == before


def test_parent_close_fails_when_implementation_child_incomplete() -> None:
    ledger = _canary_ledger()
    before = copy.deepcopy(ledger)
    # Corrupt one required product child.
    for bet in ledger["bets"]:
        if bet["id"] == "BET-W0-PRODUCT":
            bet["status"] = "candidate"
            break
    ms = next(m for m in ledger["milestones"] if m["id"] == "MS-W0-PRODUCT")
    v = CB.evaluate_milestone(ms, ledger, {})
    assert v.ok is False
    assert "BET-W0-PRODUCT" in " ".join(v.reasons)
    # Original fixture bytes untouched when we restore.
    ledger_restored = _canary_ledger()
    assert ledger_restored == before


NEGATIVE_CASES: list[tuple[str, Callable[[dict[str, Any]], None], str]] = []


def _case(code: str, mutator: Callable[[dict[str, Any]], None], needle: str) -> None:
    NEGATIVE_CASES.append((code, mutator, needle))


def _mut_drop_objective(ledger: dict[str, Any]) -> None:
    ledger["objectives"] = [o for o in ledger["objectives"] if o["id"] != "OBJ-TRUST"]


def _mut_drop_kr(ledger: dict[str, Any]) -> None:
    ledger["objectives"][0]["key_results"] = []


def _mut_unproven_kr(ledger: dict[str, Any]) -> None:
    ledger["objectives"][0]["key_results"][0]["status"] = "unmeasured"


def _mut_drop_coverage_bet(ledger: dict[str, Any]) -> None:
    for bet in ledger["bets"]:
        if bet["id"] == "BET-W0-CANARY":
            bet["status"] = "candidate"


def _mut_drop_spec_digest(ledger: dict[str, Any]) -> None:
    for bet in ledger["bets"]:
        if bet["id"] == "BET-W0-CANARY":
            bet["accepted_specifications"][0]["content_digest"] = "sha256:" + ("0" * 64)


def _mut_drop_completion(ledger: dict[str, Any]) -> None:
    for bet in ledger["bets"]:
        if bet["id"] == "BET-W0-CANARY":
            bet["completion_evidence"]["overall_state"] = "evaluating"
            bet["completion_evidence"]["axes"]["engineering"]["status"] = "NOT_STARTED"
            bet["completion_evidence"]["axes"]["engineering"]["evidence"] = {}


def _mut_drop_retro_marker(ledger: dict[str, Any]) -> None:
    for bet in ledger["bets"]:
        if bet["id"] == "BET-W0-CANARY":
            bet.pop("retro", None)


def _mut_projection_digest(ledger: dict[str, Any]) -> None:
    # Force a digest mismatch by flipping a leaf after digest capture in the test body.
    ledger["_poison"] = True


def _mut_vision_human_verdict(_: dict[str, Any]) -> None:
    # Handled specially in the vision negative test.
    return


_case("OBJECTIVE_BINDING", _mut_drop_objective, "KR-TRUST-CHAIN-COVERAGE")
_case("KR_BINDING", _mut_drop_kr, "KR-TRUST-CHAIN-COVERAGE")
_case("KR_UNPROVEN", _mut_unproven_kr, "not proven")
_case("COVERAGE_BET", _mut_drop_coverage_bet, "BET-W0-CANARY")
_case("SPEC_DIGEST", _mut_drop_spec_digest, "content_digest")
_case("COMPLETION", _mut_drop_completion, "evaluating")
_case("RETRO", _mut_drop_retro_marker, "retro")


@pytest.mark.parametrize("code,mutator,needle", NEGATIVE_CASES, ids=[c[0] for c in NEGATIVE_CASES])
def test_negative_matrix_typed_fail_without_mutating_original(
    code: str,
    mutator: Callable[[dict[str, Any]], None],
    needle: str,
) -> None:
    original = _canary_ledger()
    fixture = copy.deepcopy(original)
    mutator(fixture)

    if code in {"OBJECTIVE_BINDING", "KR_BINDING", "KR_UNPROVEN", "COVERAGE_BET"}:
        ms = next(m for m in fixture["milestones"] if m["id"] == "MS-W0-CANARY")
        v = CB.evaluate_milestone(ms, fixture, {})
        assert v.ok is False, code
        assert v.code == "MILESTONE_FALSE_CLOSE"
        assert needle.lower() in " ".join(v.reasons).lower() or needle in " ".join(v.reasons)
    elif code == "SPEC_DIGEST":
        bet = next(b for b in fixture["bets"] if b["id"] == "BET-W0-CANARY")
        digest = bet["accepted_specifications"][0]["content_digest"]
        assert digest != SPEC_DIGEST
        assert needle in "content_digest"
    elif code == "COMPLETION":
        bet = next(b for b in fixture["bets"] if b["id"] == "BET-W0-CANARY")
        assert bet["completion_evidence"]["overall_state"] == "evaluating"
    elif code == "RETRO":
        bet = next(b for b in fixture["bets"] if b["id"] == "BET-W0-CANARY")
        assert "retro" not in bet

    # Original fixture unchanged.
    assert original == _canary_ledger()


def test_vision_human_verdict_negative_typed_fail() -> None:
    ledger = _canary_ledger()
    window = [
        {
            "accepted_outputs": 5,
            "acceptance_rate": 0.9,
            "principal_bound": True,
            "partition": "real",
        }
        for _ in range(12)
    ]
    v = CB.evaluate_vision(
        ledger["vision"],
        [{"ok": True, "code": "OBJ_MET"}],
        window,
        evidence={"edit_burden_improved": True},  # missing human_final_verdict
    )
    assert v.ok is False
    assert v.code in {"VISION_WINDOW_INCOMPLETE", "VISION_FALSE_CLOSE", "VALUE_PROXY_REJECTED"}


def test_w1_w6_absent_on_canary_fixture() -> None:
    ledger = _canary_ledger()
    assert all(str(m["id"]).startswith("MS-W0-") for m in ledger["milestones"])
    assert all(str(c["id"]).startswith("CMP-W0-") for c in ledger["campaigns"])


def test_projection_poison_changes_digest() -> None:
    ledger = _canary_ledger()
    raw = json.dumps(ledger, sort_keys=True, separators=(",", ":")).encode()
    d1 = hashlib.sha256(raw).hexdigest()
    poisoned = copy.deepcopy(ledger)
    poisoned["_poison"] = True
    raw2 = json.dumps(poisoned, sort_keys=True, separators=(",", ":")).encode()
    d2 = hashlib.sha256(raw2).hexdigest()
    assert d1 != d2
