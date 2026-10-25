import importlib.util
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock


def load_ledger_module():
    path = Path(__file__).resolve().parents[2] / "bin/plan/bet-ledger.py"
    spec = importlib.util.spec_from_file_location("bet_ledger_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ListJsonSerializationTest(unittest.TestCase):
    def test_done_at_date_objects_are_serialized(self):
        ledger = load_ledger_module()
        rows = [{"id": "BET-1", "done_at": date(2026, 10, 25)}]
        args = SimpleNamespace(track=None, window=None, status=None, claimable=False, json=True)
        with mock.patch("builtins.print") as printed:
            exit_code = ledger.cmd_list({"bets": rows}, args)
        self.assertEqual(exit_code, 0)
        payload = json.loads(printed.call_args.args[0])
        self.assertEqual(payload[0]["done_at"], "2026-10-25")
