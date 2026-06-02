# OMO Governance Overlay Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a separate governance overlay lane inside `.omo` that manages future roadmap, milestone ordering, and autopilot policy without changing the existing numbered phase lane.

**Architecture:** Keep the current phase / goals / task SSOT intact and add a parallel governance overlay shell that references existing task and debt truth by pointer. A pure helper in `scripts/omo_governance_overlay.py` will read overlay control/truth files and generate a canonical status surface, while `scripts/omo_worker.py` will expose a thin `task governance-overlay-status` command that writes `.omo/workers/governance-overlay/current.*`.

**Tech Stack:** Python 3, `pathlib`, `yaml`, existing `.omo` control/truth/task/debt surfaces, existing `scripts/omo_worker.py`, pytest under `.omo/tests`

---

## File map

- **Create:** `scripts/omo_governance_overlay.py`
  - Pure helper for loading governance overlay state/roadmap/policy, validating pointer refs, resolving dependency readiness, and rendering YAML/Markdown status packets.
- **Modify:** `scripts/omo_worker.py`
  - Add `task governance-overlay-status --omo-dir .omo [--now <ISO8601>]`.
- **Create:** `.omo/tests/test_omo_governance_overlay.py`
  - Unit tests for status packet building, dependency blocking, invalid refs, and next-action derivation.
- **Modify:** `.omo/tests/test_omo_automation.py`
  - CLI regression for `governance-overlay-status`.
- **Modify:** `.omo/tests/test_worker_mechanism_consistency.py`
  - Docs regression for the governance overlay lane.
- **Create:** `.omo/_control/governance-overlay/current.yaml`
  - Control-plane state for the separate overlay program.
- **Create:** `.omo/_truth/governance-overlay/roadmap.yaml`
  - Ordered roadmap registry that references existing task/debt truth.
- **Create:** `.omo/_truth/governance-overlay/autopilot-policy.yaml`
  - Explicit autonomy policy for the overlay lane.
- **Modify:** `.omo/workers/README.md`
- **Modify:** `.omo/AGENT.md`
- **Modify:** `.omo/tasks/README.md`
  - Document how the overlay lane relates to task truth and promotion.
- **Create:** `.omo/workers/governance-overlay/current.yaml`
- **Create:** `.omo/workers/governance-overlay/current.md`
  - Generated operator-facing status surface.

## Constraints and invariants

1. Do **not** change `current_phase` or overwrite `.omo/goals/current.yaml`.
2. Do **not** introduce a second task SSOT; roadmap items must reference existing task/debt truth by pointer.
3. The shell stays read-only: it recommends next actions but does not execute promotion / dispatch yet.
4. Because `scripts/` is a nested repo, commits must happen in two layers:
   1. commit `/Users/xiamingxing/Workspace/scripts`
   2. then commit the root repo to capture the updated `scripts` gitlink plus `.omo/*` files

---

### Task 1: Build the governance overlay helper with TDD

**Files:**
- Create: `.omo/tests/test_omo_governance_overlay.py`
- Create: `scripts/omo_governance_overlay.py`

- [ ] **Step 1: Write the failing helper tests**

