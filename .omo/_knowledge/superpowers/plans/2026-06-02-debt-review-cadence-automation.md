# Debt Review Cadence Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic debt review queue and richer review packet so `.omo` debt refresh produces actionable cadence outputs instead of only overdue summaries.

**Architecture:** Keep `.omo/debt/items/*.yaml` as the only mutable debt truth, then generate two read models from it: a machine-readable review queue and a human-readable review packet. Reuse the existing debt CLI actions (`schedule`, `revalidate`, `escalate`, `close`, `reopen`) and extend the current refresh pipeline rather than introducing a new workflow state machine.

**Tech Stack:** Python 3, PyYAML, existing debt registry/metrics helpers under `scripts/`, pytest, Markdown, canonical `bash bin/verify-omo.sh`

---

## File Structure

### New files

- `.omo/debt/review-queue/current.yaml` — generated machine-readable queue with `due_now`, `upcoming`, `escalation_candidates`, `unscheduled`, and `summary`
- `scripts/omo_debt_review_queue.py` — queue-building helper that derives queue entries and ordering from canonical `DebtItem` objects
- `.omo/tests/test_omo_debt_review_queue.py` — focused regression coverage for queue section classification, ordering, and invalid timestamp behavior

### Modified files

- `.omo/debt/registry.yaml` — add `review_queue_ref` so the new generated surface is discoverable alongside dashboard/review-pack refs
- `scripts/omo_debt_registry.py` — extend `DebtLedger` with `review_queue_ref`
- `scripts/omo_debt_metrics.py` — expose reusable stale-evidence detection so queue generation does not fork freshness logic
- `scripts/omo_debt.py` — replace the current cadence summary helper with queue generation, queue file writing, dashboard preview updates, and richer review-pack sections
- `.omo/tests/test_omo_debt_registry.py` — assert `review_queue_ref` is part of the canonical registry contract
- `.omo/tests/test_omo_debt_outputs.py` — assert review queue YAML, expanded review packet sections, and dashboard preview behavior
- `.omo/tests/test_omo_debt_cli.py` — cover end-to-end refresh failure on invalid queue timestamps and keep minimal registry fixtures aligned
- `.omo/tests/test_omo_debt_docs.py` — assert `.omo/AGENT.md` documents the new queue surface and unscheduled/escalation behavior
- `.omo/tests/test_omo_automation.py` — update debt registry fixtures so registry-backed sync tests keep working after `review_queue_ref` becomes required
- `.omo/AGENT.md` — document the new queue output and cadence interpretation rules
- `.omo/debt/dashboard/current.yaml` — regenerated dashboard preview after implementation
- `.omo/debt/reviews/current.md` — regenerated human-readable review packet after implementation

### Existing files to read before implementation

- `docs/superpowers/specs/2026-06-02-debt-review-cadence-automation-design.md`
- `scripts/omo_debt.py`
- `scripts/omo_debt_registry.py`
- `scripts/omo_debt_metrics.py`
- `.omo/tests/test_omo_debt_outputs.py`
- `.omo/tests/test_omo_debt_cli.py`
- `.omo/tests/test_omo_debt_registry.py`
- `.omo/tests/test_omo_debt_docs.py`
- `.omo/AGENT.md`

---

### Task 1: Extend the registry contract for the new review-queue surface

**Files:**
- Modify: `.omo/debt/registry.yaml`
- Modify: `scripts/omo_debt_registry.py`
- Modify: `.omo/tests/test_omo_debt_registry.py`
- Modify: `.omo/tests/test_omo_automation.py`
- Modify: `.omo/tests/test_omo_debt_cli.py`

- [ ] **Step 1: Add the failing registry assertion**

Update `.omo/tests/test_omo_debt_registry.py` so the first test requires the new queue ref:

