---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Debt Reporting Execution Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a narrow additive `execution_progress` block to `report-trend` so operators can compare unfinished debt against the oldest selected run without introducing forecast semantics.

**Architecture:** Keep all progress math inside the pure trend helper by deriving `open_item_count = total_items - executed_item_count` from already selected summary runs. Emit a top-level `execution_progress` block in the packet, render it in markdown, then lock the contract with CLI/docs regressions and refreshed live artifacts.

**Tech Stack:** Python 3, argparse, PyYAML, pytest, existing `scripts/omo_debt_reporting_trend.py` helper, existing `scripts/omo_debt.py` trend command, `.omo` docs/tests, nested `scripts/` git repo + root gitlink workflow

---

## File structure map

- Modify: `scripts/omo_debt_reporting_trend.py`
  - Add the pure `execution_progress` helper and markdown rendering.
- Modify: `.omo/tests/test_omo_debt_reporting_trend.py`
  - Add helper regressions for normal baseline-relative progress, unchanged/increasing open counts, baseline-zero handling, insufficient-history null behavior, and markdown rendering.
- Modify: `.omo/tests/test_omo_debt_cli.py`
  - Add a CLI regression showing `report-trend --last 2` emits `execution_progress` from the selected window with no new CLI loader logic.
- Modify: `.omo/AGENT.md`
  - Document `execution_progress`, `open_item_count`, sign semantics, and the deliberate non-forecast contract.
- Modify: `.omo/tests/test_omo_debt_docs.py`
  - Lock the updated operator guidance.
- Refresh: `.omo/debt/reporting/trend/current.yaml`
  - Regenerate the live packet; the current repo state should still produce `execution_progress: null` because only one run is selected.
- Refresh: `.omo/debt/reporting/trend/current.md`
  - Regenerate markdown from the refreshed live packet.

## Implementation notes before starting

- Work from `/Users/xiamingxing/Workspace`.
- Do **not** use a root worktree; `scripts/` is a nested git repo / gitlink and live verification depends on the nested repo contents.
- Preserve these contracts:
  1. no new command
  2. no projection / slope / forecast math
  3. `execution_progress` is top-level and additive
  4. `execution_progress` is `null` when `trend_status` is `insufficient_history`
  5. `open_item_count = total_items - executed_item_count`
  6. `progress_status` is `progress_available` or `baseline_fully_executed`
  7. `open_item_delta_vs_baseline < 0` means progress
- Commit in repo order:
  1. nested `scripts` repo helper commit(s)
  2. root repo tests/docs/artifacts + gitlink update

### Task 1: Add the core `execution_progress` helper contract

**Files:**
- Modify: `.omo/tests/test_omo_debt_reporting_trend.py`
- Modify: `scripts/omo_debt_reporting_trend.py`
- Test: `.omo/tests/test_omo_debt_reporting_trend.py`

- [ ] **Step 1: Write the failing helper test for baseline-relative execution progress**

Add this test to `.omo/tests/test_omo_debt_reporting_trend.py`:

```python
def test_build_reporting_trend_packet_adds_execution_progress_from_oldest_selected_run() -> None:
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

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
    )

    assert packet["execution_progress"] == {
        "progress_status": "progress_available",
        "anchor_run_stamp": "2026-05-20T00-00-00Z",
        "baseline_open_item_count": 10,
        "runs": [
            {
                "run_stamp": "2026-05-20T00-00-00Z",
                "open_item_count": 10,
                "open_item_delta_vs_baseline": 0,
                "open_item_ratio_vs_baseline": 1.0,
            },
            {
                "run_stamp": "2026-06-01T00-00-00Z",
                "open_item_count": 8,
                "open_item_delta_vs_baseline": -2,
                "open_item_ratio_vs_baseline": 0.8,
            },
            {
                "run_stamp": "2026-06-10T00-00-00Z",
                "open_item_count": 5,
                "open_item_delta_vs_baseline": -5,
                "open_item_ratio_vs_baseline": 0.5,
            },
        ],
    }
```

- [ ] **Step 2: Run the helper test to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q -k execution_progress_from_oldest_selected_run
```

Expected: FAIL because the packet has no `execution_progress` block yet.

- [ ] **Step 3: Write the minimal helper implementation**

Add these helpers to `scripts/omo_debt_reporting_trend.py` and thread the new block into `build_reporting_trend_packet(...)`:

```python
def _execution_progress_run(
    run: dict[str, object],
    baseline_open_item_count: int,
) -> dict[str, object]:
    open_item_count = int(run["total_items"]) - int(run["executed_item_count"])
    return {
        "run_stamp": run["run_stamp"],
        "open_item_count": open_item_count,
        "open_item_delta_vs_baseline": open_item_count - baseline_open_item_count,
        "open_item_ratio_vs_baseline": open_item_count / baseline_open_item_count,
    }


