# Debt Reporting State Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an additive `state_progress` block to `report-trend` so selected-window trend output shows how unfinished debt splits across `pending_approval`, `ready_to_execute`, and `executed`, anchored to the same oldest selected run as `execution_progress`.

**Architecture:** Keep the change inside the existing `report-trend` flow. The pure helper in `scripts/omo_debt_reporting_trend.py` should derive `state_progress` from selected history runs plus already-loaded per-run reporting artifacts, while the CLI continues to do all file I/O and simply reuses its current selected-run artifact loader. Rendering, docs, and live artifacts should be updated only after the helper contract is locked by tests.

**Tech Stack:** Python 3, PyYAML, pytest, `.omo` doc regressions, `bash bin/verify-omo.sh`

---

## File map

- Modify: `scripts/omo_debt_reporting_trend.py`
  - Add pure helper logic for `state_progress`
  - Keep `executed` sourced from history
  - Keep markdown rendering parallel to `execution_progress`
- Modify: `.omo/tests/test_omo_debt_reporting_trend.py`
  - Add helper regressions for happy path, unchanged/increase, null on insufficient history, anchor parity, mismatch fail-closed, and markdown rendering
- Modify: `.omo/tests/test_omo_debt_cli.py`
  - Add `report-trend --last 2` regression proving `state_progress` is emitted from selected per-run reporting artifacts
- Modify: `.omo/tests/test_omo_debt_docs.py`
  - Lock operator contract for `state_progress`
- Modify: `.omo/AGENT.md`
  - Document the new block, source-of-truth split, anchor parity, and delta semantics
- Refresh: `.omo/debt/reporting/trend/current.yaml`
- Refresh: `.omo/debt/reporting/trend/current.md`

## Repo boundary note

`scripts/` is a nested git repo / gitlink. Every implementation commit that touches `scripts/omo_debt_reporting_trend.py` should be committed in repo order:

1. commit inside `/Users/xiamingxing/Workspace/scripts`
2. then commit `/Users/xiamingxing/Workspace` so the root repo records the updated `scripts` gitlink plus `.omo/*` changes

## Task 1: Lock the happy-path helper contract

**Files:**
- Modify: `.omo/tests/test_omo_debt_reporting_trend.py`
- Modify: `scripts/omo_debt_reporting_trend.py`

- [ ] **Step 1: Write the failing helper regression for artifact-backed state progress**

Add this test near the existing `execution_progress` helper tests in `.omo/tests/test_omo_debt_reporting_trend.py`:

```python
def test_build_reporting_trend_packet_adds_state_progress_from_selected_reporting_artifacts() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 3,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=8,
                executed_item_count=3,
                approval_coverage_rate=1.0,
                execution_completion_rate=3 / 8,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
            _history_entry(
                "2026-05-20T00-00-00Z",
                total_items=10,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
        ],
    }

    reporting_packets_by_run = {
        "2026-05-20T00-00-00Z": _owner_reporting_packet("2026-05-20T00-00-00Z", owners=[]),
        "2026-06-01T00-00-00Z": _owner_reporting_packet("2026-06-01T00-00-00Z", owners=[]),
        "2026-06-10T00-00-00Z": _owner_reporting_packet("2026-06-10T00-00-00Z", owners=[]),
    }
    reporting_packets_by_run["2026-05-20T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 4,
        "ready_to_execute": 6,
        "executed": 0,
    }
    reporting_packets_by_run["2026-06-01T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 2,
        "ready_to_execute": 6,
        "executed": 1,
    }
    reporting_packets_by_run["2026-06-10T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 1,
        "ready_to_execute": 4,
        "executed": 3,
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run=reporting_packets_by_run,
    )

    assert packet["state_progress"] == {
        "state_progress_status": "state_progress_available",
        "anchor_run_stamp": "2026-05-20T00-00-00Z",
        "baseline_pending_approval": 4,
        "runs": [
            {
                "run_stamp": "2026-05-20T00-00-00Z",
                "pending_approval": 4,
                "ready_to_execute": 6,
                "executed": 0,
                "pending_approval_delta_vs_baseline": 0,
            },
            {
                "run_stamp": "2026-06-01T00-00-00Z",
                "pending_approval": 2,
                "ready_to_execute": 6,
                "executed": 1,
                "pending_approval_delta_vs_baseline": -2,
            },
            {
                "run_stamp": "2026-06-10T00-00-00Z",
                "pending_approval": 1,
                "ready_to_execute": 4,
                "executed": 3,
                "pending_approval_delta_vs_baseline": -3,
            },
        ],
    }
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py::test_build_reporting_trend_packet_adds_state_progress_from_selected_reporting_artifacts -q
```