Create `.omo/tests/test_omo_governance_overlay.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.omo_governance_overlay import build_governance_overlay_status


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_build_governance_overlay_status_reports_candidate_and_blocked_items(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M1",
            "next_milestone": "GOV-M2",
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T06:30:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {
            "autopilot_mode": "full_omo_autopilot",
            "auto_select": True,
            "auto_promote_when_safe": True,
            "human_gate_on_high_risk": True,
            "retry_on_blocked": "explicit",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M1-ROADMAP-E2E",
                    "type": "task-bundle",
                    "title": "E2E and pricing debt closure",
                    "priority": "P0",
                    "status": "pending",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [
                        ".omo/tasks/planned/D2-CI-E2E-TEST-ENV.yaml",
                        ".omo/tasks/planned/D3-EU-PRICING-TEST.yaml",
                    ],
                    "success_criteria": ["D2 and D3 promoted and closed"],
                },
                {
                    "id": "GOV-M2-BRIDGE",
                    "type": "debt-bundle",
                    "title": "SharedBrain bridge recovery",
                    "priority": "P1",
                    "status": "pending",
                    "depends_on": ["GOV-M1-ROADMAP-E2E"],
                    "source_refs": [".omo/debt/registry.yaml"],
                    "target_refs": [".omo/debt/dashboard/current.yaml"],
                    "success_criteria": ["bridge debt no longer blocks roadmap"],
                },
            ]
        },
    )
    _write_yaml(tmp_path / ".omo" / "tasks" / "planned" / "D2-CI-E2E-TEST-ENV.yaml", {"id": "D2-CI-E2E-TEST-ENV"})
    _write_yaml(tmp_path / ".omo" / "tasks" / "planned" / "D3-EU-PRICING-TEST.yaml", {"id": "D3-EU-PRICING-TEST"})
    _write_yaml(tmp_path / ".omo" / "debt" / "dashboard" / "current.yaml", {"items": []})

    result = build_governance_overlay_status(tmp_path, omo_dir=".omo", now="2026-06-03T06:35:00Z")

    assert result["yaml"]["eligible_count"] == 1
    assert result["yaml"]["blocked_count"] == 1
    assert result["yaml"]["autopilot_candidates"][0]["id"] == "GOV-M1-ROADMAP-E2E"
    assert result["yaml"]["blocked_items"][0]["id"] == "GOV-M2-BRIDGE"
    assert result["yaml"]["next_action"] == "advance:GOV-M1-ROADMAP-E2E"


def test_build_governance_overlay_status_marks_missing_target_refs_invalid(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M1",
            "next_milestone": None,
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T06:30:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {
            "autopilot_mode": "full_omo_autopilot",
            "auto_select": True,
            "auto_promote_when_safe": True,
            "human_gate_on_high_risk": True,
            "retry_on_blocked": "explicit",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M1-MISSING",
                    "type": "task-bundle",
                    "title": "Missing target ref bundle",
                    "priority": "P0",
                    "status": "pending",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/DOES-NOT-EXIST.yaml"],
                    "success_criteria": ["missing ref repaired"],
                }
            ]
        },
    )

    result = build_governance_overlay_status(tmp_path, omo_dir=".omo", now="2026-06-03T06:35:00Z")

    assert result["yaml"]["eligible_count"] == 0
    assert result["yaml"]["blocked_count"] == 1
    assert result["yaml"]["blocked_items"][0]["reason"] == "missing_target_refs"
    assert result["yaml"]["next_action"] == "repair_refs"


def test_build_governance_overlay_status_requires_overlay_inputs(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="governance-overlay/current.yaml"):
        build_governance_overlay_status(tmp_path, omo_dir=".omo", now="2026-06-03T06:35:00Z")
```

- [ ] **Step 2: Run helper tests to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_governance_overlay.py -q
```

Expected: import failure because `scripts/omo_governance_overlay.py` does not exist yet.

- [ ] **Step 3: Write the minimal helper implementation**

Create `scripts/omo_governance_overlay.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml


def _load_yaml_required(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path.as_posix())
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _item_sort_key(item: dict[str, object]) -> tuple[int, str]:
    return (0 if item["priority"] == "P0" else 1, str(item["id"]))


def _missing_target_refs(root: Path, omo_ref: Path, refs: list[str]) -> list[str]:
    missing = []
    for ref in refs:
        if not (root / ref).exists():
            missing.append(ref)
    return missing


def build_governance_overlay_status(root: Path, *, omo_dir: str | Path = ".omo", now: str) -> dict[str, object]:
    omo_ref = Path(omo_dir)
    state = _load_yaml_required(root / omo_ref / "_control" / "governance-overlay" / "current.yaml")
    roadmap = _load_yaml_required(root / omo_ref / "_truth" / "governance-overlay" / "roadmap.yaml")
    policy = _load_yaml_required(root / omo_ref / "_truth" / "governance-overlay" / "autopilot-policy.yaml")

    completed_or_eligible: set[str] = set()
    autopilot_candidates: list[dict[str, object]] = []
    blocked_items: list[dict[str, object]] = []

    for item in sorted(roadmap.get("items", []), key=_item_sort_key):
        missing_refs = _missing_target_refs(root, omo_ref, list(item.get("target_refs", [])))
        unmet_deps = [dep for dep in item.get("depends_on", []) if dep not in completed_or_eligible]
        if missing_refs:
            blocked_items.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "reason": "missing_target_refs",
                    "missing_target_refs": missing_refs,
                }
            )
            continue
        if unmet_deps:
            blocked_items.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "reason": "unmet_dependencies",
                    "depends_on": unmet_deps,
                }
            )
            continue
        autopilot_candidates.append(
            {
                "id": item["id"],
                "title": item["title"],
                "type": item["type"],
                "priority": item["priority"],
                "target_refs": item.get("target_refs", []),
            }
        )
        completed_or_eligible.add(item["id"])

    next_action = "idle"
    if autopilot_candidates:
        next_action = f"advance:{autopilot_candidates[0]['id']}"
    elif any(item["reason"] == "missing_target_refs" for item in blocked_items):
        next_action = "repair_refs"

    yaml_packet = {
        "overlay_id": state["overlay_id"],
        "generated_at": now,
        "status": state["status"],
        "autopilot_mode": state["autopilot_mode"],
        "intake_scope": state["intake_scope"],
        "current_milestone": state["current_milestone"],
        "next_milestone": state["next_milestone"],
        "success_target": state["success_target"],
        "eligible_count": len(autopilot_candidates),
        "blocked_count": len(blocked_items),
        "autopilot_candidates": autopilot_candidates,
        "blocked_items": blocked_items,
        "next_action": next_action,
        "policy": policy,
    }
    markdown_lines = [
        "# Governance Overlay Status",
        "",
        f"Overlay: {yaml_packet['overlay_id']}",
        f"Generated at: {now}",
        f"Current milestone: {yaml_packet['current_milestone']}",
        f"Next milestone: {yaml_packet['next_milestone'] or 'none'}",
        f"Eligible items: {yaml_packet['eligible_count']}",
        f"Blocked items: {yaml_packet['blocked_count']}",
        f"Next action: {yaml_packet['next_action']}",
    ]
    for item in autopilot_candidates:
        markdown_lines.extend(
            [
                "",
                f"## Candidate: {item['id']}",
                "",
                f"title={item['title']}",
                f"priority={item['priority']}",
                f"type={item['type']}",
            ]
        )
    for item in blocked_items:
        markdown_lines.extend(
            [
                "",
                f"## Blocked: {item['id']}",
                "",
                f"title={item['title']}",
                f"reason={item['reason']}",
            ]
        )
    return {"yaml": yaml_packet, "markdown": "\n".join(markdown_lines) + "\n"}
