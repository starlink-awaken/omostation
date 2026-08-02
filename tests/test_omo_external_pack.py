from __future__ import annotations

import json
import sys
from io import StringIO

import omo.omo_external_resources as external_resources
import pytest
from omo.cli import main as cli_main
from omo.omo_external_pack import (
    ExternalResourcePackProposalError,
    read_external_resource_pack_proposals,
    record_external_resource_pack_proposal,
)


def _projection(status: str = "ready_for_catalog_preview") -> dict[str, object]:
    return {
        "schema": "external-resource-pack-check/v1",
        "mode": "read_only_conformance",
        "activation": "forbidden",
        "status": status,
        "reason_codes": [],
        "pack": {
            "pack_id": "pack:research",
            "pack_version": "1.0.0",
            "provider": "research-provider",
        },
        "catalog_preview": {
            "schema": "external-resource-pack-catalog-preview/v1",
            "mode": "read_only_pack_preview",
            "activation": "forbidden",
            "status": status,
            "source": "external-resource-pack-manifest",
            "pack": {"pack_id": "pack:research", "pack_version": "1.0.0"},
            "resource": {
                "id": "source:research",
                "kind": "knowledge_source",
                "provider": "research-provider",
                "version": "1.0.0",
                "lifecycle": "sandbox",
                "mode": "live_query",
                "capabilities": ["discover", "search"],
                "permission_ref": "permission://research/read",
                "availability": "unobserved",
                "health": {
                    "status": "unobserved",
                    "source": "external-resource-pack-manifest",
                },
            },
            "next_action": "通过只读目录发现和健康探针后再评估可用性。",
        },
    }


def test_pack_proposal_is_safe_durable_and_idempotent(tmp_path):
    first = record_external_resource_pack_proposal(
        tmp_path,
        _projection(),
        proposal_id="proposal:research:1",
        actor="operator:test",
        review_ref="evidence://review/research-1",
    )
    repeated = record_external_resource_pack_proposal(
        tmp_path,
        _projection(),
        proposal_id="proposal:research:1",
        actor="operator:test",
        review_ref="evidence://review/research-1",
    )

    assert first["status"] == "recorded"
    assert repeated["status"] == "deduplicated"
    proposal = first["proposal"]
    assert proposal["schema"] == "external-resource-pack-proposal-observation/v1"
    assert proposal["activation"] == "forbidden"
    assert proposal["provider_invocation"] is False
    assert proposal["next_stage"] == "catalog_discovery"
    assert len(read_external_resource_pack_proposals(tmp_path)) == 1
    encoded = json.dumps(proposal, ensure_ascii=False)
    assert "raw_output" not in encoded
    assert "permission://research/read" in encoded


def test_proposal_only_pack_routes_to_evaluation(tmp_path):
    result = record_external_resource_pack_proposal(
        tmp_path,
        _projection("proposal_only"),
        proposal_id="proposal:method:1",
        review_action="defer",
    )

    assert result["proposal"]["proposal_status"] == "proposal_only"
    assert result["proposal"]["next_stage"] == "proposal_evaluation"
    assert result["proposal"]["review_action"] == "defer"


def test_blocked_pack_and_tampered_preview_fail_closed(tmp_path):
    with pytest.raises(ExternalResourcePackProposalError, match="only proposal_only"):
        record_external_resource_pack_proposal(
            tmp_path,
            _projection("blocked"),
            proposal_id="proposal:blocked:1",
        )

    tampered = _projection()
    tampered["catalog_preview"] = dict(tampered["catalog_preview"], resource={"availability": "available"})
    with pytest.raises(ExternalResourcePackProposalError, match="availability"):
        record_external_resource_pack_proposal(
            tmp_path,
            tampered,
            proposal_id="proposal:tampered:1",
        )


def test_conflicting_proposal_id_fails_closed(tmp_path):
    record_external_resource_pack_proposal(
        tmp_path, _projection(), proposal_id="proposal:fixed:1"
    )
    changed = _projection()
    changed["pack"] = {"pack_id": "pack:other", "pack_version": "2.0.0", "provider": "other"}
    with pytest.raises(ExternalResourcePackProposalError, match="conflicting"):
        record_external_resource_pack_proposal(
            tmp_path, changed, proposal_id="proposal:fixed:1"
        )


def test_pack_proposal_cli_records_safe_receipt(tmp_path, capsys, monkeypatch):
    payload = json.dumps(_projection())

    monkeypatch.setattr(external_resources, "find_omo_dir", lambda: tmp_path)

    old_stdin = sys.stdin
    try:
        sys.stdin = StringIO(payload)
        assert (
            cli_main(
                [
                    "external-resources",
                    "record-pack-proposal",
                    "--stdin",
                    "--proposal-id",
                    "proposal:cli:1",
                    "--json",
                ]
            )
            == 0
        )
    finally:
        sys.stdin = old_stdin
    body = json.loads(capsys.readouterr().out)
    assert body["ok"] is True
    assert body["proposal"]["proposal_receipt_id"].startswith("external-pack-proposal:")