Expected: `FAIL` with `KeyError: 'state_progress'` or an equivalent assertion failure showing the block is missing.

- [ ] **Step 3: Add the minimal helper implementation**

Patch `scripts/omo_debt_reporting_trend.py` by adding a state-progress run builder, a state-progress aggregator, and the new packet field:

```python
def _state_progress_run(
    run: dict[str, object],
    reporting_packet: dict[str, object],
    baseline_pending_approval: int,
) -> dict[str, object]:
    state_counts = reporting_packet["summary"]["state_counts"]
    pending_approval = int(state_counts["pending_approval"])
    executed = int(run["executed_item_count"])
    ready_to_execute = int(run["total_items"]) - pending_approval - executed
    return {
        "run_stamp": run["run_stamp"],
        "pending_approval": pending_approval,
        "ready_to_execute": ready_to_execute,
        "executed": executed,
        "pending_approval_delta_vs_baseline": pending_approval - baseline_pending_approval,
    }


def _state_progress(
    ordered_runs: list[dict[str, object]],
    reporting_packets_by_run: dict[str, dict[str, object]] | None,
) -> dict[str, object] | None:
    if len(ordered_runs) < 2 or reporting_packets_by_run is None:
        return None

    anchor_run = ordered_runs[0]
    anchor_packet = reporting_packets_by_run[str(anchor_run["run_stamp"])]
    baseline_pending_approval = int(anchor_packet["summary"]["state_counts"]["pending_approval"])
    runs = [
        _state_progress_run(
            run,
            reporting_packets_by_run[str(run["run_stamp"])],
            baseline_pending_approval,
        )
        for run in ordered_runs
    ]
    return {
        "state_progress_status": "state_progress_available",
        "anchor_run_stamp": anchor_run["run_stamp"],
        "baseline_pending_approval": baseline_pending_approval,
        "runs": runs,
    }
```

And thread it into `build_reporting_trend_packet(...)`:

```python
    state_progress = _state_progress(ordered_runs, reporting_packets_by_run)
    return {
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
        "execution_progress": execution_progress,
        "state_progress": state_progress,
    }
```

- [ ] **Step 4: Re-run the helper test and then the helper file**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py::test_build_reporting_trend_packet_adds_state_progress_from_selected_reporting_artifacts -q
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q -k 'state_progress or execution_progress'
```

Expected:

1. the targeted test is `1 passed`
2. the focused helper subset is green

- [ ] **Step 5: Commit the helper slice in repo order**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_reporting_trend.py && git -c core.hooksPath=/dev/null commit -m "feat(debt): add state progress helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
cd /Users/xiamingxing/Workspace && git add scripts .omo/tests/test_omo_debt_reporting_trend.py && git -c core.hooksPath=/dev/null commit -m "test(omo): cover debt state progress helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Task 2: Enforce invariants and null semantics

**Files:**
- Modify: `.omo/tests/test_omo_debt_reporting_trend.py`
- Modify: `scripts/omo_debt_reporting_trend.py`

- [ ] **Step 1: Add edge-case helper regressions**

Add these tests after the happy-path test in `.omo/tests/test_omo_debt_reporting_trend.py`:

```python
def test_build_reporting_trend_packet_keeps_state_progress_null_for_insufficient_history() -> None:
    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet={
            "generated_at": "2026-06-12T00:00:00Z",
            "latest_run_stamp": "2026-06-10T00-00-00Z",
            "prior_run_stamp": None,
            "run_count": 1,
            "runs": [
                _history_entry(
                    "2026-06-10T00-00-00Z",
                    total_items=8,
                    executed_item_count=3,
                    approval_coverage_rate=1.0,
                    execution_completion_rate=3 / 8,
                )
            ],
        },
    )

    assert packet["state_progress"] is None


