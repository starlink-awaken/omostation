"""Tests for whoami — system self-description."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch


from ecos.services.core.whoami import (
    get_capabilities,
    get_debts,
    get_health,
    get_scripts,
    get_topology,
    run,
)


class TestRun:
    @patch("ecos.services.core.whoami.subprocess.run")
    def test_success(self, mock_run):
        mock_result = MagicMock()
        mock_result.stdout = "output"
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        result = run(["python3", "test.py"])
        assert result == "output"

    @patch("ecos.services.core.whoami.subprocess.run")
    def test_silent_on_error(self, mock_run):
        mock_run.side_effect = Exception("boom")
        result = run(["python3", "test.py"])
        assert result == ""


class TestGetTopology:
    @patch("ecos.services.core.whoami.run")
    @patch("ecos.services.core.whoami.SCRIPTS")
    @patch("ecos.services.core.whoami.ECOS")
    def test_returns_topology(self, mock_ecos, mock_scripts, mock_run):
        mock_ecos.__truediv__.return_value.glob.return_value = []
        mock_scripts.__truediv__.return_value = Path("/fake/scripts/ecos-sla-tracker.py")
        mock_run.return_value = ""
        topo = get_topology()
        assert topo["version"] == "eCOS v5.3.0"
        assert "L4_self" in topo["layers"]
        assert "L3_entry" in topo["layers"]
        assert "L2_kernel" in topo["layers"]
        assert "L1_runtime" in topo["layers"]
        assert "L0_protocol" in topo["layers"]
        assert "I0_fabric" in topo["layers"]

    @patch("ecos.services.core.whoami.run")
    @patch("ecos.services.core.whoami.SCRIPTS")
    @patch("ecos.services.core.whoami.ECOS")
    def test_layers_have_health(self, mock_ecos, mock_scripts, mock_run):
        mock_ecos.__truediv__.return_value.glob.return_value = []
        mock_scripts.__truediv__.return_value = Path("/fake/scripts/ecos-sla-tracker.py")
        mock_run.return_value = ""
        topo = get_topology()
        for layer in ["L4_self", "L3_entry", "L2_kernel", "L1_runtime", "L0_protocol", "I0_fabric"]:
            assert "health" in topo["layers"][layer]


class TestGetHealth:
    @patch("ecos.services.core.whoami.run")
    @patch("ecos.services.core.whoami.SCRIPTS")
    def test_all_pass(self, mock_scripts, mock_run):
        mock_scripts.__truediv__.__truediv__.return_value = Path("/fake/ecos-health-check.py")
        mock_run.return_value = json.dumps({"results": [{"pass": True}, {"pass": True}]})
        health = get_health()
        assert health["all_pass"] is True
        assert health["passed"] == 2

    @patch("ecos.services.core.whoami.run")
    @patch("ecos.services.core.whoami.SCRIPTS")
    def test_some_fail(self, mock_scripts, mock_run):
        mock_scripts.__truediv__.__truediv__.return_value = Path("/fake/ecos-health-check.py")
        mock_run.return_value = json.dumps({"results": [{"pass": True}, {"pass": False}]})
        health = get_health()
        assert health["all_pass"] is False
        assert health["failed"] == 1

    @patch("ecos.services.core.whoami.run")
    @patch("ecos.services.core.whoami.SCRIPTS")
    def test_bad_json(self, mock_scripts, mock_run):
        mock_scripts.__truediv__.__truediv__.return_value = Path("/fake/ecos-health-check.py")
        mock_run.return_value = "not json"
        health = get_health()
        assert health["all_pass"] is None


class TestGetDebts:
    def test_returns_dict(self):
        debts = get_debts()
        assert debts["total"] == 0
        assert debts["closed"] == 11


class TestGetCapabilities:
    def test_returns_list(self):
        caps = get_capabilities()
        assert len(caps) >= 4
        assert any(c["id"] == "brief" for c in caps)
        assert any(c["id"] == "health" for c in caps)


class TestGetScripts:
    @patch("ecos.services.core.whoami.SCRIPTS")
    @patch("ecos.services.core.whoami.ECOS")
    @patch("ecos.services.core.whoami.DOCS")
    def test_returns_scripts(self, mock_docs, mock_ecos, mock_scripts):
        mock_scripts.exists.return_value = True
        mock_scripts.iterdir.return_value = [Path("test.py"), Path("other.sh")]
        mock_ecos.__truediv__.return_value.exists.return_value = False
        mock_docs.__truediv__.__truediv__.__truediv__.__truediv__.return_value.exists.return_value = False
        scripts = get_scripts()
        assert len(scripts) >= 1
        assert any("test.py" in s for s in scripts)
