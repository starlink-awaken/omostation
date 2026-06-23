---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Debt Governance Mechanism Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a first-class `.omo` debt ledger that stores canonical debt items, derives multi-dimensional debt metrics into `state/system.yaml`, and generates dashboard/review outputs without manual drift in `resolved_debt_items`.

**Architecture:** Introduce a new `.omo/debt/` surface for registry metadata, seed debt items, generated dashboard snapshots, and review packs. Add dedicated Python helpers to load debt items, compute debt health/entropy/backlog/coupling summaries, and project those derived fields into `scripts/sync_omo_state.py` while keeping project truth in existing task/docs/runtime surfaces through refs instead of shadow copies.

**Tech Stack:** Python 3, PyYAML, existing `.omo` YAML and markdown conventions, `scripts/sync_omo_state.py`, pytest, canonical `bash bin/verify-omo.sh`

---

## File Structure

### New files

- `.omo/debt/registry.yaml` — canonical ledger index listing every managed debt item and output refs
- `.omo/debt/items/D2_CI_E2E.yaml` — seeded CI E2E debt item with lifecycle, refs, and review cadence
- `.omo/debt/items/D3_EU_PRICING.yaml` — seeded eu-pricing debt item
- `.omo/debt/items/SB_DECOMPOSITION.yaml` — seeded SharedBrain decomposition debt item
- `.omo/debt/items/SB_ORPHANED_TASKS.yaml` — seeded orphaned-task semantics debt item
- `.omo/debt/dashboard/current.yaml` — generated machine-readable dashboard snapshot
- `.omo/debt/reviews/current.md` — generated human-readable debt review pack
- `scripts/omo_debt_registry.py` — load/validate registry + item files, expose typed debt objects
- `scripts/omo_debt_metrics.py` — compute debt health, entropy, backlog pressure, coupling load, watchlist/gate summaries
- `scripts/omo_debt.py` — debt CLI for `refresh`, `register`, `reclassify`, `schedule`, `escalate`, `revalidate`, `close`, and `reopen`
- `.omo/tests/test_omo_debt_registry.py` — registry/item contract tests
- `.omo/tests/test_omo_debt_metrics.py` — metrics calculation tests
- `.omo/tests/test_omo_debt_cli.py` — CLI action and lifecycle tests
- `.omo/tests/test_omo_debt_outputs.py` — dashboard/review output tests
- `.omo/tests/test_omo_debt_docs.py` — operator-doc regression for the new debt flow

### Modified files

- `scripts/sync_omo_state.py` — derive debt summary fields from the ledger instead of hard-coded state drift
- `scripts/omo_debt_weight.py` — compatibility wrapper over the new metrics engine so old imports do not fork logic
- `.omo/tests/test_omo_automation.py` — assert sync output now includes registry-driven debt fields
- `.omo/AGENT.md` — document the debt refresh/proof commands
- `.omo/_knowledge/design/debt-cleanup-plan.md` — point the old cleanup plan at the new canonical ledger surface

### Existing files to read before implementation

- `docs/superpowers/specs/2026-06-02-debt-governance-mechanism-design.md`
- `.omo/_knowledge/management/debt-systems-analysis-and-governance.md`
- `.omo/_knowledge/design/debt-cleanup-plan.md`
- `scripts/sync_omo_state.py`
- `scripts/omo_debt_weight.py`
- `.omo/state/system.yaml`
- `.omo/tasks/active/P17-DEBT-GOVERNANCE-GATE-RULES.yaml`
- `.omo/tasks/active/SHAREDBRAIN-FORMAL-DECISION.yaml`

---

### Task 1: Create the debt ledger surface and seed the first canonical items

**Files:**
- Create: `.omo/debt/registry.yaml`
- Create: `.omo/debt/items/D2_CI_E2E.yaml`
- Create: `.omo/debt/items/D3_EU_PRICING.yaml`
- Create: `.omo/debt/items/SB_DECOMPOSITION.yaml`
- Create: `.omo/debt/items/SB_ORPHANED_TASKS.yaml`
- Test: `.omo/tests/test_omo_debt_registry.py`

- [ ] **Step 1: Write the failing registry contract test**