def test_build_reporting_trend_packet_aligns_state_progress_anchor_with_execution_progress() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=8,
                executed_item_count=3,
                approval_coverage_rate=1.0,
                execution_completion_rate=3 / 8,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
        ],
    }
    reporting_packets_by_run = {
        "2026-06-01T00-00-00Z": _owner_reporting_packet("2026-06-01T00-00-00Z", owners=[]),
        "2026-06-10T00-00-00Z": _owner_reporting_packet("2026-06-10T00-00-00Z", owners=[]),
    }
    reporting_packets_by_run["2026-06-01T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 2,
        "ready_to_execute": 6,
        "executed": 1,
    }
    reporting_packets_by_run["2026-06-10T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 4,
        "ready_to_execute": 1,
        "executed": 3,
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run=reporting_packets_by_run,
    )

    assert packet["state_progress"]["anchor_run_stamp"] == packet["execution_progress"]["anchor_run_stamp"]
    assert [run["run_stamp"] for run in packet["state_progress"]["runs"]] == [
        run["run_stamp"] for run in packet["execution_progress"]["runs"]
    ]


def test_build_reporting_trend_packet_keeps_state_progress_unchanged_at_baseline() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=8,
                executed_item_count=3,
                approval_coverage_rate=1.0,
                execution_completion_rate=3 / 8,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
        ],
    }
    reporting_packets_by_run = {
        "2026-06-01T00-00-00Z": _owner_reporting_packet("2026-06-01T00-00-00Z", owners=[]),
        "2026-06-10T00-00-00Z": _owner_reporting_packet("2026-06-10T00-00-00Z", owners=[]),
    }
    reporting_packets_by_run["2026-06-01T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 2,
        "ready_to_execute": 6,
        "executed": 1,
    }
    reporting_packets_by_run["2026-06-10T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 2,
        "ready_to_execute": 3,
        "executed": 3,
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run=reporting_packets_by_run,
    )

    assert packet["state_progress"]["runs"] == [
        {
            "run_stamp": "2026-06-01T00-00-00Z",
            "pending_approval": 2,
            "ready_to_execute": 6,
            "executed": 1,
            "pending_approval_delta_vs_baseline": 0,
        },
        {
            "run_stamp": "2026-06-10T00-00-00Z",
            "pending_approval": 2,
            "ready_to_execute": 3,
            "executed": 3,
            "pending_approval_delta_vs_baseline": 0,
        },
    ]


def test_build_reporting_trend_packet_reports_state_progress_increase_vs_baseline() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=8,
                executed_item_count=2,
                approval_coverage_rate=1.0,
                execution_completion_rate=0.25,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=8,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=0.125,
            ),
        ],
    }
    reporting_packets_by_run = {
        "2026-06-01T00-00-00Z": _owner_reporting_packet("2026-06-01T00-00-00Z", owners=[]),
        "2026-06-10T00-00-00Z": _owner_reporting_packet("2026-06-10T00-00-00Z", owners=[]),
    }
    reporting_packets_by_run["2026-06-01T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 1,
        "ready_to_execute": 6,
        "executed": 1,
    }
    reporting_packets_by_run["2026-06-10T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 3,
        "ready_to_execute": 3,
        "executed": 2,
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run=reporting_packets_by_run,
    )

    assert packet["state_progress"]["runs"][-1] == {
        "run_stamp": "2026-06-10T00-00-00Z",
        "pending_approval": 3,
        "ready_to_execute": 3,
        "executed": 2,
        "pending_approval_delta_vs_baseline": 2,
    }


def test_build_reporting_trend_packet_fails_closed_when_state_counts_do_not_match_total_items() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=8,
                executed_item_count=3,
                approval_coverage_rate=1.0,
                execution_completion_rate=3 / 8,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
        ],
    }
    reporting_packets_by_run = {
        "2026-06-01T00-00-00Z": _owner_reporting_packet("2026-06-01T00-00-00Z", owners=[]),
        "2026-06-10T00-00-00Z": _owner_reporting_packet("2026-06-10T00-00-00Z", owners=[]),
    }
    reporting_packets_by_run["2026-06-01T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 2,
        "ready_to_execute": 99,
        "executed": 1,
    }
    reporting_packets_by_run["2026-06-10T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 1,
        "ready_to_execute": 4,
        "executed": 3,
    }

    with pytest.raises(ValueError, match="invalid state progress counts for run: 2026-06-01T00-00-00Z"):
        build_reporting_trend_packet(
            generated_at="2026-06-12T01:00:00Z",
            history_packet=history_packet,
            reporting_packets_by_run=reporting_packets_by_run,
        )
