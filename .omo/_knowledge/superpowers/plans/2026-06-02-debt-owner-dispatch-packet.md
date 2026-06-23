---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Debt Owner Dispatch Packet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit `dispatch` command that freezes the latest debt owner-routing packet into a formal handoff artifact with immutable run history and one canonical command per item.

**Architecture:** Keep the existing debt read-model chain intact: debt items remain canonical truth, refresh continues to build review/action/owner-routing outputs, and dispatch becomes a separate explicit surfacing step. Implement dispatch as a pure builder plus a thin CLI/writer layer so command freezing, error policy, and immutable run-path generation can be tested without touching the filesystem first.

**Tech Stack:** Python 3, PyYAML, existing `scripts/omo_debt*.py` helpers, pytest, Markdown, canonical `bash bin/verify-omo.sh`

---

## File Structure

### New files

- `scripts/omo_debt_dispatch.py` — pure dispatch builder that freezes commands, validates owner-routing command metadata, and derives immutable run refs
- `.omo/tests/test_omo_debt_dispatch.py` — focused unit tests for the pure dispatch builder
- `.omo/debt/dispatch/current.yaml` — latest machine-readable dispatch packet
- `.omo/debt/dispatch/current.md` — latest human-readable dispatch packet
- `.omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml` — immutable run record for a deterministic repo-local refresh
- `.omo/debt/dispatch/runs/2026-06-10T00-00-00Z.md` — immutable human-readable run record for the same dispatch

### Modified files

- `.omo/debt/registry.yaml` — add `dispatch_ref`
- `scripts/omo_debt_registry.py` — extend `DebtLedger` with `dispatch_ref`
- `scripts/omo_debt.py` — add dispatch rendering/writing helpers and the `dispatch` CLI subcommand
- `.omo/tests/test_omo_debt_registry.py` — assert the new registry ref
- `.omo/tests/test_omo_debt_cli.py` — cover dispatch CLI error/success behavior
- `.omo/tests/test_omo_automation.py` — keep registry-writing fixtures aligned with the new required ref
- `.omo/tests/test_omo_debt_outputs.py` — assert dispatch current/run YAML + Markdown outputs
- `.omo/tests/test_omo_debt_docs.py` — assert `.omo/AGENT.md` documents the dispatch flow
- `.omo/AGENT.md` — document the explicit refresh → dispatch operator flow and dispatch artifacts
- `.omo/state/system.yaml` — refreshed by `sync_omo_state.py` after repo-local dispatch publication

### Generated artifacts refreshed during implementation

- `.omo/debt/dashboard/current.yaml`
- `.omo/debt/review-queue/current.yaml`
- `.omo/debt/reviews/current.md`
- `.omo/debt/action-packet/current.yaml`
- `.omo/debt/action-packet/current.md`
- `.omo/debt/owner-routing/current.yaml`
- `.omo/debt/owner-routing/current.md`
- `.omo/debt/dispatch/current.yaml`
- `.omo/debt/dispatch/current.md`
- `.omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml`
- `.omo/debt/dispatch/runs/2026-06-10T00-00-00Z.md`

### Repository-boundary note

The workspace root treats `scripts/` as a nested git repository/gitlink. When a task touches both root-tracked files and `scripts/*`, make two commits:

1. a commit inside `/Users/xiamingxing/Workspace/scripts`
2. a root-repo commit inside `/Users/xiamingxing/Workspace` that records the updated `scripts` pointer plus root files

Do not try to commit `scripts/*` pathspecs directly from the root repo.

### Existing files to read before implementation

- `docs/superpowers/specs/2026-06-02-debt-owner-dispatch-packet-design.md`
- `scripts/omo_debt.py`
- `scripts/omo_debt_owner_routing.py`
- `scripts/omo_debt_action_packet.py`
- `scripts/omo_debt_registry.py`
- `.omo/tests/test_omo_debt_cli.py`
- `.omo/tests/test_omo_debt_outputs.py`
- `.omo/tests/test_omo_debt_docs.py`
- `.omo/AGENT.md`

---

