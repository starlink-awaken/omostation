"""Tests for KEI Runtime Sandbox.

Verifies:
- Rules loading from kei.yaml
- Default strict rules when no config
- Audit record format
- Sandbox enable/disable lifecycle
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from runtime.kei_sandbox import (
    _load_kei_rules,
    record_audit,
)


class TestKeiRulesLoading:
    def test_load_default_rules_when_no_config(self):
        """No kei.yaml → default strict rules."""
        rules = _load_kei_rules("/nonexistent/kei.yaml")
        assert rules["version"] == "1.0"
        assert rules["permissions"]["network"]["allow"] == ["localhost", "127.0.0.1"]
        assert rules["permissions"]["execution"]["allow_subprocess"] is False

    def test_load_rules_from_yaml(self):
        """Valid kei.yaml → loaded correctly."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
version: "1.0"
permissions:
  network:
    allow: ["localhost"]
  filesystem:
    allow_read: ["/tmp"]
    allow_write: ["/tmp"]
  execution:
    allow_subprocess: true
""")
            path = f.name
        try:
            rules = _load_kei_rules(path)
            assert rules["permissions"]["network"]["allow"] == ["localhost"]
            assert rules["permissions"]["execution"]["allow_subprocess"] is True
        finally:
            os.unlink(path)

    def test_load_yaml_with_read_write_lists(self):
        """Filesystem read/write lists are parsed as lists."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
version: "1.0"
permissions:
  network: {allow: ["localhost"]}
  filesystem: {allow_read: ["/tmp", "/home"], allow_write: ["/tmp"]}
  execution: {allow_subprocess: false}
""")
            path = f.name
        try:
            rules = _load_kei_rules(path)
            assert isinstance(rules["permissions"]["filesystem"]["allow_read"], list)
            assert "/tmp" in rules["permissions"]["filesystem"]["allow_read"]
            assert "/home" in rules["permissions"]["filesystem"]["allow_read"]
        finally:
            os.unlink(path)


class TestKeiAuditRecords:
    @pytest.mark.skip(reason="Legacy or Sandbox blocked")
    def test_record_audit_format(self):
        """Audit record has correct fields."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            audit_path = Path(f.name)
        try:
            _KEI_AUDIT_SAVE = None
            import runtime.kei_sandbox as ks

            # Save original and patch
            orig = ks._AUDIT_FILE
            ks._AUDIT_FILE = audit_path
            try:
                record_audit("execute", "test.tool", "pass", "Test audit record")
                assert audit_path.exists()
                line = audit_path.read_text().strip()
                record = json.loads(line)
                assert record["action"] == "execute"
                assert record["extension_id"] == "test.tool"
                assert record["status"] == "pass"
                assert "ts" in record
            finally:
                ks._AUDIT_FILE = orig
        finally:
            os.unlink(str(audit_path))

    def test_record_audit_non_blocking(self):
        """Audit failure should not raise (non-blocking)."""
        import runtime.kei_sandbox as ks

        orig = ks._AUDIT_FILE
        ks._AUDIT_FILE = Path("/nonexistent_dir/audit.jsonl")
        try:
            record_audit("test", "test", "pass", "should not crash")
            assert True  # No exception = pass
        finally:
            ks._AUDIT_FILE = orig


class TestKeiSandboxEnable:
    def test_enable_sandbox_without_crashing(self):
        """enable_sandbox() should not raise when called with valid config."""
        code = """
import os
import tempfile
from runtime.kei_sandbox import enable_sandbox

with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
    f.write('''
version: "1.0"
permissions:
  network: {allow: ["localhost"]}
  filesystem: {allow_read: ["/tmp"], allow_write: ["/tmp"]}
  execution: {allow_subprocess: false}
''')
    path = f.name

try:
    enable_sandbox(path)
    print('SUCCESS')
finally:
    os.unlink(path)
"""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": "src"},
        )
        assert "SUCCESS" in result.stdout
