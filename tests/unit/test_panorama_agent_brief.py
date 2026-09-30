import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


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
            "legacy_records": 2,
            "legacy_qualifying": 0,
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
    assert value["schema"] == "panorama-value-proof-readiness/v2"
    assert value["v2_records"] == 0
    assert value["legacy_records"] == 2
    assert value["remaining_to_target"] == 30
    assert value["legacy_qualifying_samples"] == 0
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


def test_agent_visibility_value_target_ignores_legacy_qualifying() -> None:
    module = _module()
    payload = _payload()
    payload["panel_value"]["samples"]["qualifying"] = 1
    payload["value_evidence_validation"]["legacy_records"] = 1
    payload["value_evidence_validation"]["legacy_qualifying"] = 1
    payload["value_evidence_validation"]["v2_records"] = 0
    payload["value_evidence_validation"]["qualifying"] = 0

    value = module.collect_agent_visibility(payload)["authority"]["value_proof_readiness"]

    assert value["schema"] == "panorama-value-proof-readiness/v2"
    assert value["qualifying_samples"] == 0
    assert value["v2_records"] == 0
    assert value["legacy_records"] == 1
    assert value["legacy_qualifying_samples"] == 1
    assert value["remaining_to_target"] == 30
    assert value["next_action"] == (
        "Collect 30 more qualifying real-use records with a frozen baseline; do not backfill."
    )


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


# ---------------------------------------------------------------------------
# 投影 revision 发布契约 (2026-09-30)
#
# 取代已失效的 `test_write_site_emits_data_and_agent_brief`:
# `write_site` 在投影 revision 重构中被 `publish_projection_revision` 取代, 而该测试
# 未被登记为 known-broken —— 它稳定失败却长期未被发现, 说明全量单测其实并不卡合并。
#
# 新旧写出契约的**产物集其实没变** (仍是 index.html / data.json / agent-brief.json),
# 变的是落位与绑定方式:
#     旧: write_site(payload) -> <OUT_DIR>/{三个产物}
#     新: publish_projection_revision(payload, state_root=R)
#           -> R/revisions/<revision_id>/{三个产物 + manifest.json}
#           -> R/current-revision.json  (指针: revision_id + manifest_sha256)
#
# 新协议的不可变性(只创建不覆盖)、hash 绑定、原子指针切换、幂等重放, 正是原测试
# 完全没覆盖、而实际会出问题的地方。
#
# 取舍: 只 stub 依赖真实 claims root / event ledger / git / dashboard 的**外部采集器**,
# revision 组装 / manifest 计算 / sha256 绑定 / 指针切换全部走真实实现。把这些也 mock
# 掉的话测试会「通过」却什么都没证明。
# ---------------------------------------------------------------------------


def _publishable_payload(module):
    """补齐 `_validate_payload_claims_binding` 要求的 claims 投影字段。

    刻意**不** mock 掉该校验 —— 它是「payload 里的 claims 状态必须与真实
    source_binding 一致」的唯一执行点。mock 掉就等于把这条契约一起测没了。
    """
    payload = _payload()
    payload["agent_visibility"] = module.collect_agent_visibility(payload)
    authority = payload["claims_authority"]
    authority["available"] = True
    authority["sequence"] = 7
    authority["status"] = {"last_receipt_digest": "sha256:STUB-RECEIPT"}
    return payload


def _expected_claims(payload) -> dict:
    projected = payload["claims_authority"]
    return {
        "sequence": projected.get("sequence"),
        "last_receipt": projected["status"].get("last_receipt_digest"),
        "activation": projected.get("activation_state"),
        "effective_authority": projected.get("effective_claim_authority"),
        "instruction_capable": projected.get("instruction_capable"),
    }


def _stub_external_collectors(module, monkeypatch, payload, *, ledger_sha: str = "sha256:STUB-LEDGER"):
    monkeypatch.setattr(
        module,
        "collect_projection_source_binding",
        lambda **kw: {
            "source_hashes": {"event_ledger_sha256": ledger_sha},
            "claims": _expected_claims(payload),
        },
    )
    monkeypatch.setattr(
        module,
        "collect_personal_value_truth",
        lambda **kw: {"event_ledger_sha256": ledger_sha, "available": True},
    )
    monkeypatch.setattr(
        module, "collect_projection_producer_identity", lambda **kw: {"producer": "stub"}
    )
    monkeypatch.setattr(
        module, "collect_projection_dashboard_identity", lambda **kw: {"dashboard": "stub"}
    )


