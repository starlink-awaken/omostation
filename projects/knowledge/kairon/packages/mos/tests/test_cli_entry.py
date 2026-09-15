"""CLI entry exercises real main() with file-backed store."""

import json

from mos.cli import main


def test_cli_write_recall_status(capsys, tmp_path, monkeypatch):
    store = tmp_path / "mos-store.json"
    monkeypatch.setenv("MOS_STORE_PATH", str(store))

    assert main(["write", "--type", "semantic", "--content", "prefers dark mode UI", "--json"]) == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["ok"] is True
    assert data["raw_ok"] is True
    assert data["theta_ok"] is True
    assert store.exists()

    # New "process" — still hits file store
    assert main(["recall", "dark mode UI", "--intent", "preference_self", "--json"]) == 0
    recall = json.loads(capsys.readouterr().out)
    assert recall["count"] >= 1
    assert any("dark" in json.dumps(h).lower() for h in recall["hits"])

    assert main(["status"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["ok"] is True
    assert status.get("theta_docs", 0) >= 1
