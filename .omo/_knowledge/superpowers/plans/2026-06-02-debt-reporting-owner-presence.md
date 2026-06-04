# Debt Reporting Owner Presence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `report-trend` with a deterministic additive `owner_presence` block that explains excluded owners over the selected window.

**Architecture:** Keep `report-trend` and the existing shared-owner `owners` block unchanged. Reuse the already-loaded selected per-run reporting packets to derive a parallel `owner_presence` block with only window-scoped fields (`run_count`, first/last run, edge booleans), then document that this block complements `owners_excluded_count` without claiming sparse-series or migration semantics.

**Tech Stack:** Python 3, argparse, PyYAML, pytest, existing `scripts/omo_debt_reporting_trend.py` helper, existing `scripts/omo_debt.py` trend command, `.omo` docs/tests, nested `scripts/` git repo + root gitlink workflow

---

## File structure map

- Modify: `scripts/omo_debt_reporting_trend.py`
  - Reuse owner maps across the selected window, add a parallel `owner_presence` block, and extend markdown rendering.
- Modify: `.omo/tests/test_omo_debt_reporting_trend.py`
  - Add helper regressions for excluded owners at first/last/middle positions, `no_excluded_owners`, `owner_presence is None`, and owner-presence markdown.
- Modify: `.omo/tests/test_omo_debt_cli.py`
  - Add a CLI regression showing `report-trend --last 2` surfaces excluded-owner presence facts without changing summary/shared-owner trend behavior.
- Modify: `.omo/AGENT.md`
  - Document `owner_presence`, its window-scoped semantics, and the two-run overlap with `report-diff`.
- Modify: `.omo/tests/test_omo_debt_docs.py`
  - Lock the updated operator guidance.
- Refresh: `.omo/debt/reporting/trend/current.yaml`
  - Regenerate the live packet; current repo state should still produce `owner_presence: null` because only one run is selected.
- Refresh: `.omo/debt/reporting/trend/current.md`
  - Regenerate markdown from the refreshed live packet.

## Implementation notes before starting

- Work from `/Users/xiamingxing/Workspace`.
- Do **not** use a root worktree; `scripts/` is still a nested git repo / gitlink and live verification depends on the nested repo contents.
- Preserve these contracts:
  1. `owners` stays shared-owner series only
  2. `owners_excluded_count` stays inside `owners`
  3. `owner_presence` is parallel to `owners`
  4. no new enum like `appeared` / `disappeared`
  5. no sparse null-filled owner series
  6. no new command
- The likely refactor to keep the helper readable is:
  1. build `owners_by_run` once
  2. compute `shared_names` once
  3. feed both shared-owner trend and excluded-owner presence paths from that shared data structure
- Commit in repo order:
  1. nested `scripts` repo helper/render commit
  2. root repo tests/docs/artifacts + gitlink update

### Task 1: Add the pure `owner_presence` helper contract

**Files:**
- Modify: `.omo/tests/test_omo_debt_reporting_trend.py`
- Modify: `scripts/omo_debt_reporting_trend.py`
- Test: `.omo/tests/test_omo_debt_reporting_trend.py`

- [ ] **Step 1: Write the first failing helper test for an excluded owner present only at the window end**

Add this test to `.omo/tests/test_omo_debt_reporting_trend.py`:

```python
def test_build_reporting_trend_packet_surfaces_excluded_owner_presence_at_window_end() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 3,
        "runs": [
            _history_entry("2026-06-10T00-00-00Z", total_items=9, executed_item_count=1, approval_coverage_rate=1.0, execution_completion_rate=1 / 9),
            _history_entry("2026-06-01T00-00-00Z", total_items=9, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
            _history_entry("2026-05-20T00-00-00Z", total_items=10, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run={
            "2026-06-10T00-00-00Z": _owner_reporting_packet(
                "2026-06-10T00-00-00Z",
                owners=[
                    _owner_entry("shared-owner", item_count=2, executed_item_count=1, approval_coverage_rate=1.0, execution_completion_rate=0.5),
                    _owner_entry("late-owner", item_count=1, executed_item_count=0, approval_coverage_rate=1.0, execution_completion_rate=0.0),
                ],
            ),
            "2026-06-01T00-00-00Z": _owner_reporting_packet(
                "2026-06-01T00-00-00Z",
                owners=[_owner_entry("shared-owner", item_count=1, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0)],
            ),
            "2026-05-20T00-00-00Z": _owner_reporting_packet(
                "2026-05-20T00-00-00Z",
                owners=[_owner_entry("shared-owner", item_count=1, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0)],
            ),
        },
    )

    assert packet["owners"]["owners_excluded_count"] == 1
    assert packet["owner_presence"] == {
        "presence_status": "presence_available",
        "window_run_count": 3,
        "entries": [
            {
                "owner": "late-owner",
                "run_count": 1,
                "first_window_run": "2026-06-10T00-00-00Z",
                "last_window_run": "2026-06-10T00-00-00Z",
                "in_first_window_run": False,
                "in_last_window_run": True,
            }
        ],
    }
```

