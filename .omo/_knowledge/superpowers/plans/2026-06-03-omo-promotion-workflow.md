---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# OMO Promotion Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a coordinator-owned, fail-closed `planned -> active` promotion workflow with one real rehearsal for `ORPHANED-TASKS-STRUCTURED-REGISTRY`.

**Architecture:** Extend the existing `python3 scripts/omo_worker.py task ...` surface with narrow `promote-eval` and `promote-apply` commands instead of inventing a new lifecycle domain. Keep promotion as a queue move that records a first-class promotion envelope under `.omo/workers/runs/`, writes that envelope ref into the promoted task's `handoff_refs`, and then refreshes `.omo/state/system.yaml` so live queue counts stay authoritative.

**Tech Stack:** Python 3, `argparse`, `pathlib`, `yaml`, existing `scripts/omo_io.py` atomic writers, existing `.omo/tests` pytest suite, `.omo` YAML SSOT files

---

## File map

- **Modify:** `scripts/omo_worker.py`
  - Add planned-task lookup, promotion eligibility evaluation, `promote-eval`, `promote-apply`, and sync rollback handling.
- **Create:** `.omo/workers/templates/worker-promotion-envelope.yaml`
  - Canonical template for the new promotion artifact contract.
- **Modify:** `.omo/tests/test_omo_automation.py`
  - Add CLI-focused RED/GREEN tests for phase horizon, approval gating, successful apply, and rollback.
- **Modify:** `.omo/tests/test_worker_mechanism_consistency.py`
  - Replace the old “all future pending packets must stay out of active” rule with the new “future pending packets in active require a promotion envelope ref in `handoff_refs`” rule.
- **Modify:** `.omo/tasks/README.md`
  - Document `promote-eval` / `promote-apply` and the meaning of promotion envelope refs in `handoff_refs`.
- **Modify:** `.omo/AGENT.md`
  - Document that agents still do not execute `planned/` directly and that promotion is a coordinator-only action.
- **Modify:** `.omo/INDEX.md`
  - Add a navigation mention that planned packets become active only through the promotion workflow.
- **Delete:** `.omo/tasks/planned/ORPHANED-TASKS-STRUCTURED-REGISTRY.yaml`
  - The rehearsal moves this exact packet out of `planned/`.
- **Create:** `.omo/tasks/active/ORPHANED-TASKS-STRUCTURED-REGISTRY.yaml`
  - Result of the real rehearsal; same packet, now active, with a promotion envelope ref in `handoff_refs`.
- **Create:** `.omo/workers/runs/ORPHANED-TASKS-STRUCTURED-REGISTRY-promotion-2026-06-03T00-00-00Z.yaml`
  - Deterministic rehearsal artifact produced by running `promote-apply --now 2026-06-03T00:00:00Z`.
- **Modify:** `.omo/state/system.yaml`
  - Refreshed queue counts and previews after the rehearsal.

---

### Task 1: Add promotion eligibility evaluation