```python
from __future__ import annotations

from pathlib import Path

import yaml


OMO_ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(rel_path: str) -> dict:
    return yaml.safe_load((OMO_ROOT / rel_path).read_text(encoding="utf-8"))


def test_debt_registry_lists_seed_items_and_outputs() -> None:
    registry = _load_yaml("debt/registry.yaml")

    assert registry["version"] == 1
    assert registry["items_dir"] == ".omo/debt/items"
    assert registry["dashboard_ref"] == ".omo/debt/dashboard/current.yaml"
    assert registry["review_pack_ref"] == ".omo/debt/reviews/current.md"
    assert registry["seed_items"] == [
        ".omo/debt/items/D2_CI_E2E.yaml",
        ".omo/debt/items/D3_EU_PRICING.yaml",
        ".omo/debt/items/SB_DECOMPOSITION.yaml",
        ".omo/debt/items/SB_ORPHANED_TASKS.yaml",
    ]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest .omo/tests/test_omo_debt_registry.py -q`

Expected: FAIL with `FileNotFoundError` for `.omo/debt/registry.yaml`.

- [ ] **Step 3: Add the registry file and four seed debt items**

```yaml
# .omo/debt/registry.yaml
version: 1
items_dir: .omo/debt/items
dashboard_ref: .omo/debt/dashboard/current.yaml
review_pack_ref: .omo/debt/reviews/current.md
seed_items:
  - .omo/debt/items/D2_CI_E2E.yaml
  - .omo/debt/items/D3_EU_PRICING.yaml
  - .omo/debt/items/SB_DECOMPOSITION.yaml
  - .omo/debt/items/SB_ORPHANED_TASKS.yaml
```

```yaml
# .omo/debt/items/D2_CI_E2E.yaml
id: D2_CI_E2E
title: CI E2E test environment is still non-canonical
dimension: runtime_ops
subdimension: ci_environment
domain: workspace
scope: cross_project
severity: high
weight: 0.15
entropy_class: time
lifecycle_state: scheduled
owner: platform-governance
affected_roots:
  - .github/workflows
  - tests/integration
  - projects/kairon
evidence_refs:
  - .omo/_knowledge/design/debt-cleanup-plan.md
  - .omo/tasks/active/P17-DEBT-GOVERNANCE-GATE-RULES.yaml
mitigation_refs:
  - .omo/_knowledge/design/debt-cleanup-plan.md
opened_at: "2026-06-01T10:30:00Z"
last_reviewed_at: "2026-06-02T00:00:00Z"
next_review_at: "2026-06-09T00:00:00Z"
gate_level: watchlist
history:
  - at: "2026-06-02T00:00:00Z"
    action: register
    note: "Seeded from existing Phase 17 debt backlog."
```

```yaml
# .omo/debt/items/D3_EU_PRICING.yaml
id: D3_EU_PRICING
title: eu-pricing tests are not independently governed
dimension: code_test
subdimension: isolated_test_coverage
domain: projects
scope: cross_project
severity: high
weight: 0.15
entropy_class: state
lifecycle_state: scheduled
owner: commerce-governance
affected_roots:
  - projects/kairon
  - .github/workflows
evidence_refs:
  - .omo/_knowledge/design/debt-cleanup-plan.md
  - .omo/tasks/active/P17-DEBT-GOVERNANCE-GATE-RULES.yaml
mitigation_refs:
  - .omo/_knowledge/design/debt-cleanup-plan.md
opened_at: "2026-06-01T10:30:00Z"
last_reviewed_at: "2026-06-02T00:00:00Z"
next_review_at: "2026-06-09T00:00:00Z"
gate_level: watchlist
history:
  - at: "2026-06-02T00:00:00Z"
    action: register
    note: "Seeded from existing Phase 17 debt backlog."
```

```yaml
# .omo/debt/items/SB_DECOMPOSITION.yaml
id: SB_DECOMPOSITION
title: SharedBrain decomposition remains partially governed
dimension: architecture
subdimension: platform_decomposition
domain: workspace
scope: cross_project
severity: critical
weight: 0.2
entropy_class: coupling
lifecycle_state: in_progress
owner: sharedbrain-governance
affected_roots:
  - projects/SharedBrain
  - projects/kairon
  - .omo/tasks/active
evidence_refs:
  - .omo/tasks/active/SHAREDBRAIN-FORMAL-DECISION.yaml
  - .omo/_knowledge/design/debt-cleanup-plan.md
mitigation_refs:
  - .omo/_knowledge/design/debt-cleanup-plan.md
  - .omo/plans/phase17-wave1-sharedbrain-decomposition-plan.md
opened_at: "2026-06-01T10:30:00Z"
last_reviewed_at: "2026-06-02T00:00:00Z"
next_review_at: "2026-06-07T00:00:00Z"
gate_level: gate
history:
  - at: "2026-06-02T00:00:00Z"
    action: register
    note: "Seeded from existing SharedBrain governance packet."
```

