import subprocess
import time
import os

def test_prune_zombies_dry_run(tmp_path):
    run_dir = tmp_path / ".omo" / "_delivery" / "agent-workflows" / "runs" / "r1"
    run_dir.mkdir(parents=True)
    # Set mtime to 4 days ago
    past_time = time.time() - (4 * 24 * 3600)
    os.utime(run_dir, (past_time, past_time))
    
    result = subprocess.run(["python3", "bin/gac/swarm-prune-zombies.py", "--dir", str(tmp_path)], capture_output=True, text=True)
    assert "Found 1 zombie runs" in result.stdout
    assert run_dir.exists() # dry-run should not delete
