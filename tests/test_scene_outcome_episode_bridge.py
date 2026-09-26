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


def _load_agent_workflow():
    spec = importlib.util.spec_from_file_location(
        "agent_workflow_bin", ROOT / "bin" / "agent-workflow.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["agent_workflow_bin"] = module
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
    """Every ``Outcome.Human.v1`` row, including the recorder's own scene mirror.

    Since SH-5 (#4363) the recorder appends an ``Outcome.Human.v1`` carrying
    ``source: scene-outcome-bridge`` for *every* adjudication — including scenes
    with no personal episode and episodes that are not bridge-eligible — before
    the kernel write.  Counting rows therefore no longer says anything about
    whether an outcome landed on an episode; use :func:`_kernel_outcomes` for
    that.
    """
    broker = LedgerBroker.connect(str(db))
    try:
        return broker.read(event_type=EVT_OUTCOME_HUMAN)
    finally:
        broker.close()


def _kernel_outcomes(db: Path) -> list[dict]:
    """Outcome rows written by the personal-episode kernel, not the recorder.

    The kernel row is the one carrying a ``feedback_id`` (its own
    ``outcome_feedback_schema``); the recorder's mirror row never has one, and
    the two differ in ``episode_id`` format as well.
    """
    return [
        row
        for row in _outcomes(db)
        if "feedback_id" in json.loads(row["payload_json"])
    ]


def _scene_mirror_outcomes(db: Path) -> list[dict]:
    """Outcome rows stamped by the recorder's own bridge step."""
    return [
        row
        for row in _outcomes(db)
        if json.loads(row["payload_json"]).get("source") == "scene-outcome-bridge"
    ]


def test_accepted_outcome_bridges_to_episode(ledger_env, ready_episode, scene_card):
    mod = _load_recorder()
    entry = mod.record_outcome(scene_card, "run-001", "accepted", actor="human", review_seconds=30, saved_seconds=120)

    assert entry["personal_episode_bridge"] is True
    assert entry["personal_episode_id"] == ready_episode

    rows = _kernel_outcomes(ledger_env)
    assert len(rows) == 1
    payload = json.loads(rows[0]["payload_json"])
    assert payload["verdict"] == "accept"
    # The recorder stamps its own scene-level row next to the kernel row; it is
    # not evidence of an episode landing, so it must stay a separate assertion.
    mirror = _scene_mirror_outcomes(ledger_env)
    assert len(mirror) == 1
    assert json.loads(mirror[0]["payload_json"])["run_id"] == "run-001"
    assert len(_outcomes(ledger_env)) == 2
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

    assert len(_kernel_outcomes(ledger_env)) == 1
    assert len(_outcomes(ledger_env)) == 2  # kernel row + one deduplicated mirror
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
    rows = _kernel_outcomes(ledger_env)
    payload = json.loads(rows[-1]["payload_json"])
    assert payload["verdict"] == "edit"
    assert payload["revision_receipt"]["changed_fields"] == ["next_action"]


def test_non_personal_scene_skips_bridge(ledger_env, ready_episode, tmp_path):
    mod = _load_recorder()
    card = tmp_path / "scene-other.yaml"
    card.write_text("scene_id: scene-admin-classify\ntitle: other\n", encoding="utf-8")
    entry = mod.record_outcome(card, "run-100", "accepted", actor="human")
    assert "personal_episode_bridge" not in entry
    # A non-personal scene still gets the recorder's mirror row; what it must
    # never get is an outcome on someone else's episode.
    assert _kernel_outcomes(ledger_env) == []
    assert len(_scene_mirror_outcomes(ledger_env)) == 1


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
    assert _kernel_outcomes(ledger_env) == []
    assert [r for r in _outcomes(ledger_env) if r.get("episode_id") == result.episode.episode_id] == []
    assert result.episode.episode_id  # episode exists but untouched


def test_older_episode_without_evidence_falls_through_to_latest(ledger_env, ready_episode, scene_card):
    """An episode lacking evidence must not shadow the later ready one."""
    mod = _load_recorder()
    entry = mod.record_outcome(scene_card, "run-300", "rejected", actor="human")
    assert entry["personal_episode_bridge"] is True
    assert entry["personal_episode_id"] == ready_episode
    payload = json.loads(_kernel_outcomes(ledger_env)[0]["payload_json"])
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


# --- workflow-scene-map resolution (BET-Y2Q4-SH-5.3) -------------------------
# The closeout bridge resolves a workflow id to a scene card before it can call
# the recorder above, so a resolver that silently drops the map's declared
# fallback loses the episode upstream of everything tested so far.  These cases
# stay on the pure resolver on purpose — the bridge itself reads a live run
# record and spawns a subprocess, which no in-repo test should depend on.

DEFAULT_CARD = "scenes/agent-workflow-closeout.yaml"


def _scene_map(**overrides):
    base = {
        "schema": "workflow-scene-map/v1",
        "map": {"project-code-change": "scenes/project-code-change.yaml"},
        "default": DEFAULT_CARD,
        "fallback_resolution": "default",
    }
    base.update(overrides)
    return base


def test_direct_map_hit_resolves_silently():
    aw = _load_agent_workflow()
    path, notice = aw._scene_card_from_map(_scene_map(), "project-code-change")
    assert path == "scenes/project-code-change.yaml"
    assert notice == ""


def test_unmapped_workflow_resolves_through_declared_default():
    aw = _load_agent_workflow()
    path, notice = aw._scene_card_from_map(_scene_map(), "state-sync")
    assert path == DEFAULT_CARD
    assert "state-sync" in notice and "fallback_resolution: default" in notice


def test_no_fallback_resolution_declared_stays_unresolved():
    aw = _load_agent_workflow()
    scene_map = _scene_map()
    del scene_map["fallback_resolution"]
    path, notice = aw._scene_card_from_map(scene_map, "state-sync")
    assert path == ""
    assert "no usable 'fallback_resolution: default'" in notice


def test_fallback_resolution_naming_an_empty_default_stays_unresolved():
    aw = _load_agent_workflow()
    path, notice = aw._scene_card_from_map(
        _scene_map(default=""), "state-sync"
    )
    assert path == ""
    assert "no usable 'fallback_resolution: default'" in notice
    assert "default: empty" in notice


def test_fallback_is_no_looser_than_direct_lookup():
    """A blank map entry behaves like an absent one; an unusable scene map resolves to nothing."""
    aw = _load_agent_workflow()
    scene_map = _scene_map(map={"round-gate-check": "   ", "project-code-change": "scenes/x.yaml"})
    path, notice = aw._scene_card_from_map(scene_map, "round-gate-check")
    assert path == DEFAULT_CARD
    assert "is not in scene map 'map:' section" in notice

    for broken in (None, [], "map", {}, {"map": ["not", "a", "mapping"]}):
        path, notice = aw._scene_card_from_map(broken, "project-code-change")  # type: ignore[arg-type]
        assert path == "", broken
        assert notice != "", broken


def test_fallback_hit_is_distinguishable_from_unresolved_bail():
    """Both carry a notice, so only the resolved path separates the two outcomes."""
    aw = _load_agent_workflow()
    hit_path, hit_notice = aw._scene_card_from_map(_scene_map(), "scene-execution")
    miss_scene_map = _scene_map()
    del miss_scene_map["default"]
    miss_path, miss_notice = aw._scene_card_from_map(miss_scene_map, "scene-execution")

    assert hit_path and miss_path == ""
    assert hit_notice and miss_notice