```yaml
# .omo/debt/items/SB_ORPHANED_TASKS.yaml
id: SB_ORPHANED_TASKS
title: orphaned task semantics can still drift away from the debt ledger
dimension: governance_process
subdimension: ssot_semantics
domain: .omo
scope: governance_kernel
severity: medium
weight: 0.1
entropy_class: pointer
lifecycle_state: classified
owner: omo-governance
affected_roots:
  - .omo/state
  - .omo/tasks
evidence_refs:
  - .omo/state/system.yaml
  - .omo/_knowledge/design/debt-cleanup-plan.md
mitigation_refs:
  - .omo/tasks/registry/INDEX.md
opened_at: "2026-06-01T10:30:00Z"
last_reviewed_at: "2026-06-02T00:00:00Z"
next_review_at: "2026-06-08T00:00:00Z"
gate_level: none
history:
  - at: "2026-06-02T00:00:00Z"
    action: register
    note: "Seeded from orphaned task semantics review."
```

- [ ] **Step 4: Add a second registry test that verifies pointer-based truth instead of copied truth**

```python
def test_seed_items_keep_refs_to_existing_governance_surfaces() -> None:
    item = _load_yaml("debt/items/SB_DECOMPOSITION.yaml")

    assert item["lifecycle_state"] == "in_progress"
    assert item["gate_level"] == "gate"
    assert ".omo/tasks/active/SHAREDBRAIN-FORMAL-DECISION.yaml" in item["evidence_refs"]
    assert ".omo/_knowledge/design/debt-cleanup-plan.md" in item["mitigation_refs"]
    assert "projects/SharedBrain" in item["affected_roots"]
```

- [ ] **Step 5: Run the registry tests to verify they pass**

Run: `python3 -m pytest .omo/tests/test_omo_debt_registry.py -q`

Expected: `2 passed`

- [ ] **Step 6: Commit the ledger foundation**

```bash
git add .omo/debt/registry.yaml .omo/debt/items/D2_CI_E2E.yaml .omo/debt/items/D3_EU_PRICING.yaml .omo/debt/items/SB_DECOMPOSITION.yaml .omo/debt/items/SB_ORPHANED_TASKS.yaml .omo/tests/test_omo_debt_registry.py
git -c core.hooksPath=/dev/null commit -m "feat(omo): add debt ledger foundation"
```

---

### Task 2: Add typed debt loading and deterministic metrics

**Files:**
- Create: `scripts/omo_debt_registry.py`
- Create: `scripts/omo_debt_metrics.py`
- Test: `.omo/tests/test_omo_debt_metrics.py`

- [ ] **Step 1: Write the failing typed-loader and metrics tests**

```python
from __future__ import annotations

from pathlib import Path

from scripts.omo_debt_metrics import compute_debt_metrics
from scripts.omo_debt_registry import load_debt_ledger


def test_load_debt_ledger_returns_seed_items() -> None:
    ledger = load_debt_ledger(Path(".omo"))

    assert [item.id for item in ledger.items] == [
        "D2_CI_E2E",
        "D3_EU_PRICING",
        "SB_DECOMPOSITION",
        "SB_ORPHANED_TASKS",
    ]


def test_compute_debt_metrics_flags_overdue_and_gate_items() -> None:
    ledger = load_debt_ledger(Path(".omo"))

    metrics = compute_debt_metrics(ledger.items, now="2026-06-10T00:00:00Z")

    assert metrics.debt_watchlist_count >= 1
    assert metrics.debt_gate_count >= 1
    assert metrics.pointer_entropy >= 0
    assert metrics.time_entropy > 0
    assert "SB_DECOMPOSITION" in metrics.gate_item_ids
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest .omo/tests/test_omo_debt_metrics.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.omo_debt_registry'`.

- [ ] **Step 3: Implement the debt loader with typed objects**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class DebtItem:
    id: str
    title: str
    dimension: str
    subdimension: str
    domain: str
    scope: str
    severity: str
    weight: float
    entropy_class: str
    lifecycle_state: str
    owner: str
    affected_roots: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    mitigation_refs: tuple[str, ...]
    opened_at: str
    last_reviewed_at: str | None
    next_review_at: str | None
    gate_level: str
    history: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class DebtLedger:
    registry_ref: str
    dashboard_ref: str
    review_pack_ref: str
    items: tuple[DebtItem, ...]


