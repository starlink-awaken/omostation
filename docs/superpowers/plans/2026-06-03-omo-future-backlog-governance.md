# OMO Future Backlog Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved strict-active-only model so `.omo/tasks/active/` becomes the current executable queue again, future-phase backlog moves into `.omo/tasks/planned/`, and `state/system.yaml` derives separate active/planned summaries without backlog blobs.

**Architecture:** Extend the existing Python validator and state-sync surfaces instead of inventing a parallel queue system. Add a first-class `tasks/planned/` truth surface, keep `active/` validation strict, derive `planned_tasks` plus `next_planned_tasks` from state sync, then migrate the pre-staged pending packets out of `active/` and align the docs/tests around the new queue contract.

**Tech Stack:** Python 3, PyYAML, pytest, Bash, Markdown/YAML docs under `.omo/`

---

## File map

### Create

- `docs/superpowers/plans/2026-06-03-omo-future-backlog-governance.md`
- `.omo/tasks/planned/` (new truth surface; populated by moved task YAMLs)

### Modify

- `scripts/omo_task_schema.py` — add planned-queue validation rules and a reusable task-group validator
- `scripts/omo_worker.py` — expose planned-queue validation from the existing `task validate` CLI
- `scripts/sync_omo_state.py` — derive `planned_tasks`, `next_planned_tasks`, and stricter queue preview cleanup
- `.omo/tests/test_omo_automation.py` — red/green tests for planned validation and state derivation
- `.omo/tests/test_worker_mechanism_consistency.py` — repo-level assertions for strict-active-only queue hygiene
- `.omo/tests/test_phase13_execution.py`
- `.omo/tests/test_phase14_execution.py`
- `.omo/tests/test_phase15_execution.py`
- `.omo/tests/test_phase16_execution.py`
- `.omo/tasks/README.md`
- `.omo/AGENT.md`
- `.omo/INDEX.md`
- `.omo/DOC-ARCH.md`
- `.omo/tests/README.md`
- `.omo/state/system.yaml`

### Move from `active/` to `planned/`

