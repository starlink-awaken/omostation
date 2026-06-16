"""Tests for Constraint Compiler."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from ecos.services.governance.constraint_compiler import (
    compile_constraints,
    format_report,
    load_compiled,
    load_yaml,
    main,
    run_compiled,
    watch_and_compile,
    write_compiled,
)


SAMPLE_DATA = {
    "version": "1.0.0",
    "protocol_registry": [
        {
            "id": "SSB",
            "version": "2.1.0",
            "introduced": "2025-01-01",
            "half_life_days": 365,
            "status": "active",
            "value_tier": 3,
        },
    ],
    "constraints": [
        {
            "id": "X4-C01",
            "description": "Protocol must be registered",
            "type": "required",
            "rule": "protocol.registered == true",
            "violation": "Protocol not registered",
        },
        {
            "id": "X4-C02",
            "description": "Cross-layer call must route through I0/Agora",
            "type": "required",
            "rule": "layer.cross_call.route == 'I0/Agora'",
            "violation": "Direct cross-layer call detected",
        },
        {
            "id": "X4-C03",
            "description": "CLAUDE.md must be fresh",
            "type": "required",
            "rule": "claude_md.age_days <= 60",
            "violation": "CLAUDE.md too old",
        },
        {
            "id": "X4-C04",
            "description": "Value tier must be declared",
            "type": "required",
            "rule": "domain.value_tier != null",
            "violation": "Missing value tier",
        },
        {
            "id": "X4-C05",
            "description": "Custom rule",
            "type": "preferred",
            "rule": "custom.check == true",
            "violation": "Custom check failed",
        },
    ],
}


class TestLoadYaml:
    @patch("ecos.services.governance.constraint_compiler.open", mock_open(read_data=json.dumps(SAMPLE_DATA)))
    def test_loads_yaml(self):
        data = load_yaml(Path("/fake/path"))
        assert data["version"] == "1.0.0"
        assert len(data["protocol_registry"]) == 1


class TestCompileConstraints:
    def test_compiles_code(self):
        code = compile_constraints(SAMPLE_DATA)
        assert "PROTOCOLS" in code
        assert "compute_decay" in code
        assert "check_constraints" in code
        assert "run" in code
        assert "SSB" in code
        assert "X4-C01" in code
        assert "X4-C02" in code
        assert "X4-C03" in code
        assert "X4-C04" in code

    def test_compiled_code_is_valid_python(self):
        code = compile_constraints(SAMPLE_DATA)
        compile(code, "<test>", "exec")  # should not raise

    def test_compiled_run_returns_result(self):
        code = compile_constraints(SAMPLE_DATA)
        namespace: dict = {}
        exec(code, namespace)
        result = namespace["run"]()
        assert "decay" in result
        assert "constraints" in result
        assert len(result["constraints"]) == 5

    def test_compiled_check_constraints_passes_with_good_state(self):
        code = compile_constraints(SAMPLE_DATA)
        namespace: dict = {}
        exec(code, namespace)
        state = {
            "protocol": {"registered": True},
            "layer": {"cross_call": {"route": "I0/Agora"}},
            "claude_md": {"age_days": 10},
            "domain": {"d1": {"value_tier": 3}},
        }
        constraints = namespace["check_constraints"](state)
        assert all(c["passed"] for c in constraints)

    def test_compiled_check_constraints_fails_with_bad_state(self):
        code = compile_constraints(SAMPLE_DATA)
        namespace: dict = {}
        exec(code, namespace)
        state = {
            "protocol": {"registered": False},
            "layer": {"cross_call": {"route": "direct"}},
            "claude_md": {"age_days": 100},
            "domain": {"d1": {}},
        }
        constraints = namespace["check_constraints"](state)
        failed = [c for c in constraints if not c["passed"]]
        assert len(failed) >= 3

    def test_compiled_compute_decay_fresh(self):
        code = compile_constraints(SAMPLE_DATA)
        namespace: dict = {}
        exec(code, namespace)
        result = namespace["compute_decay"]("SSB")
        assert result["protocol"] == "SSB"
        assert result["status"] in ("fresh", "aging", "expired")

    def test_compiled_compute_decay_unknown(self):
        code = compile_constraints(SAMPLE_DATA)
        namespace: dict = {}
        exec(code, namespace)
        result = namespace["compute_decay"]("UNKNOWN")
        assert "error" in result

    def test_compiled_report_all_decay(self):
        code = compile_constraints(SAMPLE_DATA)
        namespace: dict = {}
        exec(code, namespace)
        results = namespace["report_all_decay"]()
        assert len(results) == 1
        assert results[0]["protocol"] == "SSB"

    def test_empty_data(self):
        code = compile_constraints({"protocol_registry": [], "constraints": [], "version": "0.0.0"})
        namespace: dict = {}
        exec(code, namespace)
        result = namespace["run"]()
        assert result["decay"] == []
        assert result["constraints"] == []


class TestWriteCompiled:
    @patch("ecos.services.governance.constraint_compiler.STATE_FILE")
    @patch("ecos.services.governance.constraint_compiler.Path.write_text")
    @patch("ecos.services.governance.constraint_compiler.Path.mkdir")
    def test_writes_code_and_state(self, mock_mkdir, mock_write, mock_state):
        output = Path("/tmp/test_output.py")
        state = write_compiled("code = 1", output)
        assert "compiled_at" in state
        assert "hash" in state
        assert state["output"] == str(output)


class TestLoadCompiled:
    @patch("ecos.services.governance.constraint_compiler.importlib.util.spec_from_file_location")
    def test_load_nonexistent(self, mock_spec):
        mock_spec.return_value = None
        result = load_compiled(Path("/fake.py"))
        assert result is None

    @patch("ecos.services.governance.constraint_compiler.importlib.util.spec_from_file_location")
    def test_spec_none(self, mock_spec):
        mock_spec.return_value = None
        result = load_compiled(Path("/fake.py"))
        assert result is None


class TestRunCompiled:
    @patch("ecos.services.governance.constraint_compiler.load_compiled")
    def test_run_nonexistent(self, mock_load):
        mock_load.return_value = None
        result = run_compiled(Path("/fake.py"))
        assert "error" in result

    @patch("ecos.services.governance.constraint_compiler.load_compiled")
    def test_run_module_error(self, mock_load):
        mock_module = MagicMock()
        mock_module.run.side_effect = ValueError("boom")
        mock_load.return_value = mock_module
        result = run_compiled(Path("/fake.py"))
        assert "error" in result
        assert "boom" in result["error"]


class TestFormatReport:
    def test_format_empty(self):
        result = format_report({"decay": [], "constraints": []})
        assert "约束" in result
        assert "0/0" in result

    def test_format_with_data(self):
        result = format_report({
            "decay": [
                {
                    "protocol": "SSB",
                    "version": "2.1.0",
                    "remaining_value": 75.0,
                    "status": "fresh",
                    "age_days": 90,
                    "half_life_days": 365,
                }
            ],
            "constraints": [
                {"id": "X4-C01", "passed": True, "type": "required", "description": "test"},
                {"id": "X4-C02", "passed": False, "type": "required", "description": "fail"},
            ],
        })
        assert "SSB" in result
        assert "X4-C01" in result
        assert "X4-C02" in result
        assert "1/2" in result

    def test_format_expired(self):
        result = format_report({
            "decay": [
                {
                    "protocol": "OLD",
                    "version": "1.0",
                    "remaining_value": 0.0,
                    "status": "expired",
                    "age_days": 400,
                    "half_life_days": 365,
                }
            ],
            "constraints": [],
        })
        assert "已超半衰期" in result


class TestWatchAndCompile:
    @patch("ecos.services.governance.constraint_compiler.CONSTRAINTS_FILE")
    @patch("ecos.services.governance.constraint_compiler.time.sleep")
    @patch("ecos.services.governance.constraint_compiler.load_yaml")
    @patch("ecos.services.governance.constraint_compiler.compile_constraints")
    @patch("ecos.services.governance.constraint_compiler.write_compiled")
    @patch("ecos.services.governance.constraint_compiler.run_compiled")
    def test_watch_detects_change(
        self, mock_run, mock_write, mock_compile, mock_load, mock_sleep, mock_file
    ):
        mock_file.exists.return_value = True
        # Return different mtime on each call to simulate change
        stat_results = [MagicMock(st_mtime=100.0), MagicMock(st_mtime=200.0)]
        mock_file.stat.side_effect = stat_results

        mock_load.return_value = SAMPLE_DATA
        mock_compile.return_value = "compiled_code"
        mock_write.return_value = {"hash": "abc123"}
        mock_run.return_value = {"decay": [], "constraints": []}

        # Stop after first sleep
        mock_sleep.side_effect = lambda *a: (_ for _ in ()).throw(SystemExit(0))

        with pytest.raises(SystemExit):
            watch_and_compile(Path("/tmp/test.py"), interval=1)

        mock_compile.assert_called_once()
        mock_write.assert_called_once()

    @patch("ecos.services.governance.constraint_compiler.CONSTRAINTS_FILE")
    @patch("ecos.services.governance.constraint_compiler.time.sleep")
    def test_watch_no_change(self, mock_sleep, mock_file):
        mock_file.exists.return_value = True
        stat_result = MagicMock()
        stat_result.st_mtime = 100.0
        mock_file.stat.return_value = stat_result

        def stop(*args):
            raise SystemExit(0)

        mock_sleep.side_effect = stop

        with pytest.raises(SystemExit):
            watch_and_compile(Path("/tmp/test.py"), interval=1)


class TestMain:
    @patch("ecos.services.governance.constraint_compiler.CONSTRAINTS_FILE")
    @patch("ecos.services.governance.constraint_compiler.argparse.ArgumentParser.parse_args")
    def test_main_file_not_exists(self, mock_args, mock_file):
        mock_file.exists.return_value = False
        mock_args.return_value = MagicMock(output="/tmp/test.py", watch=False, json=False, interval=60)
        with pytest.raises(SystemExit):
            main()

    @patch("ecos.services.governance.constraint_compiler.CONSTRAINTS_FILE")
    @patch("ecos.services.governance.constraint_compiler.argparse.ArgumentParser.parse_args")
    @patch("ecos.services.governance.constraint_compiler.load_yaml")
    @patch("ecos.services.governance.constraint_compiler.compile_constraints")
    @patch("ecos.services.governance.constraint_compiler.write_compiled")
    @patch("ecos.services.governance.constraint_compiler.run_compiled")
    def test_main_single_run(
        self, mock_run, mock_write, mock_compile, mock_load, mock_args, mock_file
    ):
        mock_file.exists.return_value = True
        mock_args.return_value = MagicMock(output="/tmp/test.py", watch=False, json=False, interval=60)
        mock_load.return_value = SAMPLE_DATA
        mock_compile.return_value = "code"
        mock_write.return_value = {"hash": "abc"}
        mock_run.return_value = {"decay": [], "constraints": []}
        main()  # should not raise

    @patch("ecos.services.governance.constraint_compiler.CONSTRAINTS_FILE")
    @patch("ecos.services.governance.constraint_compiler.argparse.ArgumentParser.parse_args")
    @patch("ecos.services.governance.constraint_compiler.load_yaml")
    @patch("ecos.services.governance.constraint_compiler.compile_constraints")
    @patch("ecos.services.governance.constraint_compiler.write_compiled")
    @patch("ecos.services.governance.constraint_compiler.run_compiled")
    def test_main_json_output(
        self, mock_run, mock_write, mock_compile, mock_load, mock_args, mock_file
    ):
        mock_file.exists.return_value = True
        mock_args.return_value = MagicMock(output="/tmp/test.py", watch=False, json=True, interval=60)
        mock_load.return_value = SAMPLE_DATA
        mock_compile.return_value = "code"
        mock_write.return_value = {"hash": "abc"}
        mock_run.return_value = {"decay": [], "constraints": []}
        main()  # should not raise