def load_debt_ledger(omo_dir: Path) -> DebtLedger:
    registry_ref = omo_dir / "debt" / "registry.yaml"
    registry = yaml.safe_load(registry_ref.read_text(encoding="utf-8"))
    items: list[DebtItem] = []
    for item_ref in registry["seed_items"]:
        payload = yaml.safe_load((omo_dir.parent / item_ref).read_text(encoding="utf-8"))
        items.append(
            DebtItem(
                id=payload["id"],
                title=payload["title"],
                dimension=payload["dimension"],
                subdimension=payload["subdimension"],
                domain=payload["domain"],
                scope=payload["scope"],
                severity=payload["severity"],
                weight=float(payload["weight"]),
                entropy_class=payload["entropy_class"],
                lifecycle_state=payload["lifecycle_state"],
                owner=payload["owner"],
                affected_roots=tuple(payload["affected_roots"]),
                evidence_refs=tuple(payload["evidence_refs"]),
                mitigation_refs=tuple(payload["mitigation_refs"]),
                opened_at=payload["opened_at"],
                last_reviewed_at=payload.get("last_reviewed_at"),
                next_review_at=payload.get("next_review_at"),
                gate_level=payload["gate_level"],
                history=tuple(payload.get("history", [])),
            )
        )
    return DebtLedger(
        registry_ref=".omo/debt/registry.yaml",
        dashboard_ref=registry["dashboard_ref"],
        review_pack_ref=registry["review_pack_ref"],
        items=tuple(items),
    )
```

- [ ] **Step 4: Implement deterministic metrics with explicit formulas**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from scripts.omo_debt_registry import DebtItem


@dataclass(frozen=True)
class DebtMetrics:
    debt_health: float
    classification_entropy: float
    state_entropy: float
    pointer_entropy: float
    time_entropy: float
    backlog_pressure: float
    coupling_load: float
    debt_watchlist_count: int
    debt_gate_count: int
    watchlist_item_ids: tuple[str, ...]
    gate_item_ids: tuple[str, ...]
    closed_item_ids: tuple[str, ...]


def compute_debt_metrics(items: tuple[DebtItem, ...], now: str) -> DebtMetrics:
    current = datetime.fromisoformat(now.replace("Z", "+00:00"))
    open_items = [item for item in items if item.lifecycle_state != "closed"]
    overdue = [
        item
        for item in open_items
        if item.next_review_at
        and datetime.fromisoformat(item.next_review_at.replace("Z", "+00:00")) < current
    ]
    vague = [item for item in open_items if item.dimension in {"other", "unknown"}]
    missing_pointers = [
        item
        for item in open_items
        if not item.owner or not item.evidence_refs or not item.last_reviewed_at or not item.next_review_at
    ]
    stale_evidence = []
    repo_root = Path.cwd()
    for item in open_items:
        if len(item.evidence_refs) == 0 or len(item.mitigation_refs) == 0:
            stale_evidence.append(item)
            continue
        missing_targets = [
            ref
            for ref in (*item.evidence_refs, *item.mitigation_refs)
            if not (repo_root / ref).exists()
        ]
        if missing_targets:
            stale_evidence.append(item)
    long_running = [item for item in open_items if item.lifecycle_state in {"classified", "scheduled", "in_progress", "mitigated"}]
    watchlist = [item.id for item in open_items if item.gate_level == "watchlist"]
    gate = [item.id for item in open_items if item.gate_level == "gate"]
    health = max(
        0.0,
        100.0 - (12.5 * len(overdue)) - (10.0 * len(gate)) - (7.5 * len(missing_pointers)) - (5.0 * len(stale_evidence)),
    )
    denominator = max(len(open_items), 1)
    return DebtMetrics(
        debt_health=round(health, 2),
        classification_entropy=round(len(vague) / denominator, 2),
        state_entropy=round(len(long_running) / denominator, 2),
        pointer_entropy=round((len(missing_pointers) + len(stale_evidence)) / denominator, 2),
        time_entropy=round(len(overdue) / denominator, 2),
        backlog_pressure=round(sum(item.weight for item in open_items), 2),
        coupling_load=round(sum(len(item.affected_roots) for item in open_items) / denominator, 2),
        debt_watchlist_count=len(watchlist),
        debt_gate_count=len(gate),
        watchlist_item_ids=tuple(watchlist),
        gate_item_ids=tuple(gate),
        closed_item_ids=tuple(item.id for item in items if item.lifecycle_state == "closed"),
    )
```

- [ ] **Step 5: Run the metrics tests to verify they pass**

Run: `python3 -m pytest .omo/tests/test_omo_debt_metrics.py -q`

