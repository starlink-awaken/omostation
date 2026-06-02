# Debt Reporting Entrypoints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make debt campaign and reporting first-class control-plane entrypoints by exposing canonical refs, promoting only reporting into state, validating generated debt refs, and updating the refresh flow.

**Architecture:** Keep the slice narrow and additive. Reuse the existing campaign/report commands and generated surfaces, extend the debt registry contract to point at them, teach `sync_omo_state.py` to validate debt-generated refs and publish only `debt_reporting_ref`, and then update operator docs plus the live `.omo` state/output artifacts. Because `scripts/` is a nested git repo / gitlink and already dirty from unrelated work, every mixed `scripts/*` + root change must use pathspec-limited two-repo commits without cleaning unrelated files.

**Tech Stack:** Python 3, PyYAML, pytest, `scripts/omo_debt.py`, `scripts/sync_omo_state.py`, `.omo` governance docs/tests

---

## File structure map

- Modify: `scripts/omo_debt_registry.py`
  - Extend `DebtLedger` with `campaign_ref` and `reporting_ref`.
- Modify: `.omo/debt/registry.yaml`
  - Publish canonical registry refs for campaign and reporting.
- Modify: `.omo/tests/test_omo_debt_registry.py`
  - Lock the new registry contract and live generated surfaces.
- Modify: `.omo/tests/test_omo_debt_cli.py`
  - Update the hardcoded registry fixture string used by CLI tests.
- Create/refresh: `.omo/debt/campaign/current.yaml`, `.omo/debt/campaign/current.md`, `.omo/debt/campaign/runs/2026-06-10T00-00-00Z/current.yaml`, `.omo/debt/campaign/runs/2026-06-10T00-00-00Z/current.md`
  - Hydrated live campaign surfaces referenced by the new registry.
- Create/refresh: `.omo/debt/reporting/current.yaml`, `.omo/debt/reporting/current.md`, `.omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.yaml`, `.omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.md`
  - Hydrated live reporting surfaces referenced by the new registry and state.
- Modify: `scripts/sync_omo_state.py`
  - Validate debt-generated refs, emit divergence detail when missing, and promote `debt_reporting_ref`.
- Modify: `.omo/tests/test_omo_automation.py`
  - Lock state promotion and debt-generated-ref validation behavior.
- Modify: `.omo/AGENT.md`
  - Document the canonical refresh flow now including `campaign` and `report`.
- Modify: `.omo/tests/test_omo_debt_docs.py`
  - Lock the updated operator guidance.
- Modify: `.omo/state/system.yaml`
  - Refresh live state so `debt_reporting_ref` is present after sync.

## Implementation notes before starting

- Work from `/Users/xiamingxing/Workspace`.
- Do **not** clean or revert unrelated changes inside `scripts/`; pathspec every add/commit.
- The current live dispatch run is `.omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml`, so hydration steps in this plan should produce run-scoped campaign/reporting files under `2026-06-10T00-00-00Z/`.
- Keep reporting explicitly single-run. This slice does not add any cross-run history, burndown, or trend math.
- `campaign_ref` belongs in the registry only. `debt_reporting_ref` belongs in `state/system.yaml`; `debt_campaign_ref` does not.

### Task 1: Extend the registry contract and hydrate live campaign/reporting refs

**Files:**
- Modify: `scripts/omo_debt_registry.py`
- Modify: `.omo/debt/registry.yaml`
- Modify: `.omo/tests/test_omo_debt_registry.py`
- Modify: `.omo/tests/test_omo_debt_cli.py`
- Create/refresh: `.omo/debt/campaign/current.yaml`
- Create/refresh: `.omo/debt/campaign/current.md`
- Create/refresh: `.omo/debt/campaign/runs/2026-06-10T00-00-00Z/current.yaml`
- Create/refresh: `.omo/debt/campaign/runs/2026-06-10T00-00-00Z/current.md`
- Create/refresh: `.omo/debt/reporting/current.yaml`
- Create/refresh: `.omo/debt/reporting/current.md`
- Create/refresh: `.omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.yaml`
- Create/refresh: `.omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.md`
- Test: `.omo/tests/test_omo_debt_registry.py`
- Test: `.omo/tests/test_omo_debt_cli.py`

- [ ] **Step 1: Write the failing registry contract test**