def _execution_progress(
    ordered_runs: list[dict[str, object]],
) -> dict[str, object] | None:
    if len(ordered_runs) < 2:
        return None

    anchor_run = ordered_runs[0]
    baseline_open_item_count = int(anchor_run["total_items"]) - int(anchor_run["executed_item_count"])
    progress_runs = [
        _execution_progress_run(run, baseline_open_item_count)
        for run in ordered_runs
    ]
    return {
        "progress_status": "progress_available",
        "anchor_run_stamp": anchor_run["run_stamp"],
        "baseline_open_item_count": baseline_open_item_count,
        "runs": progress_runs,
    }
```

Then add the field to the packet return:

```python
execution_progress = _execution_progress(ordered_runs)
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
}
```

- [ ] **Step 4: Run the helper test to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q -k execution_progress_from_oldest_selected_run
```

Expected: PASS.

- [ ] **Step 5: Commit the nested helper change**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_reporting_trend.py && git -c core.hooksPath=/dev/null commit -m "feat(debt): add execution progress helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: commit succeeds in the nested `scripts` repo.

### Task 2: Handle baseline-zero and remaining helper edges

**Files:**
- Modify: `.omo/tests/test_omo_debt_reporting_trend.py`
- Modify: `scripts/omo_debt_reporting_trend.py`
- Test: `.omo/tests/test_omo_debt_reporting_trend.py`

- [ ] **Step 1: Write failing helper tests for baseline-zero and null activation**

Append these tests:

```python
def test_build_reporting_trend_packet_marks_execution_progress_baseline_fully_executed() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=4,
                executed_item_count=2,
                approval_coverage_rate=1.0,
                execution_completion_rate=0.5,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=3,
                executed_item_count=3,
                approval_coverage_rate=1.0,
                execution_completion_rate=1.0,
            ),
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
    )

    assert packet["execution_progress"] == {
        "progress_status": "baseline_fully_executed",
        "anchor_run_stamp": "2026-06-01T00-00-00Z",
        "baseline_open_item_count": 0,
        "runs": [
            {
                "run_stamp": "2026-06-01T00-00-00Z",
                "open_item_count": 0,
                "open_item_delta_vs_baseline": 0,
                "open_item_ratio_vs_baseline": None,
            },
            {
                "run_stamp": "2026-06-10T00-00-00Z",
                "open_item_count": 2,
                "open_item_delta_vs_baseline": 2,
                "open_item_ratio_vs_baseline": None,
            },
        ],
    }


def test_build_reporting_trend_packet_leaves_execution_progress_null_when_history_is_insufficient() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": None,
        "run_count": 1,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            )
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
    )

    assert packet["trend_status"] == "insufficient_history"
    assert packet["execution_progress"] is None
```

Also add these coverage tests, which should remain green after the helper is fixed:

```python
def test_build_reporting_trend_packet_keeps_execution_progress_unchanged_at_baseline() -> None:
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
                total_items=7,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 7,
            ),
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
    )

    assert packet["execution_progress"]["runs"][-1] == {
        "run_stamp": "2026-06-10T00-00-00Z",
        "open_item_count": 6,
        "open_item_delta_vs_baseline": 0,
        "open_item_ratio_vs_baseline": 1.0,
    }


def test_build_reporting_trend_packet_surfaces_execution_progress_increase_vs_baseline() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=10,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=0.1,
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

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
    )

    assert packet["execution_progress"]["runs"][-1] == {
        "run_stamp": "2026-06-10T00-00-00Z",
        "open_item_count": 9,
        "open_item_delta_vs_baseline": 2,
        "open_item_ratio_vs_baseline": 9 / 7,
    }
```

- [ ] **Step 2: Run the helper tests to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q -k 'baseline_fully_executed or execution_progress_null'
```

Expected: FAIL because the first implementation divides by zero or reports the wrong status when `baseline_open_item_count == 0`.

- [ ] **Step 3: Extend the helper to handle baseline-zero safely**

Replace the helper bodies with:

```python
def _execution_progress_run(
    run: dict[str, object],
    baseline_open_item_count: int,
) -> dict[str, object]:
    open_item_count = int(run["total_items"]) - int(run["executed_item_count"])
    return {
        "run_stamp": run["run_stamp"],
        "open_item_count": open_item_count,
        "open_item_delta_vs_baseline": open_item_count - baseline_open_item_count,
        "open_item_ratio_vs_baseline": (
            None
            if baseline_open_item_count == 0
            else open_item_count / baseline_open_item_count
        ),
    }