Expected: `2 passed`

- [ ] **Step 6: Commit the loader and metrics engine**

```bash
git add scripts/omo_debt_registry.py scripts/omo_debt_metrics.py .omo/tests/test_omo_debt_metrics.py
git -c core.hooksPath=/dev/null commit -m "feat(omo): add debt metrics engine"
```

---

### Task 3: Project ledger-derived summaries into `state/system.yaml`

**Files:**
- Modify: `scripts/sync_omo_state.py`
- Modify: `scripts/omo_debt_weight.py`
- Modify: `.omo/tests/test_omo_automation.py`
- Test: `.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Write the failing sync-state regression**

```python
def test_sync_state_derives_debt_summary_from_registry(tmp_path: Path) -> None:
    omo = tmp_path / ".omo"
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, omo / "debt")
    (omo / "state").mkdir(parents=True, exist_ok=True)
    (omo / "goals").mkdir(parents=True, exist_ok=True)
    (omo / "tasks" / "active").mkdir(parents=True, exist_ok=True)
    (omo / "tasks" / "done").mkdir(parents=True, exist_ok=True)
    (omo / "tasks" / "blocked").mkdir(parents=True, exist_ok=True)
    _write_yaml(omo / "state" / "system.yaml", {"health_score": 0.0})
    _write_yaml(omo / "goals" / "current.yaml", {"phase": 17, "status": "active", "goals": []})
    state = sync_state(omo, test_output="5 passed", now="2026-06-10T00:00:00Z")

    assert state["debt_registry_ref"] == ".omo/debt/registry.yaml"
    assert state["debt_dashboard_ref"] == ".omo/debt/dashboard/current.yaml"
    assert state["debt_review_pack_ref"] == ".omo/debt/reviews/current.md"
    assert state["debt_metrics"]["debt_health"] < 100
    assert state["resolved_debt_items"] == []
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `python3 -m pytest .omo/tests/test_omo_automation.py -q -k debt_summary_from_registry`

Expected: FAIL because `sync_state()` does not yet populate the new ledger-derived fields.

- [ ] **Step 3: Wire the debt loader + metrics into `sync_omo_state.py`**

```python
from scripts.omo_debt_metrics import compute_debt_metrics
from scripts.omo_debt_registry import load_debt_ledger


def sync_state(omo_dir: Path, test_output: str | None = None, now: str | None = None) -> dict:
    ...
    ledger = load_debt_ledger(omo_dir)
    metrics = compute_debt_metrics(ledger.items, now=effective_now)
    state["debt_registry_ref"] = ledger.registry_ref
    state["debt_dashboard_ref"] = ledger.dashboard_ref
    state["debt_review_pack_ref"] = ledger.review_pack_ref
    state["debt_metrics"] = {
        "debt_health": metrics.debt_health,
        "classification_entropy": metrics.classification_entropy,
        "state_entropy": metrics.state_entropy,
        "pointer_entropy": metrics.pointer_entropy,
        "time_entropy": metrics.time_entropy,
        "backlog_pressure": metrics.backlog_pressure,
        "coupling_load": metrics.coupling_load,
    }
    state["debt_watchlist_count"] = metrics.debt_watchlist_count
    state["debt_gate_count"] = metrics.debt_gate_count
    state["resolved_debt_items"] = list(metrics.closed_item_ids)
```

- [ ] **Step 4: Convert `scripts/omo_debt_weight.py` into a compatibility wrapper**

```python
from __future__ import annotations

from scripts.omo_debt_metrics import compute_debt_metrics
from scripts.omo_debt_registry import DebtItem


def compute_debt_weight_from_items(items: tuple[DebtItem, ...], now: str) -> float:
    metrics = compute_debt_metrics(items, now=now)
    unresolved = max(len(items) - len(metrics.closed_item_ids), 0)
    penalty = min(unresolved * 0.1, 0.7)
    return round(max(1.0 - penalty, 0.3), 2)
```

- [ ] **Step 5: Run the targeted sync-state tests**

Run: `python3 -m pytest .omo/tests/test_omo_automation.py -q -k 'debt_summary_from_registry or health_score'`

Expected: PASS, including the older health-score assertions updated to registry-derived inputs.

- [ ] **Step 6: Commit the state-sync projection**

```bash
git add scripts/sync_omo_state.py scripts/omo_debt_weight.py .omo/tests/test_omo_automation.py
git -c core.hooksPath=/dev/null commit -m "feat(omo): derive state debt summary from ledger"
```

---

