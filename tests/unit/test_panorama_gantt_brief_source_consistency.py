"""Actual native merge/publish with hermetic external collectors and bound artifacts."""
import ast
import copy
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("gantt_brief_fixtures", Path(__file__).with_name("test_panorama_agent_brief.py"))
helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(helpers)
STAMP = "2026-01-01T00:00:00Z"


def cohort():
    records = [{"id": "T16-B", "status": "pending", "track": "T16-DRIFT-GUARD", "window": "W1"},
               {"id": "DONE", "status": "done", "window": "W0"},
               {"id": "ACTIVE", "status": "in_progress", "window": "W1"}]
    return {"sha": "a"*40, "ledger_sha256": "b"*64, "observed_at": STAMP,
        "state": "PARTIAL", "source": "github://fixed/oid", "actual": 3,
        "counts": {"pending": 1, "done": 1, "in_progress": 1}, "bet_records": records}


def test_brief_counts_use_same_cohort_not_conflicting_native_ledger():
    module = helpers._module(); payload = helpers._payload(); payload["portfolio"] = cohort()
    payload["bets"]["total"] = 999
    payload["bets"]["in_progress"] = [{"id": "OTHER-ROOT"}]
    bets = module.collect_agent_visibility(payload)["work_state"]["bets"]
    assert bets["total"] == 3 and bets["counts"] == cohort()["counts"]
    assert [b["id"] for b in bets["in_progress"]] == ["ACTIVE"]
    assert bets["source_binding"]["sha"] == cohort()["sha"]
    assert bets["source_binding"]["ledger_sha256"] == cohort()["ledger_sha256"]
    assert bets["source_binding"]["observed_at"] == STAMP


def test_incomplete_or_conflicting_cohort_does_not_fall_back_to_other_bets():
    module = helpers._module(); payload = helpers._payload(); p = cohort(); p["counts"]["done"] = 200
    payload["portfolio"] = p
    bets = module.collect_agent_visibility(payload)["work_state"]["bets"]
    assert bets["available"] is False and bets["source_binding"]["reason"] == "portfolio_counts_conflict"
    del p["sha"]
    assert module._brief_bet_source(payload)[1]["reason"] == "portfolio_identity_incomplete"


def test_actual_build_assembles_current_cohort_before_brief(tmp_path, monkeypatch):
    module = helpers._module(); p = cohort()
    current = {"portfolio": p, "source_states": {"portfolio": {"status": "PARTIAL", "observed_at": STAMP},
        "agent_brief": {"status": "OK", "observed_at": "previous"}},
        "gantt": {key: p[key] for key in ("sha", "ledger_sha256", "observed_at")},
        "strategic": {"trace": {"nodes": [], "edges": []}}, "generation_id": "cohort-fixed"}
    (tmp_path/"current.json").write_text(json.dumps(current))
    monkeypatch.setenv("ZHIXING_DASHBOARD_CODE_ROOT", str(tmp_path))
    # Keep native build and Brief derivation real; only external IO is replaced.
    names = {n.func.id for n in ast.walk(ast.parse(inspect.getsource(module.build_payload)))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and (n.func.id.startswith("collect_") or n.func.id == "_collect_panels")}
    for name in names - {"collect_agent_visibility"}:
        monkeypatch.setattr(module, name, lambda *args, **kwargs: {})
    monkeypatch.setattr(module, "collect_bets", lambda: {"total": 999, "counts": {"done": 999}})
    payload = module.build_payload()
    assert payload["agent_visibility"]["work_state"]["bets"]["counts"] == p["counts"]
    assert payload["bets"]["total"] == 3 and payload["generation_id"] == "cohort-fixed"
    assert payload["agent_visibility"]["work_state"]["bets"]["source_binding"]["observed_at"] == STAMP
    current["gantt"]["sha"] = "c"*40
    (tmp_path/"current.json").write_text(json.dumps(current))
    rejected = module.build_payload()
    assert rejected["gantt"]["state"] == "UNPROVABLE"
    assert rejected["source_states"]["gantt"]["reason"] == "gantt_portfolio_source_mismatch"