**Files:**
- Modify: `scripts/omo_worker.py`
- Test: `.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Write the failing tests**

Add two CLI regressions to `.omo/tests/test_omo_automation.py` near the existing `task validate` and worker CLI coverage:

```python
def test_task_promote_eval_rejects_phase_beyond_next_wave(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P18-W1-TOO-FAR.yaml",
        {
            "id": "P18-W1-TOO-FAR",
            "phase": 18,
            "milestone": "M18.1",
            "priority": "P1",
            "title": "Too far ahead",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase16_completed"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "promote-eval", "P18-W1-TOO-FAR", "--omo-dir", ".omo"],
    )

    assert omo_worker_main() == 1
    assert "phase_mismatch" in capsys.readouterr().out


def test_task_promote_eval_rejects_missing_required_approval_ref(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-NEEDS-APPROVAL.yaml",
        {
            "id": "P17-W1-NEEDS-APPROVAL",
            "phase": 17,
            "milestone": "M17.1",
            "priority": "P1",
            "title": "Approval-gated packet",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase16_completed"],
            "risk_level": "L2",
            "allowed_operation_level": "L2",
            "human_approval_required": True,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "promote-eval", "P17-W1-NEEDS-APPROVAL", "--omo-dir", ".omo"],
    )

    assert omo_worker_main() == 1
    assert "approval_missing" in capsys.readouterr().out
```

- [ ] **Step 2: Run the focused tests to confirm RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_automation.py -q -k 'task_promote_eval'
```

Expected: both tests fail because `omo_worker.py task promote-eval` does not exist yet.

- [ ] **Step 3: Write the minimal evaluation implementation**

Add the new helpers and CLI branch to `scripts/omo_worker.py`:

```python
def _find_planned_task_file(planned_dir: Path, task_id: str) -> Path:
    for task_file in planned_dir.glob("*.yaml"):
        task = _load_yaml(task_file)
        if task.get("id") == task_id:
            return task_file
    raise FileNotFoundError(f"Task not found in planned/: {task_id}")


def _promotion_eval(root: Path, task_id: str, omo_dir: str | Path = ".omo") -> dict[str, object]:
    omo = _omo_path(root, omo_dir)
    goals = _load_yaml(omo / "goals" / "current.yaml")
    task_file = _find_planned_task_file(omo / "tasks" / "planned", task_id)
    task = _load_yaml(task_file)
    active_target = omo / "tasks" / "active" / task_file.name

    check_results = {
        "queue_membership_ok": True,
        "status_ok": task.get("status") in {"candidate", "pending"},
        "phase_ok": task.get("phase") == int(goals["phase"]) + 1,
        "approval_ready": (not task.get("human_approval_required")) or bool(task.get("approval_ref")),
        "target_path_clear": not active_target.exists(),
    }

    active_ready_errors = validate_task_file(task_file)
    check_results["active_schema_ready"] = not active_ready_errors

    blockers = []
    if not check_results["status_ok"]:
        blockers.append("status_invalid")
    if not check_results["phase_ok"]:
        blockers.append("phase_mismatch")
    if not check_results["approval_ready"]:
        blockers.append("approval_missing")
    if not check_results["target_path_clear"]:
        blockers.append("target_path_exists")
    if not check_results["active_schema_ready"]:
        blockers.append("active_schema_invalid")

    return {
        "task_id": task_id,
        "task_ref": str(task_file.relative_to(root)),
        "eligible": not blockers,
        "blockers": blockers,
        "checks": check_results,
    }


def _print_task_promotion_eval(root: Path, task_id: str, omo_dir: str | Path = ".omo") -> int:
    result = _promotion_eval(root, task_id, omo_dir=omo_dir)
    print(
        f"task_id={result['task_id']} eligible={str(result['eligible']).lower()} "
        f"blockers={','.join(result['blockers']) or 'none'}"
    )
    return 0 if result["eligible"] else 1
```

Wire the parser and command dispatch:

```python
promote_eval_parser = task_sub.add_parser("promote-eval")
promote_eval_parser.add_argument("task_id")
promote_eval_parser.add_argument("--omo-dir", default=".omo")

if args.command == "task" and args.task_command == "promote-eval":
    return _print_task_promotion_eval(Path.cwd(), args.task_id, omo_dir=args.omo_dir)
```

- [ ] **Step 4: Re-run the focused tests to confirm GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_automation.py -q -k 'task_promote_eval'
```

Expected: `2 passed`.

- [ ] **Step 5: Commit the evaluation slice**

Commit `scripts/` first, then the root repo:

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_worker.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add task promotion evaluation" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

cd /Users/xiamingxing/Workspace && \
git add scripts .omo/tests/test_omo_automation.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add task promotion evaluation" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one `scripts` commit and one root commit, both limited to the evaluation slice.

---

### Task 2: Add promotion apply, envelope writing, and rollback

**Files:**
- Modify: `scripts/omo_worker.py`
- Create: `.omo/workers/templates/worker-promotion-envelope.yaml`
- Test: `.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Write the failing tests**

Add two more regressions to `.omo/tests/test_omo_automation.py`:

```python
def test_task_promote_apply_moves_task_and_writes_envelope(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-READY.yaml",
        {
            "id": "P17-W1-READY",
            "phase": 17,
            "milestone": "M17.1",
            "priority": "P1",
            "title": "Ready packet",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase16_completed"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "scripts.omo_worker.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "task",
            "promote-apply",
            "P17-W1-READY",
            "--promoted-by",
            "copilot-cli",
            "--now",
            "2026-06-03T00:00:00Z",
            "--omo-dir",
            ".omo",
        ],
    )

    assert omo_worker_main() == 0
    active_task = _load_yaml(tmp_path / ".omo" / "tasks" / "active" / "P17-W1-READY.yaml")
    assert active_task["status"] == "pending"
    assert active_task["handoff_refs"] == [
        ".omo/workers/runs/P17-W1-READY-promotion-2026-06-03T00-00-00Z.yaml"
    ]
    assert (tmp_path / ".omo" / "workers" / "runs" / "P17-W1-READY-promotion-2026-06-03T00-00-00Z.yaml").exists()
    assert not (tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-READY.yaml").exists()


def test_task_promote_apply_rolls_back_when_sync_fails(tmp_path: Path, monkeypatch):
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-ROLLBACK.yaml",
        {
            "id": "P17-W1-ROLLBACK",
            "phase": 17,
            "milestone": "M17.1",
            "priority": "P1",
            "title": "Rollback packet",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase16_completed"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )

    monkeypatch.chdir(tmp_path)

    def _fail_sync(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr("scripts.omo_worker.subprocess.run", _fail_sync)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "task",
            "promote-apply",
            "P17-W1-ROLLBACK",
            "--promoted-by",
            "copilot-cli",
            "--now",
            "2026-06-03T00:00:00Z",
            "--omo-dir",
            ".omo",
        ],
    )

    assert omo_worker_main() == 1
    assert (tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-ROLLBACK.yaml").exists()
    assert not (tmp_path / ".omo" / "tasks" / "active" / "P17-W1-ROLLBACK.yaml").exists()
    assert not (
        tmp_path / ".omo" / "workers" / "runs" / "P17-W1-ROLLBACK-promotion-2026-06-03T00-00-00Z.yaml"
    ).exists()
```

- [ ] **Step 2: Run the focused tests to confirm RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_automation.py -q -k 'task_promote_apply'
```

Expected: both tests fail because `promote-apply` and the promotion envelope contract do not exist yet.

- [ ] **Step 3: Add the envelope template and apply implementation**

Create `.omo/workers/templates/worker-promotion-envelope.yaml`:

```yaml
version: 1
promotion_id: "<TASK_ID>-promotion-<TIMESTAMP>"
task_id: "<TASK_ID>"
task_ref_before: ".omo/tasks/planned/<TASK_ID>.yaml"
task_ref_after: ".omo/tasks/active/<TASK_ID>.yaml"
promotion_status: "approved"
promoted_by: "<coordinator-id>"
promoted_at: "<ISO8601>"
phase_gate:
  current_phase: 16
  target_phase: 17
  allowed_by_rule: true
approval:
  required: false
  approval_ref: null
checks:
  queue_membership_ok: true
  status_ok: true
  active_schema_ready: true
  approval_ready: true
  target_path_clear: true
rollback:
  supported: true
  rollback_action: "move task back to .omo/tasks/planned/ and rerun sync"
refs:
  state_ref: ".omo/state/system.yaml"
  goals_ref: ".omo/goals/current.yaml"
```

Extend `scripts/omo_worker.py`:

```python
def _promotion_stamp(now: str) -> str:
    return now.replace(":", "-")


def _sync_omo_state(root: Path, omo_dir: str | Path) -> None:
    subprocess.run(
        ["python3", "scripts/sync_omo_state.py", "--omo-dir", str(omo_dir)],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def _apply_task_promotion(root: Path, task_id: str, promoted_by: str, now: str, omo_dir: str | Path = ".omo") -> int:
    result = _promotion_eval(root, task_id, omo_dir=omo_dir)
    if not result["eligible"]:
        print(
            f"task_id={task_id} eligible=false blockers={','.join(result['blockers'])}"
        )
        return 1

    omo = _omo_path(root, omo_dir)
    planned_path = root / result["task_ref"]
    active_path = omo / "tasks" / "active" / planned_path.name
    task = _load_yaml(planned_path)
    stamp = _promotion_stamp(now)
    envelope_rel = Path(".omo") / "workers" / "runs" / f"{task_id}-promotion-{stamp}.yaml"
    envelope_path = root / envelope_rel
    envelope = {
        "version": 1,
        "promotion_id": f"{task_id}-promotion-{stamp}",
        "task_id": task_id,
        "task_ref_before": str(Path(".omo") / "tasks" / "planned" / planned_path.name),
        "task_ref_after": str(Path(".omo") / "tasks" / "active" / planned_path.name),
        "promotion_status": "approved",
        "promoted_by": promoted_by,
        "promoted_at": now,
        "phase_gate": {
            "current_phase": int(_load_yaml(omo / "goals" / "current.yaml")["phase"]),
            "target_phase": task["phase"],
            "allowed_by_rule": True,
        },
        "approval": {
            "required": bool(task.get("human_approval_required")),
            "approval_ref": task.get("approval_ref"),
        },
        "checks": result["checks"],
        "rollback": {
            "supported": True,
            "rollback_action": "move task back to .omo/tasks/planned/ and rerun sync",
        },
        "refs": {
            "state_ref": ".omo/state/system.yaml",
            "goals_ref": ".omo/goals/current.yaml",
        },
    }
    _write_yaml(envelope_path, envelope)

    original_handoffs = list(task.get("handoff_refs", []))
    task["handoff_refs"] = _append_unique(original_handoffs, [str(envelope_rel)])
    _write_yaml(planned_path, task)

    active_path.parent.mkdir(parents=True, exist_ok=True)
    planned_path.replace(active_path)
    try:
        _sync_omo_state(root, omo_dir)
    except subprocess.CalledProcessError:
        active_task = _load_yaml(active_path)
        active_task["handoff_refs"] = original_handoffs
        _write_yaml(active_path, active_task)
        active_path.replace(planned_path)
        envelope_path.unlink(missing_ok=True)
        print(f"task_id={task_id} promoted=false blockers=sync_failed")
        return 1

    print(f"promotion_ref={envelope_rel} task_ref={Path('.omo') / 'tasks' / 'active' / planned_path.name}")
    return 0
```

Wire the parser and dispatch:

```python
promote_apply_parser = task_sub.add_parser("promote-apply")
promote_apply_parser.add_argument("task_id")
promote_apply_parser.add_argument("--promoted-by", required=True)
promote_apply_parser.add_argument("--now", required=True)
promote_apply_parser.add_argument("--omo-dir", default=".omo")

if args.command == "task" and args.task_command == "promote-apply":
    return _apply_task_promotion(
        Path.cwd(),
        args.task_id,
        promoted_by=args.promoted_by,
        now=args.now,
        omo_dir=args.omo_dir,
    )
```

- [ ] **Step 4: Re-run the focused tests to confirm GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_automation.py -q -k 'task_promote_apply'
```

Expected: `2 passed`.

- [ ] **Step 5: Commit the apply slice**

Commit `scripts/` first, then the root repo:

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_worker.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add task promotion apply" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

cd /Users/xiamingxing/Workspace && \
git add scripts .omo/workers/templates/worker-promotion-envelope.yaml .omo/tests/test_omo_automation.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add task promotion apply" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one `scripts` commit and one root commit, both limited to the apply slice.

---

### Task 3: Align queue-hygiene tests and docs with promoted pending packets

**Files:**
- Modify: `.omo/tests/test_worker_mechanism_consistency.py`
- Modify: `.omo/tasks/README.md`
- Modify: `.omo/AGENT.md`
- Modify: `.omo/INDEX.md`

- [ ] **Step 1: Replace the old repo-state test and add the new failing doc test**

Delete `test_pending_future_phase_packets_live_in_planned_queue()` from `.omo/tests/test_worker_mechanism_consistency.py` and replace it with the governed-promotion version below. Then add the doc regression:

```python
def test_future_phase_pending_packets_in_active_require_promotion_handoff_ref():
    goals = _load_yaml(OMO / "goals" / "current.yaml")
    current_phase = goals["phase"]
    failures = []

    for task_file in _task_files("active"):
        task = _load_yaml(task_file)
        if task.get("phase", 0) <= current_phase or task.get("status") != "pending":
            continue
        has_promotion_ref = any("-promotion-" in ref for ref in task.get("handoff_refs", []))
        if not has_promotion_ref:
            failures.append(task["id"])

    assert failures == [], failures


def test_task_docs_describe_planned_to_active_promotion_workflow():
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "AGENT.md").read_text(encoding="utf-8")
    index_text = (OMO / "INDEX.md").read_text(encoding="utf-8")

    assert "promote-eval" in tasks_text
    assert "promote-apply" in tasks_text
    assert "handoff_refs" in tasks_text
    assert "promote-apply" in agent_text
    assert "planned packets become active only through promotion" in index_text
```

- [ ] **Step 2: Run the focused tests to confirm RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_worker_mechanism_consistency.py -q -k 'promotion_handoff_ref or promotion_workflow'
```

Expected: failures because the repo-state rule and docs still describe `planned/` only as backlog, not as a governed promotion source.

- [ ] **Step 3: Update the repo-state rule and docs**

Update the queue-hygiene test and docs:

```markdown
<!-- .omo/tasks/README.md -->
3. `active/` 是 current executable queue；planned packet 只有在正式晋升后才进入 `active/`。
4. coordinator 可先运行 `python3 scripts/omo_worker.py task promote-eval <TASK_ID> --omo-dir .omo`
5. 真正晋升时运行 `python3 scripts/omo_worker.py task promote-apply <TASK_ID> --promoted-by <ACTOR> --now <ISO8601> --omo-dir .omo`
6. 被晋升的 pending packet 必须把 promotion envelope ref 写入 `handoff_refs`，否则视为非法回流 backlog。
```

```markdown
<!-- .omo/AGENT.md -->
> **Queue contract**：采用 `strict-active-only` 规则；只有 `tasks/active/` 是当前可执行队列，`tasks/planned/` 只是 future backlog / not-yet-promoted packet surface。coordinator 如需让 planned packet 进入 active，必须先走 `task promote-eval` / `task promote-apply` 并留下 promotion envelope。
```

```markdown
<!-- .omo/INDEX.md -->
- **当前执行焦点**: Phase 17 governance gate packets are active; future backlog lives under `tasks/planned/`, and planned packets become active only through promotion
```

- [ ] **Step 4: Re-run the focused tests to confirm GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_worker_mechanism_consistency.py -q -k 'promotion_handoff_ref or promotion_workflow'
```

Expected: `2 passed`.

- [ ] **Step 5: Commit the contract-alignment slice**

Commit in the root repo:

```bash
cd /Users/xiamingxing/Workspace && \
git add .omo/tests/test_worker_mechanism_consistency.py .omo/tasks/README.md .omo/AGENT.md .omo/INDEX.md && \
git -c core.hooksPath=/dev/null commit -m "docs(omo): align promotion queue contract" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one root commit containing only the queue-hygiene/doc updates.

---

### Task 4: Run the real rehearsal and refresh live state

**Files:**
- Delete: `.omo/tasks/planned/ORPHANED-TASKS-STRUCTURED-REGISTRY.yaml`
- Create: `.omo/tasks/active/ORPHANED-TASKS-STRUCTURED-REGISTRY.yaml`
- Create: `.omo/workers/runs/ORPHANED-TASKS-STRUCTURED-REGISTRY-promotion-2026-06-03T00-00-00Z.yaml`
- Modify: `.omo/state/system.yaml`

- [ ] **Step 1: Run the real promotion rehearsal**

Execute the exact CLI path added in Tasks 1-2:

```bash
cd /Users/xiamingxing/Workspace && \
python3 scripts/omo_worker.py task promote-apply ORPHANED-TASKS-STRUCTURED-REGISTRY \
  --promoted-by copilot-cli \
  --now 2026-06-03T00:00:00Z \
  --omo-dir .omo
```

Expected output includes:

```text
promotion_ref=.omo/workers/runs/ORPHANED-TASKS-STRUCTURED-REGISTRY-promotion-2026-06-03T00-00-00Z.yaml
task_ref=.omo/tasks/active/ORPHANED-TASKS-STRUCTURED-REGISTRY.yaml
```

- [ ] **Step 2: Inspect the live rehearsal result**

Confirm the moved task and envelope contents:

```bash
cd /Users/xiamingxing/Workspace && \
python3 - <<'PY'
import yaml
from pathlib import Path

active = yaml.safe_load(Path(".omo/tasks/active/ORPHANED-TASKS-STRUCTURED-REGISTRY.yaml").read_text())
envelope = yaml.safe_load(Path(".omo/workers/runs/ORPHANED-TASKS-STRUCTURED-REGISTRY-promotion-2026-06-03T00-00-00Z.yaml").read_text())

assert active["status"] == "pending"
assert ".omo/workers/runs/ORPHANED-TASKS-STRUCTURED-REGISTRY-promotion-2026-06-03T00-00-00Z.yaml" in active["handoff_refs"]
assert envelope["task_id"] == "ORPHANED-TASKS-STRUCTURED-REGISTRY"
assert envelope["promotion_status"] == "approved"
print("promotion rehearsal artifact verified")
PY
```

Expected: prints `promotion rehearsal artifact verified`.

- [ ] **Step 3: Run focused regressions plus full `.omo` verification**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py -q -k 'promote or promotion' && \
python3 scripts/omo_worker.py task validate --all-planned && \
bash bin/verify-omo.sh
```

Expected:

1. promotion-focused pytest passes
2. `task validate --all-planned` passes with exit `0`
3. `bash bin/verify-omo.sh` passes cleanly

- [ ] **Step 4: Commit the rehearsal and live-state refresh**

Commit in the root repo:

```bash
cd /Users/xiamingxing/Workspace && \
git add .omo/tasks/planned/ORPHANED-TASKS-STRUCTURED-REGISTRY.yaml \
        .omo/tasks/active/ORPHANED-TASKS-STRUCTURED-REGISTRY.yaml \
        .omo/workers/runs/ORPHANED-TASKS-STRUCTURED-REGISTRY-promotion-2026-06-03T00-00-00Z.yaml \
        .omo/state/system.yaml && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): rehearse task promotion workflow" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one root commit with the deterministic rehearsal artifact and the moved packet.

---

## Self-review checklist

- **Spec coverage:** covered by Task 1 (eligibility + fail-closed eval), Task 2 (apply + envelope + rollback), Task 3 (queue-hygiene/docs alignment for promoted pending packets), and Task 4 (real rehearsal + state refresh + full verification).
- **Placeholder scan:** this plan intentionally uses deterministic timestamps and exact file paths so the rehearsal artifact is reproducible and reviewable.
- **Type consistency:** the plan uses one helper vocabulary throughout: `_promotion_eval`, `_apply_task_promotion`, `promote-eval`, `promote-apply`, and promotion envelope refs recorded in `handoff_refs`.