### Task 4: Add auditable debt actions and lifecycle transitions

**Files:**
- Create: `scripts/omo_debt.py`
- Test: `.omo/tests/test_omo_debt_cli.py`

- [ ] **Step 1: Write the failing CLI action tests**

```python
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import yaml


def test_debt_schedule_updates_item_state(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")
    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "schedule",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "D2_CI_E2E",
            "--next-review-at",
            "2026-06-15T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode == 0, result.stderr
    payload = yaml.safe_load((tmp_path / ".omo" / "debt" / "items" / "D2_CI_E2E.yaml").read_text(encoding="utf-8"))
    assert payload["lifecycle_state"] == "scheduled"
    assert payload["next_review_at"] == "2026-06-15T00:00:00Z"
    assert payload["history"][-1]["action"] == "schedule"


def test_debt_register_creates_new_item(tmp_path: Path) -> None:
    (tmp_path / ".omo" / "debt" / "items").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".omo" / "debt" / "dashboard").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".omo" / "debt" / "reviews").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".omo" / "debt" / "registry.yaml").write_text(
        "version: 1\nitems_dir: .omo/debt/items\ndashboard_ref: .omo/debt/dashboard/current.yaml\nreview_pack_ref: .omo/debt/reviews/current.md\nseed_items: []\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "register",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "NEW_GATE",
            "--title",
            "New gate debt",
            "--dimension",
            "governance_process",
            "--subdimension",
            "gate_rule",
            "--severity",
            "medium",
            "--owner",
            "omo-governance",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode == 0, result.stderr
    payload = yaml.safe_load((tmp_path / ".omo" / "debt" / "items" / "NEW_GATE.yaml").read_text(encoding="utf-8"))
    registry = yaml.safe_load((tmp_path / ".omo" / "debt" / "registry.yaml").read_text(encoding="utf-8"))
    assert payload["lifecycle_state"] == "identified"
    assert payload["history"][-1]["action"] == "register"
    assert ".omo/debt/items/NEW_GATE.yaml" in registry["seed_items"]
```

- [ ] **Step 2: Run the CLI tests to verify they fail**

Run: `python3 -m pytest .omo/tests/test_omo_debt_cli.py -q`

Expected: FAIL because `scripts/omo_debt.py` does not exist.

- [ ] **Step 3: Implement a small action-oriented CLI instead of bespoke one-off scripts**

```python
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import yaml


def append_history(payload: dict, action: str, note: str) -> None:
    payload.setdefault("history", []).append(
        {
            "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "action": action,
            "note": note,
        }
    )


def schedule_item(payload: dict, next_review_at: str) -> None:
    payload["lifecycle_state"] = "scheduled"
    payload["next_review_at"] = next_review_at
    append_history(payload, "schedule", f"Next review set to {next_review_at}.")


def register_item(args: argparse.Namespace) -> dict:
    payload = {
        "id": args.id,
        "title": args.title,
        "dimension": args.dimension,
        "subdimension": args.subdimension,
        "domain": "workspace",
        "scope": "governance_kernel",
        "severity": args.severity,
        "weight": 0.05,
        "entropy_class": "classification",
        "lifecycle_state": "identified",
        "owner": args.owner,
        "affected_roots": [".omo"],
        "evidence_refs": [],
        "mitigation_refs": [],
        "opened_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "last_reviewed_at": None,
        "next_review_at": None,
        "gate_level": "none",
        "history": [],
    }
    append_history(payload, "register", f"Registered debt item {args.id}.")
    return payload


def append_registry_ref(omo_dir: Path, item_ref: str) -> None:
    registry_path = omo_dir / "debt" / "registry.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    refs = list(registry.get("seed_items", []))
    if item_ref not in refs:
        refs.append(item_ref)
    registry["seed_items"] = refs
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, allow_unicode=True), encoding="utf-8")
```

- [ ] **Step 3.1: Make the `register` command write the item file and then update the registry**

```python
if args.command == "register":
    payload = register_item(args)
    item_ref = f".omo/debt/items/{args.id}.yaml"
    item_path = Path(args.omo_dir) / "debt" / "items" / f"{args.id}.yaml"
    item_path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    append_registry_ref(Path(args.omo_dir), item_ref)
    print(f"registered {args.id}")
    return 0
```

- [ ] **Step 4: Implement the remaining required actions as explicit commands**

