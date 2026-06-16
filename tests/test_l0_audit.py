"""Tests for L0 Audit layer."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, mock_open, patch


from ecos.services.governance.l0_audit import (
    get_audit_log,
    load_constraints,
    log_operation,
    validate_operation,
)


# ── load_constraints ──

class TestLoadConstraints:
    @patch("ecos.services.governance.l0_audit.CONSTRAINTS_PATH")
    def test_file_not_exists(self, mock_path):
        mock_path.exists.return_value = False
        assert load_constraints() == []

    @patch("ecos.services.governance.l0_audit.CONSTRAINTS_PATH")
    def test_loads_constraints(self, mock_path):
        mock_path.exists.return_value = True
        data = {"constraints": [{"id": "X4-C05", "rule": "no direct write", "type": "required"}]}
        with patch("ecos.services.governance.l0_audit.open", mock_open(read_data=json.dumps(data))):
            constraints = load_constraints()
            assert len(constraints) == 1
            assert constraints[0]["id"] == "X4-C05"


# ── validate_operation ──

class TestValidateOperation:
    @patch("ecos.services.governance.l0_audit.load_constraints")
    @patch("ecos.services.governance.l0_audit.log_operation")
    def test_read_operation_no_violations(self, mock_log, mock_load):
        mock_load.return_value = []
        result = validate_operation("test", "read", "bos://test/resource")
        assert result["passed"] is True
        assert result["violations"] == []

    @patch("ecos.services.governance.l0_audit.load_constraints")
    @patch("ecos.services.governance.l0_audit.log_operation")
    def test_write_operation_checks_x4_c05(self, mock_log, mock_load):
        mock_load.return_value = [{"id": "X4-C05", "rule": "no direct write", "type": "required"}]
        result = validate_operation("test", "write_file", "bos://test/resource")
        assert len(result["violations"]) == 1
        assert result["violations"][0]["constraint"] == "X4-C05"

    @patch("ecos.services.governance.l0_audit.load_constraints")
    @patch("ecos.services.governance.l0_audit.log_operation")
    def test_non_bos_uri_violation(self, mock_log, mock_load):
        mock_load.return_value = []
        result = validate_operation("test", "read", "/local/path")
        assert result["passed"] is False
        assert result["violations"][0]["constraint"] == "X4-C10"

    @patch("ecos.services.governance.l0_audit.load_constraints")
    @patch("ecos.services.governance.l0_audit.log_operation")
    def test_domain_create_checks_kems(self, mock_log, mock_load):
        mock_load.return_value = []
        result = validate_operation("test", "domain_create")
        assert result["passed"] is True  # KEMS is preferred, not required
        assert any(v["constraint"] == "X4-C08" for v in result["violations"])

    @patch("ecos.services.governance.l0_audit.load_constraints")
    @patch("ecos.services.governance.l0_audit.log_operation")
    def test_passed_false_when_required_violation(self, mock_log, mock_load):
        mock_load.return_value = [{"id": "X4-C05", "rule": "no direct write", "type": "required"}]
        result = validate_operation("test", "write_file", "/local/path")
        assert result["passed"] is False
        assert len(result["violations"]) == 2  # X4-C05 + X4-C10

    @patch("ecos.services.governance.l0_audit.load_constraints")
    @patch("ecos.services.governance.l0_audit.log_operation")
    def test_no_uri_no_violation(self, mock_log, mock_load):
        mock_load.return_value = []
        result = validate_operation("test", "read")
        assert result["passed"] is True
        assert result["violations"] == []


# ── log_operation ──

class TestLogOperation:
    @patch("ecos.services.governance.l0_audit.AUDIT_LOG")
    def test_writes_to_audit_log(self, mock_path):
        mock_path.parent.mkdir = MagicMock()
        result = {"domain": "test", "operation": "read", "passed": True, "violations": []}
        with patch("ecos.services.governance.l0_audit.open", mock_open()) as m:
            log_operation(result)
            handle = m()
            written = handle.write.call_args[0][0]
            parsed = json.loads(written)
            assert parsed["domain"] == "test"
            assert parsed["passed"] is True

    @patch("ecos.services.governance.l0_audit.AUDIT_LOG")
    @patch("ecos.services.governance.l0_audit.HAS_UNIFIED", True)
    @patch("ecos.services.governance.l0_audit.log_event")
    def test_calls_unified_log_when_available(self, mock_log_event, mock_audit_log):
        mock_audit_log.parent.mkdir = MagicMock()
        result = {"domain": "test", "operation": "read", "passed": True, "violations": []}
        with patch("ecos.services.governance.l0_audit.open", mock_open()):
            log_operation(result)
            mock_log_event.assert_called_once()

    @patch("ecos.services.governance.l0_audit.AUDIT_LOG")
    @patch("ecos.services.governance.l0_audit.HAS_UNIFIED", False)
    def test_skips_unified_log_when_not_available(self, mock_path):
        mock_path.parent.mkdir = MagicMock()
        result = {"domain": "test", "operation": "read", "passed": True, "violations": []}
        with patch("ecos.services.governance.l0_audit.open", mock_open()):
            log_operation(result)  # should not raise


# ── get_audit_log ──

class TestGetAuditLog:
    @patch("ecos.services.governance.l0_audit.AUDIT_LOG")
    def test_file_not_exists(self, mock_path):
        mock_path.exists.return_value = False
        assert get_audit_log() == []

    @patch("ecos.services.governance.l0_audit.AUDIT_LOG")
    def test_reads_entries(self, mock_path):
        mock_path.exists.return_value = True
        lines = [
            json.dumps({"domain": "a", "operation": "read"}),
            json.dumps({"domain": "b", "operation": "write"}),
        ]
        with patch("ecos.services.governance.l0_audit.open", mock_open(read_data="\n".join(lines))):
            entries = get_audit_log()
            assert len(entries) == 2

    @patch("ecos.services.governance.l0_audit.AUDIT_LOG")
    def test_filters_by_domain(self, mock_path):
        mock_path.exists.return_value = True
        lines = [
            json.dumps({"domain": "a", "operation": "read"}),
            json.dumps({"domain": "b", "operation": "write"}),
        ]
        with patch("ecos.services.governance.l0_audit.open", mock_open(read_data="\n".join(lines))):
            entries = get_audit_log(domain="a")
            assert len(entries) == 1
            assert entries[0]["domain"] == "a"

    @patch("ecos.services.governance.l0_audit.AUDIT_LOG")
    def test_skips_bad_lines(self, mock_path):
        mock_path.exists.return_value = True
        lines = ["not json", json.dumps({"domain": "a", "operation": "read"})]
        with patch("ecos.services.governance.l0_audit.open", mock_open(read_data="\n".join(lines))):
            entries = get_audit_log()
            assert len(entries) == 1

    @patch("ecos.services.governance.l0_audit.AUDIT_LOG")
    def test_respects_limit(self, mock_path):
        mock_path.exists.return_value = True
        lines = [
            json.dumps({"domain": "a", "operation": f"op-{i}"})
            for i in range(10)
        ]
        with patch("ecos.services.governance.l0_audit.open", mock_open(read_data="\n".join(lines))):
            entries = get_audit_log(limit=3)
            assert len(entries) == 3
            assert entries[-1]["operation"] == "op-9"
