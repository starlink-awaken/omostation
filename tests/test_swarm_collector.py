"""
projects/cockpit/tests/test_swarm_collector.py — Swarm Observability 单元测试
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from cockpit.tui.swarm_cli import render_swarm_status_panel
from cockpit.tui.swarm_collector import (
    AgentHeartbeat,
    BetLedgerSummary,
    LockSummary,
    SubmoduleRadarSummary,
    SwarmAgentSummary,
    SwarmGlobalState,
    SwarmStateCollector,
    _find_repo_root,
)


def test_find_repo_root() -> None:
    root = _find_repo_root()
    assert isinstance(root, Path)
    assert root.exists()


def test_collect_agents_fallback(tmp_path: Path) -> None:
    collector = SwarmStateCollector(root=tmp_path)
    summary = collector.collect_agents()
    assert summary.total_agents == 6
    assert summary.healthy_count == 0
    assert summary.last_tick_iso == "N/A"
    assert len(summary.agents) == 6


def test_collect_agents_with_data(tmp_path: Path) -> None:
    state_dir = tmp_path / ".omo" / "state"
    state_dir.mkdir(parents=True)
    tick_file = state_dir / "agent-tick-daemon.jsonl"
    tick_file.write_text(
        json.dumps(
            {
                "ts": "2026-08-15T12:00:00Z",
                "agent_count": 6,
                "ok_count": 6,
                "failed_count": 0,
                "actions": ["noop", "learn", "noop", "alert", "eval", "eval"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    collector = SwarmStateCollector(root=tmp_path)
    summary = collector.collect_agents()
    assert summary.total_agents == 6
    assert summary.healthy_count == 6
    assert summary.failed_count == 0
    assert len(summary.agents) == 6
    assert summary.agents[0].name == "governor"
    assert summary.agents[1].action == "learn"


def test_collect_locks(tmp_path: Path) -> None:
    locks_dir = tmp_path / ".omo" / "state" / "locks"
    locks_dir.mkdir(parents=True)
    (locks_dir / "test.lock").write_text("lock", encoding="utf-8")

    collector = SwarmStateCollector(root=tmp_path)
    summary = collector.collect_locks()
    assert summary.total_locks >= 1
    assert len(summary.details) >= 1


def test_collect_bets(tmp_path: Path) -> None:
    plan_dir = tmp_path / "docs" / "plans"
    plan_dir.mkdir(parents=True)
    ledger = plan_dir / "3y-bet-ledger.yaml"
    ledger.write_text(
        """
bets:
  - id: BET-01
    track: T1-TRUTH
    status: done
  - id: BET-02
    track: T1-TRUTH
    status: in_progress
  - id: BET-03
    track: T2-EXEC
    status: blocked
""",
        encoding="utf-8",
    )

    collector = SwarmStateCollector(root=tmp_path)
    summary = collector.collect_bets()
    assert summary.total_bets == 3
    assert summary.done_count == 1
    assert summary.in_progress_count == 1
    assert summary.blocked_count == 1
    assert len(summary.tracks) == 2
    assert summary.overall_percent == 33.3


def test_collect_submodules(tmp_path: Path) -> None:
    gitmodules = tmp_path / ".gitmodules"
    gitmodules.write_text(
        """
[submodule "projects/omlxc"]
\tpath = projects/omlxc
\turl = https://github.com/starlink-awaken/omostation-omlxc
[submodule "projects/cockpit"]
\tpath = projects/cockpit
\turl = https://github.com/starlink-awaken/cockpit
""",
        encoding="utf-8",
    )

    collector = SwarmStateCollector(root=tmp_path)
    summary = collector.collect_submodules(probe_remote=False)
    assert summary.total_submodules == 2
    assert len(summary.items) == 2
    assert summary.items[0].name == "omlxc"
    assert summary.items[1].name == "cockpit"


def test_collect_a2a_messages(tmp_path: Path) -> None:
    state_dir = tmp_path / ".omo" / "state"
    state_dir.mkdir(parents=True)
    msg_file = state_dir / "a2a-messages.jsonl"
    msg_file.write_text(
        json.dumps(
            {
                "from": "advisor",
                "to": "governor",
                "type": "reply",
                "ts": "2026-08-15T12:00:00Z",
                "payload": {"action": "processed"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    collector = SwarmStateCollector(root=tmp_path)
    msgs = collector.collect_a2a_messages()
    assert len(msgs) == 1
    assert msgs[0].from_agent == "advisor"
    assert msgs[0].to_agent == "governor"
    assert msgs[0].summary == "processed"


def test_render_swarm_status_panel() -> None:
    state = SwarmGlobalState(
        timestamp_iso="2026-08-15T12:00:00Z",
        agents=SwarmAgentSummary(
            total_agents=6,
            healthy_count=6,
            failed_count=0,
            last_tick_iso="2026-08-15T12:00:00Z",
            agents=[AgentHeartbeat("gov", "healthy", "noop", "2026-08-15T12:00:00Z", 10.0)],
        ),
        locks=LockSummary(active_runs=1, total_locks=1, stale_locks=0, details=[]),
        bets=BetLedgerSummary(
            total_bets=10,
            done_count=5,
            in_progress_count=3,
            blocked_count=0,
            overall_percent=50.0,
            tracks=[],
        ),
        submodules=SubmoduleRadarSummary(total_submodules=2, aligned_count=2, drifted_count=0, items=[]),
        recent_messages=[],
    )

    test_console = Console(record=True, width=100)
    render_swarm_status_panel(state, console=test_console)
    output = test_console.export_text()
    assert "SWARM OBSERVABILITY CONTROL PLANE" in output
    assert "BET Progress" in output