def _execution_progress(
    ordered_runs: list[dict[str, object]],
) -> dict[str, object] | None:
    if len(ordered_runs) < 2:
        return None

    anchor_run = ordered_runs[0]
    baseline_open_item_count = int(anchor_run["total_items"]) - int(anchor_run["executed_item_count"])
    progress_runs = [
        _execution_progress_run(run, baseline_open_item_count)
        for run in ordered_runs
    ]
    return {
        "progress_status": (
            "baseline_fully_executed"
            if baseline_open_item_count == 0
            else "progress_available"
        ),
        "anchor_run_stamp": anchor_run["run_stamp"],
        "baseline_open_item_count": baseline_open_item_count,
        "runs": progress_runs,
    }
```

- [ ] **Step 4: Run the helper suite to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q -k 'execution_progress'
```

Expected: PASS for the new `execution_progress` helper coverage.

- [ ] **Step 5: Commit the nested helper edge handling**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_reporting_trend.py && git -c core.hooksPath=/dev/null commit -m "feat(debt): handle execution progress baseline" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: commit succeeds in the nested `scripts` repo.

### Task 3: Render `execution_progress` in trend markdown

**Files:**
- Modify: `.omo/tests/test_omo_debt_reporting_trend.py`
- Modify: `scripts/omo_debt_reporting_trend.py`
- Test: `.omo/tests/test_omo_debt_reporting_trend.py`

- [ ] **Step 1: Write the failing markdown regression**

Append this test:

```python
def test_render_reporting_trend_markdown_includes_execution_progress_section() -> None:
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
        "owners": None,
        "owner_presence": None,
        "execution_progress": {
            "progress_status": "progress_available",
            "anchor_run_stamp": "2026-05-20T00-00-00Z",
            "baseline_open_item_count": 10,
            "runs": [
                {
                    "run_stamp": "2026-05-20T00-00-00Z",
                    "open_item_count": 10,
                    "open_item_delta_vs_baseline": 0,
                    "open_item_ratio_vs_baseline": 1.0,
                },
                {
                    "run_stamp": "2026-06-10T00-00-00Z",
                    "open_item_count": 5,
                    "open_item_delta_vs_baseline": -5,
                    "open_item_ratio_vs_baseline": 0.5,
                },
            ],
        },
    }

    markdown = render_reporting_trend_markdown(packet)

    assert "## Execution Progress" in markdown
    assert "progress_status=progress_available" in markdown
    assert "anchor_run_stamp=2026-05-20T00-00-00Z" in markdown
    assert "baseline_open_item_count=10" in markdown
    assert "### Progress Run: 2026-06-10T00-00-00Z" in markdown
    assert "open_item_delta_vs_baseline=-5" in markdown
    assert "open_item_ratio_vs_baseline=0.5" in markdown
```

- [ ] **Step 2: Run the markdown test to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q -k execution_progress_section
```

Expected: FAIL because markdown rendering has no `Execution Progress` section yet.

- [ ] **Step 3: Render the new block in markdown**

Extend `render_reporting_trend_markdown(...)` with:

```python
execution_progress = packet.get("execution_progress")
if execution_progress is not None:
    lines.extend(
        [
            "## Execution Progress",
            "",
            f"progress_status={execution_progress['progress_status']}",
            f"anchor_run_stamp={execution_progress['anchor_run_stamp']}",
            f"baseline_open_item_count={execution_progress['baseline_open_item_count']}",
            "",
        ]
    )
    for run in execution_progress["runs"]:
        lines.extend(
            [
                f"### Progress Run: {run['run_stamp']}",
                "",
                f"open_item_count={run['open_item_count']}",
                f"open_item_delta_vs_baseline={run['open_item_delta_vs_baseline']}",
                f"open_item_ratio_vs_baseline={run['open_item_ratio_vs_baseline']}",
                "",
            ]
        )