- [ ] **Step 2: Run the helper test to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q -k window_end
```

Expected: FAIL because the packet has no `owner_presence` block yet.

- [ ] **Step 3: Implement the minimal `owner_presence` helper path**

Refactor `scripts/omo_debt_reporting_trend.py` so owner maps are built once and reused. Add helpers like:

```python
def _owners_by_run(
    ordered_runs: list[dict[str, object]],
    reporting_packets_by_run: dict[str, dict[str, object]] | None,
) -> list[dict[str, dict[str, object]]] | None:
    if len(ordered_runs) < 2 or reporting_packets_by_run is None:
        return None

    owners_by_run = []
    for run in ordered_runs:
        run_stamp = str(run["run_stamp"])
        reporting_packet = reporting_packets_by_run.get(run_stamp)
        if reporting_packet is None:
            raise ValueError(f"missing owner reporting packet for run: {run_stamp}")
        owners_by_run.append({str(entry["owner"]): entry for entry in reporting_packet.get("owners", [])})
    return owners_by_run


def _owner_presence(
    ordered_runs: list[dict[str, object]],
    owners_by_run: list[dict[str, dict[str, object]]] | None,
    shared_names: set[str] | None,
) -> dict[str, object] | None:
    if owners_by_run is None or shared_names is None:
        return None

    union_names = set().union(*(owner_map.keys() for owner_map in owners_by_run))
    excluded_names = sorted(union_names - shared_names)
    if not excluded_names:
        return {
            "presence_status": "no_excluded_owners",
            "window_run_count": len(ordered_runs),
            "entries": [],
        }

    entries = []
    for owner_name in excluded_names:
        present_stamps = [
            str(run["run_stamp"])
            for run, owner_map in zip(ordered_runs, owners_by_run, strict=True)
            if owner_name in owner_map
        ]
        entries.append(
            {
                "owner": owner_name,
                "run_count": len(present_stamps),
                "first_window_run": present_stamps[0],
                "last_window_run": present_stamps[-1],
                "in_first_window_run": present_stamps[0] == ordered_runs[0]["run_stamp"],
                "in_last_window_run": present_stamps[-1] == ordered_runs[-1]["run_stamp"],
            }
        )

    return {
        "presence_status": "presence_available",
        "window_run_count": len(ordered_runs),
        "entries": entries,
    }
```

Then thread it into `build_reporting_trend_packet(...)`:

```python
owners_by_run = _owners_by_run(ordered_runs, reporting_packets_by_run)
owners = _owner_trends(ordered_runs, owners_by_run)
owner_presence = _owner_presence(
    ordered_runs,
    owners_by_run,
    set(entry["owner"] for entry in owners["compared"]) if owners and owners["owners_trend_status"] == "owners_trend_available" else set(),
)
packet = {
    "generated_at": generated_at,
    "trend_status": "trend_available" if len(ordered_runs) >= 2 else "insufficient_history",
    "window_requested": window_requested,
    "from_run_stamp_requested": from_run_stamp_requested,
    "to_run_stamp_requested": to_run_stamp_requested,
    "window_run_count": len(ordered_runs),
    "oldest_run_stamp": oldest_run_stamp,
    "latest_run_stamp": latest_run_stamp,
    "runs": ordered_runs,
    "intervals": intervals,
    "owners": owners,
    "owner_presence": owner_presence,
}
return packet
```

Update `_owner_trends(...)` to accept `owners_by_run` instead of rebuilding it internally.

- [ ] **Step 4: Run the helper test to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q -k window_end
```

