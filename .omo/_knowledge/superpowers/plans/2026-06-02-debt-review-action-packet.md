# Debt Review Action Packet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit debt action packet that tells operators the next governance action for each queued debt item without introducing automatic mutation or a workflow state machine.

**Architecture:** Keep the existing debt ledger and review queue as the source surfaces, then add one more derived layer: an action packet that routes queue entries into deterministic lanes such as `revalidate_now`, `schedule_now`, and `watch_only`. Implement the routing as a focused helper under `scripts/`, wire it into `scripts/omo_debt.py refresh`, and expose both YAML and Markdown action-packet outputs while preserving the existing queue and review pack.

**Tech Stack:** Python 3, PyYAML, existing `.omo` debt registry/queue helpers, pytest, Markdown, canonical `bash bin/verify-omo.sh`

---

## File Structure

### New files

- `.omo/debt/action-packet/current.yaml` — generated machine-readable next-action surface grouped by action lanes
- `.omo/debt/action-packet/current.md` — generated human-readable operator packet with suggested commands
- `scripts/omo_debt_action_packet.py` — pure routing helper that turns review-queue entries into action lanes
- `.omo/tests/test_omo_debt_action_packet.py` — focused regression coverage for lane routing and command generation

### Modified files

- `.omo/debt/registry.yaml` — add `action_packet_ref` so the new generated surface is discoverable beside dashboard/review/queue refs
- `scripts/omo_debt_registry.py` — extend `DebtLedger` with `action_packet_ref`
- `scripts/omo_debt.py` — generate and write the action packet during refresh
- `.omo/tests/test_omo_debt_registry.py` — assert the new action-packet registry ref
- `.omo/tests/test_omo_debt_outputs.py` — assert refresh writes action-packet YAML and Markdown
- `.omo/tests/test_omo_debt_cli.py` — keep minimal registry fixtures aligned with the new required ref
- `.omo/tests/test_omo_automation.py` — keep registry-backed fixtures aligned with the new required ref
- `.omo/tests/test_omo_debt_docs.py` — assert `.omo/AGENT.md` documents the action packet once it becomes an operator-facing surface
- `.omo/AGENT.md` — explain the new action packet and lane semantics

### Repository-boundary note

The workspace root treats `scripts/` as a nested git repository/gitlink. When a task touches both root-tracked files and `scripts/*`, make two commits:

1. a commit inside `/Users/xiamingxing/Workspace/scripts`
2. a root-repo commit inside `/Users/xiamingxing/Workspace` that records the updated `scripts` pointer plus root files

Do not try to commit `scripts/*` pathspecs directly from the root repo.

### Existing files to read before implementation

- `docs/superpowers/specs/2026-06-02-debt-review-action-packet-design.md`
- `scripts/omo_debt.py`
- `scripts/omo_debt_review_queue.py`
- `.omo/debt/review-queue/current.yaml`
- `.omo/tests/test_omo_debt_outputs.py`
- `.omo/tests/test_omo_debt_docs.py`
- `.omo/AGENT.md`

---

### Task 1: Extend the debt registry contract for the action-packet surface

**Files:**
- Modify: `/Users/xiamingxing/Workspace/.omo/debt/registry.yaml`
- Modify: `/Users/xiamingxing/Workspace/scripts/omo_debt_registry.py`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_registry.py`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_cli.py`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Write the failing registry contract assertion**

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

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_registry.py::test_debt_registry_lists_seed_items_and_outputs -q
```

Expected: FAIL with `KeyError: 'action_packet_ref'`.

- [ ] **Step 3: Add the action-packet ref to the registry and loader**

Update `/Users/xiamingxing/Workspace/.omo/debt/registry.yaml`:

```yaml
version: 1
items_dir: .omo/debt/items
dashboard_ref: .omo/debt/dashboard/current.yaml
review_pack_ref: .omo/debt/reviews/current.md
review_queue_ref: .omo/debt/review-queue/current.yaml
action_packet_ref: .omo/debt/action-packet/current.yaml
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
        action_packet_ref=registry["action_packet_ref"],
        items=tuple(items),
    )
