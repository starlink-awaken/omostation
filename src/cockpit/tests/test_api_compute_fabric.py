"""Unit tests for cockpit compute fabric API endpoints."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web.api_compute import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_api_compute_fabric_status() -> None:
    fake_data = {
        "schema_version": "1",
        "data": {
            "thermal_pressure": "nominal",
            "supported_tiers": ["fast", "standard", "reasoning"],
            "cache_stats": {"hit_rate": 0.85},
        },
    }
    mock_proc = MagicMock(returncode=0, stdout=json.dumps(fake_data), stderr="")

    with patch("subprocess.run", return_value=mock_proc):
        resp = client.get("/api/governance/compute/fabric")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["data"]["thermal_pressure"] == "nominal"
        assert payload["data"]["cache_stats"]["hit_rate"] == 0.85


def test_api_compute_fabric_warm() -> None:
    fake_data = {
        "schema_version": "1",
        "data": {
            "model_id": "coding",
            "warmed_count": 3,
            "estimated_saved_tokens": 120,
        },
    }
    mock_proc = MagicMock(returncode=0, stdout=json.dumps(fake_data), stderr="")

    with patch("subprocess.run", return_value=mock_proc):
        resp = client.post("/api/governance/compute/fabric/warm", json={"model_id": "coding"})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["data"]["warmed_count"] == 3


def test_api_compute_fabric_triage() -> None:
    fake_data = {
        "schema_version": "1",
        "data": {
            "tier": "reasoning",
            "confidence": 0.85,
        },
    }
    mock_proc = MagicMock(returncode=0, stdout=json.dumps(fake_data), stderr="")

    with patch("subprocess.run", return_value=mock_proc):
        resp = client.post(
            "/api/governance/compute/fabric/triage",
            json={"prompt": "Design a distributed consensus protocol"},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["data"]["tier"] == "reasoning"


def test_api_compute_fabric_vram() -> None:
    fake_data = {
        "schema_version": "1",
        "data": {
            "model_id": "coding",
            "context_tokens": 32768,
            "kv_cache_mb": 8448.0,
        },
    }
    mock_proc = MagicMock(returncode=0, stdout=json.dumps(fake_data), stderr="")

    with patch("subprocess.run", return_value=mock_proc):
        resp = client.post(
            "/api/governance/compute/fabric/vram",
            json={"model_id": "coding", "context_tokens": 32768},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["data"]["kv_cache_mb"] == 8448.0


def test_api_compute_fabric_compact() -> None:
    fake_data = {
        "schema_version": "1",
        "data": {
            "model_id": "coding",
            "compaction_advised": True,
            "compression_ratio": 0.32,
            "pruned_tokens": 8192,
        },
    }
    mock_proc = MagicMock(returncode=0, stdout=json.dumps(fake_data), stderr="")

    with patch("subprocess.run", return_value=mock_proc):
        resp = client.post(
            "/api/governance/compute/fabric/compact",
            json={"model_id": "coding", "tokens": 32768, "available_mb": 4096.0},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["data"]["compaction_advised"] is True
        assert payload["data"]["compression_ratio"] == 0.32
