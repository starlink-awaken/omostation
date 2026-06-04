# Governance Overlay Launch Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the governance overlay treat task-declared write scope as a first-class launch gate so autonomous execution only launches when the task packet declares safe deliverables, and otherwise fails closed with a canonical contract-gap outcome.

**Architecture:** Reuse the existing task `deliverables` field as the only source of write authority, then thread that contract through three layers: read-side active target synthesis, `governance-overlay-run-next` control actions, and worker dispatch/launch execution. The key change is to distinguish `dispatched`, `running`, and `contract-gap` states instead of collapsing all active work into `active_in_progress`.

**Tech Stack:** Python 3, YAML task packets, pytest, existing OMO worker/governance overlay scripts

---

## File structure / decomposition

- Modify: `scripts/omo_governance_overlay.py`
  - Responsibility: canonical read-side overlay status synthesis
  - Add launch-contract helpers, dispatch artifact inspection, richer active target states, and `contract:` / `launch:` next actions.

- Modify: `scripts/omo_governance_overlay_loop.py`
  - Responsibility: run planning for `governance-overlay-run-next`
  - Keep `continue_active` authoritative, but preserve richer next-action semantics and summaries for contract-gap / launch branches.

- Modify: `scripts/omo_worker.py`
  - Responsibility: write-side coordinator behavior
  - Add reusable launch-contract helper(s), make `dispatch_task(..., launch=True)` transition to a running dispatch state, and add `contract:` / `launch:` execution branches to `_write_task_governance_overlay_run_next(...)`.

- Modify: `.omo/tests/test_omo_governance_overlay.py`
  - Responsibility: read-side regression coverage for new target states and next-action precedence.

- Modify: `.omo/tests/test_omo_governance_overlay_loop.py`
  - Responsibility: planner regression coverage for `continue_active` next-action interpretation.

- Modify: `.omo/tests/test_omo_automation.py`
  - Responsibility: write-side regression coverage for `governance-overlay-run-next`, `dispatch_task`, and launch transitions.

- Modify: `.omo/tests/test_worker_mechanism_consistency.py`
  - Responsibility: docs/operator contract regression coverage.

- Modify: `.omo/AGENT.md`
- Modify: `.omo/tasks/README.md`
- Modify: `.omo/workers/README.md`
  - Responsibility: operator contract updates for `contract:<TASK_ID>` / `launch:<TASK_ID>` and the rule that autonomous launch requires explicit task `deliverables`.

---

### Task 1: Add read-side launch-contract synthesis

**Files:**
- Modify: `scripts/omo_governance_overlay.py`
- Test: `.omo/tests/test_omo_governance_overlay.py`

- [ ] **Step 1: Write the failing contract-gap test**

Add this test to `.omo/tests/test_omo_governance_overlay.py`:

```python
def test_build_governance_overlay_status_surfaces_contract_gap_for_dispatched_empty_scope(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M1-EXECUTION-HARDENING",
            "next_milestone": "GOV-M2-SHAREDBRAIN-DEBT",
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T07:10:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {"autopilot_mode": "full_omo_autopilot", "auto_select": True},
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M1-EXECUTION-HARDENING",
                    "type": "task-bundle",
                    "title": "Execution hardening",
                    "priority": "P0",
                    "status": "in_progress",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/TASK-A.yaml"],
                    "success_criteria": ["execution hardening closed"],
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "active" / "TASK-A.yaml",
        {
            "id": "TASK-A",
            "status": "in_progress",
            "deliverables": [],
            "run_ref": ".omo/workers/runs/task-a-dispatch.yaml",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "task-a-dispatch.yaml",
        {"dispatch_state": "dispatched"},
    )

    result = build_governance_overlay_status(tmp_path, omo_dir=".omo", now="2026-06-03T07:12:00Z")

    assert result["yaml"]["active_target_states"][0]["state"] == "active_dispatch_blocked"
    assert result["yaml"]["active_target_states"][0]["detail"] == "dispatch exists but task has no launch-ready write scope"
    assert result["yaml"]["next_action"] == "contract:TASK-A"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_governance_overlay.py -q -k 'contract_gap_for_dispatched_empty_scope'
```