```

- [ ] **Step 2: Run the new edge tests and verify at least one fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q -k 'state_progress and (insufficient_history or aligns_state_progress_anchor or state_counts_do_not_match_total_items)'
```

Expected: `FAIL` because the helper does not yet validate mismatched state counts, even though the unchanged/increase tests may already pass once the basic helper exists.

- [ ] **Step 3: Add validation and keep the helper null-safe**

Update `scripts/omo_debt_reporting_trend.py` so `_state_progress_run(...)` validates the derived identity:

```python
def _state_progress_run(
    run: dict[str, object],
    reporting_packet: dict[str, object],
    baseline_pending_approval: int,
) -> dict[str, object]:
    state_counts = reporting_packet["summary"]["state_counts"]
    pending_approval = int(state_counts["pending_approval"])
    executed = int(run["executed_item_count"])
    ready_to_execute = int(run["total_items"]) - pending_approval - executed
    artifact_ready_to_execute = int(state_counts["ready_to_execute"])
    if artifact_ready_to_execute != ready_to_execute:
        raise ValueError(f"invalid state progress counts for run: {run['run_stamp']}")
    return {
        "run_stamp": run["run_stamp"],
        "pending_approval": pending_approval,
        "ready_to_execute": ready_to_execute,
        "executed": executed,
        "pending_approval_delta_vs_baseline": pending_approval - baseline_pending_approval,
    }
```

And keep `_state_progress(...)` returning `None` when:

```python
if len(ordered_runs) < 2 or reporting_packets_by_run is None:
    return None
```

- [ ] **Step 4: Re-run the targeted edge tests and the full helper module**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q -k 'state_progress'
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q
```

Expected:

1. the `state_progress` subset is green
2. the full trend helper file stays green

- [ ] **Step 5: Commit the invariant slice in repo order**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_reporting_trend.py && git -c core.hooksPath=/dev/null commit -m "feat(debt): validate state progress counts" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
cd /Users/xiamingxing/Workspace && git add scripts .omo/tests/test_omo_debt_reporting_trend.py && git -c core.hooksPath=/dev/null commit -m "test(omo): harden debt state progress regressions" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Task 3: Render the new block in markdown

**Files:**
- Modify: `.omo/tests/test_omo_debt_reporting_trend.py`
- Modify: `scripts/omo_debt_reporting_trend.py`

- [ ] **Step 1: Add the markdown regression**

Append this test after the current execution-progress markdown test in `.omo/tests/test_omo_debt_reporting_trend.py`:

```python
def test_render_reporting_trend_markdown_includes_state_progress_section() -> None:
    packet = {
        "generated_at": "2026-06-12T01:00:00Z",
        "trend_status": "trend_available",
        "window_requested": None,
        "from_run_stamp_requested": None,
        "to_run_stamp_requested": None,
        "window_run_count": 2,
        "oldest_run_stamp": "2026-06-01T00-00-00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "runs": [],
        "intervals": [],
        "owners": None,
        "owner_presence": None,
        "execution_progress": None,
        "state_progress": {
            "state_progress_status": "state_progress_available",
            "anchor_run_stamp": "2026-06-01T00-00-00Z",
            "baseline_pending_approval": 2,
            "runs": [
                {
                    "run_stamp": "2026-06-01T00-00-00Z",
                    "pending_approval": 2,
                    "ready_to_execute": 6,
                    "executed": 1,
                    "pending_approval_delta_vs_baseline": 0,
                },
                {
                    "run_stamp": "2026-06-10T00-00-00Z",
                    "pending_approval": 1,
                    "ready_to_execute": 4,
                    "executed": 3,
                    "pending_approval_delta_vs_baseline": -1,
                },
            ],
        },
    }

    markdown = render_reporting_trend_markdown(packet)

    assert "## State Progress" in markdown
    assert "state_progress_status=state_progress_available" in markdown
    assert "baseline_pending_approval=2" in markdown
    assert "### State Run: 2026-06-10T00-00-00Z" in markdown
    assert "pending_approval_delta_vs_baseline=-1" in markdown