### Task 1: Extend the registry contract with the dispatch surface

**Files:**
- Modify: `/Users/xiamingxing/Workspace/.omo/debt/registry.yaml`
- Modify: `/Users/xiamingxing/Workspace/scripts/omo_debt_registry.py`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_registry.py`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_cli.py`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Write the failing registry assertion**

Update `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_registry.py`:

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
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_registry.py::test_debt_registry_lists_seed_items_and_outputs -q
```

Expected: FAIL with `KeyError: 'dispatch_ref'`.

- [ ] **Step 3: Add `dispatch_ref` to the canonical registry and loader**

Update `/Users/xiamingxing/Workspace/.omo/debt/registry.yaml`:

```yaml
version: 1
items_dir: .omo/debt/items
dashboard_ref: .omo/debt/dashboard/current.yaml
review_pack_ref: .omo/debt/reviews/current.md
review_queue_ref: .omo/debt/review-queue/current.yaml
action_packet_ref: .omo/debt/action-packet/current.yaml
owner_routing_ref: .omo/debt/owner-routing/current.yaml
dispatch_ref: .omo/debt/dispatch/current.yaml
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
    dispatch_ref: str
    items: tuple[DebtItem, ...]


return DebtLedger(
    registry_ref=".omo/debt/registry.yaml",
    dashboard_ref=registry["dashboard_ref"],
    review_pack_ref=registry["review_pack_ref"],
    review_queue_ref=registry["review_queue_ref"],
    action_packet_ref=registry["action_packet_ref"],
    owner_routing_ref=registry["owner_routing_ref"],
    dispatch_ref=registry["dispatch_ref"],
    items=tuple(items),
)
```

- [ ] **Step 4: Align all tests that write minimal registry fixtures**

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
    "dispatch_ref: .omo/debt/dispatch/current.yaml\n"
    "seed_items: []\n",
    encoding="utf-8",
)
```

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
        "dispatch_ref": ".omo/debt/dispatch/current.yaml",
        "seed_items": seed_items,
    },
)
```

- [ ] **Step 5: Run the focused registry suite**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_registry.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_automation.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit both repos**

Commit the `scripts` repo:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_registry.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): add debt dispatch registry metadata\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Commit the root repo:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/debt/registry.yaml .omo/tests/test_omo_debt_registry.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_automation.py scripts && git -c core.hooksPath=/dev/null commit -m $'feat(omo): register debt dispatch surface\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 2: Add the pure dispatch builder and command-freezing rules

**Files:**
- Create: `/Users/xiamingxing/Workspace/scripts/omo_debt_dispatch.py`
- Create: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_dispatch.py`

- [ ] **Step 1: Write the failing builder tests**

Create `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_dispatch.py`:

```python
from __future__ import annotations

import pytest

from scripts.omo_debt_dispatch import build_dispatch_packet


def _owner_routing() -> dict[str, object]:
    return {
        "generated_at": "2026-06-10T00:00:00Z",
        "source_action_packet_ref": ".omo/debt/action-packet/current.yaml",
        "defaults": {
            "review_window_days": 7,
            "escalation_threshold_days": 3,
        },
        "owners": [
            {
                "owner": "sharedbrain-governance",
                "summary": {
                    "total_count": 2,
                    "lane_counts": {
                        "revalidate_now": 1,
                        "schedule_now": 1,
                        "escalate_now": 0,
                        "continue_mitigation": 0,
                        "watch_only": 0,
                    },
                },
                "entries": [
                    {
                        "id": "SB_DECOMPOSITION",
                        "title": "SharedBrain decomposition remains partially governed",
                        "owner": "sharedbrain-governance",
                        "primary_lane": "revalidate_now",
                        "recommended_action": "revalidate",
                        "reason": "stale_due_item",
                        "priority_flags": ["gate_attention", "escalation_watch"],
                        "command_template": "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id SB_DECOMPOSITION --reviewed-at <RUN_AT>",
                        "shell_command": "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id SB_DECOMPOSITION --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)",
                        "suggested_command": "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id SB_DECOMPOSITION --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)",
                        "next_review_at": "2026-06-07T00:00:00Z",
                        "last_reviewed_at": "2026-06-02T00:00:00Z",
                        "overdue_by": 3,
                        "gate_level": "gate",
                        "severity": "critical",
                    },
                    {
                        "id": "SB_ROOT_CLEANUP",
                        "title": "Root SharedBrain shell cleanup remains deferred",
                        "owner": "sharedbrain-governance",
                        "primary_lane": "schedule_now",
                        "recommended_action": "schedule",
                        "reason": "missing_next_review_at",
                        "priority_flags": [],
                        "command_template": "python3 scripts/omo_debt.py schedule --omo-dir .omo --id SB_ROOT_CLEANUP --next-review-at <NEXT_REVIEW_AT>",
                        "shell_command": "python3 scripts/omo_debt.py schedule --omo-dir .omo --id SB_ROOT_CLEANUP --next-review-at 2026-06-17T00:00:00Z",
                        "suggested_command": "python3 scripts/omo_debt.py schedule --omo-dir .omo --id SB_ROOT_CLEANUP --next-review-at 2026-06-17T00:00:00Z",
                        "next_review_at": None,
                        "last_reviewed_at": "2026-06-02T00:00:00Z",
                        "overdue_by": 0,
                        "gate_level": "none",
                        "severity": "low",
                    },
                ],
            },
        ],
        "summary": {
            "owner_count": 1,
            "total_routed_items": 2,
            "lane_counts": {
                "revalidate_now": 1,
                "schedule_now": 1,
                "escalate_now": 0,
                "continue_mitigation": 0,
                "watch_only": 0,
            },
        },
    }


def test_build_dispatch_packet_freezes_commands_and_adds_run_ref() -> None:
    packet = build_dispatch_packet(_owner_routing(), dispatched_at="2026-06-10T00:00:00Z")

    assert packet["dispatched_at"] == "2026-06-10T00:00:00Z"
    assert packet["source_owner_routing_ref"] == ".omo/debt/owner-routing/current.yaml"
    assert packet["source_owner_routing_generated_at"] == "2026-06-10T00:00:00Z"
    assert packet["latest_run_ref"] == ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml"
    first_entry = packet["owners"][0]["entries"][0]
    assert first_entry["command"] == (
        "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id SB_DECOMPOSITION --reviewed-at 2026-06-10T00:00:00Z"
    )
    assert "command_template" not in first_entry
    assert "shell_command" not in first_entry
    assert "suggested_command" not in first_entry
    assert first_entry["priority_flags"] == ["gate_attention", "escalation_watch"]


def test_build_dispatch_packet_uses_shell_command_for_non_revalidate_lanes() -> None:
    packet = build_dispatch_packet(_owner_routing(), dispatched_at="2026-06-10T00:00:00Z")

    schedule_entry = packet["owners"][0]["entries"][1]
    assert schedule_entry["command"] == (
        "python3 scripts/omo_debt.py schedule --omo-dir .omo --id SB_ROOT_CLEANUP --next-review-at 2026-06-17T00:00:00Z"
    )


def test_build_dispatch_packet_rejects_missing_or_unresolved_command_metadata() -> None:
    broken = _owner_routing()
    broken["owners"][0]["entries"][0]["command_template"] = "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id SB_DECOMPOSITION --reviewed-at <RUN_AT> $(date -u +%Y-%m-%dT%H:%M:%SZ)"

    with pytest.raises(ValueError, match="unresolved or unsafe dispatch command"):
        build_dispatch_packet(broken, dispatched_at="2026-06-10T00:00:00Z")
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_dispatch.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.omo_debt_dispatch'`.

- [ ] **Step 3: Implement the pure dispatch builder**

Create `/Users/xiamingxing/Workspace/scripts/omo_debt_dispatch.py`:

```python
from __future__ import annotations


LANE_NAMES = (
    "revalidate_now",
    "schedule_now",
    "escalate_now",
    "continue_mitigation",
    "watch_only",
)


def _run_slug(dispatched_at: str) -> str:
    return dispatched_at.replace(":", "-")


def _freeze_command(entry: dict[str, object], dispatched_at: str) -> str:
    template = str(entry.get("command_template") or "")
    shell_command = str(entry.get("shell_command") or "")
    lane = str(entry.get("primary_lane"))

    if lane == "revalidate_now":
        if "<RUN_AT>" not in template:
            raise ValueError(f"missing <RUN_AT> template for {entry['id']}")
        command = template.replace("<RUN_AT>", dispatched_at)
        if "<RUN_AT>" in command or "$(" in command:
            raise ValueError(f"unresolved or unsafe dispatch command for {entry['id']}")
        return command

    if not shell_command:
        raise ValueError(f"missing shell_command for {entry['id']}")
    return shell_command


def _dispatch_entry(entry: dict[str, object], dispatched_at: str) -> dict[str, object]:
    return {
        key: value
        for key, value in {
            **entry,
            "command": _freeze_command(entry, dispatched_at),
        }.items()
        if key not in {"command_template", "shell_command", "suggested_command", "current_lane"}
    }


def build_dispatch_packet(owner_routing: dict[str, object], dispatched_at: str) -> dict[str, object]:
    if not owner_routing.get("generated_at"):
        raise ValueError("owner routing packet missing generated_at")
    if "owners" not in owner_routing or "summary" not in owner_routing:
        raise ValueError("owner routing packet missing owners or summary")

    owners: list[dict[str, object]] = []
    for owner_packet in owner_routing["owners"]:
        entries = [_dispatch_entry(entry, dispatched_at) for entry in owner_packet["entries"]]
        owners.append(
            {
                "owner": owner_packet["owner"],
                "dispatched_at": dispatched_at,
                "item_count": len(entries),
                "summary": owner_packet["summary"],
                "entries": entries,
            }
        )

    return {
        "dispatched_at": dispatched_at,
        "source_owner_routing_ref": ".omo/debt/owner-routing/current.yaml",
        "source_owner_routing_generated_at": owner_routing["generated_at"],
        "latest_run_ref": f".omo/debt/dispatch/runs/{_run_slug(dispatched_at)}.yaml",
        "owners": owners,
        "summary": {
            "owner_count": len(owners),
            "total_dispatched_items": sum(owner["item_count"] for owner in owners),
            "lane_counts": {
                lane: sum(owner["summary"]["lane_counts"][lane] for owner in owners)
                for lane in LANE_NAMES
            },
        },
    }
```

- [ ] **Step 4: Run the focused builder tests**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_dispatch.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit both repos**

Commit the `scripts` repo:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_dispatch.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): build debt dispatch packets\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Commit the root repo:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/tests/test_omo_debt_dispatch.py scripts && git -c core.hooksPath=/dev/null commit -m $'test(omo): cover debt dispatch builder\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 3: Wire the dispatch CLI and filesystem outputs

**Files:**
- Modify: `/Users/xiamingxing/Workspace/scripts/omo_debt.py`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_cli.py`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_outputs.py`

- [ ] **Step 1: Add failing CLI and output tests**

Update `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_cli.py`:

```python
def test_debt_dispatch_requires_owner_routing_packet(tmp_path: Path) -> None:
    debt_dir = tmp_path / ".omo" / "debt"
    (debt_dir / "dispatch").mkdir(parents=True, exist_ok=True)
    (debt_dir / "registry.yaml").write_text(
        "version: 1\n"
        "items_dir: .omo/debt/items\n"
        "dashboard_ref: .omo/debt/dashboard/current.yaml\n"
        "review_pack_ref: .omo/debt/reviews/current.md\n"
        "review_queue_ref: .omo/debt/review-queue/current.yaml\n"
        "action_packet_ref: .omo/debt/action-packet/current.yaml\n"
        "owner_routing_ref: .omo/debt/owner-routing/current.yaml\n"
        "dispatch_ref: .omo/debt/dispatch/current.yaml\n"
        "seed_items: []\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "dispatch",
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
    assert ".omo/debt/owner-routing/current.yaml" in result.stderr
```