Expected: `FAIL` because `build_governance_overlay_status(...)` still returns `active_in_progress` / `monitor:GOV-M1-EXECUTION-HARDENING`.

- [ ] **Step 3: Write the failing launch-ready test**

Add this second test in the same file:

```python
def test_build_governance_overlay_status_surfaces_launch_for_dispatched_ready_scope(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M1-EXECUTION-HARDENING",
            "next_milestone": "GOV-M2-SHAREDBRAIN-DEBT",
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T07:10:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {"autopilot_mode": "full_omo_autopilot", "auto_select": True},
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M1-EXECUTION-HARDENING",
                    "type": "task-bundle",
                    "title": "Execution hardening",
                    "priority": "P0",
                    "status": "in_progress",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/TASK-A.yaml"],
                    "success_criteria": ["execution hardening closed"],
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "active" / "TASK-A.yaml",
        {
            "id": "TASK-A",
            "status": "in_progress",
            "deliverables": ["src/app.py"],
            "run_ref": ".omo/workers/runs/task-a-dispatch.yaml",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "task-a-dispatch.yaml",
        {"dispatch_state": "dispatched"},
    )

    result = build_governance_overlay_status(tmp_path, omo_dir=".omo", now="2026-06-03T07:13:00Z")

    assert result["yaml"]["active_target_states"][0]["state"] == "active_dispatched"
    assert result["yaml"]["next_action"] == "launch:TASK-A"
```

- [ ] **Step 4: Run the test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_governance_overlay.py -q -k 'surfaces_launch_for_dispatched_ready_scope'
```

Expected: `FAIL` because the read-side code has no `active_dispatched` / `launch:` branch yet.

- [ ] **Step 5: Implement the minimal read-side helpers**

Update `scripts/omo_governance_overlay.py` with small focused helpers and the new state logic:

```python
def _dispatch_payload(root: Path, run_ref: str | None) -> dict[str, object] | None:
    if not run_ref:
        return None
    path = root / run_ref
    if not path.exists():
        return None
    return _load_yaml_required(path)


def _derived_allowed_write_paths(task: dict[str, object]) -> list[str]:
    paths: list[str] = []
    for deliverable in task.get("deliverables", []):
        path = str(deliverable)
        if path.endswith("/"):
            candidate = path
        else:
            candidate = str(Path(path).parent)
            if candidate == ".":
                candidate = path
            elif not candidate.endswith("/"):
                candidate = f"{candidate}/"
        if candidate not in paths:
            paths.append(candidate)
    return paths


def _launch_contract_state(task: dict[str, object], dispatch: dict[str, object] | None) -> tuple[str, str]:
    deliverables = list(task.get("deliverables", []))
    allowed_paths = _derived_allowed_write_paths(task)
    if not deliverables or not allowed_paths:
        return ("contract_gap", "dispatch exists but task has no launch-ready write scope")
    if dispatch and dispatch.get("dispatch_state") == "dispatched":
        return ("dispatch_only", "dispatch exists and task is ready for launch")
    return ("launch_ready", "task has explicit launch-ready write scope")