def _publish(module, monkeypatch, tmp_path, payload):
    """在干净 state_root 上发布一次, 返回 (result, revision_dir)。"""
    # 固定模板来源: 不指向真实 dashboard 仓, 退回内嵌 TEMPLATE, 避免受本机环境影响
    monkeypatch.setenv("ZHIXING_DASHBOARD_CODE_ROOT", str(tmp_path / "no-dashboard"))
    _stub_external_collectors(module, monkeypatch, payload)
    state_root = tmp_path / "projection-state"
    result = module.publish_projection_revision(payload, state_root=state_root)
    return result, state_root / module.PROJECTION_REVISIONS_NAME / result["revision_id"]


def test_publish_projection_revision_emits_data_and_agent_brief(tmp_path, monkeypatch) -> None:
    module = _module()
    _, revision = _publish(module, monkeypatch, tmp_path, _publishable_payload(module))

    assert revision.is_dir()
    data = json.loads((revision / "data.json").read_text(encoding="utf-8"))
    brief = json.loads((revision / "agent-brief.json").read_text(encoding="utf-8"))
    assert data["agent_visibility"]["schema"] == "panorama-agent-brief/v1"
    assert brief["schema"] == "panorama-agent-brief/v1"
    assert (revision / "index.html").is_file()
    # agent-brief.json 就是 agent_visibility 本身, 不是整个 payload
    assert brief == data["agent_visibility"]


