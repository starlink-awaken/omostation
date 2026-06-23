---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Debt Owner Routing Packet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an owner-routed debt execution surface that groups action-packet entries by owner, emits execution-safe command guidance, and refreshes owner-routing YAML/Markdown outputs without introducing mutable workflow state.

**Architecture:** Keep the existing debt ledger, review queue, and action packet as the read-model spine, then add a focused owner-routing layer on top. Tighten the action-packet command contract first so owner routing can reuse safe command metadata instead of re-deriving shell instructions independently, then wire the new owner-routing outputs into `scripts/omo_debt.py refresh`.

**Tech Stack:** Python 3, PyYAML, existing `.omo` debt helpers under `scripts/`, pytest, Markdown, canonical `bash bin/verify-omo.sh`

---

## File Structure

### New files

- `.omo/debt/owner-routing/current.yaml` — generated machine-readable owner-routing packet
- `.omo/debt/owner-routing/current.md` — generated human-readable owner execution packet
- `scripts/omo_debt_owner_routing.py` — pure builder that groups action-packet entries by owner and adds attention flags
- `.omo/tests/test_omo_debt_owner_routing.py` — focused owner-routing regression suite

### Modified files

- `.omo/debt/registry.yaml` — add `owner_routing_ref`
- `scripts/omo_debt_registry.py` — extend `DebtLedger` with `owner_routing_ref`
- `scripts/omo_debt_action_packet.py` — emit execution-safe `command_template` and `shell_command` metadata
- `scripts/omo_debt.py` — generate and render owner-routing outputs during refresh
- `.omo/tests/test_omo_debt_registry.py` — assert `owner_routing_ref`
- `.omo/tests/test_omo_debt_cli.py` — keep minimal registry fixtures aligned with the new required ref
- `.omo/tests/test_omo_automation.py` — keep registry-backed fixtures aligned with the new required ref
- `.omo/tests/test_omo_debt_action_packet.py` — assert action-packet command metadata contract
- `.omo/tests/test_omo_debt_outputs.py` — assert refresh writes owner-routing YAML + Markdown
- `.omo/tests/test_omo_debt_docs.py` — assert `.omo/AGENT.md` documents owner routing
- `.omo/AGENT.md` — explain the owner-routing surface and execution-safe command guidance

### Generated artifacts refreshed during implementation

- `.omo/debt/action-packet/current.yaml`
- `.omo/debt/action-packet/current.md`
- `.omo/debt/owner-routing/current.yaml`
- `.omo/debt/owner-routing/current.md`
- `.omo/debt/dashboard/current.yaml`
- `.omo/debt/review-queue/current.yaml`
- `.omo/debt/reviews/current.md`

### Repository-boundary note

The workspace root treats `scripts/` as a nested git repository/gitlink. When a task touches both root-tracked files and `scripts/*`, make two commits:

1. a commit inside `/Users/xiamingxing/Workspace/scripts`
2. a root-repo commit inside `/Users/xiamingxing/Workspace` that records the updated `scripts` pointer plus root files

Do not try to commit `scripts/*` pathspecs directly from the root repo.

### Existing files to read before implementation

- `docs/superpowers/specs/2026-06-02-debt-owner-routing-packet-design.md`
- `scripts/omo_debt.py`
- `scripts/omo_debt_action_packet.py`
- `scripts/omo_debt_registry.py`
- `.omo/tests/test_omo_debt_action_packet.py`
- `.omo/tests/test_omo_debt_outputs.py`
- `.omo/tests/test_omo_debt_docs.py`
- `.omo/AGENT.md`

---

### Task 1: Extend the debt registry contract for owner routing

**Files:**
- Modify: `/Users/xiamingxing/Workspace/.omo/debt/registry.yaml`
- Modify: `/Users/xiamingxing/Workspace/scripts/omo_debt_registry.py`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_registry.py`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_cli.py`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Write the failing registry contract assertion**

Update `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_registry.py` so the output contract includes the new owner-routing ref:

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
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_registry.py::test_debt_registry_lists_seed_items_and_outputs -q
```

Expected: FAIL with `KeyError: 'owner_routing_ref'`.

- [ ] **Step 3: Add the owner-routing ref to the registry and loader**

Update `/Users/xiamingxing/Workspace/.omo/debt/registry.yaml`:

```yaml
version: 1
items_dir: .omo/debt/items
dashboard_ref: .omo/debt/dashboard/current.yaml
review_pack_ref: .omo/debt/reviews/current.md
review_queue_ref: .omo/debt/review-queue/current.yaml
action_packet_ref: .omo/debt/action-packet/current.yaml
owner_routing_ref: .omo/debt/owner-routing/current.yaml
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