Extend `.omo/tests/test_omo_debt_registry.py`:

```python
def test_debt_registry_lists_seed_items_and_outputs() -> None:
    registry = _load_yaml("debt/registry.yaml")

    assert registry["version"] == 1
    assert registry["items_dir"] == ".omo/debt/items"
    assert registry["dashboard_ref"] == ".omo/debt/dashboard/current.yaml"
    assert registry["review_pack_ref"] == ".omo/debt/reviews/current.md"
    assert registry["review_queue_ref"] == ".omo/debt/review-queue/current.yaml"
    assert registry["action_packet_ref"] == ".omo/debt/action-packet/current.yaml"
    assert registry["owner_routing_ref"] == ".omo/debt/owner-routing/current.yaml"
    assert registry["dispatch_ref"] == ".omo/debt/dispatch/current.yaml"
    assert registry["campaign_ref"] == ".omo/debt/campaign/current.yaml"
    assert registry["reporting_ref"] == ".omo/debt/reporting/current.yaml"


def test_debt_registry_campaign_and_reporting_refs_exist() -> None:
    registry = _load_yaml("debt/registry.yaml")

    assert (OMO_ROOT / registry["campaign_ref"]).exists()
    assert (OMO_ROOT / registry["reporting_ref"]).exists()
```

- [ ] **Step 2: Run the registry tests to verify they fail**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_registry.py -q
```

Expected: FAIL with `KeyError: 'campaign_ref'` or `KeyError: 'reporting_ref'`.

- [ ] **Step 3: Make the registry contract and live artifacts real**

Update `scripts/omo_debt_registry.py` so `DebtLedger` carries the new refs:

```python
@dataclass(frozen=True)
class DebtLedger:
    registry_ref: str
    dashboard_ref: str
    review_pack_ref: str
    review_queue_ref: str
    action_packet_ref: str
    owner_routing_ref: str
    dispatch_ref: str
    campaign_ref: str
    reporting_ref: str
    items: tuple[DebtItem, ...]
```

```python
    return DebtLedger(
        registry_ref=".omo/debt/registry.yaml",
        dashboard_ref=registry["dashboard_ref"],
        review_pack_ref=registry["review_pack_ref"],
        review_queue_ref=registry["review_queue_ref"],
        action_packet_ref=registry["action_packet_ref"],
        owner_routing_ref=registry["owner_routing_ref"],
        dispatch_ref=registry["dispatch_ref"],
        campaign_ref=registry["campaign_ref"],
        reporting_ref=registry["reporting_ref"],
        items=tuple(items),
    )
```

Update `.omo/debt/registry.yaml`:

```yaml
version: 1
items_dir: .omo/debt/items
dashboard_ref: .omo/debt/dashboard/current.yaml
review_pack_ref: .omo/debt/reviews/current.md
review_queue_ref: .omo/debt/review-queue/current.yaml
action_packet_ref: .omo/debt/action-packet/current.yaml
owner_routing_ref: .omo/debt/owner-routing/current.yaml
dispatch_ref: .omo/debt/dispatch/current.yaml
campaign_ref: .omo/debt/campaign/current.yaml
reporting_ref: .omo/debt/reporting/current.yaml
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

Update the CLI fixture string in `.omo/tests/test_omo_debt_cli.py`:

```python
    (debt_dir / "registry.yaml").write_text(
        "version: 1\nitems_dir: .omo/debt/items\ndashboard_ref: .omo/debt/dashboard/current.yaml\nreview_pack_ref: .omo/debt/reviews/current.md\nreview_queue_ref: .omo/debt/review-queue/current.yaml\naction_packet_ref: .omo/debt/action-packet/current.yaml\nowner_routing_ref: .omo/debt/owner-routing/current.yaml\ndispatch_ref: .omo/debt/dispatch/current.yaml\ncampaign_ref: .omo/debt/campaign/current.yaml\nreporting_ref: .omo/debt/reporting/current.yaml\nseed_items: []\n",
        encoding="utf-8",
    )
```

Hydrate the live generated surfaces **before** committing the new refs:

```bash
cd /Users/xiamingxing/Workspace && python3 scripts/omo_debt.py campaign --omo-dir .omo
cd /Users/xiamingxing/Workspace && python3 scripts/omo_debt.py report --omo-dir .omo
```

