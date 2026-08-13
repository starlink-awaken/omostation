"""CLI tests for cockpit — argument parsing and command dispatch."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cockpit.cli import main
from cockpit.storage import set_data_access


class MockDataAccess:
    """Minimal mock that satisfies get_data_access()."""

    def save_research(self, topic="", summary="", full_text="", source_count=0, agent=""):
        return 42

    def list_research(self, limit=10, include_quarantined=False, include_archived=False):
        return []

    def search_research(self, keyword="", limit=10):
        return []

    def get_research(self, research_id=0):
        return None

    def set_research_tags(self, research_id=0, tags=None):
        return tags or []

    def rename_research(self, research_id=0, new_topic=""):
        return True

    def quarantine_research(self, research_ids=None, reason=""):
        return [], []

    def restore_research(self, research_ids=None):
        return [], []

    def archive_research(self, research_ids=None, reason=""):
        return [], []

    def restore_archived_research(self, research_ids=None):
        return [], []

    def add_follow_up(self, research_id=0, question="", answer=""):
        pass

    def add_research_relations(self, parent_ids=None, child_id=0, relation_type=""):
        pass

    def save_published_report(self, research_id=0, style="", output_path=""):
        return 0

    def get_research_timeline(self, research_id=0):
        return []

    def get_research_dossier(self, research_id=0):
        return None

    def set_research_agent(self, research_id=0, agent_name=""):
        return True

    def compute_half_life(self, research_id=0):
        return {}

    def export_backup(self):
        return {
            "version": 1,
            "exported_at": 0.0,
            "research": [],
            "relations": [],
            "published_reports": [],
            "events": [],
        }

    def import_backup(self, data=None):
        return {"research": 0, "relations": 0, "published_reports": 0, "events": 0, "skipped": 0}

    def set_research_relations(self, *args, **kwargs):
        pass


def _setup_mock():
    set_data_access(MockDataAccess())


def test_help_command():
    """cockpit help should return 0."""
    _setup_mock()
    with patch("sys.argv", ["workspace", "help"]):
        rc = main()
    assert rc == 0


def test_demo_command(monkeypatch, tmp_path):
    """cockpit demo should return 0 with mock data access."""
    _setup_mock()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    with patch("sys.argv", ["workspace", "demo"]):
        rc = main()
    assert rc == 0


def test_status_command():
    """cockpit status should return 0 with mock."""
    _setup_mock()
    with patch("sys.argv", ["workspace", "status"]):
        rc = main()
    assert rc == 0


def test_daily_command():
    """cockpit daily should return 0 with mock."""
    _setup_mock()
    with patch("sys.argv", ["workspace", "daily"]):
        rc = main()
    assert rc == 0


def test_daily_with_days():
    """cockpit daily --days 7 should return 0."""
    _setup_mock()
    with patch("sys.argv", ["workspace", "daily", "--days", "7"]):
        rc = main()
    assert rc == 0


def test_research_list_command():
    """cockpit research --list should return 0."""
    _setup_mock()
    with patch("sys.argv", ["workspace", "research", "--list"]):
        rc = main()
    assert rc == 0


def test_research_search_command():
    """cockpit research --search keyword should return 0."""
    _setup_mock()
    with patch("sys.argv", ["workspace", "research", "--search", "llm"]):
        rc = main()
    assert rc == 0


def test_research_health_command():
    """cockpit research --health should return 0."""
    _setup_mock()
    with patch("sys.argv", ["workspace", "research", "--health"]):
        rc = main()
    assert rc == 0


def test_research_follow_up_command():
    """cockpit research --follow-up should return 0."""
    _setup_mock()
    with patch("sys.argv", ["workspace", "research", "--follow-up"]):
        rc = main()
    assert rc == 0


def test_no_command_shows_banner():
    """Running workspace with no args should show welcome banner and return 0."""
    _setup_mock()
    with patch("sys.argv", ["workspace"]):
        rc = main()
    assert rc == 0


def test_omo_subcommand_registered():
    """cockpit omo 必须注册到 argparse (防声明/执行鸿沟 P110-COCKPIT 再犯).

    前次 bug: dispatch dict 有 "omo": lambda cmd_omo 但缺 add_parser("omo") →
    `cockpit omo debt list` 报 invalid choice 'omo'. 后端 cockpit.commands.omo.cmd_omo
    齐全, 只缺前端 argparse 注册. 关联 omo CLI argv 签名修复 (PR#122) 同源问题.
    """
    import pytest

    _setup_mock()
    with patch("sys.argv", ["workspace", "omo", "--help"]):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0  # --help 正常退出 = 已注册 (invalid choice 会 code=2)


def test_runtime_subcommand_registered():
    """cockpit runtime 必须注册到 argparse (同 omo 鸿沟)."""
    import pytest

    _setup_mock()
    with patch("sys.argv", ["workspace", "runtime", "--help"]):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0


def test_domain_status_json_propagates_ok_status(monkeypatch, capsys):
    from cockpit.commands import l4bridge

    payload = {
        "schema": "cockpit.domain-project-status.v1",
        "status": "ok",
        "available": True,
        "total": 1,
        "summary": {"ok": 1, "degraded": 0, "unavailable": 0},
        "domains": [],
    }
    monkeypatch.setattr(l4bridge.governance_context, "domain_project_status", lambda _domain_id="": payload)

    with patch("sys.argv", ["cockpit", "domain-status", "vault", "--json"]):
        rc = main()

    assert rc == 0
    assert json.loads(capsys.readouterr().out) == payload


def test_domain_status_maps_degraded_and_unavailable_to_nonzero(monkeypatch):
    from cockpit.commands import l4bridge

    monkeypatch.setattr(
        l4bridge.governance_context,
        "domain_project_status",
        lambda _domain_id="": {"status": "degraded", "domains": [], "summary": {}},
    )
    with patch("sys.argv", ["cockpit", "domain-status"]):
        assert main() == 1

    monkeypatch.setattr(
        l4bridge.governance_context,
        "domain_project_status",
        lambda _domain_id="": {"status": "unavailable", "domains": [], "summary": {}},
    )
    with patch("sys.argv", ["cockpit", "domain-status", "unknown"]):
        assert main() == 2


def test_facts_audit_json_forwards_domain_id_and_preserves_envelope(monkeypatch, capsys):
    """facts-audit forwards its optional domain ID and prints the shared envelope unchanged."""
    from cockpit.commands import l4bridge

    payload = {
        "schema": "cockpit.domain-facts-audit.v1",
        "status": "ok",
        "available": True,
        "domains": [],
        "summary": {"present": 1, "missing": 0, "unreadable": 0, "invalid": 0},
    }
    seen = []
    monkeypatch.setattr(
        l4bridge.governance_context,
        "domain_facts_audit",
        lambda domain_id="": seen.append(domain_id) or payload,
    )

    with patch("sys.argv", ["cockpit", "facts-audit", "vault", "--json"]):
        assert main() == 0

    assert seen == ["vault"]
    assert json.loads(capsys.readouterr().out) == payload


def test_facts_audit_maps_violations_and_unavailable_to_contract_exit_codes(monkeypatch):
    """facts-audit reserves exit 1 for violations and exit 2 for unavailable results."""
    from cockpit.commands import l4bridge

    monkeypatch.setattr(
        l4bridge.governance_context,
        "domain_facts_audit",
        lambda domain_id="": {"status": "violations", "domains": [], "summary": {}},
    )
    with patch("sys.argv", ["cockpit", "facts-audit"]):
        assert main() == 1

    monkeypatch.setattr(
        l4bridge.governance_context,
        "domain_facts_audit",
        lambda domain_id="": {"status": "unavailable", "domains": [], "summary": {}},
    )
    with patch("sys.argv", ["cockpit", "facts-audit", "unknown"]):
        assert main() == 2


def test_facts_validation_json_forwards_runtime_evidence_contract(monkeypatch, capsys):
    """facts-validation preserves the bounded Runtime evidence envelope."""
    from cockpit.commands import l4bridge

    payload = {
        "schema": "cockpit.domain-facts-validation.v1",
        "status": "ok",
        "available": True,
        "domain_id": "vault",
        "validation": {"facts_total": 3, "by_type": {"info": 3}, "error_count": 0, "warning_count": 0},
    }
    seen = []
    monkeypatch.setattr(
        l4bridge.governance_context,
        "domain_facts_validation_status",
        lambda domain_id="": seen.append(domain_id) or payload,
    )

    with patch("sys.argv", ["cockpit", "facts-validation", "vault", "--json"]):
        assert main() == 0

    assert seen == ["vault"]
    assert json.loads(capsys.readouterr().out) == payload


def test_kems_status_json_preserves_governance_envelope(monkeypatch, capsys):
    """The fast KEMS projection must be consumable without parsing Rich output."""
    from cockpit.commands import kems

    payload = {
        "schema": "cockpit.kems-status.v1",
        "status": "degraded",
        "available": True,
        "documents_root": "/tmp/Documents",
        "domains": {"status": "ok", "total": 12},
        "content_audit": {
            "owner": "l4-kernel",
            "status": "not_run",
            "available": False,
            "violations": [],
            "reason": "full Documents content audit is on-demand; run cockpit kems scan",
        },
        "owners": {"omo": {"status": "ok"}, "kairon": {"status": "ok"}},
    }
    monkeypatch.setattr(kems.governance_context, "kems_status", lambda: payload)

    with patch("sys.argv", ["cockpit", "kems", "status", "--json"]):
        assert main() == 1

    assert json.loads(capsys.readouterr().out) == payload


def test_facts_validation_maps_violations_and_unavailable_to_contract_exit_codes(monkeypatch):
    from cockpit.commands import l4bridge

    monkeypatch.setattr(
        l4bridge.governance_context,
        "domain_facts_validation_status",
        lambda domain_id="": {"status": "violations", "validation": {}},
    )
    with patch("sys.argv", ["cockpit", "facts-validation", "vault"]):
        assert main() == 1

    monkeypatch.setattr(
        l4bridge.governance_context,
        "domain_facts_validation_status",
        lambda domain_id="": {"status": "unavailable", "validation": {}},
    )
    with patch("sys.argv", ["cockpit", "facts-validation", "unknown"]):
        assert main() == 2


@pytest.mark.parametrize(
    ("status", "expected_exit"),
    [("ok", 0), ("attention", 1), ("unavailable", 2)],
)
def test_model_freshness_json_preserves_envelope_and_exit_contract(monkeypatch, capsys, status, expected_exit):
    from cockpit.commands import l4bridge

    payload = {
        "schema": "cockpit.domain-model-freshness.v1",
        "status": status,
        "available": status != "unavailable",
        "domain_id": "work-weijian",
        "freshness": {
            "checked_on": "2026-08-14",
            "facts_last_reviewed": "2026-08-13",
            "model_markdown_count": 2,
            "fresh_model_count": 1,
            "stale_model_count": 1,
            "invalid_reviewed_count": 0,
            "unreadable_regular_file_count": 0,
            "error": None,
        },
    }
    seen = []
    monkeypatch.setattr(
        l4bridge.governance_context,
        "domain_model_freshness_status",
        lambda domain_id: seen.append(domain_id) or payload,
        raising=False,
    )

    with patch("sys.argv", ["cockpit", "model-freshness", "work-weijian", "--json"]):
        assert main() == expected_exit

    assert seen == ["work-weijian"]
    assert json.loads(capsys.readouterr().out) == payload


def test_model_freshness_text_prints_only_status_and_aggregates(monkeypatch, capsys):
    from cockpit.commands import l4bridge

    payload = {
        "schema": "cockpit.domain-model-freshness.v1",
        "status": "attention",
        "available": True,
        "domain_id": "work-weijian",
        "freshness": {
            "model_markdown_count": 2,
            "fresh_model_count": 1,
            "stale_model_count": 1,
            "invalid_reviewed_count": 0,
            "unreadable_regular_file_count": 0,
            "private_model_name": "fixture-private-model.md",
        },
    }
    monkeypatch.setattr(
        l4bridge.governance_context,
        "domain_model_freshness_status",
        lambda _domain_id: payload,
        raising=False,
    )

    with patch("sys.argv", ["cockpit", "model-freshness", "work-weijian"]):
        assert main() == 1

    output = capsys.readouterr().out
    assert "attention" in output
    assert "models=2" in output
    assert "fresh=1" in output
    assert "stale=1" in output
    assert "invalid=0" in output
    assert "unreadable=0" in output
    assert "fixture-private-model.md" not in output


def test_controller_shadow_json_preserves_observed_not_cut_over_contract(monkeypatch, capsys):
    from cockpit.commands import l4bridge

    payload = {
        "schema": "cockpit.domain-controller-shadow.v2",
        "status": "shadow_observed",
        "available": True,
        "domain_id": "work-weijian",
        "shadow": {"legacy_controller_replaced": False},
    }
    monkeypatch.setattr(
        l4bridge.governance_context,
        "domain_controller_shadow_status",
        lambda domain_id="": payload,
    )
    with patch("sys.argv", ["cockpit", "controller-shadow", "work-weijian", "--json"]):
        assert main() == 1

    assert json.loads(capsys.readouterr().out) == payload
