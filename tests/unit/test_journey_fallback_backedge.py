"""兜底转移(states[].next, 无显式 transition)形成的环也必须计入回边保护。

2026-09-29 全链路场景实测: oversight-to-decision 高风险分支 escalated → status_collected
只写在 next 里, 回边检测只看 transitions, 同一输入原地打转到 50 步上限后报 completed。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("rel", ["runtime/ssot-stable/journey-runner.py", "bin/ssot/journey-runner.py"])
def test_fallback_next_edge_is_detected_as_backedge(rel: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str((ROOT / rel).parent))  # 运行器同目录的 _shared 等
    spec_obj = importlib.util.spec_from_file_location(f"jr_{rel.split('/')[0]}", ROOT / rel)
    mod = importlib.util.module_from_spec(spec_obj)
    spec_obj.loader.exec_module(mod)
    spec = {
        "states": [
            {"name": "status_collected", "next": ["risk_assessed"]},
            {"name": "risk_assessed", "next": ["escalated"]},
            {"name": "escalated", "next": ["status_collected"]},
        ],
        "transitions": [
            {"from": "status_collected", "to": "risk_assessed", "condition": "status == succeeded"},
            {"from": "risk_assessed", "to": "escalated", "condition": "supervision.risk_level == high"},
        ],
    }
    assert ("escalated", "status_collected") in mod._detect_backedges(spec)