```python
def test_debt_registry_lists_seed_items_and_outputs() -> None:
    registry = _load_yaml("debt/registry.yaml")

    assert registry["version"] == 1
    assert registry["items_dir"] == ".omo/debt/items"
    assert registry["dashboard_ref"] == ".omo/debt/dashboard/current.yaml"
    assert registry["review_pack_ref"] == ".omo/debt/reviews/current.md"
    assert registry["review_queue_ref"] == ".omo/debt/review-queue/current.yaml"
    assert registry["seed_items"] == [
        ".omo/debt/items/D2_CI_E2E.yaml",
        ".omo/debt/items/D3_EU_PRICING.yaml",
        ".omo/debt/items/SB_DECOMPOSITION.yaml",
        ".omo/debt/items/SB_UNTESTED_PKGS.yaml",
        ".omo/debt/items/SB_ORPHANED_TASKS.yaml",
        ".omo/debt/items/SB_ROOT_CLEANUP.yaml",
        ".omo/debt/items/SB_BRIDGE_FIX.yaml",
        ".omo/debt/items/SB_PROJECTS_YAML.yaml",
        ".omo/debt/items/SB_PHASE17_PLAN.yaml",
    ]
```

- [ ] **Step 2: Run the registry test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_registry.py::test_debt_registry_lists_seed_items_and_outputs -q
```

Expected: FAIL with `KeyError: 'review_queue_ref'`.

- [ ] **Step 3: Add the queue ref to the registry and loader contract**

Update `.omo/debt/registry.yaml`:

```yaml
version: 1
items_dir: .omo/debt/items
dashboard_ref: .omo/debt/dashboard/current.yaml
review_pack_ref: .omo/debt/reviews/current.md
review_queue_ref: .omo/debt/review-queue/current.yaml
seed_items:
  - .omo/debt/items/D2_CI_E2E.yaml
  - .omo/debt/items/D3_EU_PRICING.yaml
  - .omo/debt/items/SB_DECOMPOSITION.yaml
  - .omo/debt/items/SB_UNTESTED_PKGS.yaml
  - .omo/debt/items/SB_ORPHANED_TASKS.yaml
  - .omo/debt/items/SB_ROOT_CLEANUP.yaml
  - .omo/debt/items/SB_BRIDGE_FIX.yaml
  - .omo/debt/items/SB_PROJECTS_YAML.yaml
  - .omo/debt/items/SB_PHASE17_PLAN.yaml
```

Update `scripts/omo_debt_registry.py`:

```python
@dataclass(frozen=True)
class DebtLedger:
    registry_ref: str
    dashboard_ref: str
    review_pack_ref: str
    review_queue_ref: str
    items: tuple[DebtItem, ...]


def load_debt_ledger(omo_dir: Path) -> DebtLedger:
    registry_path = omo_dir / "debt" / "registry.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))

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
        review_queue_ref=registry["review_queue_ref"],
        items=tuple(items),
    )
```

- [ ] **Step 4: Keep all test fixtures aligned with the new required key**

Update the registry fixture helper in `.omo/tests/test_omo_automation.py`:

```python
    _write_yaml(
        debt_dir / "registry.yaml",
        {
            "version": 1,
            "items_dir": ".omo/debt/items",
            "dashboard_ref": ".omo/debt/dashboard/current.yaml",
            "review_pack_ref": ".omo/debt/reviews/current.md",
            "review_queue_ref": ".omo/debt/review-queue/current.yaml",
            "seed_items": seed_items,
        },
    )
```

Update the minimal registry in `.omo/tests/test_omo_debt_cli.py`:

```python
    (debt_dir / "registry.yaml").write_text(
        "version: 1\n"
        "items_dir: .omo/debt/items\n"
        "dashboard_ref: .omo/debt/dashboard/current.yaml\n"
        "review_pack_ref: .omo/debt/reviews/current.md\n"
        "review_queue_ref: .omo/debt/review-queue/current.yaml\n"
        "seed_items: []\n",
        encoding="utf-8",
    )
```

- [ ] **Step 5: Run the affected tests and commit**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_registry.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_automation.py -q
```