- [ ] **Step 4: Run the focused registry + fixture checks to verify they pass**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_registry.py .omo/tests/test_omo_debt_cli.py -q -k 'debt_registry or debt_register_creates_new_item'
```

Expected: PASS, and the live repo now has:

```text
.omo/debt/campaign/current.yaml
.omo/debt/campaign/current.md
.omo/debt/campaign/runs/2026-06-10T00-00-00Z/current.yaml
.omo/debt/campaign/runs/2026-06-10T00-00-00Z/current.md
.omo/debt/reporting/current.yaml
.omo/debt/reporting/current.md
.omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.yaml
.omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.md
```

- [ ] **Step 5: Commit the registry contract with the two-repo pattern**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_registry.py && git -c core.hooksPath=/dev/null commit -m $'feat(debt): add campaign and reporting registry refs\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
cd /Users/xiamingxing/Workspace && git add -- .omo/debt/registry.yaml .omo/debt/campaign/current.yaml .omo/debt/campaign/current.md .omo/debt/campaign/runs/2026-06-10T00-00-00Z/current.yaml .omo/debt/campaign/runs/2026-06-10T00-00-00Z/current.md .omo/debt/reporting/current.yaml .omo/debt/reporting/current.md .omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.yaml .omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.md .omo/tests/test_omo_debt_registry.py .omo/tests/test_omo_debt_cli.py scripts && git -c core.hooksPath=/dev/null commit -m $'test(omo): expose debt campaign and reporting refs\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Expected: one `scripts/` commit for the registry model, one root commit for the live registry/output/test contract.

### Task 2: Promote reporting into state and validate debt-generated refs

**Files:**
- Modify: `scripts/sync_omo_state.py`
- Modify: `.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Add failing sync/state tests**

Extend `.omo/tests/test_omo_automation.py` with two focused tests:

```python
def test_sync_state_promotes_debt_reporting_ref_but_not_campaign_ref(tmp_path: Path) -> None:
    omo = tmp_path / ".omo"
    _write_debt_registry_fixture(
        omo,
        [
            {
                "id": "LEDGER_ALPHA",
                "title": "Ledger alpha title",
                "dimension": "architecture",
                "subdimension": "boundaries",
                "domain": "workspace",
                "scope": "cross_project",
                "severity": "high",
                "weight": 0.4,
                "entropy_class": "coupling",
                "lifecycle_state": "identified",
                "owner": "platform-governance",
                "affected_roots": ["projects/demo"],
                "evidence_refs": [".omo/_knowledge/design/demo.md"],
                "mitigation_refs": [".omo/_knowledge/design/demo.md"],
                "opened_at": "2026-06-01T00:00:00Z",
                "last_reviewed_at": None,
                "next_review_at": "2026-06-08T00:00:00Z",
                "gate_level": "watchlist",
                "history": [],
            }
        ],
    )
    for rel_path in (
        "debt/dashboard/current.yaml",
        "debt/reviews/current.md",
        "debt/review-queue/current.yaml",
        "debt/action-packet/current.yaml",
        "debt/owner-routing/current.yaml",
        "debt/dispatch/current.yaml",
        "debt/campaign/current.yaml",
        "debt/reporting/current.yaml",
    ):
        path = omo / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("generated\n", encoding="utf-8")
    _write_yaml(omo / "state" / "system.yaml", {"health_score": 0.0})
    _write_yaml(omo / "goals" / "current.yaml", {"phase": 17, "status": "active", "goals": []})

    state = sync_state(omo, test_output="5 passed", now="2026-06-10T00:00:00Z")

    assert state["debt_reporting_ref"] == ".omo/debt/reporting/current.yaml"
    assert "debt_campaign_ref" not in state


def test_sync_state_flags_missing_debt_generated_refs(tmp_path: Path) -> None:
    omo = tmp_path / ".omo"
    _write_debt_registry_fixture(omo, [])
    (omo / "debt" / "dashboard").mkdir(parents=True, exist_ok=True)
    (omo / "debt" / "dashboard" / "current.yaml").write_text("generated\n", encoding="utf-8")
    (omo / "state").mkdir(parents=True, exist_ok=True)
    (omo / "goals").mkdir(parents=True, exist_ok=True)
    for group in ("active", "done", "blocked"):
        (omo / "tasks" / group).mkdir(parents=True, exist_ok=True)
    _write_yaml(omo / "state" / "system.yaml", {"health_score": 0.0})
    _write_yaml(omo / "goals" / "current.yaml", {"phase": 17, "status": "active", "goals": []})

    state = sync_state(omo, test_output="5 passed", now="2026-06-10T00:00:00Z")

    assert any(flag.startswith("missing_debt_generated_ref:") for flag in state["divergence_flags"])
    assert "debt_generated_refs" in state["divergence_detail_refs"]
```