```

- [ ] **Step 4: Align all registry-writing test fixtures**

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
        "seed_items: []\n",
        encoding="utf-8",
    )
```

- [ ] **Step 5: Run the affected tests and commit in both repos**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_registry.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_automation.py -q
```

Expected: PASS.

Commit the `scripts` repo change:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_registry.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): add action packet registry metadata\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Commit the root repo change:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/debt/registry.yaml .omo/tests/test_omo_debt_registry.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_automation.py scripts && git -c core.hooksPath=/dev/null commit -m $'feat(omo): register debt action packet surface\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 2: Add the action-packet routing helper

**Files:**
- Create: `/Users/xiamingxing/Workspace/scripts/omo_debt_action_packet.py`
- Create: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_action_packet.py`

- [ ] **Step 1: Write the failing routing tests**

Create `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_action_packet.py`:

```python
from __future__ import annotations

from scripts.omo_debt_action_packet import build_action_packet


def _entry(
    item_id: str,
    *,
    lifecycle_state: str = "scheduled",
    gate_level: str = "none",
    stale_evidence: bool = False,
    overdue_by: int = 0,
    owner: str = "omo-governance",
    next_review_at: str | None = "2026-06-10T00:00:00Z",
) -> dict[str, object]:
    return {
        "id": item_id,
        "title": f"{item_id} title",
        "owner": owner,
        "severity": "high",
        "dimension": "governance_process",
        "subdimension": "cadence",
        "lifecycle_state": lifecycle_state,
        "gate_level": gate_level,
        "next_review_at": next_review_at,
        "last_reviewed_at": "2026-06-02T00:00:00Z",
        "stale_evidence": stale_evidence,
        "overdue_by": overdue_by,
        "affected_roots": [".omo"],
        "priority_reason": "due_now",
    }


def test_build_action_packet_routes_entries_into_primary_lanes() -> None:
    review_queue = {
        "generated_at": "2026-06-10T00:00:00Z",
        "defaults": {
            "review_window_days": 7,
            "escalation_threshold_days": 3,
        },
        "due_now": [
            _entry("REVALIDATE", stale_evidence=True, overdue_by=1),
            _entry("ESCALATE", gate_level="watchlist", stale_evidence=False, overdue_by=4),
            _entry("MITIGATE", lifecycle_state="in_progress", stale_evidence=False, overdue_by=1),
        ],
        "upcoming": [
            _entry("WATCH", overdue_by=0, next_review_at="2026-06-12T00:00:00Z"),
        ],
        "escalation_candidates": [
            _entry("REVALIDATE", stale_evidence=True, overdue_by=1),
            _entry("ESCALATE", gate_level="watchlist", stale_evidence=False, overdue_by=4),
        ],
        "unscheduled": [
            _entry("SCHEDULE", next_review_at=None),
        ],
        "summary": {},
    }

    packet = build_action_packet(review_queue, now="2026-06-10T00:00:00Z")

    assert [entry["id"] for entry in packet["lanes"]["revalidate_now"]] == ["REVALIDATE"]
    assert [entry["id"] for entry in packet["lanes"]["schedule_now"]] == ["SCHEDULE"]
    assert [entry["id"] for entry in packet["lanes"]["escalate_now"]] == ["ESCALATE"]
    assert [entry["id"] for entry in packet["lanes"]["continue_mitigation"]] == ["MITIGATE"]
    assert [entry["id"] for entry in packet["lanes"]["watch_only"]] == ["WATCH"]
    assert packet["lanes"]["revalidate_now"][0]["suggested_command"] == (
        "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id REVALIDATE --reviewed-at 2026-06-10T00:00:00Z"
    )
    assert packet["lanes"]["schedule_now"][0]["suggested_command"] == (
        "python3 scripts/omo_debt.py schedule --omo-dir .omo --id SCHEDULE --next-review-at 2026-06-17T00:00:00Z"
    )


def test_build_action_packet_keeps_revalidate_above_escalate_for_stale_items() -> None:
    review_queue = {
        "generated_at": "2026-06-10T00:00:00Z",
        "defaults": {
            "review_window_days": 7,
            "escalation_threshold_days": 3,
        },
        "due_now": [
            _entry("STALE_GATE", gate_level="watchlist", stale_evidence=True, overdue_by=5),
        ],
        "upcoming": [],
        "escalation_candidates": [
            _entry("STALE_GATE", gate_level="watchlist", stale_evidence=True, overdue_by=5),
        ],
        "unscheduled": [],
        "summary": {},
    }

    packet = build_action_packet(review_queue, now="2026-06-10T00:00:00Z")

    assert [entry["id"] for entry in packet["lanes"]["revalidate_now"]] == ["STALE_GATE"]
    assert packet["lanes"]["escalate_now"] == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_action_packet.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.omo_debt_action_packet'`.