```

- [ ] **Step 4: Run helper tests to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_governance_overlay.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit the nested `scripts` repo helper**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_governance_overlay.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add governance overlay helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: new `scripts` commit created.

---

### Task 2: Wire the CLI, docs, and seed overlay files

**Files:**
- Modify: `scripts/omo_worker.py`
- Modify: `.omo/tests/test_omo_automation.py`
- Modify: `.omo/tests/test_worker_mechanism_consistency.py`
- Create: `.omo/_control/governance-overlay/current.yaml`
- Create: `.omo/_truth/governance-overlay/roadmap.yaml`
- Create: `.omo/_truth/governance-overlay/autopilot-policy.yaml`
- Modify: `.omo/workers/README.md`
- Modify: `.omo/AGENT.md`
- Modify: `.omo/tasks/README.md`
- Create: `.omo/workers/governance-overlay/current.yaml`
- Create: `.omo/workers/governance-overlay/current.md`

- [ ] **Step 1: Write the failing CLI/docs regressions**

Add to `.omo/tests/test_omo_automation.py`:

```python
def test_task_governance_overlay_status_writes_current_surfaces(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M1",
            "next_milestone": "GOV-M2",
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T06:30:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {
            "autopilot_mode": "full_omo_autopilot",
            "auto_select": True,
            "auto_promote_when_safe": True,
            "human_gate_on_high_risk": True,
            "retry_on_blocked": "explicit",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M1-ROADMAP-E2E",
                    "type": "task-bundle",
                    "title": "E2E and pricing debt closure",
                    "priority": "P0",
                    "status": "pending",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/D2-CI-E2E-TEST-ENV.yaml"],
                    "success_criteria": ["D2 promoted and closed"],
                }
            ]
        },
    )
    _write_yaml(tmp_path / ".omo" / "tasks" / "planned" / "D2-CI-E2E-TEST-ENV.yaml", {"id": "D2-CI-E2E-TEST-ENV"})

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "governance-overlay-status", "--omo-dir", ".omo", "--now", "2026-06-03T06:35:00Z"],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    packet = _load_yaml(tmp_path / ".omo" / "workers" / "governance-overlay" / "current.yaml")

    assert "eligible_count=1" in output
    assert packet["next_action"] == "advance:GOV-M1-ROADMAP-E2E"
    assert (tmp_path / ".omo" / "workers" / "governance-overlay" / "current.md").exists()
```

Add to `.omo/tests/test_worker_mechanism_consistency.py`:

```python
def test_worker_docs_describe_governance_overlay_surface():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "AGENT.md").read_text(encoding="utf-8")
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")

    assert "governance-overlay-status" in workers_text
    assert "workers/governance-overlay/current.yaml" in workers_text
    assert "governance overlay" in agent_text.lower()
    assert "governance overlay" in tasks_text.lower()
```

- [ ] **Step 2: Run the new regressions to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py -q -k 'governance_overlay'
```

Expected:

1. argparse rejects `governance-overlay-status`
2. docs assertions fail because the overlay lane is not documented yet

- [ ] **Step 3: Add the thin CLI wiring**

Modify `scripts/omo_worker.py`:

```python
from scripts.omo_governance_overlay import build_governance_overlay_status
```

```python
def _write_task_governance_overlay_status(root: Path, omo_dir: str | Path = ".omo", now: str | None = None) -> int:
    result = build_governance_overlay_status(root, omo_dir=omo_dir, now=now or _utc_now())
    omo = _omo_path(root, omo_dir)
    output_dir = omo / "workers" / "governance-overlay"
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(output_dir / "current.yaml", result["yaml"])
    write_text_atomic(output_dir / "current.md", result["markdown"])
    print(
        "eligible_count="
        f"{result['yaml']['eligible_count']} "
        f"blocked_count={result['yaml']['blocked_count']} "
        f"next_action={result['yaml']['next_action']}"
    )
    return 0
```

```python
governance_overlay_status_parser = task_sub.add_parser("governance-overlay-status")
governance_overlay_status_parser.add_argument("--omo-dir", default=".omo")
governance_overlay_status_parser.add_argument("--now")
```

```python
if args.command == "task" and args.task_command == "governance-overlay-status":
    return _write_task_governance_overlay_status(Path.cwd(), omo_dir=args.omo_dir, now=args.now)
```

- [ ] **Step 4: Seed the overlay shell files**

Create `.omo/_control/governance-overlay/current.yaml`:

```yaml
overlay_id: GOV-OVERLAY-2026-06
status: active
autopilot_mode: full_omo_autopilot
intake_scope: future_planned_debt
current_milestone: GOV-M1-EXECUTION-HARDENING
next_milestone: GOV-M2-SHAREDBRAIN-DEBT
success_target: future roadmap, planned queue, and debt watchlist are governed through the overlay lane
updated_at: "2026-06-03T06:35:00Z"
```

Create `.omo/_truth/governance-overlay/autopilot-policy.yaml`:

```yaml
autopilot_mode: full_omo_autopilot
auto_select: true
auto_promote_when_safe: true
auto_dispatch_when_safe: true
auto_verify_when_safe: true
human_gate_on_high_risk: true
retry_on_blocked: explicit
blocked_requeue_policy: write-blocked-and-continue
success_condition: continue iterating milestone-by-milestone until all overlay roadmap items are closed or explicitly human-blocked
```

Create `.omo/_truth/governance-overlay/roadmap.yaml`:

```yaml
items:
  - id: GOV-M1-EXECUTION-HARDENING
    type: task-bundle
    title: "Execution hardening and E2E debt closure"
    priority: P0
    status: pending
    depends_on: []
    source_refs:
      - .omo/MASTER-BLUEPRINT.md
      - .omo/tasks/registry/INDEX.md
    target_refs:
      - .omo/tasks/planned/D2-CI-E2E-TEST-ENV.yaml
      - .omo/tasks/planned/D3-EU-PRICING-TEST.yaml
      - .omo/tasks/planned/P25-W1-E2E-INTEGRATION.yaml
      - .omo/tasks/planned/P25-W2-DOCS-DEBT-CLOSURE.yaml
    success_criteria:
      - "execution-hardening tasks promoted, executed, and closed"
  - id: GOV-M2-SHAREDBRAIN-DEBT
    type: debt-bundle
    title: "SharedBrain debt convergence"
    priority: P1
    status: pending
    depends_on:
      - GOV-M1-EXECUTION-HARDENING
    source_refs:
      - .omo/debt/registry.yaml
      - .omo/debt/dashboard/current.yaml
    target_refs:
      - .omo/debt/registry.yaml
      - .omo/debt/dashboard/current.yaml
    success_criteria:
      - "SharedBrain bridge, tests, orphaned semantics, and registry debt are no longer roadmap blockers"
  - id: GOV-M3-FUTURE-PROMOTION-OPERATIONS
    type: phase-bridge
    title: "Promotion-driven future phase operations"
    priority: P1
    status: pending
    depends_on:
      - GOV-M2-SHAREDBRAIN-DEBT
    source_refs:
      - .omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml
      - .omo/tasks/planned/P24-W2-NUCLEUS-REPLACE.yaml
    target_refs:
      - .omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml
      - .omo/tasks/planned/P24-W2-NUCLEUS-REPLACE.yaml
    success_criteria:
      - "future high-value planned packets are governed through promotion / approval / execution under the overlay lane"
```

- [ ] **Step 5: Document the governance overlay lane**

Update `.omo/workers/README.md`:

