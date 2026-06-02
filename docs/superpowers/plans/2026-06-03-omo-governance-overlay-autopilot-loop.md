# OMO Governance Overlay Autopilot Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe first-step governance overlay autopilot loop that advances the top eligible planned-task roadmap item through existing promotion and approval mechanisms.

**Architecture:** Keep the loop thin and in-process. A pure helper in `scripts/omo_governance_overlay_loop.py` will load the governance overlay shell surfaces, resolve the top eligible roadmap item, process only `.omo/tasks/planned/*.yaml` refs, write a governance run artifact, mutate roadmap item status, and then rely on the existing governance overlay status helper to regenerate the current surface. The loop will not auto-handle debt bundles in this slice.

**Tech Stack:** Python 3, `pathlib`, `yaml`, existing governance overlay files, existing promotion / approval helpers already wired in `scripts/omo_worker.py`, pytest under `.omo/tests`

---

## File map

- **Create:** `scripts/omo_governance_overlay_loop.py`
  - Pure helper that advances the top eligible roadmap item, writes a run artifact, and updates roadmap item status.
- **Modify:** `scripts/omo_worker.py`
  - Add `task governance-overlay-run-next --omo-dir .omo --actor <ACTOR> [--now <ISO8601>]`.
- **Create:** `.omo/tests/test_omo_governance_overlay_loop.py`
  - Unit tests for no-op, approval-request, and unsupported-ref paths.
- **Modify:** `.omo/tests/test_omo_automation.py`
  - CLI regression for `governance-overlay-run-next`.
- **Modify:** `.omo/tests/test_worker_mechanism_consistency.py`
  - Docs regression for the autopilot loop command.
- **Modify:** `.omo/_truth/governance-overlay/roadmap.yaml`
  - Roadmap items will now carry mutable execution statuses (`pending|in_progress|blocked|done`).
- **Create:** `.omo/workers/runs/governance-overlay-<STAMP>.yaml`
  - Live governance run artifact from a real loop execution.
- **Modify:** `.omo/workers/README.md`
- **Modify:** `.omo/AGENT.md`
- **Modify:** `.omo/tasks/README.md`
  - Document the overlay loop and how it reuses promotion/approval machinery.
- **Modify:** `.omo/workers/governance-overlay/current.yaml`
- **Modify:** `.omo/workers/governance-overlay/current.md`
  - Regenerated after the loop runs.

## Constraints and invariants

1. Only support `.omo/tasks/planned/*.yaml` refs in first version.
2. Never bypass existing approval gates.
3. Never mutate debt bundles beyond marking the roadmap item blocked for unsupported target refs.
4. Keep using nested `scripts` repo commit flow.

---

### Task 1: Build the autopilot loop helper with TDD

**Files:**
- Create: `.omo/tests/test_omo_governance_overlay_loop.py`
- Create: `scripts/omo_governance_overlay_loop.py`

- [ ] **Step 1: Write the failing helper tests**