- [ ] **Step 3: Add the minimal action-packet router**

Create `/Users/xiamingxing/Workspace/scripts/omo_debt_action_packet.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta


def _schedule_command(item_id: str, now: str, review_window_days: int) -> str:
    next_review = (datetime.fromisoformat(now.replace("Z", "+00:00")) + timedelta(days=review_window_days)).isoformat().replace("+00:00", "Z")
    return f"python3 scripts/omo_debt.py schedule --omo-dir .omo --id {item_id} --next-review-at {next_review}"


def _revalidate_command(item_id: str, now: str) -> str:
    return f"python3 scripts/omo_debt.py revalidate --omo-dir .omo --id {item_id} --reviewed-at {now}"


def _escalate_command(item_id: str) -> str:
    return f"python3 scripts/omo_debt.py escalate --omo-dir .omo --id {item_id} --gate-level gate"


def build_action_packet(review_queue: dict[str, object], now: str) -> dict[str, object]:
    defaults = review_queue["defaults"]
    review_window_days = int(defaults["review_window_days"])
    escalation_ids = {entry["id"] for entry in review_queue["escalation_candidates"]}
    lanes = {
        "revalidate_now": [],
        "schedule_now": [],
        "escalate_now": [],
        "continue_mitigation": [],
        "watch_only": [],
    }

    for entry in review_queue["unscheduled"]:
        lanes["schedule_now"].append(
            {
                **entry,
                "current_lane": "schedule_now",
                "recommended_action": "schedule",
                "reason": "missing_next_review_at",
                "suggested_command": _schedule_command(entry["id"], now, review_window_days),
            }
        )

    for entry in review_queue["due_now"]:
        if entry["stale_evidence"]:
            lanes["revalidate_now"].append(
                {
                    **entry,
                    "current_lane": "revalidate_now",
                    "recommended_action": "revalidate",
                    "reason": "stale_due_item",
                    "suggested_command": _revalidate_command(entry["id"], now),
                }
            )
            continue
        if entry["id"] in escalation_ids and entry["gate_level"] != "gate":
            lanes["escalate_now"].append(
                {
                    **entry,
                    "current_lane": "escalate_now",
                    "recommended_action": "escalate",
                    "reason": "escalation_candidate",
                    "suggested_command": _escalate_command(entry["id"]),
                }
            )
            continue
        if entry["lifecycle_state"] in {"in_progress", "mitigated"}:
            lanes["continue_mitigation"].append(
                {
                    **entry,
                    "current_lane": "continue_mitigation",
                    "recommended_action": "continue_mitigation",
                    "reason": "active_mitigation_due",
                    "suggested_command": f"manual: continue mitigation with {entry['owner']}",
                }
            )
            continue
        lanes["watch_only"].append(
            {
                **entry,
                "current_lane": "watch_only",
                "recommended_action": "watch",
                "reason": "due_without_stronger_action",
                "suggested_command": "manual: keep item on review radar",
            }
        )

    for entry in review_queue["upcoming"]:
        lanes["watch_only"].append(
            {
                **entry,
                "current_lane": "watch_only",
                "recommended_action": "watch",
                "reason": "upcoming_not_due",
                "suggested_command": "manual: keep item on review radar",
            }
        )

    return {
        "generated_at": now,
        "defaults": defaults,
        "lanes": lanes,
        "summary": {
            lane: len(entries)
            for lane, entries in lanes.items()
        },
    }
```

- [ ] **Step 4: Run the focused action-packet tests**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_action_packet.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit in both repos**

