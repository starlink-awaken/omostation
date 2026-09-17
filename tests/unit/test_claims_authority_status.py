import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/gac/claims-authority-status.py"


def _module():
    spec = importlib.util.spec_from_file_location("claims_authority_status", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_status_observer_whitelists_fields_and_does_not_grant_authority(monkeypatch) -> None:
    module = _module()

    def fake_status():
        return {
            "activation_state": "unactivated",
            "authority_epoch": 0,
            "authority_id": "omo-claims-authority-r0",
            "code": "not_activated",
            "descriptor_digest": None,
            "effective_claim_authority": "v1",
            "fresh": False,
            "instruction_capable": False,
            "last_receipt_digest": None,
            "observed_at": None,
            "security_level": "R0_COOPERATIVE",
            "sequence": 0,
            "secret_internal": "must-not-leak",
        }

    monkeypatch.setattr(module, "ROOT", ROOT)
    import omo.workflow.claims_authority as authority
    monkeypatch.setattr(authority, "authority_status", fake_status)
    report = module.observe()
    assert report["schema"] == "claims-authority-observation/v1"
    assert report["ok"] is True
    assert report["verdict"] == "READ_ONLY"
    assert report["mutation_performed"] is False
    assert report["authorization_granted"] is False
    assert report["status"]["activation_state"] == "unactivated"
    assert report["status"]["instruction_capable"] is False
    assert "secret_internal" not in report["status"]


def test_invalid_status_is_fail_closed(monkeypatch) -> None:
    module = _module()
    import omo.workflow.claims_authority as authority
    monkeypatch.setattr(authority, "authority_status", lambda: [])
    report = module.observe()
    assert report["ok"] is False
    assert report["verdict"] == "INVALID"
    assert report["authorization_granted"] is False
