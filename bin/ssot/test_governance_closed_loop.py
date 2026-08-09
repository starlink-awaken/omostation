import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from governance_closed_loop import run_closed_loop, summarize


def test_run_closed_loop_returns_stages():
    stages = run_closed_loop()
    assert "derived" in stages
    assert "index" in stages
    assert "owl" in stages
    assert "m0" in stages


def test_summarize_counts():
    stages = {"derived": {"constraints": 137}, "index": {"constraints": 135},
              "owl": {"constraints": 137}, "m0": {"drifts": 2}, "inference": {"findings": 1}}
    report = summarize(stages)
    assert "137" in report
    assert "2" in report