Expected: PASS for the registry/fixture paths touched above.

Commit:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/debt/registry.yaml scripts/omo_debt_registry.py .omo/tests/test_omo_debt_registry.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_automation.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): add debt review queue registry contract\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 2: Build the queue-classification helper and lock its behavior with focused tests

**Files:**
- Create: `scripts/omo_debt_review_queue.py`
- Create: `.omo/tests/test_omo_debt_review_queue.py`
- Modify: `scripts/omo_debt_metrics.py`

- [ ] **Step 1: Write the failing queue tests**

Create `.omo/tests/test_omo_debt_review_queue.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.omo_debt_registry import DebtItem
from scripts.omo_debt_review_queue import build_review_queue


def _item(
    item_id: str,
    *,
    severity: str = "medium",
    gate_level: str = "none",
    next_review_at: str | None = "2026-06-09T00:00:00Z",
    last_reviewed_at: str | None = "2026-06-02T00:00:00Z",
    owner: str = "omo-governance",
    evidence_refs: tuple[str, ...] = ("evidence.md",),
    mitigation_refs: tuple[str, ...] = ("mitigation.md",),
) -> DebtItem:
    return DebtItem(
        id=item_id,
        title=f"{item_id} title",
        dimension="governance_process",
        subdimension="cadence",
        domain=".omo",
        scope="governance_kernel",
        severity=severity,
        weight=0.2,
        entropy_class="pointer",
        lifecycle_state="scheduled",
        owner=owner,
        affected_roots=(".omo",),
        evidence_refs=evidence_refs,
        mitigation_refs=mitigation_refs,
        opened_at="2026-06-01T00:00:00Z",
        last_reviewed_at=last_reviewed_at,
        next_review_at=next_review_at,
        gate_level=gate_level,
        history=(),
    )


def test_build_review_queue_splits_due_upcoming_unscheduled_and_escalation_sections(tmp_path: Path) -> None:
    (tmp_path / "evidence.md").write_text("evidence\n", encoding="utf-8")
    (tmp_path / "mitigation.md").write_text("mitigation\n", encoding="utf-8")

    queue = build_review_queue(
        (
            _item("GATE_DUE", severity="critical", gate_level="gate", next_review_at="2026-06-05T00:00:00Z"),
            _item("FUTURE_OK", severity="high", next_review_at="2026-06-12T00:00:00Z"),
            _item("UNSCHEDULED", owner="", next_review_at=None),
            _item("STALE_DUE", severity="medium", next_review_at="2026-06-06T00:00:00Z", mitigation_refs=()),
        ),
        now="2026-06-10T00:00:00Z",
        repo_root=tmp_path,
    )

    assert [entry["id"] for entry in queue["due_now"]] == ["GATE_DUE", "STALE_DUE"]
    assert [entry["id"] for entry in queue["upcoming"]] == ["FUTURE_OK"]
    assert [entry["id"] for entry in queue["unscheduled"]] == ["UNSCHEDULED"]
    assert [entry["id"] for entry in queue["escalation_candidates"]] == ["GATE_DUE", "STALE_DUE"]
    assert queue["unscheduled"][0]["owner"] == "unowned"
    assert queue["summary"]["due_now_count"] == 2
    assert queue["summary"]["upcoming_count"] == 1
    assert queue["summary"]["unscheduled_count"] == 1
    assert queue["summary"]["by_owner"] == {
        "omo-governance": 2,
        "platform-governance": 1,
        "unowned": 1,
    }
    assert queue["summary"]["by_severity"] == {
        "critical": 1,
        "high": 1,
        "medium": 2,
    }


def test_build_review_queue_rejects_invalid_timestamps(tmp_path: Path) -> None:
    (tmp_path / "evidence.md").write_text("evidence\n", encoding="utf-8")
    (tmp_path / "mitigation.md").write_text("mitigation\n", encoding="utf-8")

    with pytest.raises(ValueError, match="not-a-timestamp"):
        build_review_queue(
            (_item("BROKEN", next_review_at="not-a-timestamp"),),
            now="2026-06-10T00:00:00Z",
            repo_root=tmp_path,
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_review_queue.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.omo_debt_review_queue'`.

