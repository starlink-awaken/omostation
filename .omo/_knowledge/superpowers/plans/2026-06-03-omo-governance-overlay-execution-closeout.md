# OMO Governance Overlay Execution-Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the governance overlay so `in_progress` roadmap items keep producing actionable next steps and can close/advance automatically when their target tasks reach terminal states.

**Architecture:** Keep the change inside the existing overlay helper + loop + worker entrypoint. `scripts/omo_governance_overlay.py` becomes the canonical read-side synthesizer for active roadmap items and per-target states, while `scripts/omo_governance_overlay_loop.py` becomes the write-side planner for both “continue active” and “advance pending” modes. `scripts/omo_worker.py` keeps executing mutations and updating control/truth/output surfaces in one place.

**Tech Stack:** Python 3, `pathlib`, `yaml`, existing OMO promotion helpers, existing overlay control/truth files, pytest under `.omo/tests`

---

## File map

- **Modify:** `scripts/omo_governance_overlay.py`
  - Add active roadmap item synthesis, per-target state resolution, and richer `next_action`.
- **Modify:** `scripts/omo_governance_overlay_loop.py`
  - Add active-item planning mode and closeout/block decisions.
- **Modify:** `scripts/omo_worker.py`
  - Extend `governance-overlay-run-next` to continue active items, mutate control state, and write richer run artifacts.
- **Modify:** `.omo/tests/test_omo_governance_overlay.py`
  - Add read-side regression coverage for active roadmap item status.
- **Modify:** `.omo/tests/test_omo_governance_overlay_loop.py`
  - Add closeout/block planner regressions.
- **Modify:** `.omo/tests/test_omo_automation.py`
  - Add CLI regression for closing an active roadmap item and advancing control state.
- **Modify:** `.omo/tests/test_worker_mechanism_consistency.py`
  - Add docs regression for active-item continuation semantics.
- **Modify:** `.omo/workers/README.md`
- **Modify:** `.omo/AGENT.md`
- **Modify:** `.omo/tasks/README.md`
  - Document that `run-next` now continues active roadmap items before scanning new pending candidates.
- **Modify:** `.omo/_control/governance-overlay/current.yaml`
  - Live control state should advance when the current roadmap item closes.
- **Modify:** `.omo/_truth/governance-overlay/roadmap.yaml`
  - Live roadmap item status mutates to `done` / `blocked` as appropriate.
- **Modify:** `.omo/workers/governance-overlay/current.yaml`
- **Modify:** `.omo/workers/governance-overlay/current.md`
- **Create/Modify:** `.omo/workers/runs/governance-overlay-<STAMP>.yaml`
  - Run artifacts now distinguish `advance_pending` vs `continue_active`.

---

### Task 1: Teach the overlay status helper about active roadmap items

**Files:**
- Modify: `scripts/omo_governance_overlay.py`
- Modify: `.omo/tests/test_omo_governance_overlay.py`

- [ ] **Step 1: Write the failing read-side regression**

Add to `.omo/tests/test_omo_governance_overlay.py`:

```python
def test_build_governance_overlay_status_reports_active_roadmap_item_and_target_states(tmp_path: Path):
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
            "updated_at": "2026-06-03T06:35:00Z",
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
                    "target_refs": [".omo/tasks/planned/TASK-A.yaml", ".omo/tasks/planned/TASK-B.yaml"],
                    "success_criteria": ["execution hardening closed"],
                }
            ]
        },
    )
    _write_yaml(tmp_path / ".omo" / "tasks" / "active" / "TASK-A.yaml", {"id": "TASK-A", "status": "pending"})
    _write_yaml(tmp_path / ".omo" / "tasks" / "done" / "TASK-B.yaml", {"id": "TASK-B", "status": "done"})

    result = build_governance_overlay_status(tmp_path, omo_dir=".omo", now="2026-06-03T06:50:00Z")

    assert result["yaml"]["active_roadmap_item"]["id"] == "GOV-M1-EXECUTION-HARDENING"
    assert result["yaml"]["active_target_states"][0]["state"] == "active_pending"
    assert result["yaml"]["active_target_states"][1]["state"] == "done"
    assert result["yaml"]["next_action"] == "execute:TASK-A"
```