Create `.omo/tests/test_omo_governance_overlay_loop.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from scripts.omo_governance_overlay_loop import run_governance_overlay_cycle


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_run_governance_overlay_cycle_returns_idle_when_no_candidates(tmp_path: Path):
    _write_yaml(tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml", {
        "overlay_id": "GOV-OVERLAY-2026-06",
        "status": "active",
        "autopilot_mode": "full_omo_autopilot",
        "intake_scope": "future_planned_debt",
        "current_milestone": "GOV-M1",
        "next_milestone": "GOV-M2",
        "success_target": "future roadmap governed through overlay lane",
        "updated_at": "2026-06-03T06:35:00Z",
    })
    _write_yaml(tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml", {
        "autopilot_mode": "full_omo_autopilot",
        "auto_select": True,
    })
    _write_yaml(tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml", {"items": []})

    result = run_governance_overlay_cycle(tmp_path, omo_dir=".omo", actor="copilot-cli", now="2026-06-03T06:40:00Z")

    assert result["run"]["summary"] == "idle"
    assert result["mutated"] is False


def test_run_governance_overlay_cycle_requests_approval_for_gated_planned_task(tmp_path: Path):
    _write_yaml(tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml", {
        "overlay_id": "GOV-OVERLAY-2026-06",
        "status": "active",
        "autopilot_mode": "full_omo_autopilot",
        "intake_scope": "future_planned_debt",
        "current_milestone": "GOV-M1-EXECUTION-HARDENING",
        "next_milestone": "GOV-M2-SHAREDBRAIN-DEBT",
        "success_target": "future roadmap governed through overlay lane",
        "updated_at": "2026-06-03T06:35:00Z",
    })
    _write_yaml(tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml", {
        "autopilot_mode": "full_omo_autopilot",
        "auto_select": True,
        "auto_promote_when_safe": True,
    })
    _write_yaml(tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml", {
        "items": [
            {
                "id": "GOV-M1-EXECUTION-HARDENING",
                "type": "task-bundle",
                "title": "Execution hardening",
                "priority": "P0",
                "status": "pending",
                "depends_on": [],
                "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                "target_refs": [".omo/tasks/planned/TASK-A.yaml"],
                "success_criteria": ["TASK-A advanced"],
            }
        ]
    })
    _write_yaml(tmp_path / ".omo" / "tasks" / "planned" / "TASK-A.yaml", {
        "id": "TASK-A",
        "phase": 17,
        "milestone": "GOV-M1",
        "priority": "P0",
        "title": "Task A",
        "status": "pending",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "source_docs": [".omo/MASTER-BLUEPRINT.md"],
        "depends_on": [],
        "risk_level": "L2",
        "allowed_operation_level": "L2",
        "human_approval_required": True,
        "entry_gate": ["governance overlay shell ready"],
        "evidence_required": ["approval request created"],
        "test_plan": [".omo/tests/test_omo_governance_overlay_loop.py"],
        "started_at": None,
        "completed_at": None,
        "blocked_by": None,
        "retry_count": 0,
    })

    result = run_governance_overlay_cycle(tmp_path, omo_dir=".omo", actor="copilot-cli", now="2026-06-03T06:40:00Z")

    assert result["run"]["target_results"][0]["result"] == "approval_requested"
    assert result["roadmap"]["items"][0]["status"] == "in_progress"


def test_run_governance_overlay_cycle_blocks_unsupported_target_ref(tmp_path: Path):
    _write_yaml(tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml", {
        "overlay_id": "GOV-OVERLAY-2026-06",
        "status": "active",
        "autopilot_mode": "full_omo_autopilot",
        "intake_scope": "future_planned_debt",
        "current_milestone": "GOV-M2-SHAREDBRAIN-DEBT",
        "next_milestone": "GOV-M3",
        "success_target": "future roadmap governed through overlay lane",
        "updated_at": "2026-06-03T06:35:00Z",
    })
    _write_yaml(tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml", {
        "autopilot_mode": "full_omo_autopilot",
        "auto_select": True,
    })
    _write_yaml(tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml", {
        "items": [
            {
                "id": "GOV-M2-SHAREDBRAIN-DEBT",
                "type": "debt-bundle",
                "title": "SharedBrain debt",
                "priority": "P1",
                "status": "pending",
                "depends_on": [],
                "source_refs": [".omo/debt/registry.yaml"],
                "target_refs": [".omo/debt/dashboard/current.yaml"],
                "success_criteria": ["debt bundle processed"],
            }
        ]
    })
    _write_yaml(tmp_path / ".omo" / "debt" / "dashboard" / "current.yaml", {"items": []})

    result = run_governance_overlay_cycle(tmp_path, omo_dir=".omo", actor="copilot-cli", now="2026-06-03T06:40:00Z")

    assert result["run"]["target_results"][0]["result"] == "unsupported_target_ref"
    assert result["roadmap"]["items"][0]["status"] == "blocked"
```

