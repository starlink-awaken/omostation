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
            "available": True,
            "verdict": "AWAITING_AUTHORIZATION",
            "activation_allowed": False,
            "hard_blockers": ["operation_specific_host_authorization_unproven"],
            "preflight": {
                "readiness": "AWAITING_AUTHORIZATION",
                "operation_specific_authorization": "UNPROVEN",
                "advisories": ["root_head_not_equal_origin_main"],
                "checked_at": "2026-09-18T00:00:00+00:00",
            },
        },
        "agent_cell_pool": {"available": True, "total": 2, "active": 1, "failed": 0},
        "reference_cell": {"id": "RC-DL", "verdict": "PASS"},
        "agent_cell_semantic": {
            "available": True,
            "verdict": "PASS",
            "receipt_chain_ok": True,
            "receipt_digests_ok": True,
            "role_bindings_ok": True,
            "capsule_bindings_ok": True,
            "mesh_bindings_ok": True,
            "queue_bindings_ok": True,
            "latest_run_id": "semantic-smoke-test",
            "latest_receipt_digest": "sha256:test",
        },
        "value_metrics": {"x3-value-stack": {"available": True}},
        "bets": {
            "total": 3,
            "counts": {"done": 2, "candidate": 1},
            "in_progress": [],
            "blocked": [{"id": "BET-X", "title": "Keep blocked"}],
            "windows": {"Y1Q1": {"total": 2, "done": 2}, "Y1Q2": {"total": 1, "done": 0}},
        },
        "workflows": [
            {"run_id": "run-active", "workflow_id": "project-code-change", "status": "active"},
            {"run_id": "run-blocked", "workflow_id": "project-code-change", "status": "blocked"},
        ],
        "tasks": {
            "total": 2,
            "open_count": 2,
            "by_status": {"pending": 1, "candidate": 1},
            "by_bucket": {"active": 1, "planned": 1},
            "duplicates": [{"id": "TASK-A", "buckets": ["active", "planned"]}],
            "open_recent": [{"id": "TASK-A", "status": "pending", "bucket": "active"}],
            "recent": [{"id": "task-a"}],
        },
        "service_lifecycle": {
            "total": 2,
            "by_lifecycle": {"active": 1, "proposed": 1},
            "recent": [],
        },
        "role_registry": {
            "schema": "panorama-role-registry/v1",
            "available": True,
            "verdict": "PASS",
            "total": 2,
            "by_state": {"admitted": 2},
            "integrity_ok": True,
            "records": [
                {"role_id": "role:alpha", "admission_state": "admitted", "version": 2, "capabilities": ["semantic.plan"]}
            ],
        },
        "alerts": {
            "total": 1,
            "high": 1,
            "alerts": [{"severity": "high", "source": "debt", "msg": "example"}],
        },
        "panel_value": {
            "schema": "panel-value/v1",
            "state": "not_proven",
            "state_reason": [
                "已有 2 条记录，但 qualifying=false（未产生净节省，不计入价值门）",
                "样本 2/30 不足",
            ],
            "samples": {
                "records": 2,
                "qualifying": 0,
                "accepted": 2,
                "adjudicated": 2,
                "net_saved_seconds": 0,
            },
            "thresholds": [
                {
                    "key": "samples",
                    "label": "真实样本",
                    "target": 30,
                    "unit": "个",
                    "comparator": "gte",
                    "current": 0,
                    "met": False,
                    "gate": None,
                }
            ],
        },
        "value_evidence_validation": {
            "schema": "value-evidence-validation/v2",
            "available": True,
            "ok": True,
            "records": 2,
            "v2_records": 0,
            "qualifying": 0,
            "target": 30,
            "issues": [],
        },
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
    readiness = brief["authority"]["claims_activation_readiness"]
    assert readiness["schema"] == "claims-activation-readiness/v1"
    assert readiness["verdict"] == "AWAITING_AUTHORIZATION"
    assert readiness["readiness"] == "AWAITING_AUTHORIZATION"
    assert readiness["operation_specific_authorization"] == "UNPROVEN"
    assert readiness["activation_allowed"] is False
    assert readiness["advisories"] == ["root_head_not_equal_origin_main"]
    assert readiness["authorization_packet"]["required_fields"] == [
        "principal_decision_id",
        "decision_timestamp",
        "authorized_surface=agents/_shared/runtime/omo-claims-authority-r0",
        "rollback_surface=agents/_shared/backups/omo-claims-authority-r0",
        "expiry_or_no_expiry",
        "observation_requirement=24h foreground/1440 samples",
    ]
    assert readiness["authorization_packet"]["not_sufficient"] == [
        "general_agent_authorization",
        "accepted_spec_binding_alone",
        "dashboard_status_or_ai_statement",
    ]
    assert readiness["observation_gate"]["minimum_samples"] == 1440
    assert readiness["observation_gate"]["first_three_are_diagnostic_only"] is True
    value = brief["authority"]["value_proof_readiness"]
    assert value["validation"]["ok"] is True
    assert value["validation"]["target"] == 30
    assert value["status"] == "NOT_PROVEN"
    assert value["available"] is True
    assert value["samples_total"] == 2
    assert value["qualifying_samples"] == 0
    assert value["net_saved_seconds"] == 0
    assert value["thresholds"][0]["target"] == 30
    assert value["next_action"] == (
        "Collect 30 more qualifying real-use records with a frozen baseline; do not backfill."
    )
    assert brief["authority"]["value_proof"] == "NOT_PROVEN"
    assert brief["health"]["gates_total"] == 2
    assert brief["health"]["gates_pass"] == 1
    assert brief["health"]["gates_failing"] == ["A2"]
    assert brief["read_interfaces"]["agent_brief_json"] == "/agent-brief.json"
    assert brief["read_interfaces"]["filesystem"]["brief"] == "runtime/dashboard/agent-brief.json"
    assert brief["work_state"]["bets"]["milestones"] == [
        {"id": "ledger-window:Y1Q1", "title": "Y1Q1", "total": 2, "done": 2,
         "remaining": 0, "completion_pct": 100.0},
        {"id": "ledger-window:Y1Q2", "title": "Y1Q2", "total": 1, "done": 0,
         "remaining": 1, "completion_pct": 0.0},
    ]
    assert brief["work_state"]["workflows"]["active_count"] == 1
    assert brief["work_state"]["workflows"]["blocked_recent_count"] == 1
    assert brief["work_state"]["tasks"]["by_status"] == {"pending": 1, "candidate": 1}
    assert brief["work_state"]["tasks"]["open_count"] == 2
    assert brief["work_state"]["tasks"]["duplicates"] == [
        {"id": "TASK-A", "buckets": ["active", "planned"]}
    ]
    assert brief["work_state"]["services"]["by_lifecycle"] == {"active": 1, "proposed": 1}
    assert brief["health"]["persistent_roles"]["total"] == 2
    assert brief["health"]["persistent_roles"]["admitted"] == 2
    assert brief["health"]["persistent_roles"]["integrity_ok"] is True
    assert brief["role_registry"]["schema"] == "panorama-role-registry/v1"
    assert brief["work_state"]["alerts"]["high"] == 1
    action_ids = {action["id"] for action in brief["next_actions"]}
    assert {
        "claims-authority-wait",
        "collect-qualifying-value-evidence",
        "plan-candidate-bets",
        "triage-high-alerts",
    } <= action_ids


