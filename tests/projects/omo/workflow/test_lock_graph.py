import os
import json
from pathlib import Path
from omo.workflow.lock_graph import generate_lock_graph_snapshot

def test_generate_lock_graph_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr("omo.workflow.lock_graph.STATE_DIR", tmp_path)
    # create mock locks
    locks_dir = tmp_path / "_delivery" / "agent-workflows" / "locks"
    locks_dir.mkdir(parents=True)
    (locks_dir / "projects=gbrain").write_text('{"run_id": "r1", "paths": ["projects/gbrain"]}')
    
    generate_lock_graph_snapshot()
    
    out_file = tmp_path / "state" / "lock-graph.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert "r1" in data["active_runs"]
