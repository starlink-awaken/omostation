import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def _module():
    spec = importlib.util.spec_from_file_location("panorama_objective_coverage_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _payload():
    gates = [{"id": f"A{i}", "verdict": "PASS", "live": True} for i in range(1, 10)]
    gates += [
        {"id": "RF0", "verdict": "PASS", "live": True},
        {"id": "RC-DL", "verdict": "PASS", "live": True},
    ]
    return {
        "gates": gates,
        "code_root_health": {"verdict": "PASS"},
        "claims_task16": {"activation_allowed": False},
    }


def _write_ledger(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
bets:
  - id: BET-Y1Q4-T10-151
    status: done
    completion_evidence:
      overall_state: delivery_accepted
      axes:
        engineering: {status: VERIFIED}
        operational: {status: PROVEN}
        value: {status: NOT_PROVEN}
  - id: BET-Y1Q4-T10-165
    status: done
    completion_evidence:
      overall_state: delivery_accepted
      axes:
        engineering: {status: VERIFIED}
        operational: {status: PROVEN}
        value: {status: NOT_PROVEN}
""",
        encoding="utf-8",
    )


def test_objective_coverage_maps_delivery_without_value_or_activation(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "CODE_ROOT", tmp_path / "code")
    _write_ledger(tmp_path / "code/docs/plans/3y-bet-ledger.yaml")

    report = module.collect_objective_coverage(_payload())

    assert report["schema"] == "panorama-objective-coverage/v1"
    assert report["activation_status"] == "AWAITING_AUTHORIZATION"
    assert report["value_proof"] == "NOT_PROVEN"
    assert report["delivery_complete"] is False
    by_id = {item["id"]: item for item in report["items"]}
    assert by_id["EXECUTION_ENVIRONMENT_A1_A9"]["status"] == "PASS"
    assert by_id["PERSISTENT_ROLE_CAPSULE_HANDOFF_CLAIM_VERIFICATION_ASD"]["status"] == "DELIVERY_ACCEPTED"
    assert by_id["PERSISTENT_ROLE_CAPSULE_HANDOFF_CLAIM_VERIFICATION_ASD"]["value_status"] == "NOT_PROVEN"
    assert by_id["REFERENCE_CELL_DIRECT_LOCAL"]["status"] == "PASS"
    assert by_id["ORCA_R0"]["status"] == "PASS"
    assert by_id["MULTICA_AS0"]["status"] == "PASS"
    assert by_id["RUFLO_RF0"]["status"] == "PASS"
    assert by_id["CLAIMS_AUTHORITY_ACTIVATION"]["status"] == "AWAITING_AUTHORIZATION"
    assert by_id["BUSINESS_VALUE"]["status"] == "NOT_PROVEN"


def test_objective_coverage_fails_partial_on_missing_ledger_or_gate(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "CODE_ROOT", tmp_path / "missing")
    payload = _payload()
    payload["gates"][0]["verdict"] = "FAIL"

    report = module.collect_objective_coverage(payload)

    by_id = {item["id"]: item for item in report["items"]}
    assert by_id["EXECUTION_ENVIRONMENT_A1_A9"]["status"] == "PARTIAL"
    assert by_id["PERSISTENT_ROLE_CAPSULE_HANDOFF_CLAIM_VERIFICATION_ASD"]["status"] == "EVIDENCE_INCOMPLETE"
    assert report["delivery_complete"] is False