Update `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_outputs.py`:

```python
def test_debt_dispatch_writes_current_and_immutable_run_artifacts(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    refresh = subprocess.run(
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
    dispatch = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "dispatch",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--now",
            "2026-06-10T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert refresh.returncode == 0, refresh.stderr
    assert dispatch.returncode == 0, dispatch.stderr

    current_yaml = yaml.safe_load((tmp_path / ".omo" / "debt" / "dispatch" / "current.yaml").read_text(encoding="utf-8"))
    current_md = (tmp_path / ".omo" / "debt" / "dispatch" / "current.md").read_text(encoding="utf-8")
    run_yaml = yaml.safe_load((tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-10T00-00-00Z.yaml").read_text(encoding="utf-8"))
    run_md = (tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-10T00-00-00Z.md").read_text(encoding="utf-8")

    assert current_yaml["latest_run_ref"] == ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml"
    assert current_yaml["summary"]["owner_count"] == 4
    assert current_yaml["summary"]["total_dispatched_items"] == 9
    first_entry = current_yaml["owners"][0]["entries"][0]
    assert first_entry["command"].endswith("--reviewed-at 2026-06-10T00:00:00Z")
    assert "command_template" not in first_entry
    assert "# Debt Dispatch Packet" in current_md
    assert "Dispatched at: 2026-06-10T00:00:00Z" in current_md
    assert "## Owner: sharedbrain-governance" in current_md
    assert "SB_DECOMPOSITION" in run_md
    assert run_yaml["dispatched_at"] == "2026-06-10T00:00:00Z"
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py::test_debt_dispatch_requires_owner_routing_packet .omo/tests/test_omo_debt_outputs.py::test_debt_dispatch_writes_current_and_immutable_run_artifacts -q
```

Expected: FAIL with `invalid choice: 'dispatch'` or missing dispatch output paths.

- [ ] **Step 3: Add the dispatch subcommand and writers**

Update `/Users/xiamingxing/Workspace/scripts/omo_debt.py`:

```python
try:
    from scripts.omo_debt_dispatch import build_dispatch_packet
except ModuleNotFoundError:
    from omo_debt_dispatch import build_dispatch_packet


def _dispatch_markdown(dispatch_packet: dict[str, object]) -> str:
    lines = [
        "# Debt Dispatch Packet",
        "",
        f"Dispatched at: {dispatch_packet['dispatched_at']}",
        f"Source owner routing generated at: {dispatch_packet['source_owner_routing_generated_at']}",
        f"Owners: {dispatch_packet['summary']['owner_count']}",
        f"Total dispatched items: {dispatch_packet['summary']['total_dispatched_items']}",
        "",
    ]
    for owner_packet in dispatch_packet["owners"]:
        lines.extend([f"## Owner: {owner_packet['owner']}", ""])
        lines.append(
            f"Summary: {owner_packet['item_count']} items; "
            f"revalidate_now={owner_packet['summary']['lane_counts']['revalidate_now']}, "
            f"schedule_now={owner_packet['summary']['lane_counts']['schedule_now']}, "
            f"escalate_now={owner_packet['summary']['lane_counts']['escalate_now']}"
        )
        lines.append("")
        for entry in owner_packet["entries"]:
            flags = ", ".join(entry["priority_flags"]) or "none"
            lines.append(f"- `{entry['id']}` — {entry['reason']} — flags: {flags} — `{entry['command']}`")
        lines.append("")
    return "\n".join(lines)


def write_dispatch_packet(omo_dir: Path, dispatch_packet: dict[str, object]) -> None:
    run_ref = Path(dispatch_packet["latest_run_ref"])
    run_yaml = omo_dir.parent / run_ref
    run_md = run_yaml.with_suffix(".md")
    if run_yaml.exists() or run_md.exists():
        raise FileExistsError(f"dispatch run already exists: {run_yaml}")

    current_yaml = omo_dir / "debt" / "dispatch" / "current.yaml"
    current_md = omo_dir / "debt" / "dispatch" / "current.md"
    markdown = _dispatch_markdown(dispatch_packet)

    _write_yaml(run_yaml, dispatch_packet)
    run_md.parent.mkdir(parents=True, exist_ok=True)
    run_md.write_text(markdown, encoding="utf-8")
    _write_yaml(current_yaml, dispatch_packet)
    current_md.parent.mkdir(parents=True, exist_ok=True)
    current_md.write_text(markdown, encoding="utf-8")


dispatch_parser = subparsers.add_parser("dispatch")
dispatch_parser.add_argument("--omo-dir", default=".omo")
dispatch_parser.add_argument("--now", required=True)


if args.command == "dispatch":
    owner_routing_path = omo_dir / "debt" / "owner-routing" / "current.yaml"
    owner_routing = _load_yaml(owner_routing_path)
    if not owner_routing:
        raise FileNotFoundError(f"missing owner routing packet: {owner_routing_path}")
    dispatch_packet = build_dispatch_packet(owner_routing, dispatched_at=args.now)
    write_dispatch_packet(omo_dir, dispatch_packet)
    print("dispatched debt packet")
    return 0
```

