from __future__ import annotations

from unittest.mock import patch


def test_runtime_backend_exports_mesh_identity_to_child_process():
    from ecos.workflow.backends.runtime import _execute_step_runtime

    class Completed:
        returncode = 0
        stdout = '{"ok": true}'
        stderr = ""

    captured: dict = {}

    def run(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        return Completed()

    with (
        patch("ecos.workflow.backends.runtime._CLI_PATHS", [["runtime-test"]]),
        patch("ecos.workflow.backends.runtime.subprocess.run", side_effect=run),
        patch("ecos.workflow.circuit_breaker.is_available", return_value=True),
    ):
        result = _execute_step_runtime(
            "step",
            "execution",
            "goal",
            "run",
            "project",
            workflow_run_id="run-child",
            trace_id="trace-child",
        )

    assert result["ok"] is True
    assert captured["env"]["WORKFLOW_RUN_ID"] == "run-child"
    assert captured["env"]["TRACE_ID"] == "trace-child"