```

- [ ] **Step 4: Run the full helper suite to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the nested markdown/render change**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_reporting_trend.py && git -c core.hooksPath=/dev/null commit -m "feat(debt): render execution progress" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: commit succeeds in the nested `scripts` repo.

### Task 4: Lock CLI, docs, and live artifacts

**Files:**
- Modify: `.omo/tests/test_omo_debt_cli.py`
- Modify: `.omo/tests/test_omo_debt_docs.py`
- Modify: `.omo/AGENT.md`
- Refresh: `.omo/debt/reporting/trend/current.yaml`
- Refresh: `.omo/debt/reporting/trend/current.md`
- Test: `.omo/tests/test_omo_debt_cli.py`
- Test: `.omo/tests/test_omo_debt_docs.py`

- [ ] **Step 1: Add the CLI regression and docs regression**

Append this CLI regression to `.omo/tests/test_omo_debt_cli.py`:

```python
def test_debt_report_trend_writes_execution_progress_for_selected_last_window(tmp_path: Path) -> None:
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
    assert packet["window_requested"] == 2
    assert packet["execution_progress"] == {
        "progress_status": "progress_available",
        "anchor_run_stamp": "2026-06-01T00-00-00Z",
        "baseline_open_item_count": 8,
        "runs": [
            {
                "run_stamp": "2026-06-01T00-00-00Z",
                "open_item_count": 8,
                "open_item_delta_vs_baseline": 0,
                "open_item_ratio_vs_baseline": 1.0,
            },
            {
                "run_stamp": "2026-06-10T00-00-00Z",
                "open_item_count": 5,
                "open_item_delta_vs_baseline": -3,
                "open_item_ratio_vs_baseline": 0.625,
            },
        ],
    }
```

Extend `.omo/tests/test_omo_debt_docs.py` with:

```python
    assert "execution_progress" in content
    assert "open_item_count" in content
    assert "open_item_delta_vs_baseline" in content
    assert "open_item_ratio_vs_baseline" in content
    assert "baseline_open_item_count" in content
    assert "anchor_run_stamp" in content
    assert "progress_available" in content
    assert "baseline_fully_executed" in content
    assert "not a forecast" in content.lower()
    assert "negative `open_item_delta_vs_baseline` means progress" in content.lower()
    assert "scope growth" in content.lower()
```

- [ ] **Step 2: Run the CLI/docs regressions**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py -q -k execution_progress_for_selected_last_window && python3 -m pytest .omo/tests/test_omo_debt_docs.py -q
```

Expected:

1. the CLI regression may already PASS once the helper layer is done
2. the docs regression should FAIL until `.omo/AGENT.md` documents the new contract

- [ ] **Step 3: Update docs and refresh live artifacts**

Add these bullets to the trend section of `.omo/AGENT.md`:

```markdown
- `execution_progress` is a parallel summary block inside `report-trend`; it is not a forecast and it is intentionally not named `burndown`
- `open_item_count` is derived as `total_items - executed_item_count`, so it measures unfinished items rather than total scope
- `execution_progress` anchors to the oldest selected run via `anchor_run_stamp` and `baseline_open_item_count`
- `open_item_delta_vs_baseline` is sign-explicit: negative means progress, zero means unchanged, and positive means more unfinished items than the baseline run
- `open_item_ratio_vs_baseline` is `null` when `baseline_open_item_count` is zero; that state is reported as `baseline_fully_executed`
- `execution_progress` can move upward when scope grows; use `intervals[*].total_items_delta` to inspect adjacent scope movement
```

Then refresh the live artifact:

```bash
cd /Users/xiamingxing/Workspace && python3 scripts/omo_debt.py report-trend --omo-dir .omo --from-run-stamp 2026-06-10T00-00-00Z --to-run-stamp 2026-06-10T00-00-00Z
```

Expected: the current live packet remains a single-run `insufficient_history` state and writes `execution_progress: null`.

- [ ] **Step 4: Run focused and canonical verification**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_docs.py -q -k 'reporting_trend or debt_report_trend or omo_agent_documents_debt_refresh_flow or execution_progress' && bash bin/verify-omo.sh
```

Expected:

1. focused regressions PASS
2. full `bin/verify-omo.sh` PASS

- [ ] **Step 5: Commit the root repo closeout**

Run:

```bash
cd /Users/xiamingxing/Workspace && git add scripts .omo/AGENT.md .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_docs.py .omo/tests/test_omo_debt_reporting_trend.py .omo/debt/reporting/trend/current.yaml .omo/debt/reporting/trend/current.md && git -c core.hooksPath=/dev/null commit -m "feat(omo): add debt execution progress" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: root commit succeeds with the nested `scripts` gitlink update plus tests/docs/artifacts.
