"""Tests for cockpit API logs + tasks — coverage to 90%."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from cockpit.dashboard_server import app


@pytest.fixture
def client():
    return TestClient(app)


class TestLogs:
    def test_get_logs(self, client):
        with patch("cockpit.web.api_logs.run_l4_script", return_value={"logs": []}):
            resp = client.get("/api/logs")
        assert resp.status_code == 200

    def test_get_logs_with_source(self, client):
        with patch("cockpit.web.api_logs.run_l4_script", return_value={"logs": [{"msg": "test"}]}):
            resp = client.get("/api/logs?source=omo")
        assert resp.status_code == 200


class TestTasks:
    def test_list_tasks(self, client):
        with patch("cockpit.web.api_tasks.get_tasks_from_omo", return_value=[]):
            resp = client.get("/api/tasks")
        assert resp.status_code == 200

    def test_get_task_detail(self, client):
        with patch("cockpit.web.api_tasks.get_tasks_from_omo", return_value=[{"id": "t1", "title": "Test"}]):
            resp = client.get("/api/tasks/t1")
        assert resp.status_code == 200

    def test_get_task_not_found(self, client):
        with patch("cockpit.web.api_tasks.get_tasks_from_omo", return_value=[]):
            resp = client.get("/api/tasks/nonexistent")
        assert resp.status_code == 404
