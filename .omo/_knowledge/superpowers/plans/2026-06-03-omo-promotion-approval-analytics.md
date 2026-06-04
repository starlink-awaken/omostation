# OMO Promotion Approval Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a canonical promotion approval analytics / rollup surface that derives operator action queues, blocker histograms, and request age buckets from the existing promotion approval current/history/readiness surfaces.

**Architecture:** Keep this slice read-only and layered. A pure helper in `scripts/omo_promotion_approval_analytics.py` will read only canonical promotion surfaces, derive one analytics packet plus Markdown, and a thin `task promotion-approval-analytics` command in `scripts/omo_worker.py` will write `.omo/workers/promotion/approvals/analytics/current.*`. This preserves the existing layering: request/status/history remain the lower-level sources, analytics becomes the next operator-facing rollup.

**Tech Stack:** Python 3, `pathlib`, `datetime`, `yaml`, existing `scripts/omo_worker.py`, promotion current/history/readiness YAML surfaces, pytest under `.omo/tests`

---

## File map

- **Create:** `scripts/omo_promotion_approval_analytics.py`
  - Pure helper for loading canonical approval surfaces, classifying actions, computing histograms/age buckets, and rendering YAML/Markdown packets.
- **Modify:** `scripts/omo_worker.py`
  - Add `task promotion-approval-analytics`.
- **Create:** `.omo/tests/test_omo_promotion_approval_analytics.py`
  - Unit tests for analytics packet building, action queue classification, blocker histogram, and age buckets.
- **Modify:** `.omo/tests/test_omo_automation.py`
  - CLI regression for `promotion-approval-analytics`.
- **Modify:** `.omo/tests/test_worker_mechanism_consistency.py`
  - Docs regression for the new analytics surface.
- **Modify:** `.omo/workers/README.md`
- **Modify:** `.omo/AGENT.md`
- **Modify:** `.omo/tasks/README.md`
  - Document the new analytics command and canonical output paths.
- **Create:** `.omo/workers/promotion/approvals/analytics/current.yaml`
- **Create:** `.omo/workers/promotion/approvals/analytics/current.md`
  - Live analytics outputs hydrated from the current repo state.

## Constraints and invariants

1. Do **not** read raw `workers/runs/*-promotion-approval-*.yaml` in this slice; consume canonical current/history/readiness surfaces only.
2. Do **not** silently rebuild missing upstream surfaces inside analytics; fail closed with explicit errors.
3. Keep the age buckets intentionally simple: `lt_1d`, `d1_to_d3`, `d3_plus`.
4. Only open requests (`approval_status: requested`) count toward age buckets.
5. Because `scripts/` is a nested repo, commits must happen in two layers:
   1. commit `/Users/xiamingxing/Workspace/scripts`
   2. then commit the root repo to capture the updated `scripts` gitlink plus `.omo/*` files

---

### Task 1: Build the analytics helper with TDD

**Files:**
- Create: `.omo/tests/test_omo_promotion_approval_analytics.py`
- Create: `scripts/omo_promotion_approval_analytics.py`

- [ ] **Step 1: Write the failing helper tests**