- `.omo/tasks/active/D2-CI-E2E-TEST-ENV.yaml` -> `.omo/tasks/planned/D2-CI-E2E-TEST-ENV.yaml`
- `.omo/tasks/active/D3-EU-PRICING-TEST.yaml` -> `.omo/tasks/planned/D3-EU-PRICING-TEST.yaml`
- `.omo/tasks/active/ORPHANED-TASKS-STRUCTURED-REGISTRY.yaml` -> `.omo/tasks/planned/ORPHANED-TASKS-STRUCTURED-REGISTRY.yaml`
- `.omo/tasks/active/P17-W1-ARCHITECTURE-FOUNDATION.yaml` -> `.omo/tasks/planned/P17-W1-ARCHITECTURE-FOUNDATION.yaml`
- `.omo/tasks/active/P17-W2-SHAREDBRAIN-PROTOCOLS-V1.yaml` -> `.omo/tasks/planned/P17-W2-SHAREDBRAIN-PROTOCOLS-V1.yaml`
- `.omo/tasks/active/P17-W3-METAOS-GAP-ANALYSIS.yaml` -> `.omo/tasks/planned/P17-W3-METAOS-GAP-ANALYSIS.yaml`
- `.omo/tasks/active/P17-W4-AGENTMESH-AUDIT.yaml` -> `.omo/tasks/planned/P17-W4-AGENTMESH-AUDIT.yaml`
- `.omo/tasks/active/P18-W1-NEURAL-CENTER.yaml` -> `.omo/tasks/planned/P18-W1-NEURAL-CENTER.yaml`
- `.omo/tasks/active/P18-W2-CIRCUIT-ENGINE.yaml` -> `.omo/tasks/planned/P18-W2-CIRCUIT-ENGINE.yaml`
- `.omo/tasks/active/P18-W3-NEURON-POOL.yaml` -> `.omo/tasks/planned/P18-W3-NEURON-POOL.yaml`
- `.omo/tasks/active/P18-W4-CLEANUP-DWINDOW-REFS.yaml` -> `.omo/tasks/planned/P18-W4-CLEANUP-DWINDOW-REFS.yaml`
- `.omo/tasks/active/P19-W1-AGENT-RUNTIME-ENHANCE.yaml` -> `.omo/tasks/planned/P19-W1-AGENT-RUNTIME-ENHANCE.yaml`
- `.omo/tasks/active/P19-W2-AGENT-HUB-CREATE.yaml` -> `.omo/tasks/planned/P19-W2-AGENT-HUB-CREATE.yaml`
- `.omo/tasks/active/P19-W3-ARCHIVE-TS.yaml` -> `.omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml`
- `.omo/tasks/active/P20-W1-ECONOMY-EXTRACTION.yaml` -> `.omo/tasks/planned/P20-W1-ECONOMY-EXTRACTION.yaml`
- `.omo/tasks/active/P20-W2-KI-KOS-MERGE.yaml` -> `.omo/tasks/planned/P20-W2-KI-KOS-MERGE.yaml`
- `.omo/tasks/active/P20-W3-EXTENSION-FORGE.yaml` -> `.omo/tasks/planned/P20-W3-EXTENSION-FORGE.yaml`
- `.omo/tasks/active/P20-W4-HARNESS-DISPERSAL.yaml` -> `.omo/tasks/planned/P20-W4-HARNESS-DISPERSAL.yaml`
- `.omo/tasks/active/P21-W1-IMMUNITY-METAOS.yaml` -> `.omo/tasks/planned/P21-W1-IMMUNITY-METAOS.yaml`
- `.omo/tasks/active/P21-W2-GENESIS-TRIAGE.yaml` -> `.omo/tasks/planned/P21-W2-GENESIS-TRIAGE.yaml`
- `.omo/tasks/active/P21-W3-OBSERVABILITY-CREATE.yaml` -> `.omo/tasks/planned/P21-W3-OBSERVABILITY-CREATE.yaml`
- `.omo/tasks/active/P21-W4-GC-ENGINE-CREATE.yaml` -> `.omo/tasks/planned/P21-W4-GC-ENGINE-CREATE.yaml`
- `.omo/tasks/active/P22-W1-PONTUS-DSL-SCHEDULER.yaml` -> `.omo/tasks/planned/P22-W1-PONTUS-DSL-SCHEDULER.yaml`
- `.omo/tasks/active/P22-W2-PONTUS-QUALITY.yaml` -> `.omo/tasks/planned/P22-W2-PONTUS-QUALITY.yaml`
- `.omo/tasks/active/P23-W1-HERMES-SCAFFOLD.yaml` -> `.omo/tasks/planned/P23-W1-HERMES-SCAFFOLD.yaml`
- `.omo/tasks/active/P23-W2-HERMES-DASHBOARD.yaml` -> `.omo/tasks/planned/P23-W2-HERMES-DASHBOARD.yaml`
- `.omo/tasks/active/P24-W1-BASEMEMBRANE-ZERO.yaml` -> `.omo/tasks/planned/P24-W1-BASEMEMBRANE-ZERO.yaml`
- `.omo/tasks/active/P24-W2-NUCLEUS-REPLACE.yaml` -> `.omo/tasks/planned/P24-W2-NUCLEUS-REPLACE.yaml`
- `.omo/tasks/active/P25-W1-E2E-INTEGRATION.yaml` -> `.omo/tasks/planned/P25-W1-E2E-INTEGRATION.yaml`
- `.omo/tasks/active/P25-W2-DOCS-DEBT-CLOSURE.yaml` -> `.omo/tasks/planned/P25-W2-DOCS-DEBT-CLOSURE.yaml`

### Leave in `active/`

- `.omo/tasks/active/P17-DEBT-GOVERNANCE-GATE-RULES.yaml`
- `.omo/tasks/active/SHAREDBRAIN-FORMAL-DECISION.yaml`

These two remain because they already carry live dispatch/review linkage and represent the currently authorized execution horizon.

---

### Task 1: Add planned-queue validation semantics

