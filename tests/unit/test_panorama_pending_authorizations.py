"""Agent-facing pending publication projections must not show terminal effects."""

from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
import shutil
import sys
import tempfile
from pathlib import Path

HOST_DIR = Path(__file__).resolve().parents[2] / "bin/panorama/assets/host"


def _module():
    with tempfile.TemporaryDirectory(prefix="pending-auth-live-server-") as directory:
        deployed = Path(directory)
        shutil.copy2(HOST_DIR / "observatory_query.py.asset", deployed / "observatory_query.py")
        server_path = deployed / "live_server_under_test.py"
        shutil.copy2(HOST_DIR / "live_server.py.asset", server_path)
        query_loader = SourceFileLoader(
            "zhixing_observatory_query_pending_auth_test",
            str(deployed / "observatory_query.py"),
        )
        query_spec = importlib.util.spec_from_loader(query_loader.name, query_loader)
        assert query_spec is not None and query_spec.loader is not None
        query_module = importlib.util.module_from_spec(query_spec)
        sys.modules[query_spec.name] = query_module
        query_loader.exec_module(query_module)
        sys.modules["observatory_query"] = query_module
        loader = SourceFileLoader("zhixing_live_server_pending_auth_test", str(server_path))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module


def _item(item_id, state, verification="READY_FOR_OPERATION_SPECIFIC_HUMAN_AUTHORIZATION"):
    return {"id": item_id, "state": state, "verification": verification}


def _manifest(*items):
    return {
        "schema": "pending-publication-manifest/v1",
        "manifest_sha256": "sha256:" + "a" * 64,
        "checked_at": "2026-09-20T00:00:00Z",
        "items": list(items),
    }


def test_merged_stale_item_is_terminal_not_pending():
    module = _module()
    pending = _manifest(_item("old", "MERGED", "STALE_OR_INVALID"))
    projected = module.pending_publication_projection(pending)
    assert projected["items"] == []
    assert projected["terminal_items_count"] == 1
    assert projected["invalid_items_count"] == 0


def test_merged_ready_item_is_still_not_pending():
    module = _module()
    pending = _manifest(_item("ready-but-merged", "MERGED"))
    projected = module.pending_publication_projection(pending)
    assert projected["items"] == []
    assert projected["terminal_items_count"] == 1


def test_actionable_nonterminal_ready_item_is_pending():
    module = _module()
    item = _item("live", "READY")
    projected = module.pending_publication_projection(_manifest(item))
    assert projected["items"] == [item]
    assert projected["terminal_items_count"] == 0
    assert projected["invalid_items_count"] == 0


def test_projection_preserves_manifest_identity_and_counts_history():
    module = _module()
    pending = _manifest(
        _item("live", "READY"),
        _item("merged", "MERGED"),
        _item("bad", None),
        "not-a-dict",
    )
    projected = module.pending_publication_projection(pending)
    assert len(projected["items"]) == 1
    assert projected["terminal_items_count"] == 1
    assert projected["invalid_items_count"] == 2
    assert projected["source_manifest_sha256"] == pending["manifest_sha256"]
    assert projected["checked_at"] == pending["checked_at"]


def test_actionable_items_helper_matches_projection():
    module = _module()
    live = _item("live", "READY")
    assert module.actionable_publication_items(_manifest(live, _item("old", "CLOSED"))) == [live]
