"""Tests for cockpit API logs + tasks — coverage to 90%."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from cockpit.dashboard_server import app
from cockpit.web.api_logs import _infer_log_level, _read_log_entries


@pytest.fixture
def client():
    return TestClient(app)


class TestLogs:
    @pytest.mark.parametrize(
        ("line", "level"),
        [
            ("2026-07-15T10:00:00Z ERROR database timeout", "error"),
            ("WARNING retrying request", "warning"),
            ("DEBUG request payload", "debug"),
            ("FATAL process panic", "fatal"),
            ("request completed", "info"),
        ],
    )
    def test_infers_log_levels(self, line, level):
        assert _infer_log_level(line) == level

    def test_reads_bounded_entries_with_level_and_timestamp(self, tmp_path):
        log_file = tmp_path / "runtime.log"
        log_file.write_text(
            "2026-07-15T10:00:00Z ERROR database timeout\n"
            "2026-07-15T10:01:00Z INFO recovered\n",
            encoding="utf-8",
        )

        entries = _read_log_entries(log_file, "runtime", 1)

        assert len(entries) == 1
        assert entries[0]["level"] == "error"
        assert entries[0]["timestamp"] == "2026-07-15T10:00:00Z"

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
