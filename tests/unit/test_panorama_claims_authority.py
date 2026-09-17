import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def _module():
    spec = importlib.util.spec_from_file_location("panorama_claims_authority", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_claims_authority_projection_is_read_only_and_fail_closed(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    report = module.collect_claims_authority()
    assert report["schema"] == "claims-authority-projection/v1"
    assert report["available"] is False
    assert report["verdict"] == "UNAVAILABLE"
    assert report["mutation_performed"] is False
    assert report["authorization_granted"] is False


def test_claims_authority_projection_projects_whitelisted_status(tmp_path, monkeypatch) -> None:
    module = _module()
    verifier_report = {
        "schema": "claims-authority-observation/v1",
        "ok": True,
        "verdict": "READ_ONLY",
        "available": True,
        "mutation_performed": False,
        "authorization_granted": False,
        "status": {
            "activation_state": "unactivated",
            "authority_id": "omo-claims-authority-r0",
            "code": "not_activated",
            "effective_claim_authority": "v1",
            "instruction_capable": False,
            "security_level": "R0_COOPERATIVE",
            "sequence": 0,
        },
    }
    monkeypatch.setattr(module, "_verify_claims_authority", lambda: verifier_report)
    result = module.collect_claims_authority()
    assert result["available"] is True
    assert result["verdict"] == "READ_ONLY"
    assert result["mutation_performed"] is False
    assert result["authorization_granted"] is False
    assert result["status"]["effective_claim_authority"] == "v1"
    assert result["status"]["instruction_capable"] is False