Create `.omo/tests/test_omo_promotion_approval_analytics.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.omo_promotion_approval_analytics import build_promotion_approval_analytics_packet


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_build_promotion_approval_analytics_packet_returns_zero_rollup_when_no_tasks_exist(tmp_path: Path):
    _write_yaml(tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "current.yaml", {
        "generated_at": "2026-06-03T06:00:00Z",
        "approval_task_count": 0,
        "requested_count": 0,
        "approved_pending_apply_count": 0,
        "granted_count": 0,
        "tasks": [],
    })
    _write_yaml(tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "history" / "current.yaml", {
        "generated_at": "2026-06-03T06:00:00Z",
        "approval_count": 0,
        "approvals": [],
    })
    _write_yaml(tmp_path / ".omo" / "workers" / "promotion" / "readiness.yaml", {
        "generated_at": "2026-06-03T06:00:00Z",
        "blocked_count": 0,
        "ready_count": 0,
        "tasks": [],
    })

    packet = build_promotion_approval_analytics_packet(tmp_path, omo_dir=".omo", now="2026-06-03T06:00:00Z")

    assert packet["yaml"]["approval_task_count"] == 0
    assert packet["yaml"]["history_approval_count"] == 0
    assert packet["yaml"]["action_queues"]["approve_now"] == []
    assert packet["yaml"]["blocker_histogram"] == {}
    assert packet["yaml"]["approval_age_buckets"] == {"lt_1d": 0, "d1_to_d3": 0, "d3_plus": 0}


def test_build_promotion_approval_analytics_packet_classifies_action_queues_and_histograms(tmp_path: Path):
    _write_yaml(tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "current.yaml", {
        "generated_at": "2026-06-03T06:00:00Z",
        "approval_task_count": 3,
        "requested_count": 2,
        "approved_pending_apply_count": 1,
        "granted_count": 1,
        "tasks": [
            {
                "task_id": "TASK-A",
                "task_ref": ".omo/tasks/planned/TASK-A.yaml",
                "approval_ref": ".omo/workers/runs/TASK-A-promotion-approval-2026-06-03T05-00-00Z.yaml",
                "approval_id": "TASK-A-promotion-approval-2026-06-03T05-00-00Z",
                "approval_status": "requested",
                "proposal_id": "TASK-A-promotion-approval-2026-06-03T05-00-00Z-proposal",
                "proposal_status": "proposed",
                "eligible": False,
                "blockers": ["approval_invalid", "phase_mismatch"],
            },
            {
                "task_id": "TASK-B",
                "task_ref": ".omo/tasks/planned/TASK-B.yaml",
                "approval_ref": ".omo/workers/runs/TASK-B-promotion-approval-2026-06-02T06-00-00Z.yaml",
                "approval_id": "TASK-B-promotion-approval-2026-06-02T06-00-00Z",
                "approval_status": "requested",
                "proposal_id": "TASK-B-promotion-approval-2026-06-02T06-00-00Z-proposal",
                "proposal_status": "approved",
                "eligible": False,
                "blockers": ["approval_invalid"],
            },
            {
                "task_id": "TASK-C",
                "task_ref": ".omo/tasks/planned/TASK-C.yaml",
                "approval_ref": ".omo/workers/runs/TASK-C-promotion-approval-2026-06-01T06-00-00Z.yaml",
                "approval_id": "TASK-C-promotion-approval-2026-06-01T06-00-00Z",
                "approval_status": "granted",
                "proposal_id": "TASK-C-promotion-approval-2026-06-01T06-00-00Z-proposal",
                "proposal_status": "verified",
                "eligible": False,
                "blockers": ["phase_mismatch"],
            },
        ],
    })
    _write_yaml(tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "history" / "current.yaml", {
        "generated_at": "2026-06-03T06:00:00Z",
        "approval_count": 3,
        "approvals": [
            {
                "approval_id": "TASK-A-promotion-approval-2026-06-03T05-00-00Z",
                "task_id": "TASK-A",
                "requested_at": "2026-06-03T05:00:00Z",
                "approval_status": "requested",
                "proposal_status": "proposed",
            },
            {
                "approval_id": "TASK-B-promotion-approval-2026-06-02T06-00-00Z",
                "task_id": "TASK-B",
                "requested_at": "2026-06-02T06:00:00Z",
                "approval_status": "requested",
                "proposal_status": "approved",
            },
            {
                "approval_id": "TASK-C-promotion-approval-2026-06-01T06-00-00Z",
                "task_id": "TASK-C",
                "requested_at": "2026-06-01T06:00:00Z",
                "approval_status": "granted",
                "proposal_status": "verified",
            },
        ],
    })
    _write_yaml(tmp_path / ".omo" / "workers" / "promotion" / "readiness.yaml", {
        "generated_at": "2026-06-03T06:00:00Z",
        "blocked_count": 3,
        "ready_count": 0,
        "tasks": [
            {"task_id": "TASK-A", "blockers": ["approval_invalid", "phase_mismatch"]},
            {"task_id": "TASK-B", "blockers": ["approval_invalid"]},
            {"task_id": "TASK-C", "blockers": ["phase_mismatch"]},
        ],
    })

    packet = build_promotion_approval_analytics_packet(tmp_path, omo_dir=".omo", now="2026-06-03T06:00:00Z")

    assert [item["task_id"] for item in packet["yaml"]["action_queues"]["approve_now"]] == ["TASK-A"]
    assert [item["task_id"] for item in packet["yaml"]["action_queues"]["apply_now"]] == ["TASK-B"]
    assert [item["task_id"] for item in packet["yaml"]["action_queues"]["check_readiness"]] == ["TASK-C"]
    assert packet["yaml"]["blocker_histogram"] == {"approval_invalid": 2, "phase_mismatch": 2}
    assert packet["yaml"]["proposal_status_histogram"] == {"proposed": 1, "approved": 1, "verified": 1, "missing": 0, "invalid": 0}


def test_build_promotion_approval_analytics_packet_assigns_age_buckets_for_open_requests(tmp_path: Path):
    _write_yaml(tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "current.yaml", {
        "generated_at": "2026-06-03T06:00:00Z",
        "approval_task_count": 3,
        "requested_count": 3,
        "approved_pending_apply_count": 0,
        "granted_count": 0,
        "tasks": [
            {"task_id": "TASK-A", "approval_id": "A", "approval_status": "requested", "proposal_id": "A-proposal", "proposal_status": "proposed", "eligible": False, "blockers": ["approval_invalid"]},
            {"task_id": "TASK-B", "approval_id": "B", "approval_status": "requested", "proposal_id": "B-proposal", "proposal_status": "proposed", "eligible": False, "blockers": ["approval_invalid"]},
            {"task_id": "TASK-C", "approval_id": "C", "approval_status": "requested", "proposal_id": "C-proposal", "proposal_status": "proposed", "eligible": False, "blockers": ["approval_invalid"]},
        ],
    })
    _write_yaml(tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "history" / "current.yaml", {
        "generated_at": "2026-06-03T06:00:00Z",
        "approval_count": 3,
        "approvals": [
            {"approval_id": "A", "task_id": "TASK-A", "requested_at": "2026-06-03T05:30:00Z", "approval_status": "requested", "proposal_status": "proposed"},
            {"approval_id": "B", "task_id": "TASK-B", "requested_at": "2026-06-02T05:00:00Z", "approval_status": "requested", "proposal_status": "proposed"},
            {"approval_id": "C", "task_id": "TASK-C", "requested_at": "2026-05-30T06:00:00Z", "approval_status": "requested", "proposal_status": "proposed"},
        ],
    })
    _write_yaml(tmp_path / ".omo" / "workers" / "promotion" / "readiness.yaml", {
        "generated_at": "2026-06-03T06:00:00Z",
        "blocked_count": 3,
        "ready_count": 0,
        "tasks": [
            {"task_id": "TASK-A", "blockers": ["approval_invalid"]},
            {"task_id": "TASK-B", "blockers": ["approval_invalid"]},
            {"task_id": "TASK-C", "blockers": ["approval_invalid"]},
        ],
    })

    packet = build_promotion_approval_analytics_packet(tmp_path, omo_dir=".omo", now="2026-06-03T06:00:00Z")

    assert packet["yaml"]["approval_age_buckets"] == {"lt_1d": 1, "d1_to_d3": 1, "d3_plus": 1}
    assert [item["task_id"] for item in packet["yaml"]["tasks"]] == ["TASK-C", "TASK-B", "TASK-A"]


def test_build_promotion_approval_analytics_packet_requires_all_canonical_inputs(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="approvals/current.yaml"):
        build_promotion_approval_analytics_packet(tmp_path, omo_dir=".omo", now="2026-06-03T06:00:00Z")
```

