# Phase 8 Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ratify Phase 8 and land the first runtime control path that can gate governed work using budget and freshness signals before execution.

**Architecture:** Reuse the existing `scripts/omo_experience.py` runtime rather than inventing a new control subsystem. First ratify Phase 8 by writing the planning/program/starter packet and switching live `.omo` state to `Phase 8 in_progress`, then add failing tests for the Wave 1 control gate, implement the minimal decision logic, and persist the resulting control artifacts alongside existing Phase 7 accounting/freshness truth.

**Tech Stack:** Markdown specs/plans, YAML control/task state, Python pytest, existing `.omo` automation scripts, `scripts/omo_experience.py`

---

### Task 1: Ratify the Phase 8 planning gate

**Files:**
- Create: `.omo/tests/test_phase8_planning_gate_docs.py`
- Create: `.omo/plans/phase8-planning-gate.md`
- Create: `.omo/plans/phase8-program-plan.md`
- Create: `.omo/plans/phase8-starter-packet-spec.md`
- Create: `.omo/summaries/phase8-planning-ratification.md`
- Create: `.omo/tasks/done/P8-r0-phase8-planning-gate.yaml`
- Create: `.omo/tasks/active/P8-w1-budget-freshness-control.yaml`
- Modify: `.omo/goals/current.yaml`
- Modify: `.omo/state/system.yaml`
- Modify: `.omo/_control/INDEX.md`
- Modify: `.omo/INDEX.md`
- Modify: `.omo/plans/README.md`
- Modify: `.omo/_knowledge/design/INDEX.md`
- Modify: `.omo/_knowledge/process/INDEX.md`

- [ ] **Step 1: Write the failing planning-gate regression**

Run: `python3 -m pytest .omo/tests/test_phase8_planning_gate_docs.py -q`

Expected: FAIL on missing `phase: 8` live state and missing Phase 8 packet artifacts.

- [ ] **Step 2: Write the planning gate docs and packet artifacts**

Create the three Phase 8 docs under `.omo/plans/`, write the ratification summary, add the done ratification packet and the single active starter packet, and update all live indexes/state together.

- [ ] **Step 3: Run planning-gate verification**

Run:

```bash
python3 scripts/omo_worker.py task validate --all-active
python3 scripts/sync_omo_state.py --omo-dir .omo
python3 -m pytest .omo/tests/test_phase8_planning_gate_docs.py -q
```

Expected: active queue contains exactly `P8-W1-BUDGET-FRESHNESS-CONTROL`; Phase 8 doc test passes.

### Task 2: Add Wave 1 red tests for budget/freshness control

**Files:**
- Modify: `.omo/tests/test_omo_experience.py`
- Test: `.omo/tests/test_omo_experience.py`

- [ ] **Step 1: Add a failing budget-block test**

```python
def test_evaluate_control_gate_blocks_when_budget_is_exceeded(tmp_path: Path):
    root = tmp_path
    _write_yaml(root / ".omo" / "_truth" / "task-center" / "usage-accounting.yaml", {
        "cost_by_org": [{"org": "starlink-core", "cost": 5.0, "calls": 10, "tokens": 3000}],
        "dispatches": {"total": 2, "workers": {"mockworker": 2}},
    })
    _write_yaml(root / ".omo" / "_delivery" / "task-center" / "freshness" / "current.yaml", {
        "freshness_score": 92,
        "stale_items": [],
    })

    decision = evaluate_control_gate(root, budget_limit_usd=2.5)

    assert decision["decision"] == "block"
    assert "budget_limit_exceeded" in decision["reasons"]
```

- [ ] **Step 2: Add a failing freshness-degrade test**

```python
def test_evaluate_control_gate_degrades_on_warning_freshness(tmp_path: Path):
    root = tmp_path
    _write_yaml(root / ".omo" / "_truth" / "task-center" / "usage-accounting.yaml", {
        "cost_by_org": [{"org": "starlink-core", "cost": 1.0, "calls": 2, "tokens": 512}],
        "dispatches": {"total": 1, "workers": {"mockworker": 1}},
    })
    _write_yaml(root / ".omo" / "_delivery" / "task-center" / "freshness" / "current.yaml", {
        "freshness_score": 72,
        "stale_items": ["state_update_stale"],
    })

    decision = evaluate_control_gate(root, budget_limit_usd=2.5, warning_score=80, critical_score=50)

    assert decision["decision"] == "degrade"
    assert "freshness_warning" in decision["reasons"]
```

- [ ] **Step 3: Add a failing routed-request test**