Update `/Users/xiamingxing/Workspace/scripts/omo_debt_registry.py`:

```python
@dataclass(frozen=True)
class DebtLedger:
    registry_ref: str
    dashboard_ref: str
    review_pack_ref: str
    review_queue_ref: str
    action_packet_ref: str
    owner_routing_ref: str
    items: tuple[DebtItem, ...]


return DebtLedger(
    registry_ref=".omo/debt/registry.yaml",
    dashboard_ref=registry["dashboard_ref"],
    review_pack_ref=registry["review_pack_ref"],
    review_queue_ref=registry["review_queue_ref"],
    action_packet_ref=registry["action_packet_ref"],
    owner_routing_ref=registry["owner_routing_ref"],
    items=tuple(items),
)
```

- [ ] **Step 4: Align all registry-writing fixtures**

Update `/Users/xiamingxing/Workspace/.omo/tests/test_omo_automation.py`:

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
        "seed_items": seed_items,
    },
)
```

Update `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_cli.py`:

```python
(debt_dir / "registry.yaml").write_text(
    "version: 1\n"
    "items_dir: .omo/debt/items\n"
    "dashboard_ref: .omo/debt/dashboard/current.yaml\n"
    "review_pack_ref: .omo/debt/reviews/current.md\n"
    "review_queue_ref: .omo/debt/review-queue/current.yaml\n"
    "action_packet_ref: .omo/debt/action-packet/current.yaml\n"
    "owner_routing_ref: .omo/debt/owner-routing/current.yaml\n"
    "seed_items: []\n",
    encoding="utf-8",
)
```

- [ ] **Step 5: Run the affected tests to verify they pass**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_registry.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_automation.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit both repos**

Commit the `scripts` repo:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_registry.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): add owner routing registry metadata\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Commit the root repo:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/debt/registry.yaml .omo/tests/test_omo_debt_registry.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_automation.py scripts && git -c core.hooksPath=/dev/null commit -m $'feat(omo): register debt owner routing surface\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 2: Harden action-packet command metadata for routed execution

**Files:**
- Modify: `/Users/xiamingxing/Workspace/scripts/omo_debt_action_packet.py`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_action_packet.py`

- [ ] **Step 1: Extend the failing action-packet tests**

Update `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_action_packet.py` so routed execution fields are part of the contract:

```python
assert packet["lanes"]["revalidate_now"][0]["command_template"] == (
    "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id REVALIDATE --reviewed-at <RUN_AT>"
)
assert packet["lanes"]["revalidate_now"][0]["shell_command"] == (
    "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id REVALIDATE --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
)
assert packet["lanes"]["schedule_now"][0]["command_template"] == (
    "python3 scripts/omo_debt.py schedule --omo-dir .omo --id SCHEDULE --next-review-at <NEXT_REVIEW_AT>"
)
assert packet["lanes"]["schedule_now"][0]["shell_command"] == (
    "python3 scripts/omo_debt.py schedule --omo-dir .omo --id SCHEDULE --next-review-at 2026-06-17T00:00:00Z"
)
assert packet["lanes"]["continue_mitigation"][0]["shell_command"] == (
    "manual: continue mitigation with omo-governance"
)
```

- [ ] **Step 2: Run the action-packet test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_action_packet.py::test_build_action_packet_routes_entries_into_primary_lanes -q
```

Expected: FAIL with `KeyError: 'command_template'` or `KeyError: 'shell_command'`.

- [ ] **Step 3: Add execution-safe command helpers to the action packet**

Update `/Users/xiamingxing/Workspace/scripts/omo_debt_action_packet.py`:

```python
def _revalidate_command_template(item_id: str) -> str:
    return f"python3 scripts/omo_debt.py revalidate --omo-dir .omo --id {item_id} --reviewed-at <RUN_AT>"