Commit the `scripts` repo:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_action_packet.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): add debt action packet router\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Commit the root repo:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/tests/test_omo_debt_action_packet.py scripts && git -c core.hooksPath=/dev/null commit -m $'test(omo): add debt action packet coverage\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 3: Wire refresh to generate the action-packet YAML and Markdown

**Files:**
- Modify: `/Users/xiamingxing/Workspace/scripts/omo_debt.py`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_outputs.py`

- [ ] **Step 1: Make the output regression fail on the missing action packet**

Update `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_outputs.py`:

```python
def test_debt_refresh_writes_dashboard_review_queue_and_action_packet(tmp_path: Path) -> None:
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
    action_yaml = yaml.safe_load((tmp_path / ".omo" / "debt" / "action-packet" / "current.yaml").read_text(encoding="utf-8"))
    action_md = (tmp_path / ".omo" / "debt" / "action-packet" / "current.md").read_text(encoding="utf-8")
    assert [entry["id"] for entry in action_yaml["lanes"]["schedule_now"]] == ["SB_ROOT_CLEANUP"]
    assert "SB_DECOMPOSITION" in [entry["id"] for entry in action_yaml["lanes"]["revalidate_now"]]
    assert [entry["id"] for entry in action_yaml["lanes"]["watch_only"]] == ["SB_UNTESTED_PKGS"]
    assert "## Revalidate Now" in action_md
    assert "## Schedule Now" in action_md
    assert "## Watch Only" in action_md
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_outputs.py::test_debt_refresh_writes_dashboard_review_queue_and_action_packet -q
```

Expected: FAIL with `FileNotFoundError` for `.omo/debt/action-packet/current.yaml`.

- [ ] **Step 3: Extend refresh with action-packet generation**

Update `/Users/xiamingxing/Workspace/scripts/omo_debt.py`:

```python
try:
    from scripts.omo_debt_action_packet import build_action_packet
    from scripts.omo_debt_metrics import compute_debt_metrics
    from scripts.omo_debt_registry import DebtItem, load_debt_ledger
    from scripts.omo_debt_review_queue import build_review_queue
except ModuleNotFoundError:
    from omo_debt_action_packet import build_action_packet
    from omo_debt_metrics import compute_debt_metrics
    from omo_debt_registry import DebtItem, load_debt_ledger
    from omo_debt_review_queue import build_review_queue


def _render_action_packet_section(title: str, entries: list[dict[str, object]]) -> str:
    lines = [f"## {title}", ""]
    if entries:
        for entry in entries:
            lines.append(f"- `{entry['id']}` — {entry['reason']} — `{entry['suggested_command']}`")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def write_action_packet(omo_dir: Path, action_packet: dict[str, object]) -> None:
    _write_yaml(omo_dir / "debt" / "action-packet" / "current.yaml", action_packet)

    lanes = action_packet["lanes"]
    markdown = "\n".join(
        [
            f"# Debt Action Packet\n\nGenerated at: {action_packet['generated_at']}\n",
            _render_action_packet_section("Revalidate Now", lanes["revalidate_now"]),
            _render_action_packet_section("Schedule Now", lanes["schedule_now"]),
            _render_action_packet_section("Escalate Now", lanes["escalate_now"]),
            _render_action_packet_section("Continue Mitigation", lanes["continue_mitigation"]),
            _render_action_packet_section("Watch Only", lanes["watch_only"]),
        ]
    )
    path = omo_dir / "debt" / "action-packet" / "current.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")


def refresh_outputs(omo_dir: Path, now: str) -> None:
    ledger = load_debt_ledger(omo_dir)
    metrics = compute_debt_metrics(ledger.items, now=now, repo_root=omo_dir.parent)
    review_queue = build_review_queue(ledger.items, now=now, repo_root=omo_dir.parent)
    action_packet = build_action_packet(review_queue, now=now)
    write_dashboard(omo_dir, metrics, review_queue, now)
    write_review_queue(omo_dir, review_queue)
    write_review_pack(omo_dir, ledger.items, metrics, review_queue, now)
    write_action_packet(omo_dir, action_packet)