```md
Canonical governance overlay surface:

1. `python3 scripts/omo_worker.py task governance-overlay-status --omo-dir .omo [--now <ISO8601>]`
2. this reads `.omo/_control/governance-overlay/current.yaml`
3. this reads `.omo/_truth/governance-overlay/roadmap.yaml`
4. this reads `.omo/_truth/governance-overlay/autopilot-policy.yaml`
5. this writes `.omo/workers/governance-overlay/current.yaml`
6. and `.omo/workers/governance-overlay/current.md`
```

Update `.omo/AGENT.md`:

```md
> **Governance overlay**：如需查看未来 roadmap / milestone / debt / planned queue 的统一治理入口，不要改 `current_phase`；运行 `python3 scripts/omo_worker.py task governance-overlay-status --omo-dir .omo [--now <ISO8601>]`，并以 `.omo/workers/governance-overlay/current.yaml` 作为 canonical read surface。
```

Update `.omo/tasks/README.md`:

```md
- governance overlay 是 control-plane 的未来 roadmap 治理层；它引用现有 task/debt truth，不创建第二套 task SSOT。
```

- [ ] **Step 6: Run the CLI/docs regressions to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py -q -k 'governance_overlay'
```

Expected: `2 passed`.

- [ ] **Step 7: Hydrate the live governance overlay surface**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 scripts/omo_worker.py task governance-overlay-status --omo-dir .omo --now 2026-06-03T06:35:00Z
```

Expected:

1. `.omo/workers/governance-overlay/current.yaml` exists
2. `.omo/workers/governance-overlay/current.md` exists
3. `next_action` points to the top eligible roadmap item

---

### Task 3: Run focused verification and commit both repos

**Files:**
- Verify: `.omo/tests/test_omo_governance_overlay.py`
- Verify: `.omo/tests/test_omo_automation.py`
- Verify: `.omo/tests/test_worker_mechanism_consistency.py`
- Verify: `.omo/workers/governance-overlay/current.yaml`
- Verify: `.omo/workers/governance-overlay/current.md`
- Commit: `scripts/`
- Commit: root repo

- [ ] **Step 1: Run the governance overlay subset**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest \
  .omo/tests/test_omo_governance_overlay.py \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  -q -k 'governance_overlay'
```

Expected: the new governance overlay helper + CLI/docs regressions all pass together.

- [ ] **Step 2: Commit the nested `scripts` repo CLI wiring**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_worker.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add governance overlay shell" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: the `scripts` repo now contains the helper + CLI wiring.

- [ ] **Step 3: Commit the root repo files**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
git add \
  scripts \
  .omo/tests/test_omo_governance_overlay.py \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  .omo/_control/governance-overlay/current.yaml \
  .omo/_truth/governance-overlay/roadmap.yaml \
  .omo/_truth/governance-overlay/autopilot-policy.yaml \
  .omo/workers/README.md \
  .omo/AGENT.md \
  .omo/tasks/README.md \
  .omo/workers/governance-overlay/current.yaml \
  .omo/workers/governance-overlay/current.md && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add governance overlay shell" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: root repo captures the `scripts` gitlink update plus overlay shell files/docs/tests.

- [ ] **Step 4: Record the milestone in the session plan**

Update `/Users/xiamingxing/.copilot/session-state/a0b6fab5-a362-4eb9-90f8-f2e4e85653bc/plan.md` with:

```md
## 2026-06-03 governance overlay shell landed

- spec committed: `docs/superpowers/specs/2026-06-03-omo-governance-overlay-shell-design.md`
- plan committed: `docs/superpowers/plans/2026-06-03-omo-governance-overlay-shell.md`
- overlay shell files now exist:
  1. `.omo/_control/governance-overlay/current.yaml`
  2. `.omo/_truth/governance-overlay/roadmap.yaml`
  3. `.omo/_truth/governance-overlay/autopilot-policy.yaml`
  4. `.omo/workers/governance-overlay/current.yaml`
- next follow-up after this shell:
  1. governance autopilot execution loop
  2. governance trend / burndown analytics
```

Do not commit the session plan file.

---

## Self-review checklist

Before handing this plan off, verify:

1. the numbered phase lane remains untouched
2. the overlay references task/debt truth by pointer rather than copying task payloads
3. the helper stays read-only and only emits a status surface
4. the roadmap registry includes initial future + planned + debt intake
5. nested `scripts` repo commits are called out explicitly

## Execution note

Plan complete and saved to `docs/superpowers/plans/2026-06-03-omo-governance-overlay-shell.md`. In normal interactive flow this would branch to a user execution choice, but the current session is running in autonomous mode, so proceed with **Inline Execution** against this plan.