Expected: PASS.

- [ ] **Step 5: Add failing helper tests for first-only, middle-only, empty, and null states**

Append these tests:

```python
def test_build_reporting_trend_packet_surfaces_excluded_owner_presence_at_window_start() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 3,
        "runs": [
            _history_entry("2026-06-10T00-00-00Z", total_items=9, executed_item_count=1, approval_coverage_rate=1.0, execution_completion_rate=1 / 9),
            _history_entry("2026-06-01T00-00-00Z", total_items=9, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
            _history_entry("2026-05-20T00-00-00Z", total_items=10, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run={
            "2026-06-10T00-00-00Z": _owner_reporting_packet("2026-06-10T00-00-00Z", owners=[_owner_entry("shared-owner", item_count=2, executed_item_count=1, approval_coverage_rate=1.0, execution_completion_rate=0.5)]),
            "2026-06-01T00-00-00Z": _owner_reporting_packet("2026-06-01T00-00-00Z", owners=[_owner_entry("shared-owner", item_count=1, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0)]),
            "2026-05-20T00-00-00Z": _owner_reporting_packet(
                "2026-05-20T00-00-00Z",
                owners=[
                    _owner_entry("shared-owner", item_count=1, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
                    _owner_entry("early-owner", item_count=2, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
                ],
            ),
        },
    )

    assert packet["owner_presence"]["entries"] == [
        {
            "owner": "early-owner",
            "run_count": 1,
            "first_window_run": "2026-05-20T00-00-00Z",
            "last_window_run": "2026-05-20T00-00-00Z",
            "in_first_window_run": True,
            "in_last_window_run": False,
        }
    ]


def test_build_reporting_trend_packet_surfaces_excluded_owner_presence_in_middle_runs() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 3,
        "runs": [
            _history_entry("2026-06-10T00-00-00Z", total_items=9, executed_item_count=1, approval_coverage_rate=1.0, execution_completion_rate=1 / 9),
            _history_entry("2026-06-01T00-00-00Z", total_items=9, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
            _history_entry("2026-05-20T00-00-00Z", total_items=10, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run={
            "2026-06-10T00-00-00Z": _owner_reporting_packet("2026-06-10T00-00-00Z", owners=[_owner_entry("shared-owner", item_count=2, executed_item_count=1, approval_coverage_rate=1.0, execution_completion_rate=0.5)]),
            "2026-06-01T00-00-00Z": _owner_reporting_packet(
                "2026-06-01T00-00-00Z",
                owners=[
                    _owner_entry("shared-owner", item_count=1, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
                    _owner_entry("middle-owner", item_count=1, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
                ],
            ),
            "2026-05-20T00-00-00Z": _owner_reporting_packet("2026-05-20T00-00-00Z", owners=[_owner_entry("shared-owner", item_count=1, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0)]),
        },
    )

    assert packet["owner_presence"]["entries"] == [
        {
            "owner": "middle-owner",
            "run_count": 1,
            "first_window_run": "2026-06-01T00-00-00Z",
            "last_window_run": "2026-06-01T00-00-00Z",
            "in_first_window_run": False,
            "in_last_window_run": False,
        }
    ]


def test_build_reporting_trend_packet_writes_no_excluded_owner_presence_state() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry("2026-06-10T00-00-00Z", total_items=9, executed_item_count=1, approval_coverage_rate=1.0, execution_completion_rate=1 / 9),
            _history_entry("2026-06-01T00-00-00Z", total_items=9, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run={
            "2026-06-10T00-00-00Z": _owner_reporting_packet("2026-06-10T00-00-00Z", owners=[_owner_entry("shared-owner", item_count=2, executed_item_count=1, approval_coverage_rate=1.0, execution_completion_rate=0.5)]),
            "2026-06-01T00-00-00Z": _owner_reporting_packet("2026-06-01T00-00-00Z", owners=[_owner_entry("shared-owner", item_count=1, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0)]),
        },
    )

    assert packet["owner_presence"] == {
        "presence_status": "no_excluded_owners",
        "window_run_count": 2,
        "entries": [],
    }


def test_build_reporting_trend_packet_keeps_owner_presence_null_when_owners_are_null() -> None:
    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet={
            "generated_at": "2026-06-12T00:00:00Z",
            "latest_run_stamp": "2026-06-10T00-00-00Z",
            "prior_run_stamp": None,
            "run_count": 1,
            "runs": [
                _history_entry("2026-06-10T00-00-00Z", total_items=9, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0)
            ],
        },
        reporting_packets_by_run={
            "2026-06-10T00-00-00Z": _owner_reporting_packet("2026-06-10T00-00-00Z", owners=[_owner_entry("omo-governance", item_count=3, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0)])
        },
    )

    assert packet["owners"] is None
    assert packet["owner_presence"] is None
```

