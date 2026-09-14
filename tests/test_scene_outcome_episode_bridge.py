"""scene-outcome-recorder → PersonalEpisodeService bridge (W2-05 integration).

End-to-end golden path: a personal-signal episode flows through
ingest → confirm → evidence, then a human scene adjudication recorded via
``scene-outcome-recorder`` must land as ``Outcome.Human.v1`` on the episode
ledger (readiness gate feedback), idempotently by feedback id.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OMO_SRC = ROOT / "projects" / "omo" / "src"
ECOS_SRC = ROOT / "projects" / "ecos" / "src"
BIN_SSOT = ROOT / "bin" / "ssot"

if not (OMO_SRC / "omo" / "personal_episode.py").exists():
    pytest.skip("omo submodule required (projects/omo/src)", allow_module_level=True)

# Insert BEFORE any omo import so the worktree's omo wins over the venv's
# .pth-installed workspace copy (which pytest.importorskip would cache).
sys.path.insert(0, str(OMO_SRC))
sys.path.insert(0, str(ECOS_SRC))
sys.path.insert(0, str(BIN_SSOT))

from omo.event_ledger import LedgerBroker  # noqa: E402
from omo.personal_episode import (  # noqa: E402
    EVT_EVIDENCE_LOCAL_DRAFT,
    EVT_EPISODE_DECISION,
    EVT_OUTCOME_HUMAN,
    PersonalEpisodeService,
    PersonalLocalSignal,
)
from omo.sovereignty import SovereigntyService  # noqa: E402

PRINCIPAL = "principal:alice"


def _load_recorder():
    spec = importlib.util.spec_from_file_location(
        "scene_outcome_recorder", BIN_SSOT / "scene-outcome-recorder.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["scene_outcome_recorder"] = module
    spec.loader.exec_module(module)
    return module


def _evidence_ref(seed: str = "draft") -> str:
    return f"evidence://personal-draft/sha256:{hashlib.sha256(seed.encode()).hexdigest()}"


@pytest.fixture()
def ledger_env(tmp_path, monkeypatch):
    db = tmp_path / "event-ledger.sqlite3"
    monkeypatch.setenv("OMO_EVENT_LEDGER_DB", str(db))
    monkeypatch.setenv("OMO_PRINCIPAL_ID", PRINCIPAL)
    return db


@pytest.fixture()
def ready_episode(ledger_env):
    """Personal-signal episode through ingest → confirm → evidence."""
    service = PersonalEpisodeService.open(str(ledger_env))
    SovereigntyService(service._broker).assign(
        PRINCIPAL,
        "role:personal-steward",
        role_name="Personal Steward",
        scope="personal",
        responsibilities=["follow-up"],
    )
    signal = PersonalLocalSignal(
        source_id="iris-local-files",
        item_id="bm90ZXMvZm9sbG93LXVwLm1k",
        title="Follow up with the project team",
        content_sha256="a" * 64,
        source_uri="iris://local-files/bm90ZXMvZm9sbG93LXVwLm1k",
        principal_id=PRINCIPAL,
        role_id="role:personal-steward",
        responsibility_id="responsibility:follow-up",
        executor_id="agent:personal-steward",
    )
    result = service.ingest_local_signal(signal)
    service.confirm(
        episode_id=result.episode.episode_id,
        principal_id=PRINCIPAL,
        executor_id="agent:personal-steward",
        human_confirmed=True,
    )
    context = service.reload_execution_context(result.episode.episode_id, PRINCIPAL)
    service.record_evidence(context, _evidence_ref("system"), output_origin="system")
    return result.episode.episode_id


@pytest.fixture()
def scene_card(tmp_path):
    card = tmp_path / "scene-personal-followup-dogfood.yaml"
    card.write_text(
        "scene_id: personal-followup-dogfood\n"
        "title: personal follow-up dogfood\n"
        "lifecycle: supervised\n",
        encoding="utf-8",
    )
    return card


def _outcomes(db: Path) -> list[dict]:
    broker = LedgerBroker.connect(str(db))
    try:
        return broker.read(event_type=EVT_OUTCOME_HUMAN)
    finally:
        broker.close()


def test_accepted_outcome_bridges_to_episode(ledger_env, ready_episode, scene_card):
    mod = _load_recorder()
    entry = mod.record_outcome(scene_card, "run-001", "accepted", actor="human", review_seconds=30, saved_seconds=120)

    assert entry["personal_episode_bridge"] is True
    assert entry["personal_episode_id"] == ready_episode

    rows = _outcomes(ledger_env)
    assert len(rows) == 1
    payload = json.loads(rows[0]["payload_json"])
    assert payload["verdict"] == "accept"
    expected_feedback_ref = (
        "feedback://sha256:"
        + hashlib.sha256("scene:personal-followup-dogfood:run-001".encode()).hexdigest()
    )
    assert payload["feedback_id"] == expected_feedback_ref
    assert payload["review_duration_seconds"] == 30.0
    assert payload["estimated_time_saved_seconds"] == 120.0


def test_replay_is_idempotent(ledger_env, ready_episode, scene_card):
    mod = _load_recorder()
    first = mod.record_outcome(scene_card, "run-001", "accepted", actor="human")
    second = mod.record_outcome(scene_card, "run-001", "accepted", actor="human")

    assert _outcomes(ledger_env).__len__() == 1
    assert second["personal_episode_id"] == first["personal_episode_id"]


def test_revised_outcome_requires_receipt(ledger_env, ready_episode, scene_card):
    mod = _load_recorder()
    entry = mod.record_outcome(scene_card, "run-002", "revised", actor="human", revision_diff="")
    assert "personal_episode_bridge" not in entry

    # revised without kernel-vocabulary fields must not fabricate a receipt
    entry = mod.record_outcome(scene_card, "run-003", "revised", actor="human", revision_diff="changed the draft body")
    assert "personal_episode_bridge" not in entry

    entry = mod.record_outcome(
        scene_card,
        "run-004",
        "revised",
        actor="human",
        revision_diff="changed the draft body",
        episode_changed_fields=["next_action"],
    )
    assert entry["personal_episode_bridge"] is True
    rows = _outcomes(ledger_env)
    payload = json.loads(rows[-1]["payload_json"])
    assert payload["verdict"] == "edit"
    assert payload["revision_receipt"]["changed_fields"] == ["next_action"]


def test_non_personal_scene_skips_bridge(ledger_env, ready_episode, tmp_path):
    mod = _load_recorder()
    card = tmp_path / "scene-other.yaml"
    card.write_text("scene_id: scene-admin-classify\ntitle: other\n", encoding="utf-8")
    entry = mod.record_outcome(card, "run-100", "accepted", actor="human")
    assert "personal_episode_bridge" not in entry
    assert _outcomes(ledger_env) == []


def test_episode_without_evidence_is_skipped(ledger_env, scene_card):
    """Episode still pending confirmation/evidence must not receive outcomes."""
    service = PersonalEpisodeService.open(str(ledger_env))
    SovereigntyService(service._broker).assign(
        PRINCIPAL,
        "role:personal-steward",
        role_name="Personal Steward",
        scope="personal",
        responsibilities=["follow-up"],
    )
    signal = PersonalLocalSignal(
        source_id="iris-local-files",
        item_id="bm90ZXMvZm9sbG93LXVwLm1k",
        title="Follow up with the project team",
        content_sha256="a" * 64,
        source_uri="iris://local-files/bm90ZXMvZm9sbG93LXVwLm1k",
        principal_id=PRINCIPAL,
        role_id="role:personal-steward",
        responsibility_id="responsibility:follow-up",
        executor_id="agent:personal-steward",
    )
    result = service.ingest_local_signal(signal)

    mod = _load_recorder()
    entry = mod.record_outcome(scene_card, "run-200", "accepted", actor="human")
    assert "personal_episode_bridge" not in entry
    assert os.environ["OMO_EVENT_LEDGER_DB"]
    assert _outcomes(ledger_env) == []
    assert result.episode.episode_id  # episode exists but untouched


def test_older_episode_without_evidence_falls_through_to_latest(ledger_env, ready_episode, scene_card):
    """An episode lacking evidence must not shadow the later ready one."""
    mod = _load_recorder()
    entry = mod.record_outcome(scene_card, "run-300", "rejected", actor="human")
    assert entry["personal_episode_bridge"] is True
    assert entry["personal_episode_id"] == ready_episode
    payload = json.loads(_outcomes(ledger_env)[0]["payload_json"])
    assert payload["verdict"] == "reject"
    # evidence event still the only one on the episode
    broker = LedgerBroker.connect(str(ledger_env))
    try:
        evidence = broker.read(episode_id=ready_episode, event_type=EVT_EVIDENCE_LOCAL_DRAFT)
        starts = broker.read(episode_id=ready_episode, event_type=EVT_EPISODE_DECISION)
        assert len(evidence) == 1
        assert len(starts) >= 1
    finally:
        broker.close()