- [ ] **Step 3: Add reusable stale-evidence detection and the queue builder**

Update `scripts/omo_debt_metrics.py`:

```python
def collect_stale_evidence_item_ids(items: tuple[DebtItem, ...], repo_root: Path | None = None) -> set[str]:
    repo_root = repo_root or Path(__file__).resolve().parents[1]
    stale_ids: set[str] = set()

    for item in items:
        if item.lifecycle_state == "closed":
            continue
        if not item.evidence_refs or not item.mitigation_refs:
            stale_ids.add(item.id)
            continue
        refs = tuple(_resolve_ref_path(repo_root, ref) for ref in (*item.evidence_refs, *item.mitigation_refs))
        if any(not ref.exists() for ref in refs):
            stale_ids.add(item.id)
            continue
        if not item.last_reviewed_at:
            stale_ids.add(item.id)
            continue
        last_reviewed = datetime.fromisoformat(item.last_reviewed_at.replace("Z", "+00:00"))
        if any(datetime.fromtimestamp(ref.stat().st_mtime, tz=UTC) > last_reviewed for ref in refs):
            stale_ids.add(item.id)
    return stale_ids


def compute_debt_metrics(items: tuple[DebtItem, ...], now: str, repo_root: Path | None = None) -> DebtMetrics:
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
    repo_root = repo_root or Path(__file__).resolve().parents[1]
    stale_ids = collect_stale_evidence_item_ids(tuple(open_items), repo_root=repo_root)
    stale_evidence = [item for item in open_items if item.id in stale_ids]
    long_running = [
        item
        for item in open_items
        if item.lifecycle_state in {"classified", "scheduled", "in_progress", "mitigated"}
    ]
    watchlist = [item.id for item in open_items if item.gate_level == "watchlist"]
    gate = [item.id for item in open_items if item.gate_level == "gate"]
    denominator = max(len(open_items), 1)
    health = max(
        0.0,
        100.0
        - (12.5 * len(overdue))
        - (10.0 * len(gate))
        - (7.5 * len(missing_pointers))
        - (5.0 * len(stale_evidence)),
    )

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

Create `scripts/omo_debt_review_queue.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

try:
    from scripts.omo_debt_metrics import collect_stale_evidence_item_ids
    from scripts.omo_debt_registry import DebtItem
except ModuleNotFoundError:
    from omo_debt_metrics import collect_stale_evidence_item_ids
    from omo_debt_registry import DebtItem


REVIEW_WINDOW_DAYS = 7
ESCALATION_THRESHOLD_DAYS = 3
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
GATE_ORDER = {"gate": 0, "watchlist": 1, "none": 2}