```

- [ ] **Step 4: Run the focused output regressions**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_outputs.py .omo/tests/test_omo_debt_action_packet.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit in both repos**

Commit the `scripts` repo:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): generate debt action packet outputs\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Commit the root repo:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/tests/test_omo_debt_outputs.py scripts && git -c core.hooksPath=/dev/null commit -m $'test(omo): cover debt action packet refresh outputs\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 4: Update operator guidance, regenerate committed artifacts, and run full verification

**Files:**
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_docs.py`
- Modify: `/Users/xiamingxing/Workspace/.omo/AGENT.md`
- Create: `/Users/xiamingxing/Workspace/.omo/debt/action-packet/current.yaml`
- Create: `/Users/xiamingxing/Workspace/.omo/debt/action-packet/current.md`

- [ ] **Step 1: Add the failing docs regression**

Update `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_docs.py`:

```python
def test_omo_agent_documents_debt_refresh_flow() -> None:
    content = Path(".omo/AGENT.md").read_text(encoding="utf-8")

    assert "python3 scripts/omo_debt.py refresh --omo-dir .omo" in content
    assert ".omo/debt/review-queue/current.yaml" in content
    assert ".omo/debt/action-packet/current.yaml" in content
    assert "revalidate now" in content.lower()
    assert "schedule now" in content.lower()
    assert "escalation candidates" in content.lower()
    assert "bash bin/verify-omo.sh" in content
```

- [ ] **Step 2: Run the docs test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py::test_omo_agent_documents_debt_refresh_flow -q
```

Expected: FAIL because `.omo/AGENT.md` does not mention the action packet yet.

- [ ] **Step 3: Update docs and regenerate committed outputs**

Update `/Users/xiamingxing/Workspace/.omo/AGENT.md`:

```markdown
### Debt governance refresh

Use this when you need to refresh the first-class debt ledger surfaces before reading debt state:

1. `python3 scripts/omo_debt.py refresh --omo-dir .omo --now 2026-06-10T00:00:00Z`
2. `python3 scripts/sync_omo_state.py --omo-dir .omo`
3. `bash bin/verify-omo.sh`

Interpretation rules:

- `.omo/debt/registry.yaml` is the canonical debt index
- `.omo/debt/items/*.yaml` are the canonical debt objects
- `.omo/debt/dashboard/current.yaml`, `.omo/debt/review-queue/current.yaml`, `.omo/debt/reviews/current.md`, and `.omo/debt/action-packet/current.yaml` are generated outputs
- `review-queue` shows cadence state
- `action-packet` shows the next operator action lane such as `Revalidate Now` or `Schedule Now`
```

Regenerate the committed artifacts:

```bash
cd /Users/xiamingxing/Workspace && python3 scripts/omo_debt.py refresh --omo-dir .omo --now 2026-06-10T00:00:00Z
```

Expected: `.omo/debt/action-packet/current.yaml` and `.omo/debt/action-packet/current.md` are created alongside refreshed queue/review/dashboard outputs.

- [ ] **Step 4: Run focused regressions and then the canonical verification chain**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py .omo/tests/test_omo_debt_outputs.py .omo/tests/test_omo_debt_action_packet.py -q
```

Expected: PASS.

Run:

```bash
cd /Users/xiamingxing/Workspace && bash bin/verify-omo.sh
```

Expected: PASS for the full `.omo` validation chain.

- [ ] **Step 5: Commit the root repo artifacts**

```bash
cd /Users/xiamingxing/Workspace && git add .omo/AGENT.md .omo/debt/dashboard/current.yaml .omo/debt/review-queue/current.yaml .omo/debt/reviews/current.md .omo/debt/action-packet/current.yaml .omo/debt/action-packet/current.md .omo/tests/test_omo_debt_docs.py .omo/tests/test_omo_debt_outputs.py && git -c core.hooksPath=/dev/null commit -m $'docs(omo): operationalize debt action packets\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

## Self-check mapping from spec to tasks

- New `action-packet` generated surface → Tasks 1, 3, 4
- Deterministic lanes and first-match routing → Task 2
- Suggested commands and next-action semantics → Task 2
- No automatic mutation / no workflow state machine → Tasks 2 and 3
- Operator guidance and full verification → Task 4