def test_manifest_binds_every_artifact_by_sha256(tmp_path, monkeypatch) -> None:
    """没有这条, 产物可以在不自知的情况下被改, 而指针仍指向它。"""
    module = _module()
    _, revision = _publish(module, monkeypatch, tmp_path, _publishable_payload(module))

    manifest = json.loads((revision / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["artifacts"], "manifest 必须登记产物"
    for name, meta in manifest["artifacts"].items():
        body = (revision / meta["filename"]).read_bytes()
        assert meta["sha256"] == hashlib.sha256(body).hexdigest(), name


def test_pointer_points_at_published_revision(tmp_path, monkeypatch) -> None:
    module = _module()
    result, revision = _publish(module, monkeypatch, tmp_path, _publishable_payload(module))

    pointer = json.loads(
        (revision.parent.parent / module.PROJECTION_POINTER_NAME).read_text(encoding="utf-8")
    )
    assert pointer["schema_version"] == module.PROJECTION_POINTER_SCHEMA
    assert pointer["revision_id"] == result["revision_id"]
    assert pointer["manifest_sha256"] == result["manifest_sha256"]
    body = (revision / "manifest.json").read_bytes()
    assert pointer["manifest_sha256"] == hashlib.sha256(body).hexdigest()


def test_republish_same_payload_is_idempotent_not_collision(tmp_path, monkeypatch) -> None:
    module = _module()
    payload = _publishable_payload(module)
    first, first_rev = _publish(module, monkeypatch, tmp_path, payload)
    second, second_rev = _publish(module, monkeypatch, tmp_path, payload)

    assert first["revision_id"] == second["revision_id"]
    assert first["manifest_sha256"] == second["manifest_sha256"]
    assert first_rev == second_rev
    revisions = first_rev.parent
    assert len([p for p in revisions.iterdir() if p.is_dir()]) == 1
    assert not [p for p in revisions.iterdir() if p.name.startswith(".staging-")]


def test_claims_binding_mismatch_fails_closed(tmp_path, monkeypatch) -> None:
    """payload 的 claims 与 source_binding 不一致时必须拒发 —— 不得写出半真 revision。"""
    module = _module()
    payload = _publishable_payload(module)
    # binding 必须用**未篡改**的快照冻结, 否则它跟着 payload 一起变, 永远自洽
    _stub_external_collectors(module, monkeypatch, _publishable_payload(module))
    monkeypatch.setenv("ZHIXING_DASHBOARD_CODE_ROOT", str(tmp_path / "no-dashboard"))
    payload["claims_authority"]["activation_state"] = "shadow-active"  # 与冻结的 binding 不符
    state_root = tmp_path / "projection-state"

    with pytest.raises(RuntimeError, match="projection_payload_claims_mismatch"):
        module.publish_projection_revision(payload, state_root=state_root)
    assert not (state_root / module.PROJECTION_POINTER_NAME).exists(), "拒发时不得留下指针"


def test_missing_agent_visibility_publishes_explicit_unavailable_brief(tmp_path, monkeypatch) -> None:
    """没有 agent_visibility 时必须显式产出 available:false 的 brief, 而不是空文件。"""
    module = _module()
    payload = _publishable_payload(module)
    payload.pop("agent_visibility")
    _, revision = _publish(module, monkeypatch, tmp_path, payload)
    brief = json.loads((revision / "agent-brief.json").read_text(encoding="utf-8"))
    assert brief["schema"] == "panorama-agent-brief/v1"
    assert brief["available"] is False
    # 发布器仍会补上 value_proof 绑定, 因此不是空壳
    assert isinstance(brief["authority"]["value_proof"], str)
    assert brief["authority"]["value_proof"]


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


def test_claims_lifecycle_authorization_projects_pending_request(tmp_path, monkeypatch) -> None:
    module = _module()
    package = {
        "schema": "claims-authority-lifecycle-authorization-request/v1",
        "status": "DRAFT_PENDING_HUMAN_APPROVAL",
        "authority_id": "omo-claims-authority-r0",
        "activation_binding": {
            "activation_receipt_digest": "sha256:receipt",
            "descriptor_digest": "sha256:descriptor",
            "authority_epoch": 1,
            "activation_state": "shadow-active",
        },
        "operations": [{"id": "managed-clone-shadow-observation"}],
        "global_forbidden": ["force push"],
        "stop_conditions": ["remote OID drift"],
    }
    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps(package), encoding="utf-8")
    review = tmp_path / "review.md"
    review.write_text("review", encoding="utf-8")
    runbook = tmp_path / "runbook.md"
    runbook.write_text("runbook", encoding="utf-8")
    gap = tmp_path / "gap.json"
    gap.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(module, "CLAIMS_LIFECYCLE_AUTHORIZATION_PACKAGE", draft)
    monkeypatch.setattr(module, "CLAIMS_LIFECYCLE_REVIEW", review)
    monkeypatch.setattr(module, "CLAIMS_LIFECYCLE_RUNBOOK", runbook)
    monkeypatch.setattr(module, "CLAIMS_LIFECYCLE_GAP_AUDIT", gap)

    report = module.collect_claims_lifecycle_authorization()

    assert report["available"] is True
    assert report["read_only"] is True
    assert report["execution"] == "NOT_EXECUTED"
    assert report["status"] == "DRAFT_PENDING_HUMAN_APPROVAL"
    assert report["operations"][0]["id"] == "managed-clone-shadow-observation"
    assert all(item["available"] for item in report["artifacts"].values())
    assert all(value.startswith("sha256:") for value in (
        report["artifacts"]["draft"]["sha256"],
        report["artifacts"]["review"]["sha256"],
        report["artifacts"]["runbook"]["sha256"],
        report["artifacts"]["gap_audit"]["sha256"],
    ))


def test_template_projects_claims_lifecycle_authorization() -> None:
    module = _module()
    host_template = module.ROOT / "bin/panorama/assets/host/template.html"
    html = host_template.read_text(encoding="utf-8")
    assert 'id="claims-lifecycle-authorization"' in html
    assert "D.claims_lifecycle_authorization" in html
    assert "operation-specific human approval" in html


def test_panel_value_is_materialized_before_agent_visibility() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    panel_call = source.index("payload.update(_collect_panels(payload))")
    brief_call = source.index(
        'payload["agent_visibility"] = collect_agent_visibility(payload)'
    )

    assert panel_call < brief_call


def test_resolve_failing_gates_action_stays_within_rendered_fields() -> None:
    module = _module()
    brief = module.collect_agent_visibility(_payload())
    action = next(a for a in brief["next_actions"] if a["id"] == "resolve-failing-gates")

    # The host template renders only title|id, detail|gate|description, owner|source
    # and state, so any other key is unread dead data.
    assert set(action) <= {
        "id", "title", "state", "detail", "gate", "description", "owner", "source",
    }
    assert "gate-health-check.py" in action["detail"]
    assert "point-in-time snapshot" in action["detail"]


def test_resolve_failing_gates_action_absent_when_all_gates_pass() -> None:
    module = _module()
    payload = _payload()
    payload["gates"] = [
        {"id": "A1", "title": "Workflow", "verdict": "PASS", "live": True},
        {"id": "A2", "title": "Host", "verdict": "PASS", "live": True},
    ]
    brief = module.collect_agent_visibility(payload)

    assert "resolve-failing-gates" not in {a["id"] for a in brief["next_actions"]}