- [ ] **Step 2: Run the focused sync tests to verify they fail**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_automation.py -q -k 'debt_reporting_ref or debt_generated_ref'
```

Expected: FAIL because `sync_state` does not yet publish `debt_reporting_ref` or validate debt-generated refs.

- [ ] **Step 3: Implement debt-generated-ref validation and state promotion**

First, extend the fixture writer inside `.omo/tests/test_omo_automation.py` so every temp registry contains the new fields:

```python
    _write_yaml(
        debt_dir / "registry.yaml",
        {
            "version": 1,
            "items_dir": ".omo/debt/items",
            "dashboard_ref": ".omo/debt/dashboard/current.yaml",
            "review_pack_ref": ".omo/debt/reviews/current.md",
            "review_queue_ref": ".omo/debt/review-queue/current.yaml",
            "action_packet_ref": ".omo/debt/action-packet/current.yaml",
            "owner_routing_ref": ".omo/debt/owner-routing/current.yaml",
            "dispatch_ref": ".omo/debt/dispatch/current.yaml",
            "campaign_ref": ".omo/debt/campaign/current.yaml",
            "reporting_ref": ".omo/debt/reporting/current.yaml",
            "seed_items": seed_items,
        },
    )
```

Then implement a debt-specific validator in `scripts/sync_omo_state.py`:

```python
def _debt_generated_ref_flags(omo_dir: Path, ledger) -> tuple[list[str], dict[str, dict[str, object]]]:
    refs = {
        "dashboard_ref": ledger.dashboard_ref,
        "review_pack_ref": ledger.review_pack_ref,
        "review_queue_ref": ledger.review_queue_ref,
        "action_packet_ref": ledger.action_packet_ref,
        "owner_routing_ref": ledger.owner_routing_ref,
        "dispatch_ref": ledger.dispatch_ref,
        "campaign_ref": ledger.campaign_ref,
        "reporting_ref": ledger.reporting_ref,
    }
    missing = {name: ref for name, ref in refs.items() if not (omo_dir.parent / ref).exists()}
    if not missing:
        return [], {}
    return (
        [f"missing_debt_generated_ref:{name}" for name in sorted(missing)],
        {
            "debt_generated_refs": {
                "count": len(missing),
                "ref": _write_divergence_detail_artifact(
                    omo_dir,
                    "debt_generated_refs",
                    {"count": len(missing), "missing_refs": missing},
                ),
            }
        },
    )
```

Wire it into `sync_state(...)` and promote only reporting:

```python
    debt_generated_ref_flags = []
    debt_generated_ref_detail_refs = {}
    if ledger:
        debt_generated_ref_flags, debt_generated_ref_detail_refs = _debt_generated_ref_flags(omo_dir, ledger)
```

```python
    divergence_flags = (
        goal_divergence_flags
        + _active_task_ref_flags(tasks_dir / "active")
        + stale_dispatch_flags
        + dangling_reference_flags
        + debt_generated_ref_flags
    )
    divergence_detail_refs = {
        **divergence_detail_refs,
        **stale_dispatch_refs,
        **dangling_reference_refs,
        **debt_generated_ref_detail_refs,
    }
```

```python
    for detail_name in ("missing_goal_tasks", "orphaned_tasks", "stale_dispatches", "dangling_refs", "debt_generated_refs"):
        if detail_name not in divergence_detail_refs:
            _clear_divergence_detail_artifact(omo_dir, detail_name)
```

```python
    if ledger and metrics:
        state["debt_registry_ref"] = ledger.registry_ref
        state["debt_dashboard_ref"] = ledger.dashboard_ref
        state["debt_review_pack_ref"] = ledger.review_pack_ref
        state["debt_reporting_ref"] = ledger.reporting_ref