def _revalidate_shell_command(item_id: str) -> str:
    return (
        "python3 scripts/omo_debt.py revalidate --omo-dir .omo "
        f"--id {item_id} --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    )


def _schedule_command_template(item_id: str) -> str:
    return f"python3 scripts/omo_debt.py schedule --omo-dir .omo --id {item_id} --next-review-at <NEXT_REVIEW_AT>"
```

Populate the fields inside each lane entry:

```python
{
    **entry,
    "current_lane": "revalidate_now",
    "recommended_action": "revalidate",
    "reason": "stale_due_item",
    "command_template": _revalidate_command_template(entry["id"]),
    "shell_command": _revalidate_shell_command(entry["id"]),
    "suggested_command": _revalidate_shell_command(entry["id"]),
}
```

For `schedule_now`:

```python
{
    **entry,
    "current_lane": "schedule_now",
    "recommended_action": "schedule",
    "reason": "missing_next_review_at",
    "command_template": _schedule_command_template(entry["id"]),
    "shell_command": _schedule_command(entry["id"], now, review_window_days),
    "suggested_command": _schedule_command(entry["id"], now, review_window_days),
}
```

For manual lanes:

```python
{
    **entry,
    "current_lane": "continue_mitigation",
    "recommended_action": "continue_mitigation",
    "reason": "active_mitigation_due",
    "command_template": "manual: continue mitigation with <OWNER>",
    "shell_command": f"manual: continue mitigation with {entry['owner']}",
    "suggested_command": f"manual: continue mitigation with {entry['owner']}",
}
```

- [ ] **Step 4: Run the focused action-packet regressions**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_action_packet.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit both repos**

Commit the `scripts` repo:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_action_packet.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): harden debt action packet commands\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Commit the root repo:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/tests/test_omo_debt_action_packet.py scripts && git -c core.hooksPath=/dev/null commit -m $'test(omo): cover action packet command templates\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 3: Add the owner-routing builder

**Files:**
- Create: `/Users/xiamingxing/Workspace/scripts/omo_debt_owner_routing.py`
- Create: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_owner_routing.py`

- [ ] **Step 1: Write the failing owner-routing tests**

Create `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_owner_routing.py`:

```python
from __future__ import annotations

import pytest

from scripts.omo_debt_owner_routing import build_owner_routing_packet


def _entry(
    item_id: str,
    *,
    owner: str,
    primary_lane: str = "revalidate_now",
    severity: str = "high",
    gate_level: str = "none",
    overdue_by: int = 0,
    last_reviewed_at: str | None = "2026-06-02T00:00:00Z",
) -> dict[str, object]:
    return {
        "id": item_id,
        "title": f"{item_id} title",
        "owner": owner,
        "current_lane": primary_lane,
        "recommended_action": "revalidate",
        "reason": "stale_due_item",
        "severity": severity,
        "gate_level": gate_level,
        "next_review_at": "2026-06-10T00:00:00Z",
        "last_reviewed_at": last_reviewed_at,
        "stale_evidence": True,
        "overdue_by": overdue_by,
        "command_template": "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id <ID> --reviewed-at <RUN_AT>",
        "shell_command": "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id ITEM --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)",
    }


def test_build_owner_routing_groups_entries_by_owner_and_sets_flags() -> None:
    action_packet = {
        "generated_at": "2026-06-10T00:00:00Z",
        "defaults": {"review_window_days": 7, "escalation_threshold_days": 3},
        "lanes": {
            "revalidate_now": [
                _entry("A_GATE", owner="sharedbrain-governance", severity="critical", gate_level="gate", overdue_by=4),
                _entry("A_FIRST", owner="omo-governance", overdue_by=2, last_reviewed_at=None),
            ],
            "schedule_now": [],
            "escalate_now": [],
            "continue_mitigation": [],
            "watch_only": [],
        },
        "summary": {},
    }

    packet = build_owner_routing_packet(action_packet)

    assert [owner["owner"] for owner in packet["owners"]] == ["sharedbrain-governance", "omo-governance"]
    assert packet["owners"][0]["entries"][0]["priority_flags"] == ["gate_attention", "escalation_watch"]
    assert packet["owners"][1]["entries"][0]["priority_flags"] == ["initial_review_required"]


def test_build_owner_routing_normalizes_ownerless_entries_and_rejects_unknown_lanes() -> None:
    action_packet = {
        "generated_at": "2026-06-10T00:00:00Z",
        "defaults": {"review_window_days": 7, "escalation_threshold_days": 3},
        "lanes": {
            "revalidate_now": [_entry("UNOWNED", owner="")],
            "schedule_now": [],
            "escalate_now": [],
            "continue_mitigation": [],
            "watch_only": [],
        },
        "summary": {},
    }

    packet = build_owner_routing_packet(action_packet)
    assert packet["owners"][0]["owner"] == "unowned"

    broken_packet = {
        **action_packet,
        "lanes": {
            **action_packet["lanes"],
            "mystery_lane": [_entry("BROKEN", owner="omo-governance")],
        },
    }

    with pytest.raises(ValueError, match="unknown primary lane"):
        build_owner_routing_packet(broken_packet)
```

- [ ] **Step 2: Run the owner-routing test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_owner_routing.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.omo_debt_owner_routing'`.

- [ ] **Step 3: Write the minimal owner-routing builder**

Create `/Users/xiamingxing/Workspace/scripts/omo_debt_owner_routing.py`:

```python
from __future__ import annotations


LANE_PRIORITY = {
    "revalidate_now": 0,
    "schedule_now": 1,
    "escalate_now": 2,
    "continue_mitigation": 3,
    "watch_only": 4,
}

SEVERITY_PRIORITY = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


def _priority_flags(entry: dict[str, object], escalation_threshold_days: int) -> list[str]:
    flags: list[str] = []
    if entry.get("last_reviewed_at") is None:
        flags.append("initial_review_required")
    if entry.get("gate_level") == "gate":
        flags.append("gate_attention")
    if entry.get("current_lane") == "revalidate_now" and int(entry.get("overdue_by", 0)) >= escalation_threshold_days:
        flags.append("escalation_watch")
    if entry.get("current_lane") == "continue_mitigation":
        flags.append("active_mitigation")
    return flags


def build_owner_routing_packet(action_packet: dict[str, object]) -> dict[str, object]:
    defaults = action_packet["defaults"]
    grouped: dict[str, list[dict[str, object]]] = {}
    for lane_name, entries in action_packet["lanes"].items():
        if lane_name not in LANE_PRIORITY:
            raise ValueError(f"unknown primary lane: {lane_name}")
        for entry in entries:
            owner = entry.get("owner") or "unowned"
            grouped.setdefault(owner, []).append(
                {
                    **entry,
                    "primary_lane": lane_name,
                    "priority_flags": _priority_flags(entry, int(defaults["escalation_threshold_days"])),
                }
            )
```

Continue with deterministic ordering and summaries:

```python
    owners = []
    for owner, entries in grouped.items():
        ordered_entries = sorted(
            entries,
            key=lambda item: (
                LANE_PRIORITY[item["primary_lane"]],
                0 if item["gate_level"] == "gate" else 1,
                SEVERITY_PRIORITY[item["severity"]],
                -int(item.get("overdue_by", 0)),
                item["id"],
            ),
        )
        owners.append(
            {
                "owner": owner,
                "summary": {
                    "total_count": len(ordered_entries),
                    "lane_counts": {
                        lane: sum(1 for item in ordered_entries if item["primary_lane"] == lane)
                        for lane in LANE_PRIORITY
                    },
                },
                "entries": ordered_entries,
            }
        )
    owners.sort(key=lambda owner: (
        0 if any("gate_attention" in item["priority_flags"] for item in owner["entries"]) else 1,
        min(SEVERITY_PRIORITY[item["severity"]] for item in owner["entries"]),
        -owner["summary"]["lane_counts"]["revalidate_now"],
        -max(int(item.get("overdue_by", 0)) for item in owner["entries"]),
        owner["owner"],
    ))
    return {
        "generated_at": action_packet["generated_at"],
        "source_action_packet_ref": ".omo/debt/action-packet/current.yaml",
        "defaults": defaults,
        "owners": owners,
        "summary": {
            "owner_count": len(owners),
            "total_routed_items": sum(owner["summary"]["total_count"] for owner in owners),
            "lane_counts": {
                lane: sum(owner["summary"]["lane_counts"][lane] for owner in owners)
                for lane in LANE_PRIORITY
            },
        },
    }
```

- [ ] **Step 4: Run the focused owner-routing tests**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_owner_routing.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit both repos**

Commit the `scripts` repo:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_owner_routing.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): add debt owner routing builder\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Commit the root repo:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/tests/test_omo_debt_owner_routing.py scripts && git -c core.hooksPath=/dev/null commit -m $'test(omo): add owner routing packet coverage\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 4: Wire refresh to generate owner-routing YAML and Markdown