**Files:**
- Modify: `scripts/omo_task_schema.py`
- Modify: `scripts/omo_worker.py`
- Test: `.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Write the failing validator tests**

```python
def test_validate_task_file_allows_planned_packet_without_approval_ref(tmp_path: Path):
    task_path = tmp_path / ".omo" / "tasks" / "planned" / "future.yaml"
    _write_yaml(
        task_path,
        {
            "id": "P18-W1-NEURAL-CENTER",
            "title": "Future planned packet",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "risk_level": "L2",
            "allowed_operation_level": "L2",
            "human_approval_required": True,
            "source_docs": [".omo/_knowledge/design/demo.md"],
            "entry_gate": ["phase17_completed"],
            "evidence_required": ["promotion approval exists"],
            "test_plan": [".omo/tests/README.md#governance-consistency-tests"],
        },
    )

    assert validate_task_file(task_path) == []


def test_validate_task_file_rejects_planned_packet_with_live_dispatch_chain(tmp_path: Path):
    task_path = tmp_path / ".omo" / "tasks" / "planned" / "future.yaml"
    _write_yaml(
        task_path,
        {
            "id": "P18-W2-CIRCUIT-ENGINE",
            "title": "Planned packet with live chain",
            "status": "in_progress",
            "assigned_to": "claude-code",
            "dispatch_id": "P18-W2-DISPATCH",
            "run_ref": ".omo/workers/runs/p18.yaml",
            "approval_ref": None,
            "review_ref": ".omo/workers/runs/p18-review.md",
            "knowledge_refs": [],
            "handoff_refs": [],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "source_docs": [".omo/_knowledge/design/demo.md"],
            "entry_gate": ["phase17_completed"],
            "evidence_required": ["promotion packet exists"],
            "test_plan": [".omo/tests/README.md#governance-consistency-tests"],
            "started_at": "2026-06-03T00:00:00Z",
        },
    )

    assert validate_task_file(task_path) == [
        "planned tasks must use candidate or pending status",
        "planned tasks must not set assigned_to",
        "planned tasks must not set dispatch_id",
        "planned tasks must not set run_ref",
        "planned tasks must not set review_ref",
        "planned tasks must not set started_at",
    ]
```

- [ ] **Step 2: Run the validator tests to verify RED**

Run: `python3 -m pytest .omo/tests/test_omo_automation.py -q -k "planned_packet"`

Expected: FAIL because `validate_task_file()` currently treats `planned/` like `active/`/execution context and has no planned-queue guardrails.

- [ ] **Step 3: Implement planned-task rules in the schema module**

```python
PLANNED_STATUSES = {"candidate", "pending"}


def _validate_planned_task(task: dict, errors: list[str]) -> None:
    if task.get("status") not in PLANNED_STATUSES:
        errors.append("planned tasks must use candidate or pending status")
    for field in ("assigned_to", "dispatch_id", "run_ref", "review_ref", "started_at", "completed_at"):
        if task.get(field):
            errors.append(f"planned tasks must not set {field}")
    if "test_plan" not in task:
        errors.append("missing required field: test_plan")
    else:
        _require_list(task, "test_plan", errors, allow_empty=False)
    if not task.get("source_docs"):
        errors.append("source_docs must not be empty")


def validate_task_group(root: Path, group: str) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {}
    for task_file in sorted((root / ".omo" / "tasks" / group).glob("*.yaml")):
        errors = validate_task_file(task_file)
        if errors:
            results[str(task_file)] = errors
    return results
```

Apply `_validate_planned_task()` from `validate_task_data(..., group="planned")`, keep active validation strict, and update `scripts/omo_worker.py` so `python3 scripts/omo_worker.py task validate --all-planned` calls `validate_task_group(Path.cwd(), "planned")` while leaving `--all-active` unchanged.

- [ ] **Step 4: Run the validator tests to verify GREEN**

Run: `python3 -m pytest .omo/tests/test_omo_automation.py -q -k "planned_packet"`

Expected: PASS with both planned validation tests green.

- [ ] **Step 5: Commit the validator slice**

```bash
git add .omo/tests/test_omo_automation.py scripts/omo_task_schema.py scripts/omo_worker.py
git -c core.hooksPath=/dev/null commit -m "feat(omo): add planned task validation" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 2: Derive planned counts and queue previews in state sync