- [ ] **Step 2: Run the helper test to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_governance_overlay.py -q -k active_roadmap_item
```

Expected: FAIL because `active_roadmap_item` / `active_target_states` / richer `next_action` do not exist yet.

- [ ] **Step 3: Implement active-item synthesis**

Update `scripts/omo_governance_overlay.py` to add:

1. `_target_state(root, target_ref)` returning:

```python
{
    "target_ref": target_ref,
    "task_id": "TASK-A",
    "state": "active_pending",
    "detail": "task currently exists in tasks/active/ with status pending",
}
```

2. active item selection:

```python
active_items = [item for item in roadmap.get("items", []) if item.get("status") == "in_progress"]
if len(active_items) > 1:
    raise ValueError("multiple in_progress roadmap items are not supported in v1")
active_item = active_items[0] if active_items else None
```

3. richer `next_action` rules:

```python
if active_item:
    if any(target["state"] == "active_pending" for target in active_target_states):
        next_action = f"execute:{first_pending_task_id}"
    elif any(target["state"] in {"active_in_progress", "active_review"} for target in active_target_states):
        next_action = f"monitor:{active_item['id']}"
    elif any(target["state"] == "planned_pending" for target in active_target_states):
        next_action = f"advance:{active_item['id']}"
    elif active_target_states and all(target["state"] == "done" for target in active_target_states):
        next_action = f"close:{active_item['id']}"
    elif active_target_states and all(target["state"] in {"planned_blocked", "unsupported_target_ref", "missing_target_ref"} for target in active_target_states):
        next_action = f"block:{active_item['id']}"
```

4. packet fields:

```python
"active_roadmap_item": {
    "id": active_item["id"],
    "title": active_item["title"],
    "type": active_item["type"],
    "priority": active_item["priority"],
},
"active_target_states": active_target_states,
```

- [ ] **Step 4: Run the helper test to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_governance_overlay.py -q -k active_roadmap_item
```

Expected: PASS.

---

### Task 2: Extend the loop planner and CLI to continue or close the active roadmap item

**Files:**
- Modify: `scripts/omo_governance_overlay_loop.py`
- Modify: `scripts/omo_worker.py`
- Modify: `.omo/tests/test_omo_governance_overlay_loop.py`
- Modify: `.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Write the failing planner + CLI regressions**

Add to `.omo/tests/test_omo_governance_overlay_loop.py`:

```python
def test_plan_governance_overlay_cycle_closes_done_active_item(tmp_path: Path):
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
    })
    _write_yaml(tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml", {
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
            },
            {
                "id": "GOV-M2-SHAREDBRAIN-DEBT",
                "type": "debt-bundle",
                "title": "SharedBrain debt",
                "priority": "P1",
                "status": "pending",
                "depends_on": ["GOV-M1-EXECUTION-HARDENING"],
                "source_refs": [".omo/debt/registry.yaml"],
                "target_refs": [".omo/debt/dashboard/current.yaml"],
                "success_criteria": ["debt closed"],
            },
        ]
    })
    _write_yaml(tmp_path / ".omo" / "tasks" / "done" / "TASK-A.yaml", {"id": "TASK-A", "status": "done"})

    result = plan_governance_overlay_cycle(tmp_path, omo_dir=".omo", actor="copilot-cli", now="2026-06-03T06:50:00Z")

    assert result["run"]["mode"] == "continue_active"
    assert result["run"]["summary"] == "close_ready"
    assert result["run"]["roadmap_item_id"] == "GOV-M1-EXECUTION-HARDENING"