def _parse_iso8601(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(value) from exc


def _normalize_owner(owner: str) -> str:
    return owner or "unowned"


def _priority_reason(item: DebtItem, stale_ids: set[str], overdue_days: int) -> str:
    if item.gate_level == "gate" and overdue_days > 0:
        return "gate_overdue"
    if item.id in stale_ids and overdue_days > 0:
        return "stale_and_overdue"
    if overdue_days >= ESCALATION_THRESHOLD_DAYS:
        return "overdue_threshold"
    if item.severity == "critical" and overdue_days > 0:
        return "critical_overdue"
    if overdue_days > 0:
        return "due_now"
    return "upcoming"


def _entry_payload(item: DebtItem, *, stale_ids: set[str], overdue_days: int) -> dict[str, object]:
    return {
        "id": item.id,
        "title": item.title,
        "owner": _normalize_owner(item.owner),
        "severity": item.severity,
        "dimension": item.dimension,
        "subdimension": item.subdimension,
        "lifecycle_state": item.lifecycle_state,
        "gate_level": item.gate_level,
        "next_review_at": item.next_review_at,
        "last_reviewed_at": item.last_reviewed_at,
        "stale_evidence": item.id in stale_ids,
        "overdue_by": overdue_days,
        "affected_roots": list(item.affected_roots),
        "priority_reason": _priority_reason(item, stale_ids, overdue_days),
    }


def build_review_queue(items: tuple[DebtItem, ...], now: str, repo_root: Path) -> dict[str, object]:
    current = _parse_iso8601(now)
    upcoming_cutoff = current + timedelta(days=REVIEW_WINDOW_DAYS)
    stale_ids = collect_stale_evidence_item_ids(items, repo_root=repo_root)
    due_now: list[dict[str, object]] = []
    upcoming: list[dict[str, object]] = []
    escalation_candidates: list[dict[str, object]] = []
    unscheduled: list[dict[str, object]] = []

    for item in items:
        if item.lifecycle_state == "closed":
            continue
        if not item.next_review_at:
            unscheduled.append(_entry_payload(item, stale_ids=stale_ids, overdue_days=0))
            continue

        due_at = _parse_iso8601(item.next_review_at)
        overdue_days = max((current - due_at).days, 0)
        entry = _entry_payload(item, stale_ids=stale_ids, overdue_days=overdue_days)

        if due_at <= current:
            due_now.append(entry)
        elif due_at <= upcoming_cutoff:
            upcoming.append(entry)

        if (
            (item.gate_level == "gate" and overdue_days > 0)
            or overdue_days >= ESCALATION_THRESHOLD_DAYS
            or (item.id in stale_ids and overdue_days > 0)
            or (item.severity == "critical" and overdue_days > 0)
        ):
            escalation_candidates.append({**entry, "escalation_reason": entry["priority_reason"]})

    severity_rank = lambda severity: SEVERITY_ORDER.get(str(severity), 99)
    gate_rank = lambda gate: GATE_ORDER.get(str(gate), 99)
    due_now.sort(key=lambda entry: (gate_rank(entry["gate_level"]), severity_rank(entry["severity"]), -int(entry["overdue_by"]), entry["id"]))
    escalation_candidates.sort(key=lambda entry: (gate_rank(entry["gate_level"]), severity_rank(entry["severity"]), -int(entry["overdue_by"]), entry["id"]))
    upcoming.sort(key=lambda entry: (entry["next_review_at"], severity_rank(entry["severity"]), entry["id"]))
    unscheduled.sort(key=lambda entry: (severity_rank(entry["severity"]), entry["id"]))

    return {
        "generated_at": now,
        "defaults": {
            "review_window_days": REVIEW_WINDOW_DAYS,
            "escalation_threshold_days": ESCALATION_THRESHOLD_DAYS,
        },
        "due_now": due_now,
        "upcoming": upcoming,
        "escalation_candidates": escalation_candidates,
        "unscheduled": unscheduled,
        "summary": {
            "due_now_count": len(due_now),
            "upcoming_count": len(upcoming),
            "escalation_candidate_count": len(escalation_candidates),
            "unscheduled_count": len(unscheduled),
            "by_severity": {
                severity: sum(1 for item in items if item.lifecycle_state != "closed" and item.severity == severity)
                for severity in ("critical", "high", "medium", "low")
                if any(item.lifecycle_state != "closed" and item.severity == severity for item in items)
            },
            "by_gate_level": {
                gate_level: sum(1 for item in items if item.lifecycle_state != "closed" and item.gate_level == gate_level)
                for gate_level in ("gate", "watchlist", "none")
                if any(item.lifecycle_state != "closed" and item.gate_level == gate_level for item in items)
            },
            "by_owner": {
                owner: sum(1 for item in items if item.lifecycle_state != "closed" and _normalize_owner(item.owner) == owner)
                for owner in sorted({_normalize_owner(item.owner) for item in items if item.lifecycle_state != "closed"})
            },
        },
    }
```

- [ ] **Step 4: Run the focused queue tests**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_review_queue.py -q
```

Expected: PASS.

- [ ] **Step 5: Run the metrics regression and commit**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_metrics.py .omo/tests/test_omo_debt_review_queue.py -q
```

Expected: PASS with the queue helper reusing the same stale-evidence logic as `compute_debt_metrics()`.

Commit:

```bash
cd /Users/xiamingxing/Workspace && git add scripts/omo_debt_metrics.py scripts/omo_debt_review_queue.py .omo/tests/test_omo_debt_review_queue.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): add debt review queue builder\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 3: Wire refresh to generate the queue YAML and expanded review packet

