from __future__ import annotations

import json

import pytest
from omo.knowledge_action import (
    KnowledgeActionError,
    build_knowledge_action_snapshot,
    read_knowledge_actions,
    record_knowledge_action,
)


def _binding() -> dict[str, str]:
    return {
        "scene_id": "engineering-delivery",
        "journey_id": "knowledge-to-action",
        "outcome_metric": "task_adoption_rate",
    }


def _task_payload() -> dict:
    return {
        "action_kind": "task_created",
        "query": "如何降低交付返工？",
        "knowledge_refs": [{"ref": "kos:delivery-1", "title": "交付复盘", "source_type": "kos", "rank": 1}],
        "scene_binding": _binding(),
        "task_ref": "cockpit-manual-1",
    }


def test_record_is_reference_only_and_idempotent(tmp_path):
    result = record_knowledge_action(tmp_path, _task_payload(), actor="cockpit-ui://knowledge-action")
    duplicate = record_knowledge_action(tmp_path, _task_payload(), actor="cockpit-ui://knowledge-action")

    assert result["status"] == "recorded"
    assert duplicate["status"] == "deduplicated"
    record = read_knowledge_actions(tmp_path)[0]
    assert record["query_digest"].startswith("sha256:")
    assert "query" not in record
    assert "raw_content" not in record
    assert (tmp_path / "_knowledge/knowledge-mesh/actions.jsonl").is_file()


def test_snapshot_projects_funnel_and_sources(tmp_path):
    record_knowledge_action(
        tmp_path,
        {"action_kind": "retrieved", "query": "治理", "knowledge_refs": [{"ref": "kos:1"}]},
    )
    record_knowledge_action(tmp_path, {"action_kind": "cited", "query": "治理", "knowledge_refs": [{"ref": "kos:1"}]})
    record_knowledge_action(tmp_path, _task_payload())

    snapshot = build_knowledge_action_snapshot(tmp_path, scene_id="engineering-delivery")
    assert snapshot["summary"]["action_count"] == 1
    assert snapshot["funnel"]["task_created"] == 1
    assert snapshot["top_sources"] == [{"ref": "kos:delivery-1", "use_count": 1}]
    assert snapshot["next_action"] == "request_workflow_from_task"


@pytest.mark.parametrize(
    "payload",
    [
        {"action_kind": "task_created", "query": "x", "knowledge_refs": [], "scene_binding": _binding(), "task_ref": "t"},
        {"action_kind": "cited", "query": "x", "knowledge_refs": [{"ref": "kos:1", "raw_content": "secret"}]},
        {"action_kind": "workflow_requested", "query": "x", "knowledge_refs": [{"ref": "kos:1"}], "scene_binding": _binding()},
    ],
)
def test_invalid_receipts_are_rejected(tmp_path, payload):
    with pytest.raises(KnowledgeActionError):
        record_knowledge_action(tmp_path, payload)


def test_log_lines_are_json_objects(tmp_path):
    record_knowledge_action(tmp_path, _task_payload())
    line = (tmp_path / "_knowledge/knowledge-mesh/actions.jsonl").read_text(encoding="utf-8").strip()
    assert isinstance(json.loads(line), dict)