def test_agent_visibility_claims_readiness_fails_closed_without_preflight() -> None:
    module = _module()
    payload = _payload()
    payload["claims_task16"] = {"activation_allowed": False}

    readiness = module.collect_agent_visibility(payload)["authority"]["claims_activation_readiness"]

    assert readiness["available"] is False
    assert readiness["verdict"] == "UNAVAILABLE"
    assert readiness["readiness"] == "UNKNOWN"
    assert readiness["operation_specific_authorization"] == "UNPROVEN"
    assert readiness["activation_allowed"] is False


def test_agent_visibility_isolated_technical_readiness_overrides_canonical_blockers() -> None:
    module = _module()
    payload = _payload()
    payload["claims_task16"].update({
        "isolated_technical_ready": True,
        "remaining_after_isolated_recovery": [
            "operation_specific_host_authorization_unproven"
        ],
        "isolated_preflight": {
            "available": True,
            "readiness": "AWAITING_AUTHORIZATION",
            "hard_blockers": [],
            "root_head_oid": "exact-main",
        },
    })
    # The canonical checkout remains visibly dirty; isolated evidence is what
    # decides technical readiness.
    payload["claims_task16"]["preflight"]["advisories"] = [
        "nonclosure_dirty_tracked_integration_root"
    ]

    readiness = module.collect_agent_visibility(payload)["authority"][
        "claims_activation_readiness"
    ]

    assert readiness["isolated_technical_ready"] is True
    assert readiness["effective_readiness"] == "AWAITING_AUTHORIZATION"
    assert readiness["activation_allowed"] is False
    assert readiness["operation_specific_authorization"] == "UNPROVEN"