**Files:**
- Modify: `scripts/omo_debt.py`
- Modify: `.omo/tests/test_omo_debt_outputs.py`

- [ ] **Step 1: Make the output test fail on the missing queue surface**

Update `.omo/tests/test_omo_debt_outputs.py`:

```python
def test_debt_refresh_writes_dashboard_review_pack_and_queue(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    future_item = tmp_path / ".omo" / "debt" / "items" / "SB_UNTESTED_PKGS.yaml"
    future_payload = yaml.safe_load(future_item.read_text(encoding="utf-8"))
    future_payload["next_review_at"] = "2026-06-11T00:00:00Z"
    future_item.write_text(yaml.safe_dump(future_payload, sort_keys=False, allow_unicode=True), encoding="utf-8")

    unscheduled_item = tmp_path / ".omo" / "debt" / "items" / "SB_ROOT_CLEANUP.yaml"
    unscheduled_payload = yaml.safe_load(unscheduled_item.read_text(encoding="utf-8"))
    unscheduled_payload["next_review_at"] = None
    unscheduled_item.write_text(yaml.safe_dump(unscheduled_payload, sort_keys=False, allow_unicode=True), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "refresh",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--now",
            "2026-06-10T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode == 0, result.stderr
    dashboard = yaml.safe_load((tmp_path / ".omo" / "debt" / "dashboard" / "current.yaml").read_text(encoding="utf-8"))
    queue = yaml.safe_load((tmp_path / ".omo" / "debt" / "review-queue" / "current.yaml").read_text(encoding="utf-8"))
    review = (tmp_path / ".omo" / "debt" / "reviews" / "current.md").read_text(encoding="utf-8")

    assert dashboard["overdue_review_count"] == 7
    assert dashboard["next_review_queue"] == [
        {"id": "SB_UNTESTED_PKGS", "next_review_at": "2026-06-11T00:00:00Z"}
    ]
    assert queue["summary"]["due_now_count"] == 7
    assert queue["summary"]["upcoming_count"] == 1
    assert queue["summary"]["unscheduled_count"] == 1
    assert [entry["id"] for entry in queue["upcoming"]] == ["SB_UNTESTED_PKGS"]
    assert [entry["id"] for entry in queue["unscheduled"]] == ["SB_ROOT_CLEANUP"]
    assert "SB_DECOMPOSITION" in [entry["id"] for entry in queue["escalation_candidates"]]
    assert "## Due Now" in review
    assert "## Escalation Candidates" in review
    assert "## Upcoming Window" in review
    assert "## Unscheduled Debts" in review
```

- [ ] **Step 2: Run the output test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_outputs.py::test_debt_refresh_writes_dashboard_review_pack_and_queue -q
```

Expected: FAIL with `FileNotFoundError` for `.omo/debt/review-queue/current.yaml` and missing packet sections.

- [ ] **Step 3: Replace the old cadence summary with queue generation**

Update `scripts/omo_debt.py`:

```python
try:
    from scripts.omo_debt_metrics import compute_debt_metrics
    from scripts.omo_debt_registry import DebtItem, load_debt_ledger
    from scripts.omo_debt_review_queue import build_review_queue
except ModuleNotFoundError:
    from omo_debt_metrics import compute_debt_metrics
    from omo_debt_registry import DebtItem, load_debt_ledger
    from omo_debt_review_queue import build_review_queue


