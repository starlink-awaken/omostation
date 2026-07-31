"""Tests for cockpit.web.api_proposals — 22% coverage file."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    from cockpit.web.api_proposals import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


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
            patch("cockpit.compat.WORKSPACE_ROOT", tmp_path),
            patch("cockpit.web.api_proposals.approve_hitl_proposal_async", return_value=(True, None)),
        ):
            resp = client.post("/api/v1/proposals/p1/approve")
        assert resp.status_code == 200
        assert "approved" in resp.json()["message"]

    def test_approve_not_found(self, client, tmp_path):
        with (
            patch("cockpit.compat.WORKSPACE_ROOT", tmp_path),
            patch("cockpit.web.api_proposals.approve_hitl_proposal_async", return_value=(False, "Proposal not found")),
        ):
            resp = client.post("/api/v1/proposals/bad-id/approve")
        assert resp.status_code == 404


class TestRejectProposal:
    def test_reject_ok(self, client, tmp_path):
        with patch("cockpit.compat.WORKSPACE_ROOT", tmp_path), patch("cockpit.web.api_proposals.reject_hitl_proposal"):
            resp = client.post("/api/v1/proposals/p1/reject")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


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
        async def mock_approve(omo_dir, pid, execute_mutation):
            proposal = {"type": "budget_increase", "debt_id": "d1"}
            result = await execute_mutation(proposal)
            return (result, None) if result else (False, "failed")

        with (
            patch("cockpit.compat.WORKSPACE_ROOT", tmp_path),
            patch("cockpit.web.api_proposals.append_hitl_override") as mock_append,
            patch("cockpit.web.api_proposals.approve_hitl_proposal_async", side_effect=mock_approve),
        ):
            resp = client.post("/api/v1/proposals/p1/approve")
        assert resp.status_code == 200
        assert mock_append.called
        # Verify the record written
        call_args = mock_append.call_args
        assert call_args[0][1] == "budget_overrides.jsonl"
        assert call_args[0][2]["action"] == "increase_limit"
        assert call_args[0][2]["amount_usd"] == 0.10

    def test_approve_model_swap(self, client, tmp_path):
        async def mock_approve(omo_dir, pid, execute_mutation):
            proposal = {"type": "model_swap", "debt_id": "d2", "target_model": "claude-3-opus"}
            result = await execute_mutation(proposal)
            return (result, None) if result else (False, "failed")

        with (
            patch("cockpit.compat.WORKSPACE_ROOT", tmp_path),
            patch("cockpit.web.api_proposals.append_hitl_override") as mock_append,
            patch("cockpit.web.api_proposals.approve_hitl_proposal_async", side_effect=mock_approve),
        ):
            resp = client.post("/api/v1/proposals/p2/approve")
        assert resp.status_code == 200
        call_args = mock_append.call_args
        assert call_args[0][1] == "model_overrides.jsonl"
        assert call_args[0][2]["action"] == "swap_model"
        assert call_args[0][2]["target_model"] == "claude-3-opus"

    def test_approve_quota_reset(self, client, tmp_path):
        async def mock_approve(omo_dir, pid, execute_mutation):
            proposal = {"type": "quota_reset", "debt_id": "d3", "scope": "project"}
            result = await execute_mutation(proposal)
            return (result, None) if result else (False, "failed")

        with (
            patch("cockpit.compat.WORKSPACE_ROOT", tmp_path),
            patch("cockpit.web.api_proposals.append_hitl_override") as mock_append,
            patch("cockpit.web.api_proposals.approve_hitl_proposal_async", side_effect=mock_approve),
        ):
            resp = client.post("/api/v1/proposals/p3/approve")
        assert resp.status_code == 200
        call_args = mock_append.call_args
        assert call_args[0][1] == "quota_resets.jsonl"
        assert call_args[0][2]["action"] == "reset_quota"
        assert call_args[0][2]["scope"] == "project"

    def test_approve_plugin_dispatch(self, client, tmp_path):
        """Test the BOS URI hook plugin mechanism for unknown proposal types."""

        async def mock_approve(omo_dir, pid, execute_mutation):
            proposal = {"type": "custom_action", "debt_id": "d4"}
            result = await execute_mutation(proposal)
            return (result, None) if result else (False, "No execution logic")

        async def mock_resolve(uri, proposal):
            return {"status": "ok", "resolved": True}

        with (
            patch("cockpit.compat.WORKSPACE_ROOT", tmp_path),
            patch("cockpit.web.api_proposals.approve_hitl_proposal_async", side_effect=mock_approve),
            patch("cockpit.adapters.agora.resolve_bos_uri", side_effect=mock_resolve),
            patch("cockpit.web.api_proposals.append_hitl_override") as mock_append,
        ):
            resp = client.post("/api/v1/proposals/p4/approve")
        assert resp.status_code == 200
        # Plugin handled it, so append should NOT be called for custom types
        assert not mock_append.called

    def test_approve_plugin_dispatch_fails(self, client, tmp_path):
        """Test plugin dispatch failure falls through to return False."""

        async def mock_approve(omo_dir, pid, execute_mutation):
            proposal = {"type": "unknown_type", "debt_id": "d5"}
            result = await execute_mutation(proposal)
            return (result, None) if result else (False, "No execution logic: unknown_type")

        async def mock_resolve(uri, proposal):
            raise Exception("Plugin not found")

        with (
            patch("cockpit.compat.WORKSPACE_ROOT", tmp_path),
            patch("cockpit.web.api_proposals.approve_hitl_proposal_async", side_effect=mock_approve),
            patch("cockpit.adapters.agora.resolve_bos_uri", side_effect=mock_resolve),
        ):
            resp = client.post("/api/v1/proposals/p5/approve")
        assert resp.status_code == 400
        assert "No execution logic" in resp.json()["error"]


class TestApproveErrorPaths:
    """Test remaining error paths in api_approve_proposal."""

    def test_approve_already_processing(self, client, tmp_path):
        with (
            patch("cockpit.compat.WORKSPACE_ROOT", tmp_path),
            patch(
                "cockpit.web.api_proposals.approve_hitl_proposal_async",
                return_value=(False, "Proposal already being processed"),
            ),
        ):
            resp = client.post("/api/v1/proposals/p1/approve")
        assert resp.status_code == 409
        assert "already being processed" in resp.json()["error"]

    def test_approve_generic_error(self, client, tmp_path):
        with (
            patch("cockpit.compat.WORKSPACE_ROOT", tmp_path),
            patch("cockpit.web.api_proposals.approve_hitl_proposal_async", return_value=(False, "Some random error")),
        ):
            resp = client.post("/api/v1/proposals/p1/approve")
        assert resp.status_code == 500
        assert resp.json()["error"] == "Some random error"