```

Then update `_target_state(...)` so `tasks/active/*.yaml` synthesize:

```python
dispatch = _dispatch_payload(root, str(task.get("run_ref")) if task.get("run_ref") else None)
status = str(task.get("status", "pending"))
if status == "review":
    return {"target_ref": target_ref, "task_id": task_id, "state": "active_review", "detail": "task currently exists in tasks/active/ with status review"}
if status == "pending":
    return {"target_ref": target_ref, "task_id": task_id, "state": "active_pending", "detail": "task currently exists in tasks/active/ with status pending"}
if status == "in_progress" and dispatch:
    contract_state, detail = _launch_contract_state(task, dispatch)
    dispatch_state = str(dispatch.get("dispatch_state"))
    if dispatch_state == "dispatched" and contract_state == "contract_gap":
        return {"target_ref": target_ref, "task_id": task_id, "state": "active_dispatch_blocked", "detail": detail}
    if dispatch_state == "dispatched":
        return {"target_ref": target_ref, "task_id": task_id, "state": "active_dispatched", "detail": detail}
    if dispatch_state in {"active", "checkpointed"}:
        return {"target_ref": target_ref, "task_id": task_id, "state": "active_running", "detail": f"dispatch currently {dispatch_state}"}
```

And update `next_action` priority:

```python
if any(target["state"] == "active_pending" for target in active_target_states):
    pending = next(target for target in active_target_states if target["state"] == "active_pending")
    next_action = f"dispatch:{pending['task_id']}"
elif any(target["state"] == "active_dispatch_blocked" for target in active_target_states):
    blocked = next(target for target in active_target_states if target["state"] == "active_dispatch_blocked")
    next_action = f"contract:{blocked['task_id']}"
elif any(target["state"] == "active_dispatched" for target in active_target_states):
    dispatched = next(target for target in active_target_states if target["state"] == "active_dispatched")
    next_action = f"launch:{dispatched['task_id']}"
elif any(target["state"] in {"active_running", "active_review"} for target in active_target_states):
    next_action = f"monitor:{active_item['id']}"
```

- [ ] **Step 6: Run the focused read-side tests**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_governance_overlay.py -q -k 'contract_gap_for_dispatched_empty_scope or surfaces_launch_for_dispatched_ready_scope'
```

Expected: `2 passed`.

- [ ] **Step 7: Commit the read-side change**

```bash
cd /Users/xiamingxing/Workspace && git add scripts/omo_governance_overlay.py .omo/tests/test_omo_governance_overlay.py && git -c core.hooksPath=/dev/null commit -m "feat(omo): add overlay launch contract states" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Add run-next contract-gap and launch execution

**Files:**
- Modify: `scripts/omo_worker.py`
- Modify: `scripts/omo_governance_overlay_loop.py`
- Test: `.omo/tests/test_omo_governance_overlay_loop.py`
- Test: `.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Write the failing contract-gap automation test**

Add this test to `.omo/tests/test_omo_automation.py` near the governance overlay run-next coverage:

```python
def test_task_governance_overlay_run_next_records_contract_gap_for_dispatched_task_without_deliverables(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"
    _write_yaml(
        omo / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M1-EXECUTION-HARDENING",
            "next_milestone": "GOV-M2-SHAREDBRAIN-DEBT",
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T07:15:00Z",
        },
    )
    _write_yaml(omo / "_truth" / "governance-overlay" / "autopilot-policy.yaml", {"autopilot_mode": "full_omo_autopilot"})
    _write_yaml(
        omo / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M1-EXECUTION-HARDENING",
                    "type": "task-bundle",
                    "title": "Execution hardening",
                    "priority": "P0",
                    "status": "in_progress",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/TASK-A.yaml"],
                    "success_criteria": ["execution hardening closed"],
                }
            ]
        },
    )
    _write_yaml(
        omo / "tasks" / "active" / "TASK-A.yaml",
        {
            "id": "TASK-A",
            "title": "Task A",
            "status": "in_progress",
            "assigned_to": "codebuddy",
            "dispatch_id": "task-a-codebuddy-20260603-071500",
            "run_ref": ".omo/workers/runs/task-a-codebuddy-20260603-071500-dispatch.yaml",
            "review_ref": ".omo/workers/runs/task-a-codebuddy-20260603-071500-review.md",
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/MASTER-BLUEPRINT.md"],
            "deliverables": [],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "entry_gate": ["phase16_completed"],
            "evidence_required": ["review note written"],
            "test_plan": ["python3 -m pytest .omo/tests/test_omo_automation.py -q"],
            "started_at": "2026-06-03T07:15:00Z",
        },
    )
    _write_yaml(
        omo / "workers" / "runs" / "task-a-codebuddy-20260603-071500-dispatch.yaml",
        {
            "dispatch_id": "task-a-codebuddy-20260603-071500",
            "task_id": "TASK-A",
            "worker_id": "codebuddy",
            "dispatch_state": "dispatched",
            "execution": {"prompt_file": ".omo/workers/runs/task-a-codebuddy-20260603-071500-prompt.md"},
        },
    )
    _write_yaml(
        omo / "workers" / "registry.yaml",
        {"default_worker_role": "worker", "workers": [{"id": "codebuddy", "enabled": True, "role": "worker", "transports": {"cli_prompt": {"command": 'python3 -c "print(\\\"ok\\\")"'}}}]},
    )

    main(["task", "governance-overlay-run-next", "--omo-dir", ".omo", "--actor", "copilot-cli", "--now", "2026-06-03T07:16:00Z"], root=root)

    run = _load_yaml(omo / "workers" / "runs" / "governance-overlay-2026-06-03T07-16-00Z.yaml")
    assert run["summary"] == "contract_gap"
    assert run["target_results"][0]["task_id"] == "TASK-A"
    assert run["target_results"][0]["result"] == "contract_gap"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_automation.py -q -k 'records_contract_gap_for_dispatched_task_without_deliverables'
```

Expected: `FAIL` because `governance-overlay-run-next` has no `contract:` branch.

- [ ] **Step 3: Write the failing launch test**

Add this test in `.omo/tests/test_omo_automation.py`:

```python
def test_task_governance_overlay_run_next_launches_dispatched_task_when_scope_is_declared(tmp_path: Path):
    root = tmp_path
    omo = root / ".omo"
    _write_yaml(
        omo / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M1-EXECUTION-HARDENING",
            "next_milestone": "GOV-M2-SHAREDBRAIN-DEBT",
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T07:15:00Z",
        },
    )
    _write_yaml(omo / "_truth" / "governance-overlay" / "autopilot-policy.yaml", {"autopilot_mode": "full_omo_autopilot"})
    _write_yaml(
        omo / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M1-EXECUTION-HARDENING",
                    "type": "task-bundle",
                    "title": "Execution hardening",
                    "priority": "P0",
                    "status": "in_progress",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/TASK-A.yaml"],
                    "success_criteria": ["execution hardening closed"],
                }
            ]
        },
    )
    _write_yaml(
        omo / "tasks" / "active" / "TASK-A.yaml",
        {
            "id": "TASK-A",
            "title": "Task A",
            "status": "in_progress",
            "assigned_to": "codebuddy",
            "dispatch_id": "task-a-codebuddy-20260603-071500",
            "run_ref": ".omo/workers/runs/task-a-codebuddy-20260603-071500-dispatch.yaml",
            "review_ref": ".omo/workers/runs/task-a-codebuddy-20260603-071500-review.md",
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/MASTER-BLUEPRINT.md"],
            "deliverables": ["src/app.py"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "entry_gate": ["phase16_completed"],
            "evidence_required": ["stdout captured"],
            "test_plan": ["python3 -m pytest .omo/tests/test_omo_automation.py -q"],
            "started_at": "2026-06-03T07:15:00Z",
        },
    )
    _write_yaml(
        omo / "workers" / "runs" / "task-a-codebuddy-20260603-071500-dispatch.yaml",
        {
            "dispatch_id": "task-a-codebuddy-20260603-071500",
            "task_id": "TASK-A",
            "worker_id": "codebuddy",
            "transport_mode": "cli_prompt",
            "dispatch_state": "dispatched",
            "execution": {
                "prompt_file": ".omo/workers/runs/task-a-codebuddy-20260603-071500-prompt.md",
                "log_ref": ".omo/workers/runs/task-a-codebuddy-20260603-071500-stdout.log",
            },
            "lease": {
                "heartbeat_interval_seconds": 300,
                "warning_after_seconds": 900,
                "lease_expired_after_seconds": 1200,
                "reclaim_after_seconds": 1800,
                "last_checkpoint_at": None,
                "last_material_write_at": None,
            },
        },
    )
    (omo / "workers" / "runs" / "task-a-codebuddy-20260603-071500-prompt.md").write_text("# prompt\n", encoding="utf-8")
    _write_yaml(
        omo / "workers" / "registry.yaml",
        {
            "default_worker_role": "worker",
            "workers": [
                {
                    "id": "codebuddy",
                    "enabled": True,
                    "role": "worker",
                    "transports": {"cli_prompt": {"command": 'python3 -c "print(\\\"launched\\\")"'}},
                }
            ],
        },
    )

    main(["task", "governance-overlay-run-next", "--omo-dir", ".omo", "--actor", "copilot-cli", "--now", "2026-06-03T07:17:00Z"], root=root)

    run = _load_yaml(omo / "workers" / "runs" / "governance-overlay-2026-06-03T07-17-00Z.yaml")
    dispatch = _load_yaml(omo / "workers" / "runs" / "task-a-codebuddy-20260603-071500-dispatch.yaml")
    stdout_text = (omo / "workers" / "runs" / "task-a-codebuddy-20260603-071500-stdout.log").read_text(encoding="utf-8")

    assert run["summary"] == "launched"
    assert dispatch["dispatch_state"] == "active"
    assert "launched" in stdout_text
```

- [ ] **Step 4: Run the test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_automation.py -q -k 'launches_dispatched_task_when_scope_is_declared'
```

Expected: `FAIL` because there is no launch branch and `dispatch_state` never transitions to `active`.

- [ ] **Step 5: Implement the minimal launch helpers**

In `scripts/omo_worker.py`, extract a reusable launch primitive instead of duplicating subprocess code:

```python
def _launch_worker_from_prompt(
    root: Path,
    registry: dict,
    worker_id: str,
    transport: str,
    prompt_path: Path,
    stdout_path: Path,
) -> str:
    prompt_text = prompt_path.read_text(encoding="utf-8")
    argv = _build_launch_argv(registry, worker_id, transport, prompt_text)
    result = subprocess.run(argv, cwd=root, capture_output=True, text=True)
    output = redact_sensitive_text((result.stdout or "") + (result.stderr or ""))
    write_text_atomic(stdout_path, output)
    return output


def _launch_existing_dispatch(root: Path, dispatch_path: Path, *, omo_dir: str | Path = ".omo") -> dict[str, object]:
    dispatch = _load_yaml(dispatch_path)
    registry = _load_yaml(_omo_path(root, omo_dir) / "workers" / "registry.yaml")
    prompt_path = root / dispatch["execution"]["prompt_file"]
    stdout_path = root / dispatch["execution"]["log_ref"]
    _launch_worker_from_prompt(root, registry, dispatch["worker_id"], dispatch["transport_mode"], prompt_path, stdout_path)
    dispatch["dispatch_state"] = "active"
    dispatch["lease"]["last_material_write_at"] = _utc_now()
    _write_yaml(dispatch_path, dispatch)
    return dispatch
```

Then update `dispatch_task(...)` so `launch=True` reuses the helper and also transitions the new dispatch into `active`:

```python
if launch:
    _launch_worker_from_prompt(root, registry, worker_id, transport, root / prompt_path, root / stdout_path)
    dispatch["dispatch_state"] = "active"
    dispatch["lease"]["last_material_write_at"] = dispatch_now
    _write_yaml(root / dispatch_path, dispatch)
```

- [ ] **Step 6: Add `contract:` and `launch:` branches to run-next**

Update `_write_task_governance_overlay_run_next(...)` in `scripts/omo_worker.py`:

```python
elif next_action.startswith("contract:"):
    task_id = next_action.split(":", 1)[1]
    run["summary"] = "contract_gap"
    run["target_results"] = [
        {
            "task_id": task_id,
            "action": "contract",
            "result": "contract_gap",
            "detail": "task must declare explicit deliverables/write scope before autonomous launch",
        }
    ]
elif next_action.startswith("launch:"):
    task_id = next_action.split(":", 1)[1]
    task = _load_yaml(_find_task_file(_omo_path(root, omo_dir) / "tasks" / "active", task_id))
    dispatch = _launch_existing_dispatch(root, root / task["run_ref"], omo_dir=omo_dir)
    run["summary"] = "launched"
    run["target_results"] = [
        {
            "task_id": task_id,
            "action": "launch",
            "result": "launched",
            "dispatch_state": dispatch["dispatch_state"],
        }
    ]
```

And update the dispatch branch so auto-dispatch becomes auto-launch when the derived scope is non-empty:

```python
allowed_paths = _dispatch_allowed_write_paths(task)
dispatch = dispatch_task(
    root,
    task_id,
    _default_enabled_worker_id(registry),
    allowed_paths,
    launch=bool(allowed_paths),
    now=run_now,
    omo_dir=omo_dir,
)
run["summary"] = "launched" if allowed_paths else "dispatched"
```

- [ ] **Step 7: Add the planner regression**

In `.omo/tests/test_omo_governance_overlay_loop.py`, add a minimal planner regression that proves the loop respects the richer next action:

```python
def test_plan_governance_overlay_cycle_preserves_contract_next_action_for_active_item(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M1-EXECUTION-HARDENING",
            "next_milestone": "GOV-M2-SHAREDBRAIN-DEBT",
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T07:18:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {"autopilot_mode": "full_omo_autopilot", "auto_select": True},
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M1-EXECUTION-HARDENING",
                    "type": "task-bundle",
                    "title": "Execution hardening",
                    "priority": "P0",
                    "status": "in_progress",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/TASK-A.yaml"],
                    "success_criteria": ["execution hardening closed"],
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "active" / "TASK-A.yaml",
        {
            "id": "TASK-A",
            "status": "in_progress",
            "deliverables": [],
            "run_ref": ".omo/workers/runs/task-a-dispatch.yaml",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "task-a-dispatch.yaml",
        {"dispatch_state": "dispatched"},
    )
    result = plan_governance_overlay_cycle(tmp_path, omo_dir=".omo", actor="copilot-cli", now="2026-06-03T07:18:00Z")
    assert result["run"]["mode"] == "continue_active"
    assert result["run"]["next_action_before_run"] == "contract:TASK-A"
    assert result["run"]["summary"] == "in_progress"
```

- [ ] **Step 8: Run the focused automation/loop tests**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_governance_overlay_loop.py .omo/tests/test_omo_automation.py -q -k 'contract_gap_for_dispatched_task_without_deliverables or launches_dispatched_task_when_scope_is_declared or preserves_contract_next_action_for_active_item'
```

Expected: all selected tests `PASS`.

- [ ] **Step 9: Commit the execution-path change**

```bash
cd /Users/xiamingxing/Workspace && git add scripts/omo_worker.py scripts/omo_governance_overlay_loop.py .omo/tests/test_omo_governance_overlay_loop.py .omo/tests/test_omo_automation.py && git -c core.hooksPath=/dev/null commit -m "feat(omo): gate overlay launch on task contract" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Update operator docs and regression contracts

**Files:**
- Modify: `.omo/AGENT.md`
- Modify: `.omo/tasks/README.md`
- Modify: `.omo/workers/README.md`
- Test: `.omo/tests/test_worker_mechanism_consistency.py`

- [ ] **Step 1: Write the failing docs regression**

Add a doc regression like this to `.omo/tests/test_worker_mechanism_consistency.py`:

```python
def test_worker_docs_describe_governance_overlay_launch_contract_actions() -> None:
    readme = (ROOT / ".omo" / "workers" / "README.md").read_text(encoding="utf-8")
    agent_doc = (ROOT / ".omo" / "AGENT.md").read_text(encoding="utf-8")
    task_readme = (ROOT / ".omo" / "tasks" / "README.md").read_text(encoding="utf-8")

    assert "contract:<TASK_ID>" in readme
    assert "launch:<TASK_ID>" in readme
    assert "deliverables" in task_readme
    assert "autonomous launch requires explicit task deliverables" in agent_doc
```

- [ ] **Step 2: Run the docs regression to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_worker_mechanism_consistency.py -q -k 'launch_contract_actions'
```

Expected: `FAIL` because the docs do not mention `contract:` / `launch:` yet.

- [ ] **Step 3: Update the docs**

Add the exact operator guidance:

```md
- active roadmap item 的 canonical next action 还可能是 `contract:<TASK_ID>` 与 `launch:<TASK_ID>`
- `contract:<TASK_ID>` 表示任务已经进入 active lifecycle，但缺少显式 `deliverables` / write scope，overlay 必须 fail closed
- `launch:<TASK_ID>` 表示 dispatch packet 已存在且 task-declared scope 完整，coordinator 可以安全启动外部 worker
- autonomous launch requires explicit task deliverables; empty `deliverables` means dispatch may be recorded, but execution must not auto-launch
```

Apply this language consistently in:

1. `.omo/AGENT.md`
2. `.omo/tasks/README.md`
3. `.omo/workers/README.md`

- [ ] **Step 4: Run the docs regression again**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_worker_mechanism_consistency.py -q -k 'launch_contract_actions'
```

Expected: `PASS`.

- [ ] **Step 5: Commit the docs**

```bash
cd /Users/xiamingxing/Workspace && git add .omo/AGENT.md .omo/tasks/README.md .omo/workers/README.md .omo/tests/test_worker_mechanism_consistency.py && git -c core.hooksPath=/dev/null commit -m "docs(omo): document overlay launch contract actions" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Hydrate live state, run focused verification, and close the slice

**Files:**
- Modify: `.omo/workers/governance-overlay/current.yaml` (generated)
- Modify: `.omo/_control/governance-overlay/current.yaml` (generated if run-next advances)
- Modify: `.omo/workers/runs/governance-overlay-*.yaml` (generated)

- [ ] **Step 1: Recompute the overlay shell after the code changes**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 scripts/omo_worker.py task governance-overlay-status --omo-dir .omo --now 2026-06-03T07:30:00Z
```

Expected:

1. `.omo/workers/governance-overlay/current.yaml` regenerates
2. GOV-M1 active target states no longer collapse empty-scope dispatches into generic `active_in_progress`

- [ ] **Step 2: Execute one live run-next cycle**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 scripts/omo_worker.py task governance-overlay-run-next --omo-dir .omo --actor copilot-cli --now 2026-06-03T07:31:00Z
```

Expected:

1. if the live tasks still have empty `deliverables`, the run artifact summary is `contract_gap`
2. if the live task packets are repaired first, the run artifact summary may become `launched`

- [ ] **Step 3: Run the full focused regression subset**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_governance_overlay.py .omo/tests/test_omo_governance_overlay_loop.py .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py -q -k 'governance_overlay or launch_contract or contract_gap or dispatch_task_uses_supplied_now_for_dispatch_identity_and_start_time'
```

Expected: all selected tests `PASS`.

- [ ] **Step 4: Commit the generated/live surfaces**

```bash
cd /Users/xiamingxing/Workspace && git add .omo/workers/governance-overlay/current.yaml .omo/_control/governance-overlay/current.yaml .omo/workers/runs/governance-overlay-*.yaml && git -c core.hooksPath=/dev/null commit -m "chore(omo): hydrate overlay launch contract surfaces" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

- [ ] **Step 5: Mark the parent todo done**

Run:

```sql
UPDATE todos
SET status = 'done', updated_at = datetime('now')
WHERE id = 'governance-overlay-launch-contract';
```

- [ ] **Step 6: Capture the next bounded slice**

Create the next parent todo only after this plan is implemented and verified:

```sql
INSERT INTO todos (id, title, description, status, created_at, updated_at)
VALUES (
  'governance-overlay-worker-closeout',
  'Designing worker closeout ingestion',
  'Teach the governance overlay to consume worker output, recognize review-ready evidence, and move active roadmap items from running to verify/closeout without widening write scope.',
  'pending',
  datetime('now'),
  datetime('now')
);
```
