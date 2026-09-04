---
lifecycle: plan
owner: governance-team
last_updated: 2026-08-18
last_updated: 2026-09-03
title: Phase 4 Federalization Implementation Plan
type: doc
---
# Phase 4 Federalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 4 of the OMO Governance Federalization, which introduces Strict Pre-allocation (Deadlock Prevention), Lock Graph Observability, Shift-Left Blast Radius constraints, and Zombie Worktree Pruning, all converging on a single source of truth (SSOT).

**Architecture:** 
1. **Deadlock Prevention**: Modify `agent-workflow.py` and `lifecycle.py` to enforce strict lock pre-allocation by checking all dependencies via `affected-graph.py`.
2. **Lock Graph Observability**: Extract active locks and affected-graph dependencies, outputting a `.omo/state/lock-graph.json` snapshot, and update `swarm-activity-dashboard.py` to parse and render it as an ASCII tree.
3. **Shift-Left Blast Radius**: Introduce `--affected-hash` check in `claim_run` to ensure agents execute `affected-graph.py` proactively. Update `AGENTS.md`.
4. **Zombie Pruning**: Create `bin/gac/swarm-prune-zombies.py` to reap inactive worktrees/locks >72h, and expose via `make swarm-prune`. Integrate into `.github/workflows/gac-maintenance.yml`.

**Tech Stack:** Python, Git, GitHub Actions, Bash, JSON

## Global Constraints

- OMO core path logic is strictly localized in `projects/omo/src/omo/`.
- All execution paths use `uv run python` where appropriate.
- Never modify `docs/layer-contract.yaml`; read it strictly as SSOT.
- All testing paths run `pytest` via `uv run pytest`.

---

### Task 1: Lock Graph Snapshot Generation

**Files:**
- Create: `projects/omo/src/omo/workflow/lock_graph.py`
- Create: `tests/projects/omo/workflow/test_lock_graph.py`

**Interfaces:**
- Consumes: `.omo/_delivery/agent-workflows/locks/` and `bin/gac/affected-graph.py` output logic.
- Produces: `omo.workflow.lock_graph.generate_lock_graph_snapshot()` -> writes to `.omo/state/lock-graph.json`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/projects/omo/workflow/test_lock_graph.py -v`
Expected: FAIL with ModuleNotFoundError or similar.

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/projects/omo/workflow/test_lock_graph.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add projects/omo/src/omo/workflow/lock_graph.py tests/projects/omo/workflow/test_lock_graph.py
git commit -m "feat(omo): add lock graph snapshot generator"
```

### Task 2: Shift-Left `--affected-hash` Enforcment in claim_run

**Files:**
- Modify: `projects/omo/src/omo/workflow/lifecycle.py`
- Modify: `projects/omo/src/omo/cli.py`

**Interfaces:**
- Consumes: `agent-workflow claim` CLI options.
- Produces: Enhanced `claim_run` that rejects locks without a valid affected-hash.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from omo.workflow.lifecycle import claim_run, WorkflowError

def test_claim_run_requires_hash(tmp_path, monkeypatch):
    # Mock environment setup
    with pytest.raises(WorkflowError, match="Missing or invalid affected-hash. You must run affected-graph.py first."):
        claim_run("run123", ["projects/gbrain"], affected_hash=None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/projects/omo/workflow/test_lifecycle.py -v`
Expected: FAIL with TypeError for unexpected keyword argument.

- [ ] **Step 3: Write minimal implementation**

Modify `omo.workflow.lifecycle`:
```python
def claim_run(run_id: str, paths: list[str], affected_hash: str = None):
    if not affected_hash:
        raise WorkflowError("Missing or invalid affected-hash. You must run affected-graph.py first.")
    # existing overlap detection...
    pass
```

Modify `omo.cli` to parse `--affected-hash` and pass to `claim_run`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/projects/omo/workflow/test_lifecycle.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add projects/omo/src/omo/workflow/lifecycle.py projects/omo/src/omo/cli.py tests/projects/omo/workflow/test_lifecycle.py
git commit -m "feat(omo): enforce affected-hash requirement for shift-left awareness"
```

### Task 3: Zombie Worktree Pruning Script

**Files:**
- Create: `bin/gac/swarm-prune-zombies.py`

**Interfaces:**
- Consumes: `.omo/_delivery/agent-workflows/runs/` timestamps.
- Produces: CLI script that removes directories older than 72 hours if `--apply` is passed.

- [ ] **Step 1: Write the failing test**

```python
import subprocess
import time
import os

def test_prune_zombies_dry_run(tmp_path):
    run_dir = tmp_path / ".omo" / "_delivery" / "agent-workflows" / "runs" / "r1"
    run_dir.mkdir(parents=True)
    # Set mtime to 4 days ago
    past_time = time.time() - (4 * 24 * 3600)
    os.utime(run_dir, (past_time, past_time))
    
    result = subprocess.run(["python", "bin/gac/swarm-prune-zombies.py", "--dir", str(tmp_path)], capture_output=True, text=True)
    assert "Found 1 zombie runs" in result.stdout
    assert run_dir.exists() # dry-run should not delete
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/bin/test_prune_zombies.py -v`
Expected: FAIL due to missing script file.

- [ ] **Step 3: Write minimal implementation**

```python
import os
import sys
import time
import shutil
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=".")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    
    base_dir = Path(args.dir) / ".omo" / "_delivery" / "agent-workflows" / "runs"
    if not base_dir.exists():
        print("Found 0 zombie runs")
        return
        
    zombies = []
    now = time.time()
    for run in base_dir.iterdir():
        if run.is_dir():
            if (now - run.stat().st_mtime) > 72 * 3600:
                zombies.append(run)
                
    print(f"Found {len(zombies)} zombie runs")
    if args.apply:
        for z in zombies:
            shutil.rmtree(z)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/bin/test_prune_zombies.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bin/gac/swarm-prune-zombies.py tests/bin/test_prune_zombies.py
git commit -m "feat(gac): add zombie run pruning script"
```

### Task 4: Hook and Makefile Integration

**Files:**
- Modify: `Makefile`
- Create: `.github/workflows/gac-maintenance.yml`

**Interfaces:**
- Consumes: `bin/gac/swarm-prune-zombies.py`
- Produces: `make swarm-prune` command, CI cron job.

- [ ] **Step 1: Write Makefile Target**

Add to `Makefile`:
```makefile
.PHONY: swarm-prune
swarm-prune:
	python3 bin/gac/swarm-prune-zombies.py --apply
```

- [ ] **Step 2: Write GitHub Action Workflow**

Create `.github/workflows/gac-maintenance.yml`:
```yaml
name: GAC Maintenance
on:
  schedule:
    - cron: '0 2 * * *'
jobs:
  prune:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: make swarm-prune
```

- [ ] **Step 3: Run test**

Run: `make swarm-prune --dry-run` to ensure command exists.

- [ ] **Step 4: Commit**

```bash
git add Makefile .github/workflows/gac-maintenance.yml
git commit -m "chore(build): add make swarm-prune and cron job"
```

---