- [ ] **Step 6: Run the new helper tests to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q -k "window_start or middle_runs or no_excluded_owner_presence_state or owner_presence_null"
```

Expected: FAIL until all edge-state behaviors line up.

- [ ] **Step 7: Make the smallest helper fixes and run the full helper suite**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit the nested helper/render change**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_reporting_trend.py && git -c core.hooksPath=/dev/null commit -m "feat(debt): add owner presence trend" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 2: Render `owner_presence` in trend markdown

**Files:**
- Modify: `.omo/tests/test_omo_debt_reporting_trend.py`
- Modify: `scripts/omo_debt_reporting_trend.py`
- Test: `.omo/tests/test_omo_debt_reporting_trend.py`

- [ ] **Step 1: Write the failing markdown test**

Append this regression:

```python
def test_render_reporting_trend_markdown_includes_owner_presence_section() -> None:
    packet = {
        "generated_at": "2026-06-12T01:00:00Z",
        "trend_status": "trend_available",
        "window_requested": None,
        "from_run_stamp_requested": None,
        "to_run_stamp_requested": None,
        "window_run_count": 3,
        "oldest_run_stamp": "2026-05-20T00-00-00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "runs": [],
        "intervals": [],
        "owners": {
            "owners_trend_status": "owners_trend_available",
            "shared_owner_count": 1,
            "owners_excluded_count": 1,
            "compared": [],
        },
        "owner_presence": {
            "presence_status": "presence_available",
            "window_run_count": 3,
            "entries": [
                {
                    "owner": "late-owner",
                    "run_count": 1,
                    "first_window_run": "2026-06-10T00-00-00Z",
                    "last_window_run": "2026-06-10T00-00-00Z",
                    "in_first_window_run": False,
                    "in_last_window_run": True,
                }
            ],
        },
    }

    markdown = render_reporting_trend_markdown(packet)

    assert "## Owner Presence" in markdown
    assert "presence_status=presence_available" in markdown
    assert "window_run_count=3" in markdown
    assert "late-owner" in markdown
    assert "in_last_window_run=True" in markdown
```

- [ ] **Step 2: Run the markdown test to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q -k owner_presence_section
```

Expected: FAIL because markdown rendering has no owner-presence section yet.

- [ ] **Step 3: Implement minimal owner-presence markdown**

Extend `render_reporting_trend_markdown(...)` like:

```python
owner_presence = packet.get("owner_presence")
if owner_presence is not None:
    lines.extend(
        [
            "## Owner Presence",
            "",
            f"presence_status={owner_presence['presence_status']}",
            f"window_run_count={owner_presence['window_run_count']}",
            "",
        ]
    )
    for entry in owner_presence["entries"]:
        lines.extend(
            [
                f"### Owner: {entry['owner']}",
                "",
                f"run_count={entry['run_count']}",
                f"first_window_run={entry['first_window_run']}",
                f"last_window_run={entry['last_window_run']}",
                f"in_first_window_run={entry['in_first_window_run']}",
                f"in_last_window_run={entry['in_last_window_run']}",
                "",
            ]
        )
```