def test_actual_revision_final_bytes_match_aliases_clock_and_external_digest(tmp_path, monkeypatch):
    module = helpers._module(); payload = helpers._publishable_payload(module)
    payload["portfolio"] = cohort()
    payload["gantt"] = {key: payload["portfolio"][key] for key in ("sha", "ledger_sha256", "observed_at")}
    payload["generation_id"] = "fixed-cohort"
    payload["source_states"] = {"agent_brief": {"observed_at": "previous", "sha256": "previous-hash"},
                                "workflow": {"status": "DEGRADED", "observed_at": STAMP}}
    original = copy.deepcopy(payload)
    result, revision = helpers._publish(module, monkeypatch, tmp_path, payload)
    body = (revision/"agent-brief.json").read_bytes()
    data = json.loads((revision/"data.json").read_bytes()); brief = json.loads(body)
    manifest = json.loads((revision/"manifest.json").read_bytes())
    assert brief == data["agent_visibility"] == data["agent_brief"]
    assert brief["next_actions"] == data["next_actions"]
    assert brief["generated_at"] == data["generated_at"] == manifest["generated_at"]
    assert data["assembled_at"] == original["generated_at"]
    assert brief["generation_id"] == data["generation_id"] == "fixed-cohort"
    assert brief["input_sources"]["portfolio"]["observed_at"] == STAMP
    assert data["source_states"]["agent_brief"]["sha256"] == hashlib.sha256(body).hexdigest() == manifest["artifacts"]["agent_brief"]["sha256"]
    assert data["source_states"]["agent_brief_feedback"]["observed_at"] == "previous"
    assert data["source_states"]["workflow"] == original["source_states"]["workflow"]
    assert brief["authority"]["value_proof"] == "NOT_PROVEN"
    assert brief["authority"]["value_proof_readiness"]["qualifying_samples"] == 0
    assert all("native Workflow" in a["execution_authority"] for a in brief["next_actions"])
    assert payload == original, "publisher must not mutate its input cohort or clocks"


def test_failed_portfolio_source_keeps_old_clock_error_and_advisory_actions():
    module = helpers._module(); payload = helpers._payload(); payload["portfolio"] = cohort()
    payload["portfolio"]["state"] = "OBSERVED"
    payload["source_states"] = {"portfolio": {"status": "STALE_UNAVAILABLE", "error": "timeout",
        "observed_at": STAMP, "last_attempt_at": "new-attempt", "last_success_at": "old-success"}}
    brief = module.collect_agent_visibility(payload)
    source = brief["work_state"]["bets"]["source_binding"]
    assert source["state"] == "STALE_UNAVAILABLE" and source["observed_at"] == STAMP
    assert source["error"] == "timeout" and source["last_attempt_at"] == "new-attempt"
    assert source["last_success_at"] == "old-success"
    actions = [a for a in brief["next_actions"] if a["id"] == "continue-active-bets"]
    assert actions and all(a["state"] == "advisory" for a in actions)


def test_actual_final_value_binding_changes_actions_before_digest(tmp_path, monkeypatch):
    module = helpers._module(); payload = helpers._publishable_payload(module)
    payload["portfolio"] = cohort()
    payload["panel_value"]["state"] = "proven"
    payload["panel_value"]["samples"]["qualifying"] = 30
    payload["value_evidence_validation"].update(ok=True, qualifying=30, v2_records=30)
    assert not any(a["id"] == "collect-qualifying-value-evidence" for a in module.collect_agent_visibility(payload)["next_actions"])
    result, revision = helpers._publish(module, monkeypatch, tmp_path, payload)
    data = json.loads((revision/"data.json").read_bytes()); body = (revision/"agent-brief.json").read_bytes(); brief = json.loads(body)
    assert brief["authority"]["value_proof"] == "NOT_PROVEN"
    assert brief["authority"]["value_proof_readiness"]["qualifying_samples"] == 0
    action = next(a for a in brief["next_actions"] if a["id"] == "collect-qualifying-value-evidence")
    assert "30 more qualifying" in action["detail"]
    assert brief["next_actions"] == data["next_actions"]
    assert data["source_states"]["agent_brief"]["sha256"] == hashlib.sha256(body).hexdigest()


def test_unavailable_brief_is_not_healthy_assembly_component(tmp_path, monkeypatch):
    module = helpers._module(); payload = helpers._publishable_payload(module)
    payload.pop("agent_visibility")
    result, revision = helpers._publish(module, monkeypatch, tmp_path, payload)
    data = json.loads((revision/"data.json").read_bytes()); brief = json.loads((revision/"agent-brief.json").read_bytes())
    assert brief["available"] is False
    assert data["source_states"]["agent_brief"]["status"] == "UNAVAILABLE"
    assert data["source_states"]["agent_brief"]["last_success_at"] is None
