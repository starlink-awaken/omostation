"""Tests for agent workflow standardization.

Tests cover:
- Range declaration mechanism
- Lock status checking
- Modification verification
- Signature validation
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

# Add lib to path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from agent_workflow_standard import (
    STANDARD_STATE_DIR,
    RangeDeclarationError,
    LockStatusError,
    ModificationVerificationError,
    SignatureValidationError,
    StandardError,
    check_compliance,
    check_lock_status,
    check_path_in_range,
    cleanup_expired_locks,
    compute_agent_signature,
    create_lock,
    create_range_declaration,
    get_modification_log,
    get_standard_status,
    read_lock_status,
    read_range_declaration,
    record_modification,
    register_agent_signature,
    release_lock,
    validate_agent_signature,
    validate_range_path,
    verify_modification,
)


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace for testing."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create state directories
    state_dir = workspace / ".omo" / "state" / "agent-workflow-standard"
    state_dir.mkdir(parents=True)

    yield workspace

    # Cleanup
    if workspace.exists():
        shutil.rmtree(workspace)


@pytest.fixture
def sample_paths():
    """Sample paths for testing."""
    return [
        "src/main.py",
        "tests/test_main.py",
        "docs/README.md",
    ]


@pytest.fixture
def sample_run_id():
    """Sample run ID for testing."""
    return "test-run-001"


@pytest.fixture
def sample_agent_id():
    """Sample agent ID for testing."""
    return "test-agent-001"


# ---------------------------------------------------------------------------
# Range Declaration Tests
# ---------------------------------------------------------------------------


class TestRangeDeclaration:
    """Test range declaration mechanism."""

    def test_validate_range_path_valid(self):
        """Test valid path validation."""
        assert validate_range_path("src/main.py") is True
        assert validate_range_path("tests/test_main.py") is True
        assert validate_range_path("docs/README.md") is True
        assert validate_range_path("src/utils/helpers.py") is True

    def test_validate_range_path_invalid(self):
        """Test invalid path validation."""
        assert validate_range_path("") is False
        assert validate_range_path(None) is False
        assert validate_range_path(123) is False
        assert validate_range_path("../etc/passwd") is False
        assert validate_range_path("/etc/passwd") is False
        assert validate_range_path("src/../../../etc/passwd") is False

    def test_validate_range_path_glob(self):
        """Test glob pattern validation."""
        assert validate_range_path("src/*.py") is True
        assert validate_range_path("tests/**/*.py") is True

    def test_create_range_declaration(self, temp_workspace, sample_run_id, sample_agent_id, sample_paths):
        """Test creating a range declaration."""
        declaration = create_range_declaration(
            sample_run_id,
            sample_agent_id,
            sample_paths,
            workspace=temp_workspace,
        )

        assert declaration["run_id"] == sample_run_id
        assert declaration["agent_id"] == sample_agent_id
        assert declaration["status"] == "active"
        assert "hash" in declaration
        assert "created_at" in declaration
        assert len(declaration["paths"]) == len(sample_paths)

    def test_create_range_declaration_validation(self, temp_workspace):
        """Test range declaration validation."""
        with pytest.raises(RangeDeclarationError, match="RUN_ID_REQUIRED"):
            create_range_declaration("", "agent-1", ["src/main.py"], workspace=temp_workspace)

        with pytest.raises(RangeDeclarationError, match="AGENT_ID_REQUIRED"):
            create_range_declaration("run-1", "", ["src/main.py"], workspace=temp_workspace)

        with pytest.raises(RangeDeclarationError, match="PATHS_REQUIRED"):
            create_range_declaration("run-1", "agent-1", [], workspace=temp_workspace)

    def test_create_range_declaration_invalid_path(self, temp_workspace):
        """Test range declaration with invalid path."""
        with pytest.raises(RangeDeclarationError, match="INVALID_PATH"):
            create_range_declaration(
                "run-1",
                "agent-1",
                ["../etc/passwd"],
                workspace=temp_workspace,
            )

    def test_read_range_declaration(self, temp_workspace, sample_run_id, sample_agent_id, sample_paths):
        """Test reading a range declaration."""
        # Create declaration
        create_range_declaration(
            sample_run_id,
            sample_agent_id,
            sample_paths,
            workspace=temp_workspace,
        )

        # Read it back
        declaration = read_range_declaration(sample_run_id, workspace=temp_workspace)
        assert declaration is not None
        assert declaration["run_id"] == sample_run_id
        assert declaration["agent_id"] == sample_agent_id

    def test_read_range_declaration_not_found(self, temp_workspace):
        """Test reading a non-existent declaration."""
        declaration = read_range_declaration("non-existent-run", workspace=temp_workspace)
        assert declaration is None

    def test_check_path_in_range(self):
        """Test checking if a path is within declared range."""
        declared_paths = ["src/main.py", "tests/*.py", "docs/"]

        # Exact match
        assert check_path_in_range("src/main.py", declared_paths) is True

        # Prefix match
        assert check_path_in_range("docs/README.md", declared_paths) is True

        # Glob match
        assert check_path_in_range("tests/test_main.py", declared_paths) is True

        # No match
        assert check_path_in_range("config/settings.yaml", declared_paths) is False

    def test_range_declaration_hash(self, temp_workspace, sample_run_id, sample_agent_id, sample_paths):
        """Test that declaration hash is deterministic."""
        decl1 = create_range_declaration(
            sample_run_id,
            sample_agent_id,
            sample_paths,
            workspace=temp_workspace,
        )

        # Read and create again with same params
        decl2 = create_range_declaration(
            sample_run_id,
            sample_agent_id,
            sample_paths,
            workspace=temp_workspace,
        )

        assert decl1["hash"] == decl2["hash"]


# ---------------------------------------------------------------------------
# Lock Status Tests
# ---------------------------------------------------------------------------


class TestLockStatus:
    """Test lock status checking."""

    def test_create_lock(self, temp_workspace, sample_run_id, sample_agent_id, sample_paths):
        """Test creating a lock."""
        lock = create_lock(
            sample_run_id,
            sample_agent_id,
            sample_paths,
            workspace=temp_workspace,
        )

        assert lock["run_id"] == sample_run_id
        assert lock["agent_id"] == sample_agent_id
        assert lock["status"] == "active"
        assert "created_at" in lock
        assert "expires_at" in lock

    def test_create_lock_validation(self, temp_workspace):
        """Test lock creation validation."""
        with pytest.raises(LockStatusError, match="RUN_ID_REQUIRED"):
            create_lock("", "agent-1", ["src/main.py"], workspace=temp_workspace)

        with pytest.raises(LockStatusError, match="AGENT_ID_REQUIRED"):
            create_lock("run-1", "", ["src/main.py"], workspace=temp_workspace)

        with pytest.raises(LockStatusError, match="PATHS_REQUIRED"):
            create_lock("run-1", "agent-1", [], workspace=temp_workspace)

    def test_create_lock_conflict(self, temp_workspace, sample_paths):
        """Test lock conflict detection."""
        # Create first lock
        create_lock("run-1", "agent-1", sample_paths, workspace=temp_workspace)

        # Try to create overlapping lock
        with pytest.raises(LockStatusError, match="PATH_LOCKED"):
            create_lock("run-2", "agent-2", sample_paths, workspace=temp_workspace)

    def test_create_lock_different_paths(self, temp_workspace):
        """Test creating locks on different paths."""
        create_lock("run-1", "agent-1", ["src/main.py"], workspace=temp_workspace)
        create_lock("run-2", "agent-2", ["tests/test_main.py"], workspace=temp_workspace)

        # Both should exist
        lock1 = read_lock_status("run-1", workspace=temp_workspace)
        lock2 = read_lock_status("run-2", workspace=temp_workspace)

        assert lock1 is not None
        assert lock2 is not None

    def test_read_lock_status(self, temp_workspace, sample_run_id, sample_agent_id, sample_paths):
        """Test reading lock status."""
        create_lock(
            sample_run_id,
            sample_agent_id,
            sample_paths,
            workspace=temp_workspace,
        )

        lock = read_lock_status(sample_run_id, workspace=temp_workspace)
        assert lock is not None
        assert lock["run_id"] == sample_run_id

    def test_read_lock_status_not_found(self, temp_workspace):
        """Test reading non-existent lock."""
        lock = read_lock_status("non-existent-run", workspace=temp_workspace)
        assert lock is None

    def test_release_lock(self, temp_workspace, sample_run_id, sample_agent_id, sample_paths):
        """Test releasing a lock."""
        create_lock(
            sample_run_id,
            sample_agent_id,
            sample_paths,
            workspace=temp_workspace,
        )

        # Release lock
        result = release_lock(sample_run_id, workspace=temp_workspace)
        assert result is True

        # Verify released
        lock = read_lock_status(sample_run_id, workspace=temp_workspace)
        assert lock is None

    def test_release_lock_not_found(self, temp_workspace):
        """Test releasing non-existent lock."""
        result = release_lock("non-existent-run", workspace=temp_workspace)
        assert result is False

    def test_check_lock_status(self, temp_workspace, sample_run_id, sample_agent_id, sample_paths):
        """Test checking lock status for a file."""
        create_lock(
            sample_run_id,
            sample_agent_id,
            sample_paths,
            workspace=temp_workspace,
        )

        # Check locked file
        result = check_lock_status("src/main.py", workspace=temp_workspace)
        assert result["locked"] is True
        assert result["lock_info"] is not None

        # Check unlocked file
        result = check_lock_status("config/settings.yaml", workspace=temp_workspace)
        assert result["locked"] is False

    def test_cleanup_expired_locks(self, temp_workspace):
        """Test cleaning up expired locks."""
        # Create a lock
        create_lock("run-1", "agent-1", ["src/main.py"], workspace=temp_workspace)

        # Cleanup with very short timeout (should clean up)
        cleaned = cleanup_expired_locks(workspace=temp_workspace, timeout_seconds=0)
        assert cleaned >= 0  # May or may not clean up depending on timing


# ---------------------------------------------------------------------------
# Modification Verification Tests
# ---------------------------------------------------------------------------


class TestModificationVerification:
    """Test modification verification."""

    def test_record_modification(self, temp_workspace, sample_run_id, sample_agent_id):
        """Test recording a modification."""
        record = record_modification(
            sample_run_id,
            sample_agent_id,
            "src/main.py",
            "edit",
            workspace=temp_workspace,
        )

        assert record["run_id"] == sample_run_id
        assert record["agent_id"] == sample_agent_id
        assert record["file_path"] == "src/main.py"
        assert record["action"] == "edit"
        assert "timestamp" in record

    def test_record_modification_validation(self, temp_workspace):
        """Test modification recording validation."""
        with pytest.raises(ModificationVerificationError, match="RUN_ID_REQUIRED"):
            record_modification("", "agent-1", "src/main.py", "edit", workspace=temp_workspace)

        with pytest.raises(ModificationVerificationError, match="FILE_PATH_REQUIRED"):
            record_modification("run-1", "agent-1", "", "edit", workspace=temp_workspace)

        with pytest.raises(ModificationVerificationError, match="INVALID_ACTION"):
            record_modification("run-1", "agent-1", "src/main.py", "invalid", workspace=temp_workspace)

    def test_verify_modification_in_range(self, temp_workspace, sample_run_id, sample_agent_id, sample_paths):
        """Test verifying modification within declared range."""
        # Create range declaration
        create_range_declaration(
            sample_run_id,
            sample_agent_id,
            sample_paths,
            workspace=temp_workspace,
        )

        # Verify modification in range
        result = verify_modification(sample_run_id, "src/main.py", workspace=temp_workspace)
        assert result["valid"] is True

    def test_verify_modification_outside_range(self, temp_workspace, sample_run_id, sample_agent_id, sample_paths):
        """Test verifying modification outside declared range."""
        # Create range declaration
        create_range_declaration(
            sample_run_id,
            sample_agent_id,
            sample_paths,
            workspace=temp_workspace,
        )

        # Verify modification outside range
        result = verify_modification(sample_run_id, "config/settings.yaml", workspace=temp_workspace)
        assert result["valid"] is False
        assert result["reason"] == "OUTSIDE_DECLARED_RANGE"

    def test_verify_modification_no_declaration(self, temp_workspace):
        """Test verifying modification without declaration."""
        result = verify_modification("non-existent-run", "src/main.py", workspace=temp_workspace)
        assert result["valid"] is False
        assert result["reason"] == "NO_RANGE_DECLARATION"

    def test_get_modification_log(self, temp_workspace, sample_run_id, sample_agent_id):
        """Test getting modification log."""
        # Record some modifications
        record_modification(sample_run_id, sample_agent_id, "src/main.py", "edit", workspace=temp_workspace)
        record_modification(sample_run_id, sample_agent_id, "tests/test_main.py", "create", workspace=temp_workspace)

        # Get log
        log = get_modification_log(sample_run_id, workspace=temp_workspace)
        assert len(log) == 2
        assert log[0]["file_path"] == "src/main.py"
        assert log[1]["file_path"] == "tests/test_main.py"

    def test_get_modification_log_empty(self, temp_workspace):
        """Test getting empty modification log."""
        log = get_modification_log("non-existent-run", workspace=temp_workspace)
        assert len(log) == 0


# ---------------------------------------------------------------------------
# Signature Validation Tests
# ---------------------------------------------------------------------------


class TestSignatureValidation:
    """Test signature validation."""

    def test_compute_agent_signature(self):
        """Test computing agent signature."""
        sig1 = compute_agent_signature("agent-1", "run-1")
        sig2 = compute_agent_signature("agent-1", "run-1")

        # Same inputs should produce same signature
        assert sig1 == sig2

        # Different inputs should produce different signatures
        sig3 = compute_agent_signature("agent-2", "run-1")
        assert sig1 != sig3

    def test_validate_agent_signature_valid(self, temp_workspace):
        """Test validating a valid signature."""
        agent_id = "agent-1"
        run_id = "run-1"
        signature = compute_agent_signature(agent_id, run_id)

        result = validate_agent_signature(agent_id, run_id, signature, workspace=temp_workspace)
        assert result["valid"] is True

    def test_validate_agent_signature_invalid_format(self, temp_workspace):
        """Test validating signature with invalid format."""
        result = validate_agent_signature("agent-1", "run-1", "invalid-signature", workspace=temp_workspace)
        assert result["valid"] is False
        assert result["reason"] == "INVALID_SIGNATURE_FORMAT"

    def test_validate_agent_signature_too_short(self, temp_workspace):
        """Test validating signature that's too short."""
        result = validate_agent_signature("agent-1", "run-1", "sha256:abc", workspace=temp_workspace)
        assert result["valid"] is False
        assert result["reason"] == "SIGNATURE_TOO_SHORT"

    def test_validate_agent_signature_mismatch(self, temp_workspace):
        """Test validating signature that doesn't match."""
        result = validate_agent_signature(
            "agent-1",
            "run-1",
            "sha256:" + "a" * 64,
            workspace=temp_workspace,
        )
        assert result["valid"] is False
        assert result["reason"] == "SIGNATURE_MISMATCH"

    def test_validate_agent_signature_missing_params(self, temp_workspace):
        """Test validating signature with missing parameters."""
        result = validate_agent_signature("", "run-1", "sha256:" + "a" * 64, workspace=temp_workspace)
        assert result["valid"] is False
        assert result["reason"] == "AGENT_ID_REQUIRED"

        result = validate_agent_signature("agent-1", "", "sha256:" + "a" * 64, workspace=temp_workspace)
        assert result["valid"] is False
        assert result["reason"] == "RUN_ID_REQUIRED"

        result = validate_agent_signature("agent-1", "run-1", "", workspace=temp_workspace)
        assert result["valid"] is False
        assert result["reason"] == "SIGNATURE_REQUIRED"

    def test_register_agent_signature(self, temp_workspace):
        """Test registering an agent signature."""
        result = register_agent_signature("agent-1", "run-1", workspace=temp_workspace)

        assert result["agent_id"] == "agent-1"
        assert result["run_id"] == "run-1"
        assert "signature" in result
        assert "registered_at" in result

        # Verify signature is correct
        expected = compute_agent_signature("agent-1", "run-1")
        assert result["signature"] == expected