**Files:**
- Modify: `/Users/xiamingxing/Workspace/scripts/omo_debt.py`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_outputs.py`

- [ ] **Step 1: Make the output regression fail on the missing owner-routing files**

Update `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_outputs.py`:

```python
owner_yaml = yaml.safe_load((tmp_path / ".omo" / "debt" / "owner-routing" / "current.yaml").read_text(encoding="utf-8"))
owner_md = (tmp_path / ".omo" / "debt" / "owner-routing" / "current.md").read_text(encoding="utf-8")

assert [owner["owner"] for owner in owner_yaml["owners"]] == [
    "sharedbrain-governance",
    "commerce-governance",
    "platform-governance",
    "omo-governance",
]
omo_owner = next(owner for owner in owner_yaml["owners"] if owner["owner"] == "omo-governance")
assert "initial_review_required" in {
    flag
    for entry in omo_owner["entries"]
    for flag in entry["priority_flags"]
}
assert "## Owner: sharedbrain-governance" in owner_md
assert "### Revalidate Now" in owner_md
```

- [ ] **Step 2: Run the output test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_outputs.py::test_debt_refresh_writes_dashboard_review_queue_and_action_packet -q
```

Expected: FAIL with `FileNotFoundError` for `.omo/debt/owner-routing/current.yaml`.