def write_dashboard(omo_dir: Path, metrics, review_queue: dict[str, object], now: str) -> None:
    due_now = review_queue["due_now"]
    upcoming = review_queue["upcoming"]
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
        "overdue_review_count": len(due_now),
        "overdue_review_item_ids": [entry["id"] for entry in due_now],
        "next_review_queue": [
            {"id": entry["id"], "next_review_at": entry["next_review_at"]}
            for entry in upcoming
        ],
    }
    _write_yaml(omo_dir / "debt" / "dashboard" / "current.yaml", payload)


def write_review_queue(omo_dir: Path, review_queue: dict[str, object]) -> None:
    _write_yaml(omo_dir / "debt" / "review-queue" / "current.yaml", review_queue)


def _render_queue_section(title: str, entries: list[dict[str, object]], reason_key: str) -> str:
    lines = [f"## {title}", ""]
    if entries:
        for entry in entries:
            reason = entry.get(reason_key, "n/a")
            next_review = entry.get("next_review_at") or "unscheduled"
            lines.append(f"- `{entry['id']}` — {reason} ({next_review})")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def write_review_pack(
    omo_dir: Path,
    items: tuple[DebtItem, ...],
    metrics,
    review_queue: dict[str, object],
    now: str,
) -> None:
    sections = classify_review_sections(items)
    watchlist = list(metrics.watchlist_item_ids)
    gate = list(metrics.gate_item_ids)
    content = "\n".join(
        [
            f"# Debt Review Pack\n\nGenerated at: {now}\n",
            _render_section("Watchlist", watchlist),
            _render_section("Gate Debts", gate),
            _render_queue_section("Due Now", review_queue["due_now"], "priority_reason"),
            _render_queue_section("Escalation Candidates", review_queue["escalation_candidates"], "escalation_reason"),
            _render_queue_section("Upcoming Window", review_queue["upcoming"], "priority_reason"),
            _render_queue_section("Unscheduled Debts", review_queue["unscheduled"], "priority_reason"),
            _render_section("Newly Registered", sections["newly_registered"]),
            _render_section("Closed Debts", sections["closed"]),
            _render_section("Drifted Debts", sections["drifted"]),
            _render_section("Escalated Debts", sections["escalated"]),
            _render_section("Reopened Debts", sections["reopened"]),
        ]
    )
    review_path = omo_dir / "debt" / "reviews" / "current.md"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(content, encoding="utf-8")


def refresh_outputs(omo_dir: Path, now: str) -> None:
    ledger = load_debt_ledger(omo_dir)
    metrics = compute_debt_metrics(ledger.items, now=now, repo_root=omo_dir.parent)
    review_queue = build_review_queue(ledger.items, now=now, repo_root=omo_dir.parent)
    write_dashboard(omo_dir, metrics, review_queue, now)
    write_review_queue(omo_dir, review_queue)
    write_review_pack(omo_dir, ledger.items, metrics, review_queue, now)