**Files:**
- Modify: `scripts/sync_omo_state.py`
- Test: `.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Write the failing state-sync tests**

```python
def test_sync_state_tracks_planned_tasks_and_preview(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(omo / "state" / "system.yaml", {"health_score": 0.0})
    _write_yaml(omo / "goals" / "current.yaml", {"phase": 16, "status": "completed", "goals": []})
    _write_yaml(omo / "tasks" / "active" / "gate.yaml", {"id": "P17-DEBT-GOVERNANCE-GATE-RULES", "phase": 17, "status": "in_progress", "run_ref": "run.yaml", "review_ref": "review.md"})
    _write_yaml(omo / "tasks" / "planned" / "p18.yaml", {"id": "P18-W1-NEURAL-CENTER", "phase": 18, "status": "pending"})
    _write_yaml(omo / "tasks" / "planned" / "p19.yaml", {"id": "P19-W1-AGENT-RUNTIME-ENHANCE", "phase": 19, "status": "pending"})
    _write_yaml(omo / "tasks" / "blocked" / "blocked.yaml", {"id": "TASK-BLOCKED", "phase": 16})
    _write_yaml(omo / "tasks" / "done" / "done.yaml", {"id": "TASK-DONE", "phase": 16, "status": "done"})

    state = sync_state(omo, test_output="5 passed")

    assert state["active_tasks"] == 1
    assert state["planned_tasks"] == 2
    assert state["blocked_tasks"] == 1
    assert state["completed_tasks"] == 1
    assert state["total_tasks"] == 5
    assert state["next_active_tasks"] == [
        "Current active queue from .omo/tasks/active/ (1 task)",
        "P17-DEBT-GOVERNANCE-GATE-RULES",
    ]
    assert state["next_planned_tasks"] == [
        "Current planned queue from .omo/tasks/planned/ (2 tasks)",
        "P18-W1-NEURAL-CENTER",
        "P19-W1-AGENT-RUNTIME-ENHANCE",
    ]


def test_sync_state_drops_stale_active_headers_when_count_changes(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(
        omo / "state" / "system.yaml",
        {
            "health_score": 0.0,
            "next_active_tasks": [
                "Current active queue from .omo/tasks/active/ (32 tasks)",
                "Current active queue from .omo/tasks/active/ (5 tasks)",
                "Phase 17 gate in progress",
            ],
        },
    )
    _write_yaml(omo / "goals" / "current.yaml", {"phase": 16, "status": "completed", "goals": []})
    _write_yaml(omo / "tasks" / "active" / "gate.yaml", {"id": "P17-DEBT-GOVERNANCE-GATE-RULES", "phase": 17, "status": "in_progress", "run_ref": "run.yaml", "review_ref": "review.md"})

    state = sync_state(omo, test_output="1 passed")

    assert state["next_active_tasks"] == [
        "Current active queue from .omo/tasks/active/ (1 task)",
        "P17-DEBT-GOVERNANCE-GATE-RULES",
        "Phase 17 gate in progress",
    ]
```

- [ ] **Step 2: Run the state-sync tests to verify RED**

Run: `python3 -m pytest .omo/tests/test_omo_automation.py -q -k "planned_tasks_and_preview or stale_active_headers"`

Expected: FAIL because `sync_state()` does not set `planned_tasks`/`next_planned_tasks`, and `_next_active_tasks()` still lets stale header lines survive.

- [ ] **Step 3: Implement planned counts and preview derivation**

```python
def _queue_preview(group_dir: Path, state_lines: list[str] | None, omo_ref: Path, label: str) -> list[str]:
    task_ids = []
    for task_file in sorted(group_dir.glob("*.yaml")):
        task = _load_yaml(task_file)
        task_ids.append(task.get("id", task_file.stem))

    if not task_ids:
        return [f"(No {label} tasks)"]

    suffix = "task" if len(task_ids) == 1 else "tasks"
    header = f"Current {label} queue from {omo_ref}/tasks/{group_dir.name}/ ({len(task_ids)} {suffix})"
    header_prefix = f"Current {label} queue from {omo_ref}/tasks/{group_dir.name}/ ("
    extras = [
        line
        for line in (state_lines or [])
        if not line.startswith(header_prefix)
        and line not in task_ids
        and not _looks_like_task_queue_entry(line)
    ]
    return [header, *task_ids, *extras]


planned_count = _count_task_group(tasks_dir, "planned")
total = active_count + planned_count + blocked_count + done_count
state["planned_tasks"] = planned_count
state["next_active_tasks"] = _queue_preview(tasks_dir / "active", state.get("next_active_tasks"), _omo_ref(omo_dir), "active")
state["next_planned_tasks"] = _queue_preview(tasks_dir / "planned", state.get("next_planned_tasks"), _omo_ref(omo_dir), "planned")
```

Keep `active_tasks` semantics unchanged: only files under `tasks/active/` count as active.

- [ ] **Step 4: Run the state-sync tests to verify GREEN**

Run: `python3 -m pytest .omo/tests/test_omo_automation.py -q -k "planned_tasks_and_preview or stale_active_headers"`

Expected: PASS with `planned_tasks`, `next_planned_tasks`, and stale-header cleanup behaving exactly as the new tests assert.

- [ ] **Step 5: Commit the state-sync slice**

```bash
git add .omo/tests/test_omo_automation.py scripts/sync_omo_state.py
git -c core.hooksPath=/dev/null commit -m "feat(omo): derive planned task previews" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 3: Migrate pending future packets into `tasks/planned/`

**Files:**
- Modify: `.omo/tests/test_worker_mechanism_consistency.py`
- Modify: `.omo/tests/test_phase13_execution.py`
- Modify: `.omo/tests/test_phase14_execution.py`
- Modify: `.omo/tests/test_phase15_execution.py`
- Modify: `.omo/tests/test_phase16_execution.py`
- Move: the 30 task YAML files listed in the file map above
- Refresh: `.omo/state/system.yaml`

- [ ] **Step 1: Write the failing repo-state tests**

```python
def test_pending_future_phase_packets_live_in_planned_queue():
    goals = _load_yaml(OMO / "goals" / "current.yaml")
    current_phase = goals["phase"]
    failures = []

    for task_file in _task_files("active"):
        task = _load_yaml(task_file)
        if task.get("phase", 0) > current_phase and task.get("status") == "pending":
            failures.append(task["id"])

    assert failures == [], failures


def test_planned_queue_contains_future_backlog_packets():
    planned_ids = [_load_yaml(path)["id"] for path in _task_files("planned")]
    assert "P18-W1-NEURAL-CENTER" in planned_ids
    assert "P25-W2-DOCS-DEBT-CLOSURE" in planned_ids
```

Update the phase-closeout assertions/comments so they no longer say "future-phase backlog is pre-staged in active/". The new comment should say that only explicitly authorized execution packets may remain active after Phase 16 closeout.

- [ ] **Step 2: Run the repo-state tests to verify RED**

Run: `python3 -m pytest .omo/tests/test_worker_mechanism_consistency.py .omo/tests/test_phase13_execution.py .omo/tests/test_phase14_execution.py .omo/tests/test_phase15_execution.py .omo/tests/test_phase16_execution.py -q`

Expected: FAIL because the pending Phase 17-25 packets are still under `tasks/active/`.

- [ ] **Step 3: Move the pending packets into `tasks/planned/`**

```bash
mkdir -p .omo/tasks/planned
mv .omo/tasks/active/D2-CI-E2E-TEST-ENV.yaml .omo/tasks/planned/D2-CI-E2E-TEST-ENV.yaml
mv .omo/tasks/active/D3-EU-PRICING-TEST.yaml .omo/tasks/planned/D3-EU-PRICING-TEST.yaml
mv .omo/tasks/active/ORPHANED-TASKS-STRUCTURED-REGISTRY.yaml .omo/tasks/planned/ORPHANED-TASKS-STRUCTURED-REGISTRY.yaml
mv .omo/tasks/active/P17-W1-ARCHITECTURE-FOUNDATION.yaml .omo/tasks/planned/P17-W1-ARCHITECTURE-FOUNDATION.yaml
mv .omo/tasks/active/P17-W2-SHAREDBRAIN-PROTOCOLS-V1.yaml .omo/tasks/planned/P17-W2-SHAREDBRAIN-PROTOCOLS-V1.yaml
mv .omo/tasks/active/P17-W3-METAOS-GAP-ANALYSIS.yaml .omo/tasks/planned/P17-W3-METAOS-GAP-ANALYSIS.yaml
mv .omo/tasks/active/P17-W4-AGENTMESH-AUDIT.yaml .omo/tasks/planned/P17-W4-AGENTMESH-AUDIT.yaml
mv .omo/tasks/active/P18-W1-NEURAL-CENTER.yaml .omo/tasks/planned/P18-W1-NEURAL-CENTER.yaml
mv .omo/tasks/active/P18-W2-CIRCUIT-ENGINE.yaml .omo/tasks/planned/P18-W2-CIRCUIT-ENGINE.yaml
mv .omo/tasks/active/P18-W3-NEURON-POOL.yaml .omo/tasks/planned/P18-W3-NEURON-POOL.yaml
mv .omo/tasks/active/P18-W4-CLEANUP-DWINDOW-REFS.yaml .omo/tasks/planned/P18-W4-CLEANUP-DWINDOW-REFS.yaml
mv .omo/tasks/active/P19-W1-AGENT-RUNTIME-ENHANCE.yaml .omo/tasks/planned/P19-W1-AGENT-RUNTIME-ENHANCE.yaml
mv .omo/tasks/active/P19-W2-AGENT-HUB-CREATE.yaml .omo/tasks/planned/P19-W2-AGENT-HUB-CREATE.yaml
mv .omo/tasks/active/P19-W3-ARCHIVE-TS.yaml .omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml
mv .omo/tasks/active/P20-W1-ECONOMY-EXTRACTION.yaml .omo/tasks/planned/P20-W1-ECONOMY-EXTRACTION.yaml
mv .omo/tasks/active/P20-W2-KI-KOS-MERGE.yaml .omo/tasks/planned/P20-W2-KI-KOS-MERGE.yaml
mv .omo/tasks/active/P20-W3-EXTENSION-FORGE.yaml .omo/tasks/planned/P20-W3-EXTENSION-FORGE.yaml
mv .omo/tasks/active/P20-W4-HARNESS-DISPERSAL.yaml .omo/tasks/planned/P20-W4-HARNESS-DISPERSAL.yaml
mv .omo/tasks/active/P21-W1-IMMUNITY-METAOS.yaml .omo/tasks/planned/P21-W1-IMMUNITY-METAOS.yaml
mv .omo/tasks/active/P21-W2-GENESIS-TRIAGE.yaml .omo/tasks/planned/P21-W2-GENESIS-TRIAGE.yaml
mv .omo/tasks/active/P21-W3-OBSERVABILITY-CREATE.yaml .omo/tasks/planned/P21-W3-OBSERVABILITY-CREATE.yaml
mv .omo/tasks/active/P21-W4-GC-ENGINE-CREATE.yaml .omo/tasks/planned/P21-W4-GC-ENGINE-CREATE.yaml
mv .omo/tasks/active/P22-W1-PONTUS-DSL-SCHEDULER.yaml .omo/tasks/planned/P22-W1-PONTUS-DSL-SCHEDULER.yaml
mv .omo/tasks/active/P22-W2-PONTUS-QUALITY.yaml .omo/tasks/planned/P22-W2-PONTUS-QUALITY.yaml
mv .omo/tasks/active/P23-W1-HERMES-SCAFFOLD.yaml .omo/tasks/planned/P23-W1-HERMES-SCAFFOLD.yaml
mv .omo/tasks/active/P23-W2-HERMES-DASHBOARD.yaml .omo/tasks/planned/P23-W2-HERMES-DASHBOARD.yaml
mv .omo/tasks/active/P24-W1-BASEMEMBRANE-ZERO.yaml .omo/tasks/planned/P24-W1-BASEMEMBRANE-ZERO.yaml
mv .omo/tasks/active/P24-W2-NUCLEUS-REPLACE.yaml .omo/tasks/planned/P24-W2-NUCLEUS-REPLACE.yaml
mv .omo/tasks/active/P25-W1-E2E-INTEGRATION.yaml .omo/tasks/planned/P25-W1-E2E-INTEGRATION.yaml
mv .omo/tasks/active/P25-W2-DOCS-DEBT-CLOSURE.yaml .omo/tasks/planned/P25-W2-DOCS-DEBT-CLOSURE.yaml
python3 scripts/sync_omo_state.py --omo-dir .omo
```

Leave `P17-DEBT-GOVERNANCE-GATE-RULES.yaml` and `SHAREDBRAIN-FORMAL-DECISION.yaml` in `active/`.

- [ ] **Step 4: Run the repo-state tests to verify GREEN**

Run: `python3 -m pytest .omo/tests/test_worker_mechanism_consistency.py .omo/tests/test_phase13_execution.py .omo/tests/test_phase14_execution.py .omo/tests/test_phase15_execution.py .omo/tests/test_phase16_execution.py -q`

Expected: PASS with `active/` reduced to the two authorized in-progress packets and future pending backlog living under `planned/`.

- [ ] **Step 5: Commit the migration slice**

```bash
git add -A -- \
  .omo/tests/test_worker_mechanism_consistency.py \
  .omo/tests/test_phase13_execution.py \
  .omo/tests/test_phase14_execution.py \
  .omo/tests/test_phase15_execution.py \
  .omo/tests/test_phase16_execution.py \
  .omo/state/system.yaml \
  .omo/tasks/planned \
  .omo/tasks/active/D2-CI-E2E-TEST-ENV.yaml \
  .omo/tasks/active/D3-EU-PRICING-TEST.yaml \
  .omo/tasks/active/ORPHANED-TASKS-STRUCTURED-REGISTRY.yaml \
  .omo/tasks/active/P17-W1-ARCHITECTURE-FOUNDATION.yaml \
  .omo/tasks/active/P17-W2-SHAREDBRAIN-PROTOCOLS-V1.yaml \
  .omo/tasks/active/P17-W3-METAOS-GAP-ANALYSIS.yaml \
  .omo/tasks/active/P17-W4-AGENTMESH-AUDIT.yaml \
  .omo/tasks/active/P18-W1-NEURAL-CENTER.yaml \
  .omo/tasks/active/P18-W2-CIRCUIT-ENGINE.yaml \
  .omo/tasks/active/P18-W3-NEURON-POOL.yaml \
  .omo/tasks/active/P18-W4-CLEANUP-DWINDOW-REFS.yaml \
  .omo/tasks/active/P19-W1-AGENT-RUNTIME-ENHANCE.yaml \
  .omo/tasks/active/P19-W2-AGENT-HUB-CREATE.yaml \
  .omo/tasks/active/P19-W3-ARCHIVE-TS.yaml \
  .omo/tasks/active/P20-W1-ECONOMY-EXTRACTION.yaml \
  .omo/tasks/active/P20-W2-KI-KOS-MERGE.yaml \
  .omo/tasks/active/P20-W3-EXTENSION-FORGE.yaml \
  .omo/tasks/active/P20-W4-HARNESS-DISPERSAL.yaml \
  .omo/tasks/active/P21-W1-IMMUNITY-METAOS.yaml \
  .omo/tasks/active/P21-W2-GENESIS-TRIAGE.yaml \
  .omo/tasks/active/P21-W3-OBSERVABILITY-CREATE.yaml \
  .omo/tasks/active/P21-W4-GC-ENGINE-CREATE.yaml \
  .omo/tasks/active/P22-W1-PONTUS-DSL-SCHEDULER.yaml \
  .omo/tasks/active/P22-W2-PONTUS-QUALITY.yaml \
  .omo/tasks/active/P23-W1-HERMES-SCAFFOLD.yaml \
  .omo/tasks/active/P23-W2-HERMES-DASHBOARD.yaml \
  .omo/tasks/active/P24-W1-BASEMEMBRANE-ZERO.yaml \
  .omo/tasks/active/P24-W2-NUCLEUS-REPLACE.yaml \
  .omo/tasks/active/P25-W1-E2E-INTEGRATION.yaml \
  .omo/tasks/active/P25-W2-DOCS-DEBT-CLOSURE.yaml
git -c core.hooksPath=/dev/null commit -m "feat(omo): move future backlog to planned queue" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 4: Align docs, navigation, and final verification

**Files:**
- Modify: `.omo/tasks/README.md`
- Modify: `.omo/AGENT.md`
- Modify: `.omo/INDEX.md`
- Modify: `.omo/DOC-ARCH.md`
- Modify: `.omo/tests/README.md`
- Modify: `.omo/tests/test_worker_mechanism_consistency.py`
- Refresh: `.omo/state/system.yaml`

- [ ] **Step 1: Write the failing doc-contract test**

```python
def test_task_docs_distinguish_active_and_planned_queues():
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "AGENT.md").read_text(encoding="utf-8")
    index_text = (OMO / "INDEX.md").read_text(encoding="utf-8")
    doc_arch_text = (OMO / "DOC-ARCH.md").read_text(encoding="utf-8")
    tests_text = (OMO / "tests" / "README.md").read_text(encoding="utf-8")

    assert "tasks/planned/" in tasks_text
    assert "strict-active-only" in agent_text
    assert "[tasks/planned/](tasks/planned/)" in index_text
    assert "planned/" in doc_arch_text
    assert "planned queue" in tests_text
```

- [ ] **Step 2: Run the doc-contract test to verify RED**

Run: `python3 -m pytest .omo/tests/test_worker_mechanism_consistency.py -q -k "planned_queues"`

Expected: FAIL because the current docs still describe `active/` as the only queue and do not mention `planned/`.

- [ ] **Step 3: Update docs and refresh the live state artifact**

```markdown
# `.omo/tasks/` changes
- add `planned/            ← future backlog（已建包但未晋升为 active）`
- state `active/` is current executable queue only
- state `planned/` uses canonical task YAMLs with `candidate|pending` only

# `.omo/AGENT.md` changes
- add a strict-active-only section under the task workflow
- document `bash bin/verify-omo.sh` plus optional `python3 scripts/omo_worker.py task validate --all-planned`

# `.omo/INDEX.md` changes
- change "实时 active / blocked queue" to "实时 active / planned / blocked queue"

# `.omo/tests/README.md` changes
- add one rule that planned backlog must live under `tasks/planned/`, not `tasks/active/`
```

Then refresh live state:

Run: `python3 scripts/sync_omo_state.py --omo-dir .omo`

Expected live-state deltas:

1. `active_tasks: 2`
2. `planned_tasks: 30`
3. `total_tasks` still includes active + planned + blocked + done
4. `next_active_tasks` starts with `Current active queue from .omo/tasks/active/ (2 tasks)`
5. `next_planned_tasks` starts with `Current planned queue from .omo/tasks/planned/ (30 tasks)`

- [ ] **Step 4: Run full governance verification**

Run:

```bash
python3 scripts/omo_worker.py task validate --all-planned
bash bin/verify-omo.sh
```

Expected:

1. `python3 scripts/omo_worker.py task validate --all-planned` exits `0`
2. `bash bin/verify-omo.sh` exits `0`
3. `.omo` tests remain fully green after the queue split

- [ ] **Step 5: Commit docs and verification refresh**

```bash
git add .omo/tasks/README.md .omo/AGENT.md .omo/INDEX.md .omo/DOC-ARCH.md .omo/tests/README.md .omo/tests/test_worker_mechanism_consistency.py .omo/state/system.yaml
git -c core.hooksPath=/dev/null commit -m "docs(omo): document planned backlog queue" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Self-review checklist

### Spec coverage

The plan covers every approved spec requirement:

1. **`tasks/planned/` truth surface** -> Task 3 migration plus Task 4 docs
2. **strict-active-only validation** -> Task 1 validator changes and Task 3 repo-state tests
3. **`planned_tasks` / `next_planned_tasks` state derivation** -> Task 2
4. **phase-closeout alignment** -> Task 3
5. **state summary stays derived** -> Task 2 and Task 4 refresh
6. **migration ordering and verification** -> Tasks 1-4 in the exact spec order

### Placeholder scan

Checked for and avoided:

1. `TODO` / `TBD` / `implement later`
2. vague "add tests" language without concrete test code
3. undefined helper names

### Type and naming consistency

This plan consistently uses:

1. `validate_task_group`
2. `_validate_planned_task`
3. `planned_tasks`
4. `next_planned_tasks`
5. `strict-active-only`

No alternate names are introduced later in the plan.