- [ ] **Step 2: Run helper tests to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_governance_overlay_loop.py -q
```

Expected: import failure because `scripts/omo_governance_overlay_loop.py` does not exist yet.

- [ ] **Step 3: Write the minimal helper implementation**

Create `scripts/omo_governance_overlay_loop.py` with:

1. YAML loaders for overlay state/policy/roadmap
2. `run_governance_overlay_cycle(...)`
3. minimal roadmap mutation rules
4. run packet generation

The implementation should:

```python
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml


def _load_yaml_required(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path.as_posix())
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _roadmap_item_sort_key(item: dict[str, object]) -> tuple[int, str]:
    return (0 if item["priority"] == "P0" else 1, str(item["id"]))


def _target_result(target_ref: str, *, result: str, detail: str, task_id: str | None = None) -> dict[str, object]:
    return {"target_ref": target_ref, "task_id": task_id, "result": result, "detail": detail}


def run_governance_overlay_cycle(root: Path, *, omo_dir: str | Path = ".omo", actor: str, now: str) -> dict[str, object]:
    omo = Path(omo_dir)
    state = _load_yaml_required(root / omo / "_control" / "governance-overlay" / "current.yaml")
    policy = _load_yaml_required(root / omo / "_truth" / "governance-overlay" / "autopilot-policy.yaml")
    roadmap = _load_yaml_required(root / omo / "_truth" / "governance-overlay" / "roadmap.yaml")
    roadmap_mutated = deepcopy(roadmap)

    candidates = [
        item for item in sorted(roadmap_mutated.get("items", []), key=_roadmap_item_sort_key)
        if item.get("status") == "pending"
    ]
    run = {
        "run_id": f"governance-overlay-{now.replace(':', '-').replace('Z', 'Z')}",
        "overlay_id": state["overlay_id"],
        "actor": actor,
        "started_at": now,
        "completed_at": now,
        "roadmap_item_id": None,
        "target_results": [],
        "summary": "idle",
    }
    if not candidates:
        return {"run": run, "roadmap": roadmap_mutated, "mutated": False}

    item = candidates[0]
    run["roadmap_item_id"] = item["id"]
    mutated = False
    unsupported = False
    for target_ref in item.get("target_refs", []):
        target_path = root / target_ref
        if ".omo/tasks/planned/" not in target_ref:
            run["target_results"].append(
                _target_result(target_ref, result="unsupported_target_ref", detail="only planned task refs are supported")
            )
            unsupported = True
            continue
        task = _load_yaml_required(target_path)
        task_id = str(task["id"])
        if task.get("human_approval_required"):
            run["target_results"].append(
                _target_result(target_ref, task_id=task_id, result="approval_requested", detail="approval request required")
            )
            item["status"] = "in_progress"
            mutated = True
        else:
            run["target_results"].append(
                _target_result(target_ref, task_id=task_id, result="promoted", detail="eligible for promotion path")
            )
            item["status"] = "in_progress"
            mutated = True
    if unsupported and not mutated:
        item["status"] = "blocked"
        run["summary"] = "blocked"
    elif mutated:
        run["summary"] = "advanced"
    return {"run": run, "roadmap": roadmap_mutated, "mutated": mutated or unsupported, "policy": policy}
```

- [ ] **Step 4: Run helper tests to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_governance_overlay_loop.py -q
```

Expected: `3 passed`.

---

### Task 2: Wire the CLI and live run artifact flow

**Files:**
- Modify: `scripts/omo_worker.py`
- Modify: `.omo/tests/test_omo_automation.py`
- Modify: `.omo/tests/test_worker_mechanism_consistency.py`
- Modify: `.omo/_truth/governance-overlay/roadmap.yaml`
- Create: `.omo/workers/runs/governance-overlay-<STAMP>.yaml`

- [ ] **Step 1: Write the failing CLI/docs regressions**

Add to `.omo/tests/test_omo_automation.py`:

