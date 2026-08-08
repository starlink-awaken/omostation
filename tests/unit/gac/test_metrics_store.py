import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "bin" / "gac" / "metrics-store.py"


def run_metrics(args: list[str] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT)]
    if args:
        cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)


class TestAppendAndQuery:
    def test_append_and_query(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        run_metrics(["append", "--check", "check-a", "--ok", "true", "--duration-ms", "10", "--reason", "ok", "--file", str(metrics_file)])
        run_metrics(["append", "--check", "check-a", "--ok", "false", "--duration-ms", "20", "--reason", "fail", "--file", str(metrics_file)])
        run_metrics(["append", "--check", "check-b", "--ok", "true", "--duration-ms", "30", "--file", str(metrics_file)])
        result = run_metrics(["query", "--check", "check-a", "--file", str(metrics_file)])
        assert result.returncode == 0
        rows = json.loads(result.stdout)
        assert len(rows) == 2
        assert rows[0]["check"] == "check-a"
        assert rows[0]["ok"] is True
        assert rows[1]["ok"] is False

    def test_query_window(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        for i in range(10):
            run_metrics(["append", "--check", "check-x", "--ok", "true", "--duration-ms", str(i), "--file", str(metrics_file)])
        result = run_metrics(["query", "--check", "check-x", "--window", "5", "--file", str(metrics_file)])
        assert result.returncode == 0
        rows = json.loads(result.stdout)
        assert len(rows) == 5
        assert rows[0]["duration_ms"] == 5
        assert rows[-1]["duration_ms"] == 9

    def test_stats_basic(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        run_metrics(["append", "--check", "check-a", "--ok", "true", "--duration-ms", "10", "--file", str(metrics_file)])
        run_metrics(["append", "--check", "check-a", "--ok", "true", "--duration-ms", "20", "--file", str(metrics_file)])
        run_metrics(["append", "--check", "check-a", "--ok", "false", "--duration-ms", "30", "--file", str(metrics_file)])
        result = run_metrics(["stats", "--check", "check-a", "--file", str(metrics_file)])
        assert result.returncode == 0
        stats = json.loads(result.stdout)
        assert stats["count"] == 3
        assert stats["ok_count"] == 2
        assert stats["fail_count"] == 1
        assert abs(stats["pass_rate"] - 2 / 3) < 1e-9
        assert stats["avg_duration_ms"] == 20
        assert stats["max_duration_ms"] == 30
        assert stats["min_duration_ms"] == 10

    def test_tail_metrics(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        for i in range(5):
            run_metrics(["append", "--check", "check-tail", "--ok", "true", "--duration-ms", str(i), "--file", str(metrics_file)])
        result = run_metrics(["tail", "--n", "2", "--file", str(metrics_file)])
        assert result.returncode == 0
        rows = json.loads(result.stdout)
        assert len(rows) == 2
        assert rows[0]["duration_ms"] == 3
        assert rows[1]["duration_ms"] == 4

    def test_append_metadata(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        run_metrics([
            "append",
            "--check", "check-meta",
            "--ok", "true",
            "--duration-ms", "5",
            "--reason", "ok",
            "--metadata", '{"layer":"default-branch"}',
            "--file", str(metrics_file),
        ])
        result = run_metrics(["query", "--check", "check-meta", "--file", str(metrics_file)])
        assert result.returncode == 0
        rows = json.loads(result.stdout)
        assert rows[0]["metadata"] == {"layer": "default-branch"}
