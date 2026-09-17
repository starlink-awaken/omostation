import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def _module():
    spec = importlib.util.spec_from_file_location("panorama_agent_brief_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _payload():
    return {
        "generated_at": "2026-09-17T00:00:00+00:00",
        "gates": [
            {"id": "A1", "title": "Workflow", "verdict": "PASS", "live": True},
            {"id": "A2", "title": "Host", "verdict": "FAIL", "live": True},
        ],
        "claims_authority": {
            "effective_claim_authority": "v1",
            "activation_state": "unactivated",
            "instruction_capable": False,
        },
        "claims_task16": {
            "activation_allowed": False,
            "hard_blockers": ["operation_specific_host_authorization_unproven"],
        },
        "agent_cell_pool": {"available": True, "total": 2, "active": 1, "failed": 0},
        "reference_cell": {"id": "RC-DL", "verdict": "PASS"},
        "value_metrics": {"x3-value-stack": {"available": True}},
    }


def test_agent_visibility_projects_authority_health_and_interfaces() -> None:
    module = _module()
    brief = module.collect_agent_visibility(_payload())

    assert brief["schema"] == "panorama-agent-brief/v1"
    assert brief["available"] is True
    assert brief["authority"]["control_plane"] == "OMO"
    assert brief["authority"]["effective_claim_authority"] == "v1"
    assert brief["authority"]["claims_activation_allowed"] is False
    assert brief["authority"]["claims_activation_blockers"] == [
        "operation_specific_host_authorization_unproven"
    ]
    assert brief["authority"]["value_proof"] == "NOT_PROVEN"
    assert brief["health"]["gates_total"] == 2
    assert brief["health"]["gates_pass"] == 1
    assert brief["health"]["gates_failing"] == ["A2"]
    assert brief["read_interfaces"]["agent_brief_json"] == "/agent-brief.json"
    assert brief["read_interfaces"]["filesystem"]["brief"] == "runtime/dashboard/agent-brief.json"


def test_write_site_emits_data_and_agent_brief(tmp_path, monkeypatch) -> None:
    module = _module()
    out_dir = tmp_path / "dashboard"
    monkeypatch.setattr(module, "OUT_DIR", out_dir)
    monkeypatch.setattr(module, "DATA_JSON", out_dir / "data.json")
    monkeypatch.setattr(module, "AGENT_BRIEF_JSON", out_dir / "agent-brief.json")
    monkeypatch.setattr(module, "INDEX_HTML", out_dir / "index.html")

    payload = _payload()
    payload["agent_visibility"] = module.collect_agent_visibility(payload)
    module.write_site(payload)

    data = json.loads((out_dir / "data.json").read_text())
    brief = json.loads((out_dir / "agent-brief.json").read_text())
    assert data["agent_visibility"]["schema"] == "panorama-agent-brief/v1"
    assert brief["schema"] == "panorama-agent-brief/v1"
    assert (out_dir / "index.html").is_file()