- [ ] **Step 3: Extend refresh to write owner-routing outputs**

Update the import block in `/Users/xiamingxing/Workspace/scripts/omo_debt.py`:

```python
try:
    from scripts.omo_debt_action_packet import build_action_packet
    from scripts.omo_debt_owner_routing import build_owner_routing_packet
    from scripts.omo_debt_metrics import compute_debt_metrics
    from scripts.omo_debt_registry import DebtItem, load_debt_ledger
    from scripts.omo_debt_review_queue import build_review_queue
except ModuleNotFoundError:
    from omo_debt_action_packet import build_action_packet
    from omo_debt_owner_routing import build_owner_routing_packet
    from omo_debt_metrics import compute_debt_metrics
    from omo_debt_registry import DebtItem, load_debt_ledger
    from omo_debt_review_queue import build_review_queue
```

Add Markdown rendering:

```python
def _render_owner_routing_section(owner_packet: dict[str, object]) -> str:
    lines = [f"## Owner: {owner_packet['owner']}", ""]
    lines.append(
        "Summary: "
        f"{owner_packet['summary']['total_count']} items; "
        f"revalidate_now={owner_packet['summary']['lane_counts']['revalidate_now']}, "
        f"schedule_now={owner_packet['summary']['lane_counts']['schedule_now']}, "
        f"escalate_now={owner_packet['summary']['lane_counts']['escalate_now']}"
    )
    lines.append("")
```

Render grouped subsections:

```python
    for lane_title, lane_name in [
        ("Revalidate Now", "revalidate_now"),
        ("Schedule Now", "schedule_now"),
        ("Escalate Now", "escalate_now"),
        ("Continue Mitigation", "continue_mitigation"),
        ("Watch Only", "watch_only"),
    ]:
        lane_entries = [entry for entry in owner_packet["entries"] if entry["primary_lane"] == lane_name]
        if not lane_entries:
            continue
        lines.extend([f"### {lane_title}", ""])
        for entry in lane_entries:
            flags = ", ".join(entry["priority_flags"]) or "none"
            lines.append(f"- `{entry['id']}` — {entry['reason']} — flags: {flags} — `{entry['shell_command']}`")
        lines.append("")
    return "\n".join(lines)
```

Add the writer and refresh wiring:

```python
def write_owner_routing(omo_dir: Path, owner_routing: dict[str, object]) -> None:
    _write_yaml(omo_dir / "debt" / "owner-routing" / "current.yaml", owner_routing)
    markdown = "\n".join(
        [
            f"# Debt Owner Routing Packet\n\nGenerated at: {owner_routing['generated_at']}\n",
            f"Owners: {owner_routing['summary']['owner_count']}\n",
            f"Total routed items: {owner_routing['summary']['total_routed_items']}\n",
            (
                "Lane counts: "
                f"revalidate_now={owner_routing['summary']['lane_counts']['revalidate_now']}, "
                f"schedule_now={owner_routing['summary']['lane_counts']['schedule_now']}, "
                f"escalate_now={owner_routing['summary']['lane_counts']['escalate_now']}, "
                f"continue_mitigation={owner_routing['summary']['lane_counts']['continue_mitigation']}, "
                f"watch_only={owner_routing['summary']['lane_counts']['watch_only']}\n"
            ),
            *[_render_owner_routing_section(owner) for owner in owner_routing["owners"]],
        ]
    )
    path = omo_dir / "debt" / "owner-routing" / "current.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")


def refresh_outputs(omo_dir: Path, now: str) -> None:
    ledger = load_debt_ledger(omo_dir)
    metrics = compute_debt_metrics(ledger.items, now=now, repo_root=omo_dir.parent)
    review_queue = build_review_queue(ledger.items, now=now, repo_root=omo_dir.parent)
    action_packet = build_action_packet(review_queue, now=now)
    owner_routing = build_owner_routing_packet(action_packet)
    write_dashboard(omo_dir, metrics, review_queue, now)
    write_review_queue(omo_dir, review_queue)
    write_review_pack(omo_dir, ledger.items, metrics, review_queue, now)
    write_action_packet(omo_dir, action_packet)
    write_owner_routing(omo_dir, owner_routing)
```

