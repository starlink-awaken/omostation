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