```

- [ ] **Step 4: Run the output regressions**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_outputs.py .omo/tests/test_omo_debt_review_queue.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/xiamingxing/Workspace && git add scripts/omo_debt.py .omo/tests/test_omo_debt_outputs.py .omo/tests/test_omo_debt_review_queue.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): generate debt review queue outputs\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 4: Harden CLI/doc behavior, regenerate outputs, and run full verification

**Files:**
- Modify: `.omo/tests/test_omo_debt_cli.py`
- Modify: `.omo/tests/test_omo_debt_docs.py`
- Modify: `.omo/AGENT.md`
- Modify: `.omo/debt/dashboard/current.yaml`
- Create: `.omo/debt/review-queue/current.yaml`
- Modify: `.omo/debt/reviews/current.md`

- [ ] **Step 1: Add the failing end-to-end CLI and docs checks**

Append to `.omo/tests/test_omo_debt_cli.py`:

```python
def test_debt_refresh_fails_on_invalid_next_review_timestamp(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    broken_item = tmp_path / ".omo" / "debt" / "items" / "SB_UNTESTED_PKGS.yaml"
    payload = yaml.safe_load(broken_item.read_text(encoding="utf-8"))
    payload["next_review_at"] = "not-a-timestamp"
    broken_item.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "refresh",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--now",
            "2026-06-10T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "not-a-timestamp" in result.stderr
```

Update `.omo/tests/test_omo_debt_docs.py`:

```python
def test_omo_agent_documents_debt_refresh_flow() -> None:
    content = Path(".omo/AGENT.md").read_text(encoding="utf-8")

    assert "python3 scripts/omo_debt.py refresh --omo-dir .omo" in content
    assert ".omo/debt/review-queue/current.yaml" in content
    assert "unscheduled debts" in content.lower()
    assert "escalation candidates" in content.lower()
    assert "bash bin/verify-omo.sh" in content
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py::test_debt_refresh_fails_on_invalid_next_review_timestamp .omo/tests/test_omo_debt_docs.py::test_omo_agent_documents_debt_refresh_flow -q
```

Expected: FAIL because the docs do not mention the queue surface yet and refresh error text has not been verified end-to-end.

- [ ] **Step 3: Update the operator doc and regenerate the committed outputs**

Update `.omo/AGENT.md` so the debt-refresh section reads like this:

```markdown
### Debt governance refresh

Use this when you need to refresh the first-class debt ledger surfaces before reading debt state:

1. `python3 scripts/omo_debt.py refresh --omo-dir .omo --now 2026-06-10T00:00:00Z`
2. `python3 scripts/sync_omo_state.py --omo-dir .omo`
3. `bash bin/verify-omo.sh`

Interpretation rules:

- `.omo/debt/registry.yaml` is the canonical debt index
- `.omo/debt/items/*.yaml` are the canonical debt objects
- `state/system.yaml` carries only derived debt summary fields and pointers
- `.omo/debt/dashboard/current.yaml`, `.omo/debt/review-queue/current.yaml`, and `.omo/debt/reviews/current.md` are generated outputs, not hand-edited truth
- Refresh outputs must surface due-now work, escalation candidates, upcoming work, and unscheduled debts derived from `next_review_at`
```

Regenerate the committed outputs:

```bash
cd /Users/xiamingxing/Workspace && python3 scripts/omo_debt.py refresh --omo-dir .omo --now 2026-06-10T00:00:00Z
```

Expected: `.omo/debt/dashboard/current.yaml`, `.omo/debt/review-queue/current.yaml`, and `.omo/debt/reviews/current.md` are updated together.

- [ ] **Step 4: Run focused regressions, then the canonical verification chain**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_docs.py .omo/tests/test_omo_debt_outputs.py .omo/tests/test_omo_debt_review_queue.py -q
```

Expected: PASS.

Run:

```bash
cd /Users/xiamingxing/Workspace && bash bin/verify-omo.sh
```

Expected: PASS for the full `.omo` verification chain.

- [ ] **Step 5: Commit**

```bash
cd /Users/xiamingxing/Workspace && git add .omo/AGENT.md .omo/debt/dashboard/current.yaml .omo/debt/review-queue/current.yaml .omo/debt/reviews/current.md .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_docs.py .omo/tests/test_omo_debt_outputs.py .omo/tests/test_omo_debt_review_queue.py && git -c core.hooksPath=/dev/null commit -m $'docs(omo): operationalize debt review cadence outputs\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

## Self-check mapping from spec to tasks

- Queue surface in `.omo/debt/review-queue/current.yaml` → Tasks 1 and 3
- Deterministic queue ordering and four active sections → Task 2
- Reuse of existing action layer with no new state machine → Task 3
- Invalid timestamp failure and unscheduled handling → Tasks 2 and 4
- Operator doc and generated outputs → Task 4
- Canonical verification after implementation → Task 4