```python
def test_task_governance_overlay_run_next_writes_run_artifact(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml", {
        "overlay_id": "GOV-OVERLAY-2026-06",
        "status": "active",
        "autopilot_mode": "full_omo_autopilot",
        "intake_scope": "future_planned_debt",
        "current_milestone": "GOV-M1-EXECUTION-HARDENING",
        "next_milestone": "GOV-M2-SHAREDBRAIN-DEBT",
        "success_target": "future roadmap governed through overlay lane",
        "updated_at": "2026-06-03T06:35:00Z",
    })
    _write_yaml(tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml", {
        "autopilot_mode": "full_omo_autopilot",
        "auto_select": True,
        "auto_promote_when_safe": True,
    })
    _write_yaml(tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml", {
        "items": [
            {
                "id": "GOV-M1-EXECUTION-HARDENING",
                "type": "task-bundle",
                "title": "Execution hardening",
                "priority": "P0",
                "status": "pending",
                "depends_on": [],
                "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                "target_refs": [".omo/tasks/planned/TASK-A.yaml"],
                "success_criteria": ["TASK-A advanced"],
            }
        ]
    })
    _write_yaml(tmp_path / ".omo" / "tasks" / "planned" / "TASK-A.yaml", {
        "id": "TASK-A",
        "phase": 17,
        "milestone": "GOV-M1",
        "priority": "P0",
        "title": "Task A",
        "status": "pending",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "source_docs": [".omo/MASTER-BLUEPRINT.md"],
        "depends_on": [],
        "risk_level": "L1",
        "allowed_operation_level": "L1",
        "human_approval_required": False,
        "entry_gate": ["overlay active"],
        "evidence_required": ["promotion path triggered"],
        "test_plan": [".omo/tests/test_omo_governance_overlay_loop.py"],
        "started_at": None,
        "completed_at": None,
        "blocked_by": None,
        "retry_count": 0,
    })

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "governance-overlay-run-next", "--omo-dir", ".omo", "--actor", "copilot-cli", "--now", "2026-06-03T06:40:00Z"],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    run_packet = _load_yaml(tmp_path / ".omo" / "workers" / "runs" / "governance-overlay-2026-06-03T06-40-00Z.yaml")

    assert "summary=advanced" in output
    assert run_packet["roadmap_item_id"] == "GOV-M1-EXECUTION-HARDENING"
```

Add to `.omo/tests/test_worker_mechanism_consistency.py`:

```python
def test_worker_docs_describe_governance_overlay_run_next():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "AGENT.md").read_text(encoding="utf-8")

    assert "governance-overlay-run-next" in workers_text
    assert "governance-overlay-run-next" in agent_text
```

- [ ] **Step 2: Run the new regressions to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py -q -k 'governance_overlay_run_next'
```

Expected: argparse rejects `governance-overlay-run-next` and docs assertions fail.

- [ ] **Step 3: Wire the CLI and run artifact write**

Modify `scripts/omo_worker.py`:

1. import `run_governance_overlay_cycle`
2. add parser:

```python
governance_overlay_run_next_parser = task_sub.add_parser("governance-overlay-run-next")
governance_overlay_run_next_parser.add_argument("--omo-dir", default=".omo")
governance_overlay_run_next_parser.add_argument("--actor", required=True)
governance_overlay_run_next_parser.add_argument("--now")
```

3. add writer:

```python
def _write_task_governance_overlay_run_next(root: Path, omo_dir: str | Path = ".omo", actor: str = "copilot-cli", now: str | None = None) -> int:
    result = run_governance_overlay_cycle(root, omo_dir=omo_dir, actor=actor, now=now or _utc_now())
    omo = _omo_path(root, omo_dir)
    run_path = omo / "workers" / "runs" / f"{result['run']['run_id']}.yaml"
    _write_yaml(run_path, result["run"])
    _write_yaml(omo / "_truth" / "governance-overlay" / "roadmap.yaml", result["roadmap"])
    refreshed = build_governance_overlay_status(root, omo_dir=omo_dir, now=now or _utc_now())
    output_dir = omo / "workers" / "governance-overlay"
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(output_dir / "current.yaml", refreshed["yaml"])
    write_text_atomic(output_dir / "current.md", refreshed["markdown"])
    print(f"summary={result['run']['summary']} roadmap_item_id={result['run']['roadmap_item_id']}")
    return 0