```

- [ ] **Step 4: Run the focused sync tests to verify they pass**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_automation.py -q -k 'debt_reporting_ref or debt_generated_ref'
```

Expected: PASS, with `debt_reporting_ref` present in state and missing generated refs reported as divergence.

- [ ] **Step 5: Commit the sync/state slice with the two-repo pattern**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add sync_omo_state.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): validate debt reporting entrypoints\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
cd /Users/xiamingxing/Workspace && git add -- .omo/tests/test_omo_automation.py scripts && git -c core.hooksPath=/dev/null commit -m $'test(omo): cover debt reporting entrypoint sync\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Expected: one `scripts/` commit for sync logic, one root commit for the automation tests plus updated gitlink.

### Task 3: Update the canonical refresh flow and refresh live state

**Files:**
- Modify: `.omo/AGENT.md`
- Modify: `.omo/tests/test_omo_debt_docs.py`
- Modify: `.omo/state/system.yaml`

- [ ] **Step 1: Add failing docs assertions**

Extend `.omo/tests/test_omo_debt_docs.py`:

```python
    assert "python3 scripts/omo_debt.py campaign --omo-dir .omo" in content
    assert "python3 scripts/omo_debt.py report --omo-dir .omo" in content
    assert "python3 scripts/sync_omo_state.py --omo-dir .omo" in content
    assert "debt_reporting_ref" in content
    assert "campaign_ref" in content
    assert "reporting_ref" in content
    assert "dispatch -> campaign -> report -> sync -> verify" in content.lower()
```

- [ ] **Step 2: Run the docs test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py -q
```

Expected: FAIL because `.omo/AGENT.md` does not yet document the new registry/state entrypoints or refresh sequence.

- [ ] **Step 3: Update docs and refresh live state**

Add a compact operator block to `.omo/AGENT.md`:

```md
- `.omo/debt/registry.yaml` now publishes `campaign_ref` and `reporting_ref` as the canonical debt entrypoints for run-level coordination and compact run progress
- `state/system.yaml` promotes `debt_reporting_ref` as the high-level debt progress pointer; campaign remains registry-only because it is still operator-detail
- Canonical refresh flow is now: `refresh` → `dispatch` → `campaign` → `report` → `sync_omo_state.py` → `bash bin/verify-omo.sh`
- If `campaign_ref` or `reporting_ref` points at a missing generated file, sync must treat that as debt-control-plane drift rather than silent success
```

Refresh live state after Task 2 is merged:

```bash
cd /Users/xiamingxing/Workspace && python3 scripts/sync_omo_state.py --omo-dir .omo
```

- [ ] **Step 4: Run grouped regressions and canonical verify**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_registry.py .omo/tests/test_omo_automation.py .omo/tests/test_omo_debt_docs.py .omo/tests/test_omo_debt_cli.py -q
cd /Users/xiamingxing/Workspace && bash bin/verify-omo.sh
```

Expected:

1. focused registry/automation/docs/CLI coverage passes
2. `state/system.yaml` contains `debt_reporting_ref: .omo/debt/reporting/current.yaml`
3. full canonical verify stays green

- [ ] **Step 5: Commit the docs/state closeout**

Run:

```bash
cd /Users/xiamingxing/Workspace && git add -- .omo/AGENT.md .omo/state/system.yaml .omo/tests/test_omo_debt_docs.py docs/superpowers/plans/2026-06-02-debt-reporting-entrypoints.md && git -c core.hooksPath=/dev/null commit -m $'docs(omo): wire debt reporting entrypoint flow\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Expected: one root commit for docs, live state refresh, and the saved implementation plan.

## Self-review checklist

- Spec coverage:
  - registry refs for campaign/reporting: Task 1
  - hydration before canonical refs are live: Task 1
  - `DebtLedger` contract expansion: Task 1
  - `debt_reporting_ref` state promotion without `debt_campaign_ref`: Task 2
  - registry-level ref validation: Task 2
  - canonical refresh flow update: Task 3
  - live state refresh + canonical verify: Task 3
- Placeholder scan:
  - no `TBD`, `TODO`, or “implement later” instructions remain
  - every code-changing step includes concrete code or exact commands
- Type consistency:
  - `campaign_ref`, `reporting_ref`, `debt_reporting_ref`, and `missing_debt_generated_ref:<name>` are used consistently throughout the plan