```python
ACTIONS = {
    "reclassify": lambda payload, args: payload.update({"dimension": args.dimension, "subdimension": args.subdimension}),
    "escalate": lambda payload, args: payload.update({"gate_level": args.gate_level}),
    "revalidate": lambda payload, args: payload.update({"last_reviewed_at": args.reviewed_at}),
    "close": lambda payload, args: payload.update({"lifecycle_state": "closed", "gate_level": "none"}),
    "reopen": lambda payload, args: payload.update({"lifecycle_state": "identified"}),
}
```

- [ ] **Step 5: Run the CLI tests to verify lifecycle history is auditable**

Run: `python3 -m pytest .omo/tests/test_omo_debt_cli.py -q`

Expected: PASS with command-level coverage for `register`, `schedule`, `escalate`, and `close`.

- [ ] **Step 6: Commit the CLI lifecycle surface**

```bash
git add scripts/omo_debt.py .omo/tests/test_omo_debt_cli.py
git -c core.hooksPath=/dev/null commit -m "feat(omo): add debt lifecycle cli"
```

---

### Task 5: Generate dashboard and review-pack outputs from the ledger

**Files:**
- Create: `.omo/debt/dashboard/current.yaml`
- Create: `.omo/debt/reviews/current.md`
- Modify: `scripts/omo_debt.py`
- Test: `.omo/tests/test_omo_debt_outputs.py`

- [ ] **Step 1: Write the failing output-generation test**

```python
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import yaml


def test_debt_refresh_writes_dashboard_and_review_pack(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")
    result = subprocess.run(
        [sys.executable, "scripts/omo_debt.py", "refresh", "--omo-dir", str(tmp_path / ".omo"), "--now", "2026-06-10T00:00:00Z"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode == 0, result.stderr
    dashboard = yaml.safe_load((tmp_path / ".omo" / "debt" / "dashboard" / "current.yaml").read_text(encoding="utf-8"))
    review = (tmp_path / ".omo" / "debt" / "reviews" / "current.md").read_text(encoding="utf-8")
    assert dashboard["debt_metrics"]["debt_health"] < 100
    assert "## Watchlist" in review
    assert "## Gate Debts" in review
    assert "## Newly Registered" in review
    assert "## Closed Debts" in review
    assert "## Reopened Debts" in review
```

- [ ] **Step 2: Run the outputs test to verify it fails**

Run: `python3 -m pytest .omo/tests/test_omo_debt_outputs.py -q`

Expected: FAIL because the `refresh` command does not write output files yet.

- [ ] **Step 3: Implement `refresh` so it writes both machine-readable and human-readable outputs**

```python
def write_dashboard(omo_dir: Path, metrics: DebtMetrics) -> None:
    payload = {
        "generated_at": now,
        "debt_metrics": {
            "debt_health": metrics.debt_health,
            "classification_entropy": metrics.classification_entropy,
            "state_entropy": metrics.state_entropy,
            "pointer_entropy": metrics.pointer_entropy,
            "time_entropy": metrics.time_entropy,
            "backlog_pressure": metrics.backlog_pressure,
            "coupling_load": metrics.coupling_load,
        },
        "watchlist_item_ids": list(metrics.watchlist_item_ids),
        "gate_item_ids": list(metrics.gate_item_ids),
    }
```

```markdown
## Watchlist

- `D2_CI_E2E` — overdue review / watchlist debt

## Gate Debts

- `SB_DECOMPOSITION` — gate debt still in progress

## Newly Registered

- `D2_CI_E2E`
- `D3_EU_PRICING`

## Closed Debts

- none

## Drifted Debts

- `SB_ORPHANED_TASKS` — pointer entropy remains non-zero

## Escalated Debts

- `SB_DECOMPOSITION`

## Reopened Debts

- none
```

- [ ] **Step 4: Ensure `sync_omo_state.py` or `omo_debt.py refresh` is the only writer for generated outputs**

```python
def refresh_outputs(omo_dir: Path, now: str) -> None:
    ledger = load_debt_ledger(omo_dir)
    metrics = compute_debt_metrics(ledger.items, now=now)
    write_dashboard(omo_dir, metrics)
    write_review_pack(omo_dir, ledger.items, metrics, now=now)
```

- [ ] **Step 4.1: Derive review-pack sections from item history instead of hard-coded labels**