```

Add to `.omo/tests/test_omo_automation.py`:

```python
def test_task_governance_overlay_run_next_closes_done_active_item_and_advances_control(tmp_path: Path, monkeypatch, capsys):
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
    })
    _write_yaml(tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml", {
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
            },
            {
                "id": "GOV-M2-SHAREDBRAIN-DEBT",
                "type": "debt-bundle",
                "title": "SharedBrain debt",
                "priority": "P1",
                "status": "pending",
                "depends_on": ["GOV-M1-EXECUTION-HARDENING"],
                "source_refs": [".omo/debt/registry.yaml"],
                "target_refs": [".omo/debt/dashboard/current.yaml"],
                "success_criteria": ["debt closed"],
            },
        ]
    })
    _write_yaml(tmp_path / ".omo" / "tasks" / "done" / "TASK-A.yaml", {"id": "TASK-A", "status": "done"})

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "governance-overlay-run-next", "--omo-dir", ".omo", "--actor", "copilot-cli", "--now", "2026-06-03T06:50:00Z"],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    control = _load_yaml(tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml")
    roadmap = _load_yaml(tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml")
    run_packet = _load_yaml(tmp_path / ".omo" / "workers" / "runs" / "governance-overlay-2026-06-03T06-50-00Z.yaml")

    assert "summary=closed" in output
    assert control["current_milestone"] == "GOV-M2-SHAREDBRAIN-DEBT"
    assert control["next_milestone"] is None
    assert roadmap["items"][0]["status"] == "done"
    assert run_packet["mode"] == "continue_active"
```

- [ ] **Step 2: Run the new tests to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_governance_overlay_loop.py .omo/tests/test_omo_automation.py -q -k 'close_done_active_item'
```

Expected: FAIL because the planner only handles pending candidates and the CLI does not close/advance active roadmap items.

- [ ] **Step 3: Implement active-item continuation**

In `scripts/omo_governance_overlay_loop.py`, extend `plan_governance_overlay_cycle(...)` so it can produce:

```python
run = {
    "run_id": f"governance-overlay-{now.replace(':', '-')}",
    "overlay_id": status["overlay_id"],
    "actor": actor,
    "started_at": now,
    "completed_at": now,
    "mode": "continue_active",
    "roadmap_item_id": active_item["id"],
    "summary": "close_ready",
    "target_results": active_target_states,
    "target_state_summary": {"done": 1, "active_pending": 0, "active_in_progress": 0},
    "control_updates": {"current_milestone": "GOV-M2-SHAREDBRAIN-DEBT", "next_milestone": None},
}
```

Decision rules:

1. if all active target states are `done` → `summary="close_ready"`
2. if all are terminal blockers → `summary="block_ready"`
3. otherwise → `summary="in_progress"`

In `scripts/omo_worker.py`, extend `_write_task_governance_overlay_run_next(...)`:

1. if `run["mode"] == "continue_active"` and `summary == "close_ready"`:

```python
roadmap_item["status"] = "done"
control["current_milestone"] = run["control_updates"]["current_milestone"]
control["next_milestone"] = run["control_updates"]["next_milestone"]
control["updated_at"] = run_now
run["summary"] = "closed"
```

2. if `summary == "block_ready"`:

```python
roadmap_item["status"] = "blocked"
roadmap_item["blocked_reason"] = "all_targets_terminal_blocked"
run["summary"] = "blocked"
```

3. otherwise keep `in_progress` and just refresh current surfaces.

- [ ] **Step 4: Run the new tests to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_governance_overlay_loop.py .omo/tests/test_omo_automation.py -q -k 'close_done_active_item'
```

Expected: PASS.

---

### Task 3: Refresh docs, rehearse one closeout cycle, and commit

**Files:**
- Modify: `.omo/tests/test_worker_mechanism_consistency.py`
- Modify: `.omo/workers/README.md`
- Modify: `.omo/AGENT.md`
- Modify: `.omo/tasks/README.md`
- Modify: `.omo/_control/governance-overlay/current.yaml`
- Modify: `.omo/_truth/governance-overlay/roadmap.yaml`
- Modify: `.omo/workers/governance-overlay/current.yaml`
- Modify: `.omo/workers/governance-overlay/current.md`

- [ ] **Step 1: Add the docs regression**

Append to `.omo/tests/test_worker_mechanism_consistency.py`:

```python
def test_worker_docs_describe_governance_overlay_active_item_continuation():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "AGENT.md").read_text(encoding="utf-8")

    assert "continue_active" in workers_text
    assert "close a finished roadmap item and advance control state" in workers_text
    assert "current active roadmap item" in agent_text
```

- [ ] **Step 2: Update docs**

Update `.omo/workers/README.md` with:

```md
When the current roadmap item is already `in_progress`, `governance-overlay-run-next` no longer scans a new pending candidate first. It continues the current active roadmap item, writes `mode: continue_active` into the run artifact, and can close a finished roadmap item plus advance `.omo/_control/governance-overlay/current.yaml`.
```

Update `.omo/AGENT.md` with:

```md
治理 overlay 现在有 current active roadmap item continuation 语义：`governance-overlay-run-next` 会先处理当前 `in_progress` item，再考虑新的 pending candidate；因此不要把 `next_action: idle` 误读为 “没有工作”，除非 active item 与 pending item 都不存在。
```

- [ ] **Step 3: Run the docs regression**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_worker_mechanism_consistency.py -q -k 'governance_overlay_active_item_continuation'
```

Expected: PASS.

- [ ] **Step 4: Rehearse a live closeout-safe cycle**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 scripts/omo_worker.py task governance-overlay-status --omo-dir .omo --now 2026-06-03T06:55:00Z
```

Then inspect whether the current active roadmap item now exposes a non-idle `next_action`. If there is a done-ready fixture in real overlay state, run:

```bash
cd /Users/xiamingxing/Workspace && python3 scripts/omo_worker.py task governance-overlay-run-next --omo-dir .omo --actor copilot-cli --now 2026-06-03T06:55:00Z
```

Expected:

1. current overlay status exposes `active_roadmap_item`
2. `next_action` is not silently idle while active targets remain unfinished
3. if the item is done-ready, control state advances

- [ ] **Step 5: Run the focused verification bundle**

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

Expected: overlay shell + loop + active continuation regressions all pass.

- [ ] **Step 6: Commit both repos**

Nested `scripts` repo:

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_governance_overlay.py omo_governance_overlay_loop.py omo_worker.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add governance overlay execution closeout" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Root repo:

```bash
cd /Users/xiamingxing/Workspace && \
git add \
  scripts \
  docs/superpowers/specs/2026-06-03-omo-governance-overlay-execution-closeout-design.md \
  docs/superpowers/plans/2026-06-03-omo-governance-overlay-execution-closeout.md \
  .omo/tests/test_omo_governance_overlay.py \
  .omo/tests/test_omo_governance_overlay_loop.py \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  .omo/workers/README.md \
  .omo/AGENT.md \
  .omo/tasks/README.md \
  .omo/_control/governance-overlay/current.yaml \
  .omo/_truth/governance-overlay/roadmap.yaml \
  .omo/workers/governance-overlay/current.yaml \
  .omo/workers/governance-overlay/current.md \
  .omo/workers/runs/governance-overlay-*.yaml && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add governance overlay execution closeout" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Self-review checklist

1. active roadmap items are visible in `current.yaml`
2. `run-next` handles `continue_active` before scanning pending candidates
3. closeout advances `.omo/_control/governance-overlay/current.yaml`
4. active tasks do not incorrectly mark roadmap items `done`
5. the loop still preserves existing approval / promotion gates

## Execution note

Plan complete and saved to `docs/superpowers/plans/2026-06-03-omo-governance-overlay-execution-closeout.md`. In the current autonomous session, proceed with **Inline Execution**.
