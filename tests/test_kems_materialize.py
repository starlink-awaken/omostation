import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location("kems_materialize", Path(__file__).parents[1] / "scripts" / "kems-materialize.py")
assert _SPEC and _SPEC.loader
kems_materialize = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(kems_materialize)


def test_source_files_deduplicate_patterns(tmp_path):
    inbox = tmp_path / "_inbox"
    inbox.mkdir()
    (inbox / "2026-auto-apple-mail.md").write_text("# mail", encoding="utf-8")
    (inbox / "2026-auto-seeyon-oa-pending.md").write_text("# oa", encoding="utf-8")
    assert [path.name for path in kems_materialize.source_files(tmp_path)] == [
        "2026-auto-apple-mail.md",
        "2026-auto-seeyon-oa-pending.md",
    ]


def test_materialize_requires_kairon_graph_store(tmp_path, monkeypatch):
    (tmp_path / "_inbox").mkdir()
    (tmp_path / "_inbox" / "2026-auto-apple-mail.md").write_text("# mail", encoding="utf-8")
    monkeypatch.setenv("BOS_KAIRon_ROOT", str(tmp_path / "missing"))
    with pytest.raises(RuntimeError, match="Kairon KOS source"):
        kems_materialize.materialize(tmp_path, tmp_path / "graph.sqlite", "run-1")