```python
def test_route_request_with_control_gate_writes_decision_and_routes_task(tmp_path: Path):
    root = tmp_path
    _write_yaml(root / ".omo" / "goals" / "current.yaml", {"phase": 8, "current_wave": 1})
    _write_yaml(root / ".omo" / "_truth" / "task-center" / "usage-accounting.yaml", {
        "cost_by_org": [{"org": "starlink-core", "cost": 0.9, "calls": 1, "tokens": 256}],
        "dispatches": {"total": 1, "workers": {"mockworker": 1}},
    })
    _write_yaml(root / ".omo" / "_delivery" / "task-center" / "freshness" / "current.yaml", {
        "freshness_score": 95,
        "stale_items": [],
    })

    result = route_request_with_control_gate(
        root,
        task_id="P8-W1-CONTROLLED-REQUEST",
        title="Control-routed request",
        request_text="Please execute a complex controlled request",
        source_docs=[".omo/plans/phase8-starter-packet-spec.md"],
        budget_limit_usd=2.5,
    )

    assert result["decision"] == "allow"
    assert (root / result["decision_ref"]).exists()
    assert (root / result["task_ref"]).exists()
```

- [ ] **Step 4: Run the targeted red tests**

Run:

```bash
python3 -m pytest .omo/tests/test_omo_experience.py -q -k "control_gate"
```

Expected: FAIL because `evaluate_control_gate` and `route_request_with_control_gate` do not exist yet.

### Task 3: Implement the minimal Wave 1 control runtime

**Files:**
- Modify: `scripts/omo_experience.py`
- Test: `.omo/tests/test_omo_experience.py`

- [ ] **Step 1: Add minimal control helpers**

Implement:

```python
def evaluate_control_gate(
    root: Path,
    budget_limit_usd: float,
    warning_score: int = 80,
    critical_score: int = 50,
) -> dict[str, object]:
    ...


def route_request_with_control_gate(
    root: Path,
    task_id: str,
    title: str,
    request_text: str,
    source_docs: list[str] | None = None,
    budget_limit_usd: float = 2.5,
    warning_score: int = 80,
    critical_score: int = 50,
    now: str | None = None,
) -> dict[str, str]:
    ...
```

Behavior:

1. read `.omo/_truth/task-center/usage-accounting.yaml`
2. read `.omo/_delivery/task-center/freshness/current.yaml`
3. decide:
   - `block` if budget is exceeded or freshness is critical
   - `degrade` if freshness is warning
   - `allow` otherwise
4. write a control decision artifact under `.omo/_delivery/task-center/control/`
5. on allow/degrade, reuse `bridge_request_to_task(...)`
6. on block, still write the decision artifact but do not create a task packet

- [ ] **Step 2: Add CLI support**

Add subcommands:

```python
control_parser = subparsers.add_parser("control")
control_parser.add_argument("--budget-limit", type=float, required=True)
control_parser.add_argument("--warning-score", type=int, default=80)
control_parser.add_argument("--critical-score", type=int, default=50)

route_parser = subparsers.add_parser("route")
route_parser.add_argument("--task-id", required=True)
route_parser.add_argument("--title", required=True)
route_parser.add_argument("--request", required=True)
route_parser.add_argument("--source-doc", action="append", default=[])
route_parser.add_argument("--budget-limit", type=float, required=True)
route_parser.add_argument("--warning-score", type=int, default=80)
route_parser.add_argument("--critical-score", type=int, default=50)
route_parser.add_argument("--now")
```

- [ ] **Step 3: Run the targeted tests to green**

Run:

```bash
python3 -m pytest .omo/tests/test_omo_experience.py -q -k "control_gate"
```

Expected: PASS

### Task 4: Verify the real Phase 8 Wave 1 starter packet

**Files:**
- Modify: `.omo/tasks/active/P8-w1-budget-freshness-control.yaml`
- Modify: `.omo/summaries/phase8-planning-ratification.md`
- Create: `.omo/_delivery/task-center/control/current.yaml`

- [ ] **Step 1: Exercise the control CLI against the real workspace**

Run:

```bash
python3 scripts/omo_experience.py accounting --now 2026-05-31T18:10:00Z
python3 scripts/omo_experience.py freshness --now 2026-05-31T18:11:00Z
python3 scripts/omo_experience.py control --budget-limit 2.5
```

Expected: a control decision artifact is written under `.omo/_delivery/task-center/control/`.

- [ ] **Step 2: Exercise routed-request behavior**

Run:

```bash
python3 scripts/omo_experience.py route \
  --task-id P8-W1-CONTROLLED-REQUEST \
  --title "Control-routed request" \
  --request "Please evaluate and route this controlled request" \
  --source-doc .omo/plans/phase8-starter-packet-spec.md \
  --budget-limit 2.5 \
  --now 2026-05-31T18:12:00Z
```

Expected: either a task packet is created (allow/degrade) or a decision artifact explains the block outcome.

- [ ] **Step 3: Run full verification**

Run:

```bash
python3 scripts/omo_worker.py task validate --all-active
python3 scripts/sync_omo_state.py --omo-dir .omo
python3 -m pytest .omo/tests/test_omo_experience.py .omo/tests/test_phase8_planning_gate_docs.py -q
python3 -m pytest .omo/tests -q
```

Expected: all tests pass and Phase 8 remains live with a single Wave 1 starter packet.