```

- [ ] **Step 2: Run the markdown test and verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py::test_render_reporting_trend_markdown_includes_state_progress_section -q
```

Expected: `FAIL` because `render_reporting_trend_markdown(...)` does not yet emit the new section.

- [ ] **Step 3: Render `state_progress` in `render_reporting_trend_markdown(...)`**

Append this block after the existing execution-progress section in `scripts/omo_debt_reporting_trend.py`:

```python
    state_progress = packet.get("state_progress")
    if state_progress is not None:
        lines.extend(
            [
                "## State Progress",
                "",
                f"state_progress_status={state_progress['state_progress_status']}",
                f"anchor_run_stamp={state_progress['anchor_run_stamp']}",
                f"baseline_pending_approval={state_progress['baseline_pending_approval']}",
                "",
            ]
        )
        for run in state_progress["runs"]:
            lines.extend(
                [
                    f"### State Run: {run['run_stamp']}",
                    "",
                    f"pending_approval={run['pending_approval']}",
                    f"ready_to_execute={run['ready_to_execute']}",
                    f"executed={run['executed']}",
                    f"pending_approval_delta_vs_baseline={run['pending_approval_delta_vs_baseline']}",
                    "",
                ]
            )
```

- [ ] **Step 4: Re-run the markdown regression and the trend render subset**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py::test_render_reporting_trend_markdown_includes_state_progress_section -q
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q -k 'render_reporting_trend_markdown'
```

Expected:

1. the targeted markdown regression passes
2. all markdown-focused trend tests stay green

- [ ] **Step 5: Commit the markdown slice in repo order**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_reporting_trend.py && git -c core.hooksPath=/dev/null commit -m "feat(debt): render state progress" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
cd /Users/xiamingxing/Workspace && git add scripts .omo/tests/test_omo_debt_reporting_trend.py && git -c core.hooksPath=/dev/null commit -m "test(omo): cover debt state progress markdown" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Task 4: Wire the CLI proof, docs, live artifacts, and final verification

**Files:**
- Modify: `.omo/tests/test_omo_debt_cli.py`
- Modify: `.omo/tests/test_omo_debt_docs.py`
- Modify: `.omo/AGENT.md`
- Refresh: `.omo/debt/reporting/trend/current.yaml`
- Refresh: `.omo/debt/reporting/trend/current.md`

- [ ] **Step 1: Add the CLI regression and docs assertions**

Add this CLI regression near `test_debt_report_trend_writes_execution_progress_for_selected_last_window(...)` in `.omo/tests/test_omo_debt_cli.py`:

```python
def test_debt_report_trend_writes_state_progress_for_selected_last_window(tmp_path: Path) -> None:
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
                        "total_items": 8,
                        "executed_item_count": 3,
                        "approval_coverage_rate": 1.0,
                        "execution_completion_rate": 3 / 8,
                    },
                    {
                        "run_stamp": "2026-06-01T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-06-01T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-06-01T00:00:00Z",
                        "total_items": 9,
                        "executed_item_count": 1,
                        "approval_coverage_rate": 1.0,
                        "execution_completion_rate": 1 / 9,
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
        pending_approval=1,
        ready_to_execute=4,
        executed=3,
        gate_item_count=1,
        approved_gate_item_count=1,
        approval_coverage_rate=1.0,
        executed_item_count=3,
        execution_completion_rate=3 / 8,
        owners=[],
    )
    _write_reporting_run_artifact(
        debt_dir,
        run_stamp="2026-06-01T00-00-00Z",
        pending_approval=2,
        ready_to_execute=6,
        executed=1,
        gate_item_count=1,
        approved_gate_item_count=1,
        approval_coverage_rate=1.0,
        executed_item_count=1,
        execution_completion_rate=1 / 9,
        owners=[],
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
    assert packet["state_progress"] == {
        "state_progress_status": "state_progress_available",
        "anchor_run_stamp": "2026-06-01T00-00-00Z",
        "baseline_pending_approval": 2,
        "runs": [
            {
                "run_stamp": "2026-06-01T00-00-00Z",
                "pending_approval": 2,
                "ready_to_execute": 6,
                "executed": 1,
                "pending_approval_delta_vs_baseline": 0,
            },
            {
                "run_stamp": "2026-06-10T00-00-00Z",
                "pending_approval": 1,
                "ready_to_execute": 4,
                "executed": 3,
                "pending_approval_delta_vs_baseline": -1,
            },
        ],
    }
```

Extend `.omo/tests/test_omo_debt_docs.py::test_omo_agent_documents_debt_refresh_flow` with:

```python
    assert "state_progress" in content
    assert "state_progress_status" in content
    assert "state_progress_available" in content
    assert "artifacts_unavailable" in content
    assert "baseline_pending_approval" in content
    assert "pending_approval_delta_vs_baseline" in content
    assert "ready_to_execute is derived" in content.lower()
    assert "same oldest selected run anchor" in content.lower()
```

- [ ] **Step 2: Run the CLI/docs regressions and verify the remaining failure is docs-only**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py::test_debt_report_trend_writes_state_progress_for_selected_last_window -q
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py::test_omo_agent_documents_debt_refresh_flow -q
```

Expected:

1. the CLI regression should already pass if the helper wiring from Tasks 1-3 is correct
2. the docs regression should fail because `.omo/AGENT.md` does not mention the new block yet

- [ ] **Step 3: Update `.omo/AGENT.md` with the operator contract**

Add bullets immediately after the existing `execution_progress` bullets:

```markdown
- `state_progress` is a parallel summary block inside `report-trend`; it is not a forecast and it is intentionally narrower than projection work
- `state_progress` uses explicit statuses: `state_progress_available` when selected reporting artifacts are available for the whole window, and `artifacts_unavailable` as the helper-level semantic when they are not
- `state_progress` shares the same oldest selected run anchor as `execution_progress` via `anchor_run_stamp`
- `baseline_pending_approval` comes from the oldest selected run's reporting artifact `summary.state_counts.pending_approval`
- `pending_approval` comes from each selected run's reporting artifact summary state counts, while `executed` stays aligned with history `executed_item_count`
- `ready_to_execute` is derived as `total_items - pending_approval - executed` so the block stays internally consistent with summary totals
- `pending_approval_delta_vs_baseline` is sign-explicit: negative means fewer approval-blocked items than baseline, zero means unchanged, and positive means more approval-blocked items than baseline
- `state_progress` stays null when `trend_status` is `insufficient_history`; there is no silent success path for missing selected-run artifacts
```

- [ ] **Step 4: Re-run focused tests, refresh the live artifact, and run canonical verification**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_docs.py -q -k 'state_progress or debt_report_trend or omo_agent_documents_debt_refresh_flow'
cd /Users/xiamingxing/Workspace && python3 scripts/omo_debt.py report-trend --omo-dir .omo --from-run-stamp 2026-06-10T00-00-00Z --to-run-stamp 2026-06-10T00-00-00Z
cd /Users/xiamingxing/Workspace && bash bin/verify-omo.sh
```

Expected:

1. the focused trend/docs/CLI slice is green
2. `.omo/debt/reporting/trend/current.yaml` and `.md` are regenerated
3. the live single-run artifact still shows `trend_status: insufficient_history`, `owners: null`, `owner_presence: null`, `execution_progress: null`, and `state_progress: null`
4. canonical verification is green

- [ ] **Step 5: Commit the root closeout**

Run:

```bash
cd /Users/xiamingxing/Workspace && git add scripts .omo/tests/test_omo_debt_reporting_trend.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_docs.py .omo/AGENT.md .omo/debt/reporting/trend/current.yaml .omo/debt/reporting/trend/current.md && git -c core.hooksPath=/dev/null commit -m "feat(omo): add debt state progress" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Spec coverage checklist

- `state_progress` additive block in `report-trend`: Task 1
- anchor parity with `execution_progress`: Task 2
- `executed` from history and `pending_approval` from artifact summary counts: Task 1 + Task 4 docs
- fail-closed count identity: Task 2
- markdown rendering: Task 3
- CLI selected-window regression: Task 4
- docs/operator guidance: Task 4
- live artifact refresh and canonical verification: Task 4