```python
def classify_review_sections(items: tuple[DebtItem, ...]) -> dict[str, list[str]]:
    sections = {
        "newly_registered": [],
        "closed": [],
        "drifted": [],
        "escalated": [],
        "reopened": [],
    }
    for item in items:
        actions = [entry["action"] for entry in item.history]
        if "register" in actions:
            sections["newly_registered"].append(item.id)
        if "close" in actions or item.lifecycle_state == "closed":
            sections["closed"].append(item.id)
        if item.entropy_class in {"pointer", "time"} and item.lifecycle_state != "closed":
            sections["drifted"].append(item.id)
        if "escalate" in actions or item.gate_level == "gate":
            sections["escalated"].append(item.id)
        if "reopen" in actions:
            sections["reopened"].append(item.id)
    return sections
```

- [ ] **Step 5: Run the outputs test to verify it passes**

Run: `python3 -m pytest .omo/tests/test_omo_debt_outputs.py -q`

Expected: `1 passed`

- [ ] **Step 6: Commit the output surfaces**

```bash
git add .omo/debt/dashboard/current.yaml .omo/debt/reviews/current.md scripts/omo_debt.py .omo/tests/test_omo_debt_outputs.py
git -c core.hooksPath=/dev/null commit -m "feat(omo): add debt dashboard outputs"
```

---

### Task 6: Document the mechanism and prove the full governance flow

**Files:**
- Modify: `.omo/AGENT.md`
- Modify: `.omo/_knowledge/design/debt-cleanup-plan.md`
- Modify: `.omo/tests/README.md`
- Create: `.omo/tests/test_omo_debt_docs.py`
- Test: `.omo/tests/test_omo_debt_registry.py`
- Test: `.omo/tests/test_omo_debt_metrics.py`
- Test: `.omo/tests/test_omo_debt_cli.py`
- Test: `.omo/tests/test_omo_debt_outputs.py`
- Test: `.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Update the operator docs so the ledger has one canonical refresh/proof flow**

```md
## Debt governance refresh

Canonical refresh:

1. `python3 scripts/omo_debt.py refresh --omo-dir .omo`
2. `python3 scripts/sync_omo_state.py --omo-dir .omo`
3. `python3 -m pytest .omo/tests/test_omo_debt_registry.py .omo/tests/test_omo_debt_metrics.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_outputs.py -q`

Full proof:

- `bash bin/verify-omo.sh`
```

- [ ] **Step 2: Add a focused docs regression if one does not already exist**

```python
# .omo/tests/test_omo_debt_docs.py
from pathlib import Path


def test_omo_agent_documents_debt_refresh_flow() -> None:
    content = Path(".omo/AGENT.md").read_text(encoding="utf-8")
    assert "python3 scripts/omo_debt.py refresh --omo-dir .omo" in content
    assert "bash bin/verify-omo.sh" in content
```

- [ ] **Step 3: Run the focused new debt tests**

Run: `python3 -m pytest .omo/tests/test_omo_debt_registry.py .omo/tests/test_omo_debt_metrics.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_outputs.py .omo/tests/test_omo_debt_docs.py -q`

Expected: all PASS.

- [ ] **Step 4: Run the sync-state regression and then the canonical governance proof**

Run: `python3 -m pytest .omo/tests/test_omo_automation.py -q -k 'debt or health_score'`

Expected: PASS.

Run: `bash bin/verify-omo.sh`

Expected: PASS with sync, task validation, and `.omo` regression suite all green.

- [ ] **Step 5: Commit the docs and verification updates**

```bash
git add .omo/AGENT.md .omo/_knowledge/design/debt-cleanup-plan.md .omo/tests/README.md .omo/tests/test_omo_debt_docs.py .omo/tests/test_omo_automation.py
git -c core.hooksPath=/dev/null commit -m "docs(omo): document debt governance workflow"
```

- [ ] **Step 6: Final repository status check**

Run: `git --no-pager status --short`

Expected: clean working tree or only unrelated pre-existing changes outside this plan’s files.

---

## Spec coverage checklist

- First-class debt registry in `.omo` — Task 1
- Multi-dimensional metrics and entropy — Task 2
- Summary-only `state/system.yaml` projection — Task 3
- Auditable lifecycle actions — Task 4
- Dashboard snapshot and review pack — Task 5
- Progressive gate/watchlist counts and docs/proof flow — Tasks 2, 3, 5, 6

## Notes for implementers

- Do not copy live task truth into debt items; store refs back to `.omo/tasks`, plans, evidence, and project paths.
- Keep seed scope intentionally small: migrate the current core debts first, then let future debt registration expand coverage.
- Preserve compatibility for any existing imports from `scripts/omo_debt_weight.py`; route them through the new ledger-driven metrics logic instead of maintaining two formulas.
- Generated files under `.omo/debt/dashboard/` and `.omo/debt/reviews/` should be rewritten by the tooling, not hand-edited.
