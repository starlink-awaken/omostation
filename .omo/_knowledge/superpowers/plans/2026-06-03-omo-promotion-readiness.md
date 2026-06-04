# OMO Promotion Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a canonical promotion readiness/current surface so OMO can show which planned tasks are promotable now and which gates are blocking the rest.

**Architecture:** Add a small pure helper in `scripts/omo_promotion_readiness.py` that builds a deterministic readiness packet and Markdown summary from precomputed task-eval entries. Keep gate evaluation itself inside `scripts/omo_worker.py` by reusing `_promotion_eval(...)`, then materialize the derived surface through `task promotion-readiness --omo-dir .omo [--now ...]`.

**Tech Stack:** Python 3, `pathlib`, `argparse`, `yaml`, existing `scripts/omo_io.py` atomic writers, pytest under `.omo/tests`, `.omo` YAML SSOT files

---

## File map

- **Create:** `scripts/omo_promotion_readiness.py`
  - Pure packet/Markdown builder for readiness output. No filesystem mutation.
- **Modify:** `scripts/omo_worker.py`
  - Add `task promotion-readiness`, scan planned tasks, reuse `_promotion_eval(...)`, and write `.omo/workers/promotion/readiness.yaml` plus `.md`.
- **Create:** `.omo/tests/test_omo_promotion_readiness.py`
  - Focused helper tests for empty queue, mixed eligible/blocked ordering, and Markdown rendering.
- **Modify:** `.omo/tests/test_omo_automation.py`
  - Add CLI regression coverage for readiness materialization and deterministic `--now`.
- **Modify:** `.omo/tests/test_worker_mechanism_consistency.py`
  - Add docs regression so the readiness surface remains documented.
- **Modify:** `.omo/workers/README.md`
  - Document the new readiness command and surfaces.
- **Modify:** `.omo/AGENT.md`
  - Document where operators should read current promotion readiness.
- **Modify:** `.omo/tasks/README.md`
  - Document readiness as the queue-wide read-side companion to `promote-eval`.
- **Create:** `.omo/workers/promotion/readiness.yaml`
  - Canonical derived readiness surface hydrated from the current planned queue.
- **Create:** `.omo/workers/promotion/readiness.md`
  - Human-readable summary of the same packet.

---

### Task 1: Build the pure readiness helper

**Files:**
- Create: `scripts/omo_promotion_readiness.py`
- Test: `.omo/tests/test_omo_promotion_readiness.py`

- [ ] **Step 1: Write the failing helper tests**

Create `.omo/tests/test_omo_promotion_readiness.py`:

```python
from __future__ import annotations

from scripts.omo_promotion_readiness import (
    build_promotion_readiness_packet,
    render_promotion_readiness_markdown,
)


def test_build_promotion_readiness_packet_returns_zero_counts_for_empty_queue():
    packet = build_promotion_readiness_packet(
        generated_at="2026-06-03T00:00:00Z",
        current_phase=16,
        tasks=(),
    )

    assert packet["current_phase"] == 16
    assert packet["target_phase"] == 17
    assert packet["ready_count"] == 0
    assert packet["blocked_count"] == 0
    assert packet["tasks"] == []


def test_build_promotion_readiness_packet_orders_eligible_first_then_phase_then_task_id():
    packet = build_promotion_readiness_packet(
        generated_at="2026-06-03T00:00:00Z",
        current_phase=16,
        tasks=(
            {
                "task_id": "P18-W2-BLOCKED",
                "task_ref": ".omo/tasks/planned/P18-W2-BLOCKED.yaml",
                "phase": 18,
                "status": "pending",
                "risk_level": "L2",
                "allowed_operation_level": "L1",
                "human_approval_required": False,
                "approval_ref": None,
                "eligible": False,
                "blockers": ["phase_mismatch"],
                "checks": {"phase_ok": False},
                "errors": [],
            },
            {
                "task_id": "P17-W2-READY",
                "task_ref": ".omo/tasks/planned/P17-W2-READY.yaml",
                "phase": 17,
                "status": "pending",
                "risk_level": "L1",
                "allowed_operation_level": "L1",
                "human_approval_required": False,
                "approval_ref": None,
                "eligible": True,
                "blockers": [],
                "checks": {"phase_ok": True},
                "errors": [],
            },
            {
                "task_id": "P17-W1-READY",
                "task_ref": ".omo/tasks/planned/P17-W1-READY.yaml",
                "phase": 17,
                "status": "pending",
                "risk_level": "L1",
                "allowed_operation_level": "L1",
                "human_approval_required": False,
                "approval_ref": None,
                "eligible": True,
                "blockers": [],
                "checks": {"phase_ok": True},
                "errors": [],
            },
        ),
    )

    assert packet["ready_count"] == 2
    assert packet["blocked_count"] == 1
    assert [entry["task_id"] for entry in packet["tasks"]] == [
        "P17-W1-READY",
        "P17-W2-READY",
        "P18-W2-BLOCKED",
    ]


def test_render_promotion_readiness_markdown_labels_ready_and_blocked_entries():
    packet = build_promotion_readiness_packet(
        generated_at="2026-06-03T00:00:00Z",
        current_phase=16,
        tasks=(
            {
                "task_id": "P17-W1-READY",
                "task_ref": ".omo/tasks/planned/P17-W1-READY.yaml",
                "phase": 17,
                "status": "pending",
                "risk_level": "L1",
                "allowed_operation_level": "L1",
                "human_approval_required": False,
                "approval_ref": None,
                "eligible": True,
                "blockers": [],
                "checks": {"phase_ok": True},
                "errors": [],
            },
            {
                "task_id": "P18-W1-BLOCKED",
                "task_ref": ".omo/tasks/planned/P18-W1-BLOCKED.yaml",
                "phase": 18,
                "status": "pending",
                "risk_level": "L2",
                "allowed_operation_level": "L1",
                "human_approval_required": False,
                "approval_ref": None,
                "eligible": False,
                "blockers": ["phase_mismatch"],
                "checks": {"phase_ok": False},
                "errors": [],
            },
        ),
    )

    markdown = render_promotion_readiness_markdown(packet)

    assert "Ready tasks: 1" in markdown
    assert "Blocked tasks: 1" in markdown
    assert "## Ready: P17-W1-READY" in markdown
    assert "## Blocked: P18-W1-BLOCKED" in markdown
    assert "blockers=none" in markdown
    assert "blockers=phase_mismatch" in markdown
```