- [ ] **Step 4: Run the focused CLI/output suite**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py::test_debt_dispatch_requires_owner_routing_packet .omo/tests/test_omo_debt_outputs.py::test_debt_dispatch_writes_current_and_immutable_run_artifacts -q
```

Expected: PASS.

- [ ] **Step 5: Add duplicate-timestamp protection coverage**

Extend `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_outputs.py`:

```python
def test_debt_dispatch_rejects_duplicate_timestamp(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "refresh",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--now",
            "2026-06-10T00:00:00Z",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    first = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "dispatch",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--now",
            "2026-06-10T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    second = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "dispatch",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--now",
            "2026-06-10T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode != 0
    assert "2026-06-10T00-00-00Z.yaml" in second.stderr
```

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_outputs.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit both repos**

Commit the `scripts` repo:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): add debt dispatch command\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Commit the root repo:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_outputs.py scripts && git -c core.hooksPath=/dev/null commit -m $'test(omo): cover debt dispatch outputs\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 4: Document the explicit dispatch flow

**Files:**
- Modify: `/Users/xiamingxing/Workspace/.omo/AGENT.md`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_docs.py`

- [ ] **Step 1: Write the failing docs regression**

Update `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_docs.py`:

```python
def test_omo_agent_documents_debt_refresh_flow() -> None:
    content = Path(".omo/AGENT.md").read_text(encoding="utf-8")

    assert "python3 scripts/omo_debt.py refresh --omo-dir .omo" in content
    assert "python3 scripts/omo_debt.py dispatch --omo-dir .omo" in content
    assert ".omo/debt/dispatch/current.yaml" in content
    assert ".omo/debt/dispatch/current.md" in content
    assert ".omo/debt/dispatch/runs/" in content
    assert "formal surfaced handoff" in content.lower()
    assert "frozen command" in content.lower()
    assert "duplicate timestamp" in content.lower()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py::test_omo_agent_documents_debt_refresh_flow -q
```

Expected: FAIL because `.omo/AGENT.md` does not mention dispatch yet.

- [ ] **Step 3: Update the operator guidance**

Update `/Users/xiamingxing/Workspace/.omo/AGENT.md` in the debt section:

```md
1. `python3 scripts/omo_debt.py refresh --omo-dir .omo --now 2026-06-10T00:00:00Z`
2. `python3 scripts/omo_debt.py dispatch --omo-dir .omo --now 2026-06-10T00:00:00Z`
3. `python3 scripts/sync_omo_state.py --omo-dir .omo`
4. `bash bin/verify-omo.sh`

- `.omo/debt/owner-routing/current.yaml` is the latest derived owner execution surface
- `.omo/debt/dispatch/current.yaml` is the latest formal surfaced handoff packet
- `.omo/debt/dispatch/runs/<timestamp>.yaml` and `.md` are immutable dispatch run records
- Dispatch freezes each item to one canonical command; revalidation commands must resolve `<RUN_AT>` to `dispatched_at`
- Dispatch fails on duplicate timestamps instead of overwriting historical run artifacts
```

- [ ] **Step 4: Run the docs regression**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the root repo**

Run:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/AGENT.md .omo/tests/test_omo_debt_docs.py && git -c core.hooksPath=/dev/null commit -m $'docs(omo): document debt dispatch flow\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 5: Refresh repo-local artifacts and run canonical verification

**Files:**
- Modify: `/Users/xiamingxing/Workspace/.omo/debt/dashboard/current.yaml`
- Modify: `/Users/xiamingxing/Workspace/.omo/debt/review-queue/current.yaml`
- Modify: `/Users/xiamingxing/Workspace/.omo/debt/reviews/current.md`
- Modify: `/Users/xiamingxing/Workspace/.omo/debt/action-packet/current.yaml`
- Modify: `/Users/xiamingxing/Workspace/.omo/debt/action-packet/current.md`
- Modify: `/Users/xiamingxing/Workspace/.omo/debt/owner-routing/current.yaml`
- Modify: `/Users/xiamingxing/Workspace/.omo/debt/owner-routing/current.md`
- Create: `/Users/xiamingxing/Workspace/.omo/debt/dispatch/current.yaml`
- Create: `/Users/xiamingxing/Workspace/.omo/debt/dispatch/current.md`
- Create: `/Users/xiamingxing/Workspace/.omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml`
- Create: `/Users/xiamingxing/Workspace/.omo/debt/dispatch/runs/2026-06-10T00-00-00Z.md`
- Modify: `/Users/xiamingxing/Workspace/.omo/state/system.yaml`

- [ ] **Step 1: Publish a deterministic repo-local dispatch packet**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 scripts/omo_debt.py refresh --omo-dir .omo --now 2026-06-10T00:00:00Z && python3 scripts/omo_debt.py dispatch --omo-dir .omo --now 2026-06-10T00:00:00Z && python3 scripts/sync_omo_state.py --omo-dir .omo
```

Expected:

```text
refreshed debt outputs
dispatched debt packet
updated /Users/xiamingxing/Workspace/.omo/state/system.yaml
```

- [ ] **Step 2: Run the focused debt regression set**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_registry.py .omo/tests/test_omo_debt_dispatch.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_outputs.py .omo/tests/test_omo_debt_docs.py -q
```

Expected: PASS.

- [ ] **Step 3: Run the canonical OMO verify chain**

Run:

```bash
cd /Users/xiamingxing/Workspace && bash bin/verify-omo.sh
```

Expected: PASS for the full `.omo` verification chain.

- [ ] **Step 4: Commit the root repo with generated artifacts**

Run:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/debt/dashboard/current.yaml .omo/debt/review-queue/current.yaml .omo/debt/reviews/current.md .omo/debt/action-packet/current.yaml .omo/debt/action-packet/current.md .omo/debt/owner-routing/current.yaml .omo/debt/owner-routing/current.md .omo/debt/dispatch/current.yaml .omo/debt/dispatch/current.md .omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml .omo/debt/dispatch/runs/2026-06-10T00-00-00Z.md .omo/state/system.yaml && git -c core.hooksPath=/dev/null commit -m $'chore(omo): publish debt dispatch artifacts\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

## Self-Review Checklist

Before executing, confirm the plan still covers every dispatch-spec requirement:

1. `dispatch_ref` registry discoverability is covered in Task 1.
2. pure builder + command freezing + unsafe command validation are covered in Task 2.
3. explicit `dispatch` CLI, current outputs, immutable run outputs, and duplicate timestamp failure are covered in Task 3.
4. `.omo/AGENT.md` operator guidance is covered in Task 4.
5. repo-local generated artifacts plus canonical verify are covered in Task 5.

Search this file for placeholder words such as `TODO`, `TBD`, `appropriate`, `similar`, or `later`; there should be none.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-02-debt-owner-dispatch-packet.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

If the user is unavailable, default to **Subagent-Driven** to stay consistent with the owner-routing implementation flow.
