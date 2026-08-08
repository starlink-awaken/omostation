import os
import json
from pathlib import Path

STATE_DIR = Path(".omo")

def generate_lock_graph_snapshot():
    locks_dir = STATE_DIR / "_delivery" / "agent-workflows" / "locks"
    state_dir = STATE_DIR / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    
    active_runs = {}
    if locks_dir.exists():
        for lock_file in locks_dir.iterdir():
            if lock_file.is_file():
                try:
                    data = json.loads(lock_file.read_text())
                    active_runs[data.get("run_id", "unknown")] = data
                except Exception:
                    pass
                    
    out_file = state_dir / "lock-graph.json"
    out_file.write_text(json.dumps({"active_runs": active_runs}, indent=2))