- [ ] **Step 2: Run helper tests to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_promotion_approval_analytics.py -q
```

Expected: import failure because `scripts/omo_promotion_approval_analytics.py` does not exist yet.

- [ ] **Step 3: Write the minimal helper implementation**

Create `scripts/omo_promotion_approval_analytics.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml


def _load_yaml_required(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path.as_posix())
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _parse_iso8601(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _age_bucket(now: datetime, requested_at: str, approval_status: str) -> str | None:
    if approval_status != "requested":
        return None
    age = now - _parse_iso8601(requested_at)
    if age.total_seconds() < 86400:
        return "lt_1d"
    if age.total_seconds() < 3 * 86400:
        return "d1_to_d3"
    return "d3_plus"


def _next_action(approval_status: str, proposal_status: str) -> str:
    if approval_status == "requested" and proposal_status == "proposed":
        return "approve"
    if approval_status == "requested" and proposal_status == "approved":
        return "apply"
    if approval_status == "granted":
        return "check_readiness"
    return "none"


def build_promotion_approval_analytics_packet(root: Path, *, omo_dir: str | Path = ".omo", now: str) -> dict[str, object]:
    omo = Path(omo_dir)
    current = _load_yaml_required(root / omo / "workers" / "promotion" / "approvals" / "current.yaml")
    history = _load_yaml_required(root / omo / "workers" / "promotion" / "approvals" / "history" / "current.yaml")
    readiness = _load_yaml_required(root / omo / "workers" / "promotion" / "readiness.yaml")
    generated_at = _parse_iso8601(now)
    history_by_task = {entry["task_id"]: entry for entry in history.get("approvals", [])}

    tasks: list[dict[str, object]] = []
    blocker_histogram: dict[str, int] = {}
    proposal_status_histogram = {"proposed": 0, "approved": 0, "verified": 0, "missing": 0, "invalid": 0}
    action_queues = {"approve_now": [], "apply_now": [], "check_readiness": []}
    approval_age_buckets = {"lt_1d": 0, "d1_to_d3": 0, "d3_plus": 0}

    for entry in current.get("tasks", []):
        history_entry = history_by_task.get(entry["task_id"], {})
        requested_at = history_entry.get("requested_at")
        if requested_at is None:
            requested_at = now
        proposal_status = str(entry.get("proposal_status", "invalid"))
        if proposal_status not in proposal_status_histogram:
            proposal_status = "invalid"
        proposal_status_histogram[proposal_status] += 1
        age_bucket = _age_bucket(generated_at, requested_at, str(entry["approval_status"]))
        if age_bucket is not None:
            approval_age_buckets[age_bucket] += 1
        next_action = _next_action(str(entry["approval_status"]), proposal_status)
        task_packet = {
            "task_id": entry["task_id"],
            "approval_id": entry["approval_id"],
            "approval_status": entry["approval_status"],
            "proposal_status": proposal_status,
            "requested_at": requested_at,
            "task_age_bucket": age_bucket,
            "eligible": entry.get("eligible", False),
            "blockers": list(entry.get("blockers", [])),
            "next_action": next_action,
        }
        tasks.append(task_packet)
        if next_action == "approve":
            action_queues["approve_now"].append(
                {
                    "task_id": entry["task_id"],
                    "approval_id": entry["approval_id"],
                    "proposal_id": entry["proposal_id"],
                    "blockers": list(entry.get("blockers", [])),
                }
            )
        elif next_action == "apply":
            action_queues["apply_now"].append(
                {
                    "task_id": entry["task_id"],
                    "approval_id": entry["approval_id"],
                    "proposal_id": entry["proposal_id"],
                    "blockers": list(entry.get("blockers", [])),
                }
            )
        elif next_action == "check_readiness":
            action_queues["check_readiness"].append(
                {
                    "task_id": entry["task_id"],
                    "approval_id": entry["approval_id"],
                    "proposal_id": entry["proposal_id"],
                    "blockers": list(entry.get("blockers", [])),
                }
            )
        for blocker in entry.get("blockers", []):
            blocker_histogram[blocker] = blocker_histogram.get(blocker, 0) + 1

    tasks.sort(
        key=lambda item: (
            {"approve": 0, "apply": 1, "check_readiness": 2, "none": 3}[str(item["next_action"])],
            0 if item["task_age_bucket"] == "d3_plus" else 1 if item["task_age_bucket"] == "d1_to_d3" else 2,
            str(item["task_id"]),
        )
    )

    yaml_packet = {
        "generated_at": now,
        "approval_task_count": current.get("approval_task_count", 0),
        "history_approval_count": history.get("approval_count", 0),
        "requested_count": current.get("requested_count", 0),
        "approved_pending_apply_count": current.get("approved_pending_apply_count", 0),
        "granted_count": current.get("granted_count", 0),
        "missing_proposal_count": proposal_status_histogram["missing"],
        "eligible_after_approval_count": sum(1 for entry in tasks if entry["next_action"] == "check_readiness" and entry["eligible"]),
        "blocked_after_approval_count": sum(1 for entry in tasks if entry["next_action"] == "check_readiness" and not entry["eligible"]),
        "action_queues": action_queues,
        "blocker_histogram": blocker_histogram,
        "proposal_status_histogram": proposal_status_histogram,
        "approval_age_buckets": approval_age_buckets,
        "tasks": tasks,
    }
    markdown_lines = [
        "# Promotion Approval Analytics",
        "",
        f"Generated at: {now}",
        f"Approval tasks: {yaml_packet['approval_task_count']}",
        f"History approvals: {yaml_packet['history_approval_count']}",
        f"Approve now: {len(action_queues['approve_now'])}",
        f"Apply now: {len(action_queues['apply_now'])}",
        f"Check readiness: {len(action_queues['check_readiness'])}",
    ]
    for item in tasks:
        markdown_lines.extend(
            [
                "",
                f"## Task: {item['task_id']}",
                "",
                f"next_action={item['next_action']}",
                f"proposal_status={item['proposal_status']}",
                f"approval_status={item['approval_status']}",
                f"age_bucket={item['task_age_bucket'] or 'n/a'}",
                f"blockers={','.join(item['blockers']) or 'none'}",
            ]
        )
    return {"yaml": yaml_packet, "markdown": "\n".join(markdown_lines) + "\n"}
```

- [ ] **Step 4: Run helper tests to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_promotion_approval_analytics.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit the nested `scripts` repo helper**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_promotion_approval_analytics.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion approval analytics helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: new `scripts` commit created.

---

### Task 2: Wire the CLI, docs, and live analytics surface

**Files:**
- Modify: `scripts/omo_worker.py`
- Modify: `.omo/tests/test_omo_automation.py`
- Modify: `.omo/tests/test_worker_mechanism_consistency.py`
- Modify: `.omo/workers/README.md`
- Modify: `.omo/AGENT.md`
- Modify: `.omo/tasks/README.md`
- Create: `.omo/workers/promotion/approvals/analytics/current.yaml`
- Create: `.omo/workers/promotion/approvals/analytics/current.md`

- [ ] **Step 1: Write the failing CLI/docs regressions**

Add to `.omo/tests/test_omo_automation.py`:

```python
def test_task_promotion_approval_analytics_writes_current_surfaces(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "current.yaml",
        {
            "generated_at": "2026-06-03T06:00:00Z",
            "approval_task_count": 1,
            "requested_count": 1,
            "approved_pending_apply_count": 0,
            "granted_count": 0,
            "tasks": [
                {
                    "task_id": "TASK-A",
                    "task_ref": ".omo/tasks/planned/TASK-A.yaml",
                    "approval_ref": ".omo/workers/runs/TASK-A-promotion-approval-2026-06-03T05-00-00Z.yaml",
                    "approval_id": "TASK-A-promotion-approval-2026-06-03T05-00-00Z",
                    "approval_status": "requested",
                    "proposal_id": "TASK-A-promotion-approval-2026-06-03T05-00-00Z-proposal",
                    "proposal_status": "proposed",
                    "eligible": False,
                    "blockers": ["approval_invalid"],
                }
            ],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "history" / "current.yaml",
        {
            "generated_at": "2026-06-03T06:00:00Z",
            "approval_count": 1,
            "approvals": [
                {
                    "approval_id": "TASK-A-promotion-approval-2026-06-03T05-00-00Z",
                    "task_id": "TASK-A",
                    "requested_at": "2026-06-03T05:00:00Z",
                    "approval_status": "requested",
                    "proposal_status": "proposed",
                }
            ],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "promotion" / "readiness.yaml",
        {
            "generated_at": "2026-06-03T06:00:00Z",
            "blocked_count": 1,
            "ready_count": 0,
            "tasks": [{"task_id": "TASK-A", "blockers": ["approval_invalid"]}],
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "promotion-approval-analytics", "--omo-dir", ".omo", "--now", "2026-06-03T06:00:00Z"],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    packet = _load_yaml(tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "analytics" / "current.yaml")

    assert "approval_task_count=1" in output
    assert packet["action_queues"]["approve_now"][0]["task_id"] == "TASK-A"
    assert (tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "analytics" / "current.md").exists()
```

Add to `.omo/tests/test_worker_mechanism_consistency.py`:

```python
def test_worker_docs_describe_promotion_approval_analytics_surface():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "AGENT.md").read_text(encoding="utf-8")
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")

    assert "promotion-approval-analytics" in workers_text
    assert "promotion/approvals/analytics/current.yaml" in workers_text
    assert "promotion-approval-analytics" in agent_text
    assert "promotion-approval-analytics" in tasks_text
```

- [ ] **Step 2: Run the new regressions to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py -q -k 'promotion_approval_analytics'
```

Expected:

1. argparse rejects `promotion-approval-analytics`
2. docs assertions fail because the command is not documented yet

- [ ] **Step 3: Add the thin CLI wiring**

Modify `scripts/omo_worker.py` to import the helper, add the parser, and write the generated surfaces:

```python
from scripts.omo_promotion_approval_analytics import build_promotion_approval_analytics_packet
```

```python
def _write_task_promotion_approval_analytics(root: Path, omo_dir: str | Path = ".omo", now: str | None = None) -> int:
    result = build_promotion_approval_analytics_packet(root, omo_dir=omo_dir, now=now or _utc_now())
    omo = _omo_path(root, omo_dir)
    analytics_dir = omo / "workers" / "promotion" / "approvals" / "analytics"
    analytics_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(analytics_dir / "current.yaml", result["yaml"])
    write_text_atomic(analytics_dir / "current.md", result["markdown"])
    print(
        "approval_task_count="
        f"{result['yaml']['approval_task_count']} "
        f"approve_now={len(result['yaml']['action_queues']['approve_now'])} "
        f"apply_now={len(result['yaml']['action_queues']['apply_now'])}"
    )
    return 0
```

```python
promotion_approval_analytics_parser = task_sub.add_parser("promotion-approval-analytics")
promotion_approval_analytics_parser.add_argument("--omo-dir", default=".omo")
promotion_approval_analytics_parser.add_argument("--now")
```

```python
if args.command == "task" and args.task_command == "promotion-approval-analytics":
    return _write_task_promotion_approval_analytics(Path.cwd(), omo_dir=args.omo_dir, now=args.now)
```

- [ ] **Step 4: Document the analytics surface**

Update `.omo/workers/README.md`:

```md
Canonical promotion approval analytics surface:

1. `python3 scripts/omo_worker.py task promotion-approval-analytics --omo-dir .omo [--now <ISO8601>]`
2. this reads `.omo/workers/promotion/approvals/current.yaml`
3. this reads `.omo/workers/promotion/approvals/history/current.yaml`
4. this writes `.omo/workers/promotion/approvals/analytics/current.yaml`
5. and `.omo/workers/promotion/approvals/analytics/current.md`
```

Update `.omo/AGENT.md`:

```md
> **Promotion approval analytics**：如需看当前 approval queue 的 action rollup、blocker histogram 与 request aging，运行 `python3 scripts/omo_worker.py task promotion-approval-analytics --omo-dir .omo [--now <ISO8601>]`；该命令读取 approval current/history/readiness 三个 canonical surfaces，并输出 `.omo/workers/promotion/approvals/analytics/current.yaml`。
```

Update `.omo/tasks/README.md`:

```md
- `promotion-approval-analytics` 是 promotion approval 的 canonical analytics / rollup surface，用来查看 approve/apply/check-readiness 三类 action queues、blocker histogram 与 open-request age buckets。
```

- [ ] **Step 5: Run the CLI/docs regressions to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py -q -k 'promotion_approval_analytics'
```

Expected: `2 passed`.

- [ ] **Step 6: Hydrate the live analytics surface**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 scripts/omo_worker.py task promotion-approval-analytics --omo-dir .omo --now 2026-06-03T06:00:00Z
```

Expected:

1. `.omo/workers/promotion/approvals/analytics/current.yaml` exists
2. `.omo/workers/promotion/approvals/analytics/current.md` exists
3. with the current repo state, the live packet should reflect one granted approval-bearing task (`P19-W3-ARCHIVE-TS`) and a `check_readiness` queue entry

---

### Task 3: Run focused verification and commit both repos cleanly

**Files:**
- Verify: `.omo/tests/test_omo_promotion_approval_analytics.py`
- Verify: `.omo/tests/test_omo_automation.py`
- Verify: `.omo/tests/test_worker_mechanism_consistency.py`
- Verify: `.omo/workers/promotion/approvals/analytics/current.yaml`
- Verify: `.omo/workers/promotion/approvals/analytics/current.md`
- Commit: `scripts/`
- Commit: root repo

- [ ] **Step 1: Run the promotion-focused analytics subset**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest \
  .omo/tests/test_omo_promotion_approval_analytics.py \
  .omo/tests/test_omo_promotion_approval_history.py \
  .omo/tests/test_omo_promotion_approval_status.py \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  -q -k 'promotion_approval_analytics or promotion_approval_history or promotion_approval_status'
```

Expected: the analytics slice passes alongside the nearby approval surfaces.

- [ ] **Step 2: Commit the nested `scripts` repo CLI wiring**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_worker.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion approval analytics surface" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: the `scripts` repo now contains the helper + CLI wiring.

- [ ] **Step 3: Commit the root repo files**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
git add \
  scripts \
  .omo/tests/test_omo_promotion_approval_analytics.py \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  .omo/workers/README.md \
  .omo/AGENT.md \
  .omo/tasks/README.md \
  .omo/workers/promotion/approvals/analytics/current.yaml \
  .omo/workers/promotion/approvals/analytics/current.md && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion approval analytics surface" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: root repo captures the `scripts` gitlink update plus `.omo/*` surfaces/docs/tests.

- [ ] **Step 4: Record the milestone in the session plan**

Update `/Users/xiamingxing/.copilot/session-state/a0b6fab5-a362-4eb9-90f8-f2e4e85653bc/plan.md` with:

```md
## 2026-06-03 promotion approval analytics planned

- spec committed: `docs/superpowers/specs/2026-06-03-omo-promotion-approval-analytics-design.md`
- plan committed: `docs/superpowers/plans/2026-06-03-omo-promotion-approval-analytics.md`
- next bounded execution slice:
  1. helper
  2. CLI/docs
  3. live analytics hydration
  4. promotion-focused verify
```

Do not commit the session plan file.

---

## Self-review checklist

Before handing this plan off, verify:

1. every spec requirement maps to a task in this plan
2. the helper never reads raw approval artifacts
3. age buckets only count open requests
4. CLI wiring writes only `.omo/workers/promotion/approvals/analytics/current.*`
5. nested `scripts` repo commits are called out explicitly

## Execution notes

1. Do **not** widen this slice into diff/trend snapshots.
2. Do **not** attempt full repo-wide deterministic verify here; unrelated `.omo/tasks/active/*` and `.omo/debt/*` drift is still known to block that path.
3. Keep the implementation bounded to analytics / rollup on top of canonical current/history/readiness surfaces.