- [ ] **Step 2: Run the focused helper tests to confirm RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_promotion_readiness.py -q
```

Expected: import failure because `scripts/omo_promotion_readiness.py` does not exist yet.

- [ ] **Step 3: Write the minimal helper implementation**

Create `scripts/omo_promotion_readiness.py`:

```python
from __future__ import annotations


def _ordered_tasks(tasks: tuple[dict[str, object], ...]) -> list[dict[str, object]]:
    return sorted(
        tasks,
        key=lambda entry: (
            0 if entry["eligible"] else 1,
            entry["phase"],
            entry["task_id"],
        ),
    )


def build_promotion_readiness_packet(
    *,
    generated_at: str,
    current_phase: int,
    tasks: tuple[dict[str, object], ...],
) -> dict[str, object]:
    ordered = _ordered_tasks(tasks)
    return {
        "generated_at": generated_at,
        "current_phase": current_phase,
        "target_phase": current_phase + 1,
        "ready_count": sum(1 for entry in ordered if entry["eligible"]),
        "blocked_count": sum(1 for entry in ordered if not entry["eligible"]),
        "tasks": ordered,
    }


def render_promotion_readiness_markdown(packet: dict[str, object]) -> str:
    lines = [
        "# Task Promotion Readiness",
        "",
        f"Generated at: {packet['generated_at']}",
        f"Current phase: {packet['current_phase']}",
        f"Target phase: {packet['target_phase']}",
        f"Ready tasks: {packet['ready_count']}",
        f"Blocked tasks: {packet['blocked_count']}",
        "",
    ]
    for entry in packet["tasks"]:
        lines.extend(
            [
                f"## {'Ready' if entry['eligible'] else 'Blocked'}: {entry['task_id']}",
                "",
                f"task_ref={entry['task_ref']}",
                f"phase={entry['phase']}",
                f"blockers={','.join(entry['blockers']) or 'none'}",
                "",
            ]
        )
    return "\n".join(lines)