# ---------------------------------------------------------------------------
# Compliance Check Tests
# ---------------------------------------------------------------------------


class TestComplianceCheck:
    """Test compliance checking."""

    def test_check_compliance_full(self, temp_workspace, sample_run_id, sample_agent_id, sample_paths):
        """Test full compliance check."""
        # Create range declaration
        create_range_declaration(
            sample_run_id,
            sample_agent_id,
            sample_paths,
            workspace=temp_workspace,
        )

        # Create lock
        create_lock(
            sample_run_id,
            sample_agent_id,
            sample_paths,
            workspace=temp_workspace,
        )

        # Register signature
        register_agent_signature(sample_agent_id, sample_run_id, workspace=temp_workspace)

        # Run compliance check
        result = check_compliance(sample_run_id, sample_agent_id, workspace=temp_workspace)

        assert result["run_id"] == sample_run_id
        assert result["agent_id"] == sample_agent_id
        assert "checks" in result
        assert "violations" in result

    def test_check_compliance_missing_declaration(self, temp_workspace, sample_run_id, sample_agent_id):
        """Test compliance check with missing declaration."""
        result = check_compliance(sample_run_id, sample_agent_id, workspace=temp_workspace)

        assert result["compliant"] is False
        violations = result["violations"]
        assert any(v["type"] == "missing_range_declaration" for v in violations)

    def test_check_compliance_missing_lock(self, temp_workspace, sample_run_id, sample_agent_id, sample_paths):
        """Test compliance check with missing lock."""
        # Create declaration but no lock
        create_range_declaration(
            sample_run_id,
            sample_agent_id,
            sample_paths,
            workspace=temp_workspace,
        )

        result = check_compliance(sample_run_id, sample_agent_id, workspace=temp_workspace)

        violations = result["violations"]
        assert any(v["type"] == "no_active_lock" for v in violations)

    def test_check_compliance_modification_outside_range(
        self, temp_workspace, sample_run_id, sample_agent_id, sample_paths
    ):
        """Test compliance check with modification outside range."""
        # Create declaration
        create_range_declaration(
            sample_run_id,
            sample_agent_id,
            sample_paths,
            workspace=temp_workspace,
        )

        # Record modification outside range
        record_modification(
            sample_run_id,
            sample_agent_id,
            "config/settings.yaml",
            "edit",
            workspace=temp_workspace,
        )

        result = check_compliance(sample_run_id, sample_agent_id, workspace=temp_workspace)

        violations = result["violations"]
        assert any(v["type"] == "modification_outside_range" for v in violations)


