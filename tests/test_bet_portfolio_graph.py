"""T1-05 Portfolio coverage graph and critical-path tests."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
LEDGER_CLI = ROOT / "bin" / "plan" / "bet-ledger.py"
GRAPH_PATH = ROOT / "bin" / "plan" / "portfolio_graph.py"
SPEC = importlib.util.spec_from_file_location("portfolio_graph", GRAPH_PATH)
assert SPEC and SPEC.loader
PORTFOLIO_GRAPH = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PORTFOLIO_GRAPH
SPEC.loader.exec_module(PORTFOLIO_GRAPH)


def _base_v2() -> dict:
    return {
        "vision": {"id": "VISION-TEST", "required_key_results": ["KR-REQ"]},
        "objectives": [
            {
                "id": "OBJ-TEST",
                "key_results": [
                    {"id": "KR-REQ", "required": True},
                    {"id": "KR-OPT", "required": False},
                ],
            }
        ],
        "campaigns": [{"id": "CMP-TEST"}],
        "milestones": [{"id": "MS-TEST", "target_window": "Y1Q4", "covers": ["KR-REQ"]}],
        "bets": [],
    }


def test_missing_dependency_ref_typed_error() -> None:
    ledger = _base_v2()
    ledger["bets"] = [
        {
            "id": "BET-A",
            "status": "candidate",
            "window": "Y1Q4",
            "depends_on": ["BET-MISSING"],
            "portfolio_binding": {"kr_refs": ["KR-REQ"], "campaign_ref": "CMP-TEST", "objective_refs": ["OBJ-TEST"]},
        }
    ]
    before = copy.deepcopy(ledger)
    graph = PORTFOLIO_GRAPH.build_graph(ledger)
    result = PORTFOLIO_GRAPH.validate_coverage(graph)
    assert any(e.startswith("DEPENDENCY_REF_MISSING:") for e in result.errors)
    assert ledger == before


def test_dependency_cycle_typed_error() -> None:
    ledger = _base_v2()
    ledger["bets"] = [
        {
            "id": "BET-A",
            "status": "candidate",
            "depends_on": ["BET-B"],
            "portfolio_binding": {"kr_refs": ["KR-REQ"]},
        },
        {
            "id": "BET-B",
            "status": "candidate",
            "depends_on": ["BET-A"],
            "portfolio_binding": {"kr_refs": ["KR-REQ"]},
        },
    ]
    graph = PORTFOLIO_GRAPH.build_graph(ledger)
    assert "DEPENDENCY_CYCLE" in graph.errors or "DEPENDENCY_CYCLE" in PORTFOLIO_GRAPH.validate_coverage(graph).errors


def test_required_kr_uncovered() -> None:
    ledger = _base_v2()
    ledger["milestones"] = []
    ledger["bets"] = [{"id": "BET-A", "status": "candidate", "portfolio_binding": {"kr_refs": ["KR-OPT"]}}]
    graph = PORTFOLIO_GRAPH.build_graph(ledger)
    result = PORTFOLIO_GRAPH.validate_coverage(graph)
    assert "REQUIRED_KR_UNCOVERED: KR-REQ" in result.errors


def test_failed_leaf_without_replacement_fails_and_replacement_restores() -> None:
    ledger = _base_v2()
    ledger["milestones"] = []
    ledger["bets"] = [
        {
            "id": "BET-FAIL",
            "status": "failed",
            "portfolio_binding": {"kr_refs": ["KR-REQ"]},
        }
    ]
    graph = PORTFOLIO_GRAPH.build_graph(ledger)
    assert "FAILED_LEAF_NO_REPLACEMENT: BET-FAIL" in PORTFOLIO_GRAPH.validate_coverage(graph).errors

    ledger["bets"].append(
        {
            "id": "BET-REPL",
            "status": "candidate",
            "replacement_of": "BET-FAIL",
            "portfolio_binding": {"kr_refs": ["KR-REQ"]},
        }
    )
    graph2 = PORTFOLIO_GRAPH.build_graph(ledger)
    errors2 = PORTFOLIO_GRAPH.validate_coverage(graph2).errors
    assert not any(e.startswith("FAILED_LEAF_NO_REPLACEMENT:") for e in errors2)
    assert "REQUIRED_KR_UNCOVERED: KR-REQ" not in errors2


def test_duplicate_coverage_requires_rationale() -> None:
    ledger = _base_v2()
    ledger["milestones"] = []
    ledger["bets"] = [
        {"id": "BET-A", "status": "candidate", "portfolio_binding": {"kr_refs": ["KR-REQ"]}},
        {"id": "BET-B", "status": "candidate", "portfolio_binding": {"kr_refs": ["KR-REQ"]}},
    ]
    bad = PORTFOLIO_GRAPH.validate_coverage(PORTFOLIO_GRAPH.build_graph(ledger))
    assert any(e.startswith("DUPLICATE_COVERAGE_NO_RATIONALE:") for e in bad.errors)

    ledger["bets"][0]["portfolio_binding"]["coverage_rationale"] = "intentional dual-track"
    ledger["bets"][1]["portfolio_binding"]["coverage_rationale"] = "intentional dual-track"
    good = PORTFOLIO_GRAPH.validate_coverage(PORTFOLIO_GRAPH.build_graph(ledger))
    assert not any(e.startswith("DUPLICATE_COVERAGE_NO_RATIONALE:") for e in good.errors)


def test_parent_bet_does_not_change_topo_order() -> None:
    ledger = _base_v2()
    ledger["milestones"] = []
    ledger["bets"] = [
        {
            "id": "BET-CHILD",
            "status": "candidate",
            "window": "Y1Q4",
            "portfolio_binding": {"parent_bet": "BET-PARENT", "kr_refs": ["KR-REQ"]},
        },
        {
            "id": "BET-PARENT",
            "status": "candidate",
            "window": "Y1Q4",
            "portfolio_binding": {"kr_refs": ["KR-REQ"], "coverage_rationale": "parent also covers"},
        },
    ]
    graph = PORTFOLIO_GRAPH.build_graph(ledger)
    report = PORTFOLIO_GRAPH.critical_path(graph)
    # Without depends_on, parent ownership alone must not force ordering by parent edge
    assert set(report["ready_bets"]) == {"BET-CHILD", "BET-PARENT"}
    assert "progress" not in report


def test_critical_path_json_byte_stable_and_schema() -> None:
    ledger = _base_v2()
    ledger["milestones"] = []
    ledger["bets"] = [
        {
            "id": "BET-ROOT",
            "status": "done",
            "window": "Y1Q3",
            "portfolio_binding": {"kr_refs": ["KR-REQ"]},
        },
        {
            "id": "BET-NEXT",
            "status": "candidate",
            "window": "Y1Q4",
            "depends_on": ["BET-ROOT"],
            "write_surfaces": ["docs/plans/3y-bet-ledger.yaml"],
            "portfolio_binding": {"kr_refs": ["KR-REQ"], "coverage_rationale": "successor"},
        },
        {
            "id": "BET-PEER",
            "status": "candidate",
            "window": "Y1Q4",
            "depends_on": ["BET-ROOT"],
            "write_surfaces": ["docs/plans/3y-bet-ledger.yaml"],
            "portfolio_binding": {"kr_refs": ["KR-REQ"], "coverage_rationale": "peer"},
        },
    ]
    graph = PORTFOLIO_GRAPH.build_graph(ledger)
    a = json.dumps(PORTFOLIO_GRAPH.critical_path(graph), sort_keys=True, separators=(",", ":"))
    b = json.dumps(PORTFOLIO_GRAPH.critical_path(graph), sort_keys=True, separators=(",", ":"))
    assert a == b
    report = json.loads(a)
    assert set(report) == {
        "ready_bets",
        "blocked_descendant_count",
        "unresolved_kr_coverage",
        "writer_lane_conflicts",
        "evidence",
    }
    assert "progress" not in report
    assert "BET-NEXT" in report["ready_bets"]
    assert report["writer_lane_conflicts"]


def test_cli_portfolio_coverage_exit_0_on_live_ledger() -> None:
    result = subprocess.run(
        [sys.executable, str(LEDGER_CLI), "portfolio", "coverage"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout


def test_cli_critical_path_json_byte_stable() -> None:
    cmd = [sys.executable, str(LEDGER_CLI), "portfolio", "critical-path", "--json"]
    a = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    b = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    assert a.returncode == 0, a.stderr + a.stdout
    assert b.returncode == 0, b.stderr + b.stdout
    assert a.stdout == b.stdout
    payload = json.loads(a.stdout)
    assert "progress" not in payload
    assert set(payload) >= {
        "ready_bets",
        "blocked_descendant_count",
        "unresolved_kr_coverage",
        "writer_lane_conflicts",
        "evidence",
    }