def test_agent_visibility_includes_exact_activation_request() -> None:
    module = _module()
    payload = _payload()
    payload["claims_activation_request"] = {
        "schema": "panorama-claims-activation-request/v1",
        "available": True,
        "status": "READY_FOR_OPERATION_SPECIFIC_HUMAN_REVIEW",
        "execution": "NOT_EXECUTED",
        "activation": "NOT_AUTHORIZED",
        "request_id": "request-1",
        "request_digest": "sha256:" + "a" * 64,
        "descriptor_digest": "sha256:" + "b" * 64,
        "authority_id": "omo-claims-authority-r0",
        "operation": "activate-shadow",
        "human_authorization_status": "UNPROVEN",
        "human_authorization_required": True,
        "execution_forbidden_without_human_authorization": True,
    }

    request = module.collect_agent_visibility(payload)["authority"][
        "claims_activation_request"
    ]

    assert request["available"] is True
    assert request["request_id"] == "request-1"
    assert request["request_digest"] == "sha256:" + "a" * 64
    assert request["descriptor_digest"] == "sha256:" + "b" * 64
    assert request["execution"] == "NOT_EXECUTED"
    assert request["activation"] == "NOT_AUTHORIZED"
    assert request["human_authorization_status"] == "UNPROVEN"


def test_agent_visibility_exposes_shadow_observation_progress() -> None:
    module = _module()
    payload = _payload()
    payload["claims_authority"] = {"activation_state": "shadow-active"}
    payload["claims_observation_progress"] = {
        "state": "IN_PROGRESS",
        "sample_count": 182,
        "minimum_samples": 1440,
    }

    authority = module.collect_agent_visibility(payload)["authority"]

    assert authority["claims_activation_state"] == "shadow-active"
    assert authority["claims_observation_progress"]["state"] == "IN_PROGRESS"
    assert authority["claims_observation_progress"]["sample_count"] == 182
    assert authority["value_proof"] == "NOT_PROVEN"


def test_agent_visibility_value_readiness_fails_closed_without_panel() -> None:
    module = _module()
    payload = _payload()
    del payload["panel_value"]

    value = module.collect_agent_visibility(payload)["authority"]["value_proof_readiness"]

    assert value["status"] == "NOT_PROVEN"
    assert value["available"] is False
    assert value["source"] == "unavailable"
    assert value["qualifying_samples"] == 0
    assert value["next_action"].startswith("Collect 30 more qualifying real-use records")


def test_agent_visibility_value_readiness_fails_closed_without_validation() -> None:
    module = _module()
    payload = _payload()
    del payload["value_evidence_validation"]

    readiness = module.collect_agent_visibility(payload)["authority"]["value_proof_readiness"]

    assert readiness["validation"]["ok"] is False
    assert readiness["validation"]["available"] is False
    assert "value-evidence validation unavailable or failed" in readiness["blockers"]


def test_value_evidence_validation_uses_runtime_paths_and_fail_closed(tmp_path, monkeypatch) -> None:
    module = _module()
    runtime_root = tmp_path / "workspace"
    code_root = tmp_path / "code"
    verifier = code_root / "bin/ssot/value-recorder.py"
    verifier.parent.mkdir(parents=True)
    verifier.write_text("", encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", runtime_root)
    monkeypatch.setattr(module, "CODE_ROOT", code_root)

    def fake_run(command, **kwargs):
        assert command[1] == str(verifier)
        assert command[2] == "validate"
        assert command[3] == "--json"
        assert command[command.index("--evidence") + 1] == str(
            runtime_root / ".omo/_delivery/ingress/value-evidence.jsonl"
        )
        assert command[command.index("--baseline-dir") + 1] == str(
            runtime_root / ".omo/state/value-baselines"
        )
        assert kwargs["cwd"] == runtime_root
        assert kwargs["timeout"] == 10
        return type("Completed", (), {"stdout": json.dumps({
            "schema": "value-evidence-validation/v2", "ok": True
        })})()

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    report = module.collect_value_evidence_validation()

    assert report["available"] is True
    assert report["ok"] is True


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


def test_template_has_agent_brief_human_surface() -> None:
    module = _module()
    assert 'id="s-agentbrief"' in module.TEMPLATE
    assert 'id="ab-kpi"' in module.TEMPLATE
    assert 'id="ab-objectives"' in module.TEMPLATE
    assert "D.agent_visibility" in module.TEMPLATE
    assert "/agent-brief.json" in module.TEMPLATE


def test_template_projects_claims_observation_progress() -> None:
    module = _module()
    host_template = module.ROOT / "bin/panorama/assets/host/template.html"
    html = host_template.read_text(encoding="utf-8")
    assert 'id="claims-observation-progress"' in html
    assert "D.claims_observation_progress" in html
    assert "claimsObjective.observation_progress" in html
    assert "samples '+" in html
    assert "不可补样或拼接窗口" in html


def test_panel_value_is_materialized_before_agent_visibility() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    panel_call = source.index("payload.update(_collect_panels(payload))")
    brief_call = source.index(
        'payload["agent_visibility"] = collect_agent_visibility(payload)'
    )

    assert panel_call < brief_call
