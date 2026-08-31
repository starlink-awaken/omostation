"""Tests for cockpit.web.api_proposals — 22% coverage file."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import auth


@pytest.fixture
def app():
    from cockpit.web.api_proposals import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app, headers={"X-Api-Key": "valid-secret"})


@pytest.fixture(autouse=True)
def configured_api_key(monkeypatch):
    monkeypatch.setenv("COCKPIT_API_KEY", "valid-secret")
    auth.reload_api_keys()
    yield
    auth.reload_api_keys()


def test_adapter_reexports_canonical_proposal_writer_without_fallback():
    import omo.omo_cockpit_bridge as canonical

    import cockpit.adapters.omo as adapter

    source = inspect.getsource(adapter)
    assert "def _proposal_dir" not in source
    assert adapter.record_hitl_proposal is canonical.record_hitl_proposal
    assert adapter.approve_hitl_proposal_async is canonical.approve_hitl_proposal_async


def test_create_proposal_requires_family_documents_scope(app):
    response = TestClient(app).post("/api/v1/proposals", json={"id": "p1"})
    assert response.status_code == 401


def test_authenticated_create_records_pending_proposal(client, monkeypatch, tmp_path):
    from cockpit.web import api_proposals

    captured = {}

    def record(_omo, proposal, *, requested_by, now):
        captured.update({"proposal": proposal, "requested_by": requested_by, "now": now})
        return proposal

    monkeypatch.setattr(api_proposals, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(api_proposals, "record_hitl_proposal", record)
    response = client.post("/api/v1/proposals", json={"id": "family-write-1"})
    assert response.status_code == 202
    assert response.json() == {"status": "pending", "proposal_id": "family-write-1"}
    assert captured["requested_by"].startswith("operator://cockpit-api/")


def test_authenticated_create_rejects_malformed_json(client):
    response = client.post(
        "/api/v1/proposals",
        content="{broken",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "proposal_object_required"


def test_approve_uses_authenticated_principal_not_body_actor(client, monkeypatch):
    from cockpit.web import api_proposals

    captured = {}

    async def approve(_omo, _proposal_id, *, principal_ref, approved_at, execute_mutation):
        captured["principal_ref"] = principal_ref
        return True, None, {"status": "verified"}

    monkeypatch.setattr(api_proposals, "approve_hitl_proposal_async", approve)
    response = client.post("/api/v1/proposals/p1/approve", json={"approved_by": "attacker"})
    assert response.status_code == 200
    assert captured["principal_ref"].startswith("operator://cockpit-api/")
    assert captured["principal_ref"] != "attacker"


@pytest.mark.asyncio
async def test_bos_error_or_unverified_result_is_not_success(monkeypatch):
    from cockpit.web import api_proposals

    monkeypatch.setattr(
        api_proposals,
        "resolve_bos_uri",
        AsyncMock(return_value={"status": "ok", "result": {"status": "rolled_back"}}),
        raising=False,
    )
    assert await api_proposals._execute_mutation({"type": "family_dashboard_document_write"}) == {
        "status": "rolled_back"
    }


class TestListProposals:
    def test_list_empty(self, client, tmp_path):
        with (
            patch("cockpit.compat.WORKSPACE_ROOT", tmp_path),
            patch("cockpit.web.api_proposals.list_hitl_proposals", return_value=[]),
        ):
            resp = client.get("/api/v1/proposals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["proposals"] == []

    def test_list_with_proposals(self, client, tmp_path):
        proposals = [{"id": "p1", "type": "budget_increase"}]
        with (
            patch("cockpit.compat.WORKSPACE_ROOT", tmp_path),
            patch("cockpit.web.api_proposals.list_hitl_proposals", return_value=proposals),
        ):
            resp = client.get("/api/v1/proposals")
        assert resp.status_code == 200
        assert len(resp.json()["proposals"]) == 1


class TestApproveProposal:
    def test_approve_ok(self, client, tmp_path):
        with (
            patch("cockpit.web.api_proposals.WORKSPACE_ROOT", tmp_path),
            patch(
                "cockpit.web.api_proposals.approve_hitl_proposal_async",
                return_value=(True, None, {"status": "verified"}),
            ),
        ):
            resp = client.post("/api/v1/proposals/p1/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "verified"

    def test_approve_not_found(self, client, tmp_path):
        with (
            patch("cockpit.web.api_proposals.WORKSPACE_ROOT", tmp_path),
            patch(
                "cockpit.web.api_proposals.approve_hitl_proposal_async",
                return_value=(False, "Proposal not found", None),
            ),
        ):
            resp = client.post("/api/v1/proposals/bad-id/approve")
        assert resp.status_code == 404


class TestRejectProposal:
    def test_reject_ok(self, client, tmp_path):
        with (
            patch("cockpit.web.api_proposals.WORKSPACE_ROOT", tmp_path),
            patch("cockpit.web.api_proposals.reject_hitl_proposal", return_value={"status": "rejected"}),
        ):
            resp = client.post("/api/v1/proposals/p1/reject")
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"


class TestListProposalsError:
    def test_list_exception_returns_empty(self, client, tmp_path):
        with (
            patch("cockpit.compat.WORKSPACE_ROOT", tmp_path),
            patch("cockpit.web.api_proposals.list_hitl_proposals", side_effect=Exception("boom")),
        ):
            resp = client.get("/api/v1/proposals")
        assert resp.status_code == 200
        assert resp.json()["proposals"] == []


class TestApproveMutationFlows:
    """Test _execute_mutation through the approve endpoint with different proposal types."""

    def test_approve_budget_increase(self, client, tmp_path):
        async def mock_approve(_omo, _pid, *, principal_ref, approved_at, execute_mutation):
            proposal = {"id": "p1", "type": "budget_increase", "debt_id": "d1"}
            result = await execute_mutation(proposal)
            return result["status"] == "verified", None, result

        receipt = tmp_path / ".omo" / "_delivery" / "hitl" / "overrides" / "p1.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text("{}\n", encoding="utf-8")

        with (
            patch("cockpit.web.api_proposals.WORKSPACE_ROOT", tmp_path),
            patch("cockpit.web.api_proposals.append_hitl_override", return_value=str(receipt)) as mock_append,
            patch("cockpit.web.api_proposals.approve_hitl_proposal_async", side_effect=mock_approve),
        ):
            resp = client.post("/api/v1/proposals/p1/approve")
        assert resp.status_code == 200
        assert mock_append.called
        # Verify the record written
        call_args = mock_append.call_args
        assert call_args[0][1] == "budget_overrides.jsonl"
        assert call_args[0][2]["proposal_id"] == "p1"
        assert call_args[0][2]["action"] == "increase_limit"
        assert call_args[0][2]["amount_usd"] == 0.10

    def test_approve_model_swap(self, client, tmp_path):
        async def mock_approve(_omo, _pid, *, principal_ref, approved_at, execute_mutation):
            proposal = {
                "id": "p2",
                "type": "model_swap",
                "debt_id": "d2",
                "target_model": "claude-3-opus",
            }
            result = await execute_mutation(proposal)
            return result["status"] == "verified", None, result

        receipt = tmp_path / ".omo" / "_delivery" / "hitl" / "overrides" / "p2.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text("{}\n", encoding="utf-8")

        with (
            patch("cockpit.web.api_proposals.WORKSPACE_ROOT", tmp_path),
            patch("cockpit.web.api_proposals.append_hitl_override", return_value=str(receipt)) as mock_append,
            patch("cockpit.web.api_proposals.approve_hitl_proposal_async", side_effect=mock_approve),
        ):
            resp = client.post("/api/v1/proposals/p2/approve")
        assert resp.status_code == 200
        call_args = mock_append.call_args
        assert call_args[0][1] == "model_overrides.jsonl"
        assert call_args[0][2]["proposal_id"] == "p2"
        assert call_args[0][2]["action"] == "swap_model"
        assert call_args[0][2]["target_model"] == "claude-3-opus"

    def test_approve_quota_reset(self, client, tmp_path):
        async def mock_approve(_omo, _pid, *, principal_ref, approved_at, execute_mutation):
            proposal = {"id": "p3", "type": "quota_reset", "debt_id": "d3", "scope": "project"}
            result = await execute_mutation(proposal)
            return result["status"] == "verified", None, result

        receipt = tmp_path / ".omo" / "_delivery" / "hitl" / "overrides" / "p3.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text("{}\n", encoding="utf-8")

        with (
            patch("cockpit.web.api_proposals.WORKSPACE_ROOT", tmp_path),
            patch("cockpit.web.api_proposals.append_hitl_override", return_value=str(receipt)) as mock_append,
            patch("cockpit.web.api_proposals.approve_hitl_proposal_async", side_effect=mock_approve),
        ):
            resp = client.post("/api/v1/proposals/p3/approve")
        assert resp.status_code == 200
        call_args = mock_append.call_args
        assert call_args[0][1] == "quota_resets.jsonl"
        assert call_args[0][2]["proposal_id"] == "p3"
        assert call_args[0][2]["action"] == "reset_quota"
        assert call_args[0][2]["scope"] == "project"

    def test_approve_plugin_dispatch(self, client, tmp_path):
        """Test the BOS URI hook plugin mechanism for unknown proposal types."""

        async def mock_approve(_omo, _pid, *, principal_ref, approved_at, execute_mutation):
            proposal = {"id": "p4", "type": "custom_action", "debt_id": "d4"}
            result = await execute_mutation(proposal)
            return result["status"] == "verified", None, result

        async def mock_resolve(uri, *, proposal):
            return {
                "status": "ok",
                "result": {
                    "status": "verified",
                    "verify_receipt_ref": "mutations/p4/verify.json",
                    "verify_receipt_sha256": "sha256:" + "c" * 64,
                },
            }

        with (
            patch("cockpit.web.api_proposals.WORKSPACE_ROOT", tmp_path),
            patch("cockpit.web.api_proposals.approve_hitl_proposal_async", side_effect=mock_approve),
            patch("cockpit.web.api_proposals.resolve_bos_uri", side_effect=mock_resolve),
            patch("cockpit.web.api_proposals.append_hitl_override") as mock_append,
        ):
            resp = client.post("/api/v1/proposals/p4/approve")
        assert resp.status_code == 200
        # Plugin handled it, so append should NOT be called for custom types
        assert not mock_append.called

    def test_approve_plugin_dispatch_fails(self, client, tmp_path):
        """Test plugin dispatch failure falls through to return False."""

        async def mock_approve(_omo, _pid, *, principal_ref, approved_at, execute_mutation):
            proposal = {"id": "p5", "type": "unknown_type", "debt_id": "d5"}
            result = await execute_mutation(proposal)
            return False, result.get("error", "bos_execution_failed"), None

        async def mock_resolve(uri, *, proposal):
            return {"status": "error"}

        with (
            patch("cockpit.web.api_proposals.WORKSPACE_ROOT", tmp_path),
            patch("cockpit.web.api_proposals.approve_hitl_proposal_async", side_effect=mock_approve),
            patch("cockpit.web.api_proposals.resolve_bos_uri", side_effect=mock_resolve),
        ):
            resp = client.post("/api/v1/proposals/p5/approve")
        assert resp.status_code == 400
        assert resp.json()["error"] == "bos_execution_failed"


class TestApproveErrorPaths:
    """Test remaining error paths in api_approve_proposal."""

    def test_approve_already_processing(self, client, tmp_path):
        with (
            patch("cockpit.web.api_proposals.WORKSPACE_ROOT", tmp_path),
            patch(
                "cockpit.web.api_proposals.approve_hitl_proposal_async",
                return_value=(False, "Proposal already being processed", None),
            ),
        ):
            resp = client.post("/api/v1/proposals/p1/approve")
        assert resp.status_code == 409
        assert "already being processed" in resp.json()["error"]

    def test_approve_generic_error(self, client, tmp_path):
        with (
            patch("cockpit.web.api_proposals.WORKSPACE_ROOT", tmp_path),
            patch(
                "cockpit.web.api_proposals.approve_hitl_proposal_async",
                return_value=(False, "Some random error", None),
            ),
        ):
            resp = client.post("/api/v1/proposals/p1/approve")
        assert resp.status_code == 400
        assert resp.json()["error"] == "Some random error"