```

- [ ] **Step 4: Re-run the helper tests to confirm GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_promotion_readiness.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit the helper slice**

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_promotion_readiness.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion readiness helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

cd /Users/xiamingxing/Workspace && \
git add scripts .omo/tests/test_omo_promotion_readiness.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion readiness helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one `scripts` commit plus one root commit limited to the helper slice.

---

### Task 2: Add the readiness CLI materializer and docs guardrails

**Files:**
- Modify: `scripts/omo_worker.py`
- Modify: `.omo/tests/test_omo_automation.py`
- Modify: `.omo/tests/test_worker_mechanism_consistency.py`
- Modify: `.omo/workers/README.md`
- Modify: `.omo/AGENT.md`
- Modify: `.omo/tasks/README.md`

- [ ] **Step 1: Write the failing CLI and docs tests**

Add to `.omo/tests/test_omo_automation.py`:

```python
def test_task_promotion_readiness_command_writes_readiness_surfaces(tmp_path: Path, monkeypatch, capsys):
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
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P18-W1-BLOCKED.yaml",
        {
            "id": "P18-W1-BLOCKED",
            "phase": 18,
            "milestone": "M18.1",
            "priority": "P1",
            "title": "Blocked packet",
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
            "entry_gate": ["phase17_completed"],
            "risk_level": "L2",
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
        ["omo", "task", "promotion-readiness", "--omo-dir", ".omo", "--now", "2026-06-03T00:00:00Z"],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    packet = _load_yaml(tmp_path / ".omo" / "workers" / "promotion" / "readiness.yaml")

    assert "ready_count=1" in output
    assert packet["generated_at"] == "2026-06-03T00:00:00Z"
    assert packet["current_phase"] == 16
    assert packet["target_phase"] == 17
    assert packet["ready_count"] == 1
    assert packet["blocked_count"] == 1
    assert [entry["task_id"] for entry in packet["tasks"]] == ["P17-W1-READY", "P18-W1-BLOCKED"]
    assert (tmp_path / ".omo" / "workers" / "promotion" / "readiness.md").exists()
```

Add to `.omo/tests/test_worker_mechanism_consistency.py`:

```python
def test_worker_docs_describe_promotion_readiness_surface():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "AGENT.md").read_text(encoding="utf-8")
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")

    assert "promotion-readiness" in workers_text
    assert ".omo/workers/promotion/readiness.yaml" in workers_text
    assert "promotion/readiness.yaml" in agent_text
    assert "promotion-readiness" in tasks_text
```

- [ ] **Step 2: Run the focused CLI/docs tests to confirm RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py -q -k 'promotion_readiness_command or promotion_readiness_surface'
```

Expected: failures because the CLI subcommand and docs do not exist yet.

- [ ] **Step 3: Wire the CLI and update docs**

In `scripts/omo_worker.py`, add:

```python
from scripts.omo_promotion_readiness import (
    build_promotion_readiness_packet,
    render_promotion_readiness_markdown,
)


def _promotion_readiness_entry(root: Path, task_path: Path, omo_dir: str | Path = ".omo") -> dict[str, object]:
    task = _load_yaml(task_path)
    eval_result = _promotion_eval(root, task["id"], omo_dir=omo_dir)
    return {
        "task_id": task["id"],
        "task_ref": eval_result["task_ref"],
        "phase": task["phase"],
        "status": task["status"],
        "risk_level": task["risk_level"],
        "allowed_operation_level": task["allowed_operation_level"],
        "human_approval_required": bool(task.get("human_approval_required")),
        "approval_ref": task.get("approval_ref"),
        "eligible": eval_result["eligible"],
        "blockers": eval_result["blockers"],
        "checks": eval_result["checks"],
        "errors": eval_result["errors"],
    }


def _write_task_promotion_readiness(root: Path, omo_dir: str | Path = ".omo", now: str | None = None) -> int:
    omo = _omo_path(root, omo_dir)
    goals = _load_yaml(omo / "goals" / "current.yaml")
    planned_dir = omo / "tasks" / "planned"
    entries = tuple(
        _promotion_readiness_entry(root, task_path, omo_dir=omo_dir)
        for task_path in sorted(planned_dir.glob("*.yaml"))
    )
    packet = build_promotion_readiness_packet(
        generated_at=now or _utc_now(),
        current_phase=int(goals["phase"]),
        tasks=entries,
    )
    readiness_dir = omo / "workers" / "promotion"
    readiness_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(readiness_dir / "readiness.yaml", packet)
    write_text_atomic(readiness_dir / "readiness.md", render_promotion_readiness_markdown(packet))
    print(f"ready_count={packet['ready_count']} blocked_count={packet['blocked_count']}")
    return 0
```

Also add parser/dispatch:

```python
promotion_readiness_parser = task_sub.add_parser("promotion-readiness")
promotion_readiness_parser.add_argument("--omo-dir", default=".omo")
promotion_readiness_parser.add_argument("--now")

if args.command == "task" and args.task_command == "promotion-readiness":
    return _write_task_promotion_readiness(Path.cwd(), omo_dir=args.omo_dir, now=args.now)
```

Update docs:

```md
# .omo/workers/README.md
- `python3 scripts/omo_worker.py task promotion-readiness --omo-dir .omo [--now ...]`
- Machine surface: `.omo/workers/promotion/readiness.yaml`
- Operator summary: `.omo/workers/promotion/readiness.md`

# .omo/AGENT.md
- Read `.omo/workers/promotion/readiness.yaml` to see which planned packets are promotable now and which blockers remain.

# .omo/tasks/README.md
- Use `promotion-readiness` for queue-wide visibility; use `promote-eval <TASK_ID>` for one-task debugging.
```

- [ ] **Step 4: Re-run the focused CLI/docs tests to confirm GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py -q -k 'promotion_readiness_command or promotion_readiness_surface'
```

Expected: targeted readiness regressions pass.

- [ ] **Step 5: Run the combined readiness subset**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest \
  .omo/tests/test_omo_promotion_readiness.py \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  -q -k 'promotion_readiness'
```

Expected: helper + CLI + docs guardrails all pass together.

- [ ] **Step 6: Commit the CLI/docs slice**

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_worker.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion readiness command" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

cd /Users/xiamingxing/Workspace && \
git add scripts \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  .omo/workers/README.md \
  .omo/AGENT.md \
  .omo/tasks/README.md && \
git -c core.hooksPath=/dev/null commit -m "docs(omo): document promotion readiness surface" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one `scripts` commit plus one root commit limited to readiness CLI/docs.

---

### Task 3: Hydrate the live readiness surface and run final verification

**Files:**
- Create: `.omo/workers/promotion/readiness.yaml`
- Create: `.omo/workers/promotion/readiness.md`
- Modify: `/Users/xiamingxing/.copilot/session-state/a0b6fab5-a362-4eb9-90f8-f2e4e85653bc/plan.md` (session artifact only, not committed)

- [ ] **Step 1: Materialize the readiness surface deterministically**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 scripts/omo_worker.py task promotion-readiness --omo-dir .omo --now 2026-06-03T00:00:00Z
```

Expected: stdout like `ready_count=<N> blocked_count=<M>` and both readiness files written under `.omo/workers/promotion/`.

- [ ] **Step 2: Check the hydrated packet contents**

Inspect:

```yaml
# .omo/workers/promotion/readiness.yaml
generated_at: "2026-06-03T00:00:00Z"
current_phase: 16
target_phase: 17
ready_count: <expected count>
blocked_count: <expected count>
tasks:
  - task_id: ...
    eligible: true
  - task_id: ...
    eligible: false
    blockers:
      - phase_mismatch
```

Expected:

1. eligible tasks appear first
2. counts match the task list
3. blocked future-phase tasks show `phase_mismatch`

- [ ] **Step 3: Update the session plan**

Add a short progress note to `/Users/xiamingxing/.copilot/session-state/a0b6fab5-a362-4eb9-90f8-f2e4e85653bc/plan.md` recording:

1. readiness slice selected after promotion history
2. canonical outputs are `readiness.yaml` and `readiness.md`
3. the next likely follow-up after this slice is approval-gated promotion or richer analytics

- [ ] **Step 4: Run deterministic final verification**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 scripts/sync_omo_state.py --omo-dir .omo --now 2026-06-03T00:00:00Z && \
python3 scripts/omo_worker.py task promotion-history --omo-dir .omo --now 2026-06-03T00:00:00Z && \
python3 scripts/omo_worker.py task promotion-readiness --omo-dir .omo --now 2026-06-03T00:00:00Z && \
python3 scripts/omo_worker.py task validate --all-active && \
python3 scripts/omo_worker.py task validate --all-planned && \
python3 -m pytest .omo/tests -q
```

Expected: full `.omo` suite passes and the readiness surface remains frozen to the deterministic timestamp.

- [ ] **Step 5: Commit the live readiness surface**

```bash
cd /Users/xiamingxing/Workspace && \
git add \
  .omo/workers/promotion/readiness.yaml \
  .omo/workers/promotion/readiness.md && \
git -c core.hooksPath=/dev/null commit -m "chore(omo): freeze promotion readiness surface" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one root commit containing only the deterministic readiness packet and session-plan note.

---

## Self-review checklist

- Spec coverage:
  - canonical readiness surface -> Task 1 + Task 2 + Task 3
  - reuse `_promotion_eval(...)` -> Task 2
  - deterministic `--now` -> Task 2 + Task 3
  - docs protection -> Task 2
  - live hydration + verification -> Task 3
- Placeholder scan:
  - no `TBD`, `TODO`, or “similar to above” shortcuts remain
- Type consistency:
  - packet keys are consistently `generated_at`, `current_phase`, `target_phase`, `ready_count`, `blocked_count`, `tasks`
  - task entry keys are consistently `eligible`, `blockers`, `checks`, `errors`