- [ ] **Step 4: Run the markdown test to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q -k owner_presence_section
```

Expected: PASS.

### Task 3: Add CLI and docs coverage, then refresh artifacts

**Files:**
- Modify: `.omo/tests/test_omo_debt_cli.py`
- Modify: `.omo/tests/test_omo_debt_docs.py`
- Modify: `.omo/AGENT.md`
- Refresh: `.omo/debt/reporting/trend/current.yaml`
- Refresh: `.omo/debt/reporting/trend/current.md`
- Test: `.omo/tests/test_omo_debt_cli.py`
- Test: `.omo/tests/test_omo_debt_docs.py`

- [ ] **Step 1: Write the failing CLI regression**

Add this test to `.omo/tests/test_omo_debt_cli.py`:

```python
def test_debt_report_trend_last_window_surfaces_owner_presence_for_excluded_owner(tmp_path: Path) -> None:
    debt_dir = tmp_path / ".omo" / "debt"
    debt_dir.mkdir(parents=True, exist_ok=True)
    history_path = debt_dir / "reporting" / "history" / "current.yaml"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        yaml.safe_dump(
            {
                "generated_at": "2026-06-12T00:00:00Z",
                "latest_run_stamp": "2026-06-10T00-00-00Z",
                "prior_run_stamp": "2026-06-01T00-00-00Z",
                "run_count": 3,
                "runs": [
                    {
                        "run_stamp": "2026-06-10T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-06-10T00:00:00Z",
                        "total_items": 9,
                        "executed_item_count": 1,
                        "approval_coverage_rate": 1.0,
                        "execution_completion_rate": 1 / 9,
                    },
                    {
                        "run_stamp": "2026-06-01T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-06-01T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-06-01T00:00:00Z",
                        "total_items": 9,
                        "executed_item_count": 0,
                        "approval_coverage_rate": 0.0,
                        "execution_completion_rate": 0.0,
                    },
                    {
                        "run_stamp": "2026-05-20T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-05-20T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-05-20T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-05-20T00:00:00Z",
                        "total_items": 10,
                        "executed_item_count": 0,
                        "approval_coverage_rate": 0.0,
                        "execution_completion_rate": 0.0,
                    },
                ],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    _write_reporting_run_artifact(
        debt_dir,
        run_stamp="2026-06-10T00-00-00Z",
        pending_approval=0,
        ready_to_execute=8,
        executed=1,
        gate_item_count=1,
        approved_gate_item_count=1,
        approval_coverage_rate=1.0,
        executed_item_count=1,
        execution_completion_rate=1 / 9,
        owners=[
            {
                "owner": "shared-owner",
                "item_count": 2,
                "state_counts": {"pending_approval": 0, "ready_to_execute": 1, "executed": 1},
                "gate_item_count": 1,
                "approved_gate_item_count": 1,
                "approval_coverage_rate": 1.0,
                "executed_item_count": 1,
                "execution_completion_rate": 0.5,
            },
            {
                "owner": "late-owner",
                "item_count": 1,
                "state_counts": {"pending_approval": 0, "ready_to_execute": 1, "executed": 0},
                "gate_item_count": 0,
                "approved_gate_item_count": 0,
                "approval_coverage_rate": 1.0,
                "executed_item_count": 0,
                "execution_completion_rate": 0.0,
            },
        ],
    )
    _write_reporting_run_artifact(
        debt_dir,
        run_stamp="2026-06-01T00-00-00Z",
        pending_approval=0,
        ready_to_execute=9,
        executed=0,
        gate_item_count=1,
        approved_gate_item_count=0,
        approval_coverage_rate=0.0,
        executed_item_count=0,
        execution_completion_rate=0.0,
        owners=[
            {
                "owner": "shared-owner",
                "item_count": 1,
                "state_counts": {"pending_approval": 0, "ready_to_execute": 1, "executed": 0},
                "gate_item_count": 0,
                "approved_gate_item_count": 0,
                "approval_coverage_rate": 0.0,
                "executed_item_count": 0,
                "execution_completion_rate": 0.0,
            }
        ],
    )
    _write_reporting_run_artifact(
        debt_dir,
        run_stamp="2026-05-20T00-00-00Z",
        pending_approval=0,
        ready_to_execute=10,
        executed=0,
        gate_item_count=1,
        approved_gate_item_count=0,
        approval_coverage_rate=0.0,
        executed_item_count=0,
        execution_completion_rate=0.0,
        owners=[
            {
                "owner": "older-only",
                "item_count": 3,
                "state_counts": {"pending_approval": 0, "ready_to_execute": 3, "executed": 0},
                "gate_item_count": 0,
                "approved_gate_item_count": 0,
                "approval_coverage_rate": 0.0,
                "executed_item_count": 0,
                "execution_completion_rate": 0.0,
            }
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-trend",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--last",
            "2",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load((debt_dir / "reporting" / "trend" / "current.yaml").read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stderr
    assert packet["owner_presence"] == {
        "presence_status": "presence_available",
        "window_run_count": 2,
        "entries": [
            {
                "owner": "late-owner",
                "run_count": 1,
                "first_window_run": "2026-06-10T00-00-00Z",
                "last_window_run": "2026-06-10T00-00-00Z",
                "in_first_window_run": False,
                "in_last_window_run": True,
            }
        ],
    }
```

- [ ] **Step 2: Run the CLI regression to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py -q -k owner_presence_for_excluded_owner
```

Expected: FAIL because the live trend packet has no `owner_presence` block yet.

- [ ] **Step 3: Run the CLI regression to verify GREEN after helper work lands**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py -q -k owner_presence_for_excluded_owner
```

Expected: PASS.

- [ ] **Step 4: Write the failing docs regression**

Extend `.omo/tests/test_omo_debt_docs.py::test_omo_agent_documents_debt_refresh_flow` with:

```python
assert "owner_presence" in content
assert "presence_status" in content
assert "window-scoped" in content.lower()
assert "in_first_window_run" in content
assert "in_last_window_run" in content
assert "does not imply migration" in content.lower()
assert "two-run windows overlap conceptually with report-diff" in content.lower()
```

- [ ] **Step 5: Run the docs regression to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py -q -k omo_agent_documents_debt_refresh_flow
```

Expected: FAIL because `.omo/AGENT.md` does not yet mention `owner_presence`.

- [ ] **Step 6: Update `.omo/AGENT.md` and refresh live artifacts**

Add additive bullets under the trend section like:

```md
- `owner_presence` is a parallel trend block that explains excluded owners over the selected window without changing the shared-owner `owners` block
- `owner_presence` is window-scoped: it reports `run_count`, `first_window_run`, `last_window_run`, `in_first_window_run`, and `in_last_window_run` for owners that appear in some selected runs but not every selected run
- These fields do not imply owner migration, rename, or system-global appearance semantics
- Two-run windows overlap conceptually with `report-diff`, but `owner_presence` remains a selected-window trend surface rather than a pairwise diff surface
```

Then refresh:

```bash
cd /Users/xiamingxing/Workspace && python3 scripts/omo_debt.py report-trend --omo-dir .omo --from-run-stamp 2026-06-10T00-00-00Z --to-run-stamp 2026-06-10T00-00-00Z
```

Expected: `generated debt reporting trend packet`

The refreshed live packet should still show:

```yaml
trend_status: insufficient_history
owners: null
owner_presence: null
```

- [ ] **Step 7: Run the docs regression to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py -q -k omo_agent_documents_debt_refresh_flow
```

Expected: PASS.

- [ ] **Step 8: Commit the root-side tests/docs/artifact change**

Run:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/tests/test_omo_debt_reporting_trend.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_docs.py .omo/AGENT.md .omo/debt/reporting/trend/current.yaml .omo/debt/reporting/trend/current.md scripts && git -c core.hooksPath=/dev/null commit -m "feat(omo): add debt owner presence" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 4: Final verification

**Files:**
- Test: `.omo/tests/test_omo_debt_reporting_trend.py`
- Test: `.omo/tests/test_omo_debt_cli.py`
- Test: `.omo/tests/test_omo_debt_docs.py`

- [ ] **Step 1: Run the focused owner-presence suite**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_docs.py -q -k "reporting_trend or debt_report_trend or omo_agent_documents_debt_refresh_flow"
```

Expected: PASS.

- [ ] **Step 2: Run canonical `.omo` verification**

Run:

```bash
cd /Users/xiamingxing/Workspace && bash bin/verify-omo.sh
```

Expected: PASS with the repo's current full `.omo` regression count.

- [ ] **Step 3: Confirm only intended files are left changed**

Run:

```bash
cd /Users/xiamingxing/Workspace && git --no-pager status --short -- scripts .omo/tests/test_omo_debt_reporting_trend.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_docs.py .omo/AGENT.md .omo/debt/reporting/trend/current.yaml .omo/debt/reporting/trend/current.md && cd /Users/xiamingxing/Workspace/scripts && git --no-pager status --short -- omo_debt_reporting_trend.py
```

Expected: clean for the feature paths after the nested commit and root commit.