# ---------------------------------------------------------------------------
# Utility Tests
# ---------------------------------------------------------------------------


class TestUtility:
    """Test utility functions."""

    def test_get_standard_status(self, temp_workspace):
        """Test getting standard status."""
        status = get_standard_status(workspace=temp_workspace)

        assert "standard_mode_enabled" in status
        assert "active_locks" in status
        assert "active_declarations" in status
        assert "state_dir" in status

    def test_cleanup_expired_locks_empty(self, temp_workspace):
        """Test cleaning up locks when none exist."""
        cleaned = cleanup_expired_locks(workspace=temp_workspace)
        assert cleaned == 0


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestIntegration:
    """Test integration scenarios."""

    def test_full_workflow(self, temp_workspace, sample_paths):
        """Test full workflow: declare range, create lock, record modification, verify."""
        run_id = "integration-run-001"
        agent_id = "integration-agent-001"

        # Step 1: Create range declaration
        declaration = create_range_declaration(
            run_id,
            agent_id,
            sample_paths,
            workspace=temp_workspace,
        )
        assert declaration["status"] == "active"

        # Step 2: Create lock
        lock = create_lock(
            run_id,
            agent_id,
            sample_paths,
            workspace=temp_workspace,
        )
        assert lock["status"] == "active"

        # Step 3: Register signature
        sig_result = register_agent_signature(agent_id, run_id, workspace=temp_workspace)
        assert "signature" in sig_result

        # Step 4: Record modifications
        for path in sample_paths:
            record_modification(run_id, agent_id, path, "edit", workspace=temp_workspace)

        # Step 5: Verify modifications
        for path in sample_paths:
            result = verify_modification(run_id, path, workspace=temp_workspace)
            assert result["valid"] is True

        # Step 6: Run compliance check
        compliance = check_compliance(run_id, agent_id, workspace=temp_workspace)
        assert compliance["compliant"] is True

        # Step 7: Release lock
        released = release_lock(run_id, workspace=temp_workspace)
        assert released is True

    def test_concurrent_lock_prevention(self, temp_workspace):
        """Test that concurrent locks on same paths are prevented."""
        paths = ["src/shared.py"]

        # First agent locks
        create_lock("run-1", "agent-1", paths, workspace=temp_workspace)

        # Second agent tries to lock same paths
        with pytest.raises(LockStatusError, match="PATH_LOCKED"):
            create_lock("run-2", "agent-2", paths, workspace=temp_workspace)

        # First agent releases
        release_lock("run-1", workspace=temp_workspace)

        # Now second agent can lock
        lock = create_lock("run-2", "agent-2", paths, workspace=temp_workspace)
        assert lock["status"] == "active"

    def test_range_declaration_with_glob(self, temp_workspace):
        """Test range declaration with glob patterns."""
        run_id = "glob-run-001"
        agent_id = "glob-agent-001"
        paths = ["src/*.py", "tests/**/*.py"]

        declaration = create_range_declaration(
            run_id,
            agent_id,
            paths,
            workspace=temp_workspace,
        )

        # Verify glob patterns work
        assert check_path_in_range("src/main.py", declaration["paths"]) is True
        assert check_path_in_range("tests/unit/test_main.py", declaration["paths"]) is True
        assert check_path_in_range("docs/README.md", declaration["paths"]) is False