- [ ] **Step 4: Run the focused output regressions**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_outputs.py .omo/tests/test_omo_debt_action_packet.py .omo/tests/test_omo_debt_owner_routing.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit both repos**

Commit the `scripts` repo:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): generate debt owner routing outputs\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Commit the root repo:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/tests/test_omo_debt_outputs.py scripts && git -c core.hooksPath=/dev/null commit -m $'test(omo): cover owner routing refresh outputs\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 5: Document owner routing, refresh artifacts, and run canonical verification

**Files:**
- Modify: `/Users/xiamingxing/Workspace/.omo/AGENT.md`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_docs.py`
- Refresh: `/Users/xiamingxing/Workspace/.omo/debt/dashboard/current.yaml`
- Refresh: `/Users/xiamingxing/Workspace/.omo/debt/review-queue/current.yaml`
- Refresh: `/Users/xiamingxing/Workspace/.omo/debt/reviews/current.md`
- Refresh: `/Users/xiamingxing/Workspace/.omo/debt/action-packet/current.yaml`
- Refresh: `/Users/xiamingxing/Workspace/.omo/debt/action-packet/current.md`
- Refresh: `/Users/xiamingxing/Workspace/.omo/debt/owner-routing/current.yaml`
- Refresh: `/Users/xiamingxing/Workspace/.omo/debt/owner-routing/current.md`

- [ ] **Step 1: Write the failing docs regression**

Update `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_docs.py`:

```python
assert ".omo/debt/owner-routing/current.yaml" in content
assert ".omo/debt/owner-routing/current.md" in content
assert "owner routing" in content.lower()
assert "initial_review_required" in content
assert "command template" in content.lower()
assert "shell example" in content.lower()
```

- [ ] **Step 2: Run the docs test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py::test_omo_agent_documents_debt_refresh_flow -q
```

Expected: FAIL with an `AssertionError` because `.omo/AGENT.md` does not mention owner routing yet.

- [ ] **Step 3: Update the operator docs**

Update `/Users/xiamingxing/Workspace/.omo/AGENT.md` in the debt refresh section:

```markdown
- `.omo/debt/action-packet/current.yaml` remains the owner-neutral next-action surface
- `.omo/debt/owner-routing/current.yaml` is the machine-readable owner execution surface
- `.omo/debt/owner-routing/current.md` is the human-readable owner execution packet
- Owner-routing packets preserve one primary lane per debt item and add flags such as `initial_review_required`, `gate_attention`, and `escalation_watch`
- Revalidation guidance now uses execution-safe command templates and shell examples instead of a stale literal review timestamp
```

- [ ] **Step 4: Refresh the repo-local generated artifacts**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 scripts/omo_debt.py refresh --omo-dir .omo --now 2026-06-10T00:00:00Z
```

Expected: `refreshed debt outputs`

- [ ] **Step 5: Run focused regressions**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py .omo/tests/test_omo_debt_outputs.py .omo/tests/test_omo_debt_action_packet.py .omo/tests/test_omo_debt_owner_routing.py -q
```

Expected: PASS.

- [ ] **Step 6: Run canonical verification**

Run:

```bash
cd /Users/xiamingxing/Workspace && bash bin/verify-omo.sh
```

Expected: PASS, with sync + active-task validation + full `.omo` regression suite green.

- [ ] **Step 7: Commit the root repo**

```bash
cd /Users/xiamingxing/Workspace && git add .omo/AGENT.md .omo/tests/test_omo_debt_docs.py .omo/debt/dashboard/current.yaml .omo/debt/review-queue/current.yaml .omo/debt/reviews/current.md .omo/debt/action-packet/current.yaml .omo/debt/action-packet/current.md .omo/debt/owner-routing/current.yaml .omo/debt/owner-routing/current.md && git -c core.hooksPath=/dev/null commit -m $'docs(omo): document debt owner routing workflow\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```
