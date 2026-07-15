"""cockpit wave2 command unit tests (no c2g subprocess required)."""

from __future__ import annotations

import argparse
from unittest.mock import patch

from cockpit.commands.wave2 import cmd_wave2


def test_wave2_dashboard_dispatches_module():
    with patch("cockpit.commands.wave2._run_c2g_module", return_value=0) as m:
        code = cmd_wave2(
            argparse.Namespace(
                wave2_command="dashboard", pretty=True, wave2_args=[]
            )
        )
        assert code == 0
        m.assert_called_once()
        assert m.call_args[0][0] == "c2g.dashboard_export"
        assert "--pretty" in m.call_args[0][1]


def test_wave2_proposals_dispatch():
    with patch("cockpit.commands.wave2._run_c2g_module", return_value=0) as m:
        code = cmd_wave2(
            argparse.Namespace(
                wave2_command="proposals", pretty=False, wave2_args=["--show-apply-plan"]
            )
        )
        assert code == 0
        assert m.call_args[0][0] == "c2g.governance_feedback"


def test_wave2_unknown():
    code = cmd_wave2(
        argparse.Namespace(wave2_command="nope", pretty=False, wave2_args=[])
    )
    assert code == 2
