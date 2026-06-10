from __future__ import annotations

import importlib


def test_execute_builds_command_and_runs(monkeypatch):
    eidos_pipeline = importlib.import_module("agora.pipelines.eidos_pipeline")

    seen = {}

    def fake_run(cmd, capture_output, text):
        seen["cmd"] = cmd
        seen["capture_output"] = capture_output
        seen["text"] = text

        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Result()

    monkeypatch.setattr(eidos_pipeline.subprocess, "run", fake_run)

    result = eidos_pipeline.execute("knowledge-base", output="/tmp/x.html")

    assert seen["cmd"][:2] == ["eidos", "pipeline"]
    assert "--output" in seen["cmd"]
    assert result.returncode == 0