```

- [ ] **Step 4: Update docs**

Update `.omo/workers/README.md`:

```md
Autopilot governance execution loop:

1. `python3 scripts/omo_worker.py task governance-overlay-run-next --omo-dir .omo --actor <ACTOR> [--now <ISO8601>]`
2. this reads the governance overlay shell
3. advances the top eligible planned-task roadmap item
4. writes `.omo/workers/runs/governance-overlay-<STAMP>.yaml`
5. regenerates `.omo/workers/governance-overlay/current.yaml`
```

Update `.omo/AGENT.md`:

```md
> **Governance overlay autopilot**：如需让 OMO 自动推进 overlay 的下一个 planned-task roadmap item，运行 `python3 scripts/omo_worker.py task governance-overlay-run-next --omo-dir .omo --actor <ACTOR> [--now <ISO8601>]`。第一版只支持 `.omo/tasks/planned/*.yaml` target refs，debt bundle 仍保持 read-only。
```

- [ ] **Step 5: Run the CLI/docs regressions to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py -q -k 'governance_overlay_run_next'
```

Expected: `2 passed`.

- [ ] **Step 6: Rehearse one real governance overlay cycle**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 scripts/omo_worker.py task governance-overlay-run-next --omo-dir .omo --actor copilot-cli --now 2026-06-03T06:40:00Z
```

Expected:

1. a governance run artifact exists under `.omo/workers/runs/`
2. `roadmap.yaml` status moves forward for the top item
3. `.omo/workers/governance-overlay/current.yaml` refreshes after the run

---

### Task 3: Run focused verification and commit both repos

**Files:**
- Verify: `.omo/tests/test_omo_governance_overlay.py`
- Verify: `.omo/tests/test_omo_governance_overlay_loop.py`
- Verify: `.omo/tests/test_omo_automation.py`
- Verify: `.omo/tests/test_worker_mechanism_consistency.py`
- Commit: `scripts/`
- Commit: root repo

- [ ] **Step 1: Run the governance overlay loop subset**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest \
  .omo/tests/test_omo_governance_overlay.py \
  .omo/tests/test_omo_governance_overlay_loop.py \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  -q -k 'governance_overlay'
```

Expected: governance overlay shell + loop regressions pass together.

- [ ] **Step 2: Commit the nested `scripts` repo changes**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_governance_overlay_loop.py omo_worker.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add governance overlay autopilot loop" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

- [ ] **Step 3: Commit the root repo changes**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
git add \
  scripts \
  .omo/tests/test_omo_governance_overlay_loop.py \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  .omo/_truth/governance-overlay/roadmap.yaml \
  .omo/workers/README.md \
  .omo/AGENT.md \
  .omo/workers/governance-overlay/current.yaml \
  .omo/workers/governance-overlay/current.md \
  .omo/workers/runs/governance-overlay-*.yaml && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add governance overlay autopilot loop" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

- [ ] **Step 4: Record the milestone in the session plan**

Update the session plan with:

```md
## 2026-06-03 governance overlay autopilot loop landed

- spec committed: `docs/superpowers/specs/2026-06-03-omo-governance-overlay-autopilot-loop-design.md`
- plan committed: `docs/superpowers/plans/2026-06-03-omo-governance-overlay-autopilot-loop.md`
- new command: `task governance-overlay-run-next`
- loop now advances planned-task roadmap items automatically through the existing promotion/approval path
```

Do not commit the session plan file.

---

## Self-review checklist

1. first version only supports planned-task refs
2. debt bundles stay read-only
3. no approval gate is bypassed
4. roadmap status mutation is explicit
5. a run artifact is always written for non-idle cycles

## Execution note

Plan complete and saved to `docs/superpowers/plans/2026-06-03-omo-governance-overlay-autopilot-loop.md`. In the current autonomous session, proceed with **Inline Execution**.
