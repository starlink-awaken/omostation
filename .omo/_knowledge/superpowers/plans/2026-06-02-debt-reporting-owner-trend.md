---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Debt Reporting Owner Trend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `report-trend` with a deterministic owner-level multi-run trend block for shared owners across the selected window.

**Architecture:** Keep `reporting/history/current.yaml` as the canonical run-selection input. Preserve the pure trend helper by passing it an optional `reporting_packets_by_run` mapping that the CLI loads from each selected history entry's `reporting_ref`, then let the helper build an additive `owners` block without changing the existing summary trend contract.

**Tech Stack:** Python 3, argparse, PyYAML, pytest, existing `scripts/omo_debt.py` CLI, `scripts/omo_debt_reporting_trend.py`, `.omo` docs/tests, nested `scripts/` git repo + root gitlink workflow

---

## File structure map

- Modify: `scripts/omo_debt_reporting_trend.py`
  - Keep summary trend logic intact, add owner-series helpers, and accept optional `reporting_packets_by_run`.
- Modify: `.omo/tests/test_omo_debt_reporting_trend.py`
  - Add pure helper regressions for shared owners, selected-window-relative intersections, `no_shared_owners`, `owners is None` under insufficient history, and fail-closed owner metadata.
- Modify: `scripts/omo_debt.py`
  - Load per-run reporting packets from `reporting_ref` for trend invocations and pass them into the pure helper.
- Modify: `.omo/tests/test_omo_debt_cli.py`
  - Cover CLI hydration of owner trends, selected-window-relative shared owners, and missing owner reporting artifacts.
- Modify: `.omo/AGENT.md`
  - Document shared-owner trend semantics, owner-scoped metric names, `owners_trend_status`, and the continued deferral of sparse gaps.
- Modify: `.omo/tests/test_omo_debt_docs.py`
  - Lock the updated operator guidance.
- Refresh: `.omo/debt/reporting/trend/current.yaml`
  - Regenerate live artifact; with the current single-run repo state it should show `owners: null`.
- Refresh: `.omo/debt/reporting/trend/current.md`
  - Regenerate markdown from the live packet.

## Implementation notes before starting

- Work from `/Users/xiamingxing/Workspace`.
- Do **not** use a root worktree; `scripts/` is still a nested git repo / gitlink and live verification depends on the nested repo contents.
- Preserve these existing contracts:
  1. summary `trend_status`, `runs[]`, and `intervals[]` stay unchanged
  2. window/range selection still happens before oldest-to-newest rendering
  3. `--last` and explicit run ranges keep their current validation semantics
  4. `report-diff` stays untouched
- Keep the helper pure:
  1. do **not** read files from `scripts/omo_debt_reporting_trend.py`
  2. `scripts/omo_debt.py` should load per-run reporting packets and pass them into the helper
  3. existing helper tests that only care about summary trend should continue to work without providing owner inputs
- Commit in repo order:
  1. nested `scripts` repo helper commit
  2. nested `scripts` repo CLI commit
  3. root repo commit for tests/docs/artifacts + gitlink update

### Task 1: Extend the pure trend helper with owner-series support

**Files:**
- Modify: `.omo/tests/test_omo_debt_reporting_trend.py`
- Modify: `scripts/omo_debt_reporting_trend.py`
- Test: `.omo/tests/test_omo_debt_reporting_trend.py`

- [ ] **Step 1: Write the first failing helper test for shared-owner trend output**

Add these fixtures and test to `.omo/tests/test_omo_debt_reporting_trend.py`:

```python
def _owner_reporting_packet(
    run_stamp: str,
    *,
    owners: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "generated_at": "2026-06-12T00:00:00Z",
        "dispatch_run_ref": f".omo/debt/dispatch/runs/{run_stamp}.yaml",
        "run_stamp": run_stamp,
        "summary": {
            "owner_count": len(owners),
            "total_items": 9,
            "state_counts": {
                "pending_approval": 0,
                "ready_to_execute": 9,
                "executed": 0,
            },
            "gate_item_count": 1,
            "approved_gate_item_count": 0,
            "approval_coverage_rate": 0.0,
            "executed_item_count": 0,
            "execution_completion_rate": 0.0,
        },
        "owners": owners,
    }


def _owner_entry(
    owner: str,
    *,
    item_count: int,
    executed_item_count: int,
    approval_coverage_rate: float,
    execution_completion_rate: float,
) -> dict[str, object]:
    return {
        "owner": owner,
        "item_count": item_count,
        "state_counts": {
            "pending_approval": 0,
            "ready_to_execute": item_count - executed_item_count,
            "executed": executed_item_count,
        },
        "gate_item_count": item_count,
        "approved_gate_item_count": int(item_count * approval_coverage_rate),
        "approval_coverage_rate": approval_coverage_rate,
        "executed_item_count": executed_item_count,
        "execution_completion_rate": execution_completion_rate,
    }


def test_build_reporting_trend_packet_adds_shared_owner_series() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run={
            "2026-06-10T00-00-00Z": _owner_reporting_packet(
                "2026-06-10T00-00-00Z",
                owners=[
                    _owner_entry(
                        "commerce-governance",
                        item_count=2,
                        executed_item_count=0,
                        approval_coverage_rate=1.0,
                        execution_completion_rate=0.0,
                    ),
                    _owner_entry(
                        "omo-governance",
                        item_count=3,
                        executed_item_count=1,
                        approval_coverage_rate=1.0,
                        execution_completion_rate=1 / 3,
                    ),
                ],
            ),
            "2026-06-01T00-00-00Z": _owner_reporting_packet(
                "2026-06-01T00-00-00Z",
                owners=[
                    _owner_entry(
                        "omo-governance",
                        item_count=2,
                        executed_item_count=0,
                        approval_coverage_rate=1.0,
                        execution_completion_rate=0.0,
                    ),
                    _owner_entry(
                        "commerce-governance",
                        item_count=1,
                        executed_item_count=0,
                        approval_coverage_rate=0.0,
                        execution_completion_rate=0.0,
                    ),
                ],
            ),
        },
    )

    assert packet["trend_status"] == "trend_available"
    assert packet["owners"]["owners_trend_status"] == "owners_trend_available"
    assert packet["owners"]["shared_owner_count"] == 2
    assert packet["owners"]["owners_excluded_count"] == 0
    assert [entry["owner"] for entry in packet["owners"]["compared"]] == [
        "commerce-governance",
        "omo-governance",
    ]
    assert packet["owners"]["compared"][0]["runs"][0]["item_count"] == 1
    assert packet["owners"]["compared"][0]["runs"][1]["item_count"] == 2
    assert packet["owners"]["compared"][1]["intervals"][0]["executed_item_count_delta"] == 1
```

- [ ] **Step 2: Run the helper test to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q -k shared_owner_series
```

Expected: FAIL because `build_reporting_trend_packet(...)` does not yet accept `reporting_packets_by_run` and has no `owners` block.

- [ ] **Step 3: Implement the minimal owner-series helper path**

Update `scripts/omo_debt_reporting_trend.py` with focused helpers like:

```python
def _owner_trend_run(owner: str, run_stamp: str, entry: dict[str, object]) -> dict[str, object]:
    if any(
        entry[field] is None
        for field in (
            "item_count",
            "executed_item_count",
            "approval_coverage_rate",
            "execution_completion_rate",
        )
    ):
        raise ValueError(f"missing owner trend metadata for owner {owner} in run: {run_stamp}")
    return {
        "run_stamp": run_stamp,
        "item_count": entry["item_count"],
        "executed_item_count": entry["executed_item_count"],
        "approval_coverage_rate": entry["approval_coverage_rate"],
        "execution_completion_rate": entry["execution_completion_rate"],
    }


def _owner_interval(previous: dict[str, object], current: dict[str, object]) -> dict[str, object]:
    return {
        "from_run_stamp": previous["run_stamp"],
        "to_run_stamp": current["run_stamp"],
        "item_count_delta": current["item_count"] - previous["item_count"],
        "executed_item_count_delta": current["executed_item_count"] - previous["executed_item_count"],
        "approval_coverage_rate_delta": current["approval_coverage_rate"] - previous["approval_coverage_rate"],
        "execution_completion_rate_delta": current["execution_completion_rate"] - previous["execution_completion_rate"],
    }


def _owner_trends(
    ordered_runs: list[dict[str, object]],
    reporting_packets_by_run: dict[str, dict[str, object]] | None,
) -> dict[str, object] | None:
    if len(ordered_runs) < 2 or reporting_packets_by_run is None:
        return None

    owners_by_run = []
    union_names: set[str] = set()
    for run in ordered_runs:
        run_stamp = str(run["run_stamp"])
        reporting_packet = reporting_packets_by_run.get(run_stamp)
        if reporting_packet is None:
            raise ValueError(f"missing owner reporting packet for run: {run_stamp}")
        owner_map = {str(entry["owner"]): entry for entry in reporting_packet.get("owners", [])}
        owners_by_run.append(owner_map)
        union_names |= set(owner_map.keys())

    shared_names = sorted(set.intersection(*(set(owner_map.keys()) for owner_map in owners_by_run)))
    if not shared_names:
        return {
            "owners_trend_status": "no_shared_owners",
            "shared_owner_count": 0,
            "owners_excluded_count": len(union_names),
            "compared": [],
        }

    compared = []
    for owner_name in shared_names:
        owner_runs = [
            _owner_trend_run(owner_name, str(run["run_stamp"]), owner_map[owner_name])
            for run, owner_map in zip(ordered_runs, owners_by_run, strict=True)
        ]
        compared.append(
            {
                "owner": owner_name,
                "runs": owner_runs,
                "intervals": [
                    _owner_interval(owner_runs[index], owner_runs[index + 1])
                    for index in range(len(owner_runs) - 1)
                ],
            }
        )

    return {
        "owners_trend_status": "owners_trend_available",
        "shared_owner_count": len(shared_names),
        "owners_excluded_count": len(union_names - set(shared_names)),
        "compared": compared,
    }
```

Then thread it into `build_reporting_trend_packet(...)`:

```python
def build_reporting_trend_packet(
    *,
    generated_at: str,
    history_packet: dict[str, object],
    reporting_packets_by_run: dict[str, dict[str, object]] | None = None,
    window_requested: int | None = None,
    from_run_stamp_requested: str | None = None,
    to_run_stamp_requested: str | None = None,
) -> dict[str, object]:
    ...
    owners = _owner_trends(ordered_runs, reporting_packets_by_run)
    return {
        ...
        "intervals": intervals,
        "owners": owners,
    }
```

- [ ] **Step 4: Run the shared-owner helper test to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q -k shared_owner_series
```

Expected: PASS.

- [ ] **Step 5: Add failing helper tests for selected-window-relative intersections and empty shared-owner state**

Append these tests:

```python
def test_build_reporting_trend_packet_computes_shared_owners_relative_to_selected_window() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 3,
        "runs": [
            _history_entry("2026-06-10T00-00-00Z", total_items=9, executed_item_count=1, approval_coverage_rate=1.0, execution_completion_rate=1 / 9),
            _history_entry("2026-06-01T00-00-00Z", total_items=9, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
            _history_entry("2026-05-20T00-00-00Z", total_items=9, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        window_requested=2,
        reporting_packets_by_run={
            "2026-06-10T00-00-00Z": _owner_reporting_packet("2026-06-10T00-00-00Z", owners=[_owner_entry("shared-owner", item_count=2, executed_item_count=1, approval_coverage_rate=1.0, execution_completion_rate=0.5)]),
            "2026-06-01T00-00-00Z": _owner_reporting_packet("2026-06-01T00-00-00Z", owners=[_owner_entry("shared-owner", item_count=1, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0)]),
            "2026-05-20T00-00-00Z": _owner_reporting_packet("2026-05-20T00-00-00Z", owners=[_owner_entry("older-only", item_count=3, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0)]),
        },
    )

    assert [entry["owner"] for entry in packet["owners"]["compared"]] == ["shared-owner"]
    assert packet["owners"]["owners_excluded_count"] == 0


def test_build_reporting_trend_packet_writes_no_shared_owners_state() -> None:
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
            "2026-06-10T00-00-00Z": _owner_reporting_packet("2026-06-10T00-00-00Z", owners=[_owner_entry("new-owner", item_count=2, executed_item_count=1, approval_coverage_rate=1.0, execution_completion_rate=0.5)]),
            "2026-06-01T00-00-00Z": _owner_reporting_packet("2026-06-01T00-00-00Z", owners=[_owner_entry("old-owner", item_count=1, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0)]),
        },
    )

    assert packet["trend_status"] == "trend_available"
    assert packet["owners"] == {
        "owners_trend_status": "no_shared_owners",
        "shared_owner_count": 0,
        "owners_excluded_count": 2,
        "compared": [],
    }
```

- [ ] **Step 6: Run the new helper tests to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q -k "selected_window or no_shared_owners"
```

Expected: FAIL until `owners_excluded_count` and selected-window-relative intersection logic are correct.

- [ ] **Step 7: Add the remaining minimal helper behavior and one fail-closed regression**

Append this additional regression and finish the implementation:

```python
def test_build_reporting_trend_packet_omits_owner_block_for_insufficient_history() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": None,
        "run_count": 1,
        "runs": [
            _history_entry("2026-06-10T00-00-00Z", total_items=9, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0)
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run={
            "2026-06-10T00-00-00Z": _owner_reporting_packet(
                "2026-06-10T00-00-00Z",
                owners=[_owner_entry("omo-governance", item_count=3, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0)],
            )
        },
    )

    assert packet["trend_status"] == "insufficient_history"
    assert packet["owners"] is None


def test_build_reporting_trend_packet_rejects_missing_owner_reporting_packet() -> None:
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

    with pytest.raises(ValueError, match="missing owner reporting packet for run: 2026-06-01T00-00-00Z"):
        build_reporting_trend_packet(
            generated_at="2026-06-12T01:00:00Z",
            history_packet=history_packet,
            reporting_packets_by_run={
                "2026-06-10T00-00-00Z": _owner_reporting_packet(
                    "2026-06-10T00-00-00Z",
                    owners=[_owner_entry("omo-governance", item_count=3, executed_item_count=1, approval_coverage_rate=1.0, execution_completion_rate=1 / 3)],
                )
            },
        )
```

No extra architecture is needed beyond `_owner_trends(...)`; just make sure it returns `None` when `len(ordered_runs) < 2`.

- [ ] **Step 8: Run the full helper suite to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit the nested helper change**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_reporting_trend.py && git -c core.hooksPath=/dev/null commit -m "feat(debt): add owner trend helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 2: Wire owner-trend inputs through the CLI

**Files:**
- Modify: `.omo/tests/test_omo_debt_cli.py`
- Modify: `scripts/omo_debt.py`
- Test: `.omo/tests/test_omo_debt_cli.py`

- [ ] **Step 1: Write the first failing CLI test for owner trend hydration**

Add this test to `.omo/tests/test_omo_debt_cli.py`:

```python
def test_debt_report_trend_writes_owner_block_from_reporting_run_artifacts(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    older_dispatch = tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-01T00-00-00Z.yaml"
    older_dispatch.parent.mkdir(parents=True, exist_ok=True)
    older_dispatch.write_text(
        (tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-10T00-00-00Z.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    older_reporting_dir = tmp_path / ".omo" / "debt" / "reporting" / "runs" / "2026-06-01T00-00-00Z"
    older_reporting_dir.mkdir(parents=True, exist_ok=True)
    older_reporting_dir.joinpath("current.yaml").write_text(
        yaml.safe_dump(
            {
                "generated_at": "2026-06-01T01:00:00Z",
                "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                "run_stamp": "2026-06-01T00-00-00Z",
                "summary": {
                    "owner_count": 2,
                    "total_items": 9,
                    "state_counts": {"pending_approval": 1, "ready_to_execute": 8, "executed": 0},
                    "gate_item_count": 1,
                    "approved_gate_item_count": 0,
                    "approval_coverage_rate": 0.0,
                    "executed_item_count": 0,
                    "execution_completion_rate": 0.0,
                },
                "owners": [
                    {
                        "owner": "commerce-governance",
                        "item_count": 1,
                        "state_counts": {"pending_approval": 1, "ready_to_execute": 0, "executed": 0},
                        "gate_item_count": 1,
                        "approved_gate_item_count": 0,
                        "approval_coverage_rate": 0.0,
                        "executed_item_count": 0,
                        "execution_completion_rate": 0.0,
                    },
                    {
                        "owner": "omo-governance",
                        "item_count": 2,
                        "state_counts": {"pending_approval": 0, "ready_to_execute": 2, "executed": 0},
                        "gate_item_count": 0,
                        "approved_gate_item_count": 0,
                        "approval_coverage_rate": 1.0,
                        "executed_item_count": 0,
                        "execution_completion_rate": 0.0,
                    },
                ],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [sys.executable, "scripts/omo_debt.py", "report-history", "--omo-dir", str(tmp_path / ".omo")],
        check=True,
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    result = subprocess.run(
        [sys.executable, "scripts/omo_debt.py", "report-trend", "--omo-dir", str(tmp_path / ".omo")],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load((tmp_path / ".omo" / "debt" / "reporting" / "trend" / "current.yaml").read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stderr
    assert packet["trend_status"] == "trend_available"
    assert packet["owners"]["owners_trend_status"] == "owners_trend_available"
    assert [entry["owner"] for entry in packet["owners"]["compared"]] == [
        "commerce-governance",
        "omo-governance",
    ]
```

- [ ] **Step 2: Run the CLI test to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py -q -k owner_block_from_reporting_run_artifacts
```

Expected: FAIL because `reporting_trend_outputs(...)` does not yet load and pass `reporting_packets_by_run`.

- [ ] **Step 3: Implement CLI loading for owner trend inputs**

Update `scripts/omo_debt.py` with a focused loader:

```python
def _reporting_trend_owner_inputs(history_packet: dict[str, object], omo_dir: Path) -> dict[str, dict[str, object]]:
    packets: dict[str, dict[str, object]] = {}
    for entry in history_packet["runs"]:
        run_stamp = str(entry["run_stamp"])
        reporting_ref = entry.get("reporting_ref")
        if reporting_ref is None:
            continue
        reporting_path = omo_dir / Path(str(reporting_ref)).relative_to(".omo")
        if not reporting_path.exists():
            raise FileNotFoundError(f"missing reporting artifact for owner trend: {reporting_path}")
        packets[run_stamp] = _load_yaml(reporting_path)
    return packets


def reporting_trend_outputs(
    omo_dir: Path,
    window_requested: int | None = None,
    from_run_stamp_requested: str | None = None,
    to_run_stamp_requested: str | None = None,
) -> None:
    history_packet = load_reporting_history_packet(omo_dir)
    ...
    reporting_packets_by_run = _reporting_trend_owner_inputs(history_packet, omo_dir)
    write_reporting_trend_packet(
        omo_dir,
        build_reporting_trend_packet(
            generated_at=_timestamp(),
            history_packet=history_packet,
            reporting_packets_by_run=reporting_packets_by_run,
            window_requested=window_requested,
            from_run_stamp_requested=from_run_stamp_requested,
            to_run_stamp_requested=to_run_stamp_requested,
        ),
    )
```

Do **not** move file I/O into `scripts/omo_debt_reporting_trend.py`.

- [ ] **Step 4: Run the first CLI test to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py -q -k owner_block_from_reporting_run_artifacts
```

Expected: PASS.

- [ ] **Step 5: Add failing CLI tests for selected-window semantics and missing owner artifacts**

Append these tests:

```python
def test_debt_report_trend_owner_intersection_respects_last_window(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")
    # add 2026-06-01 and 2026-05-20 dispatch/reporting runs; only the newest two share `shared-owner`
    # then run report-history and:
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

    packet = yaml.safe_load((tmp_path / ".omo" / "debt" / "reporting" / "trend" / "current.yaml").read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stderr
    assert [entry["owner"] for entry in packet["owners"]["compared"]] == ["shared-owner"]


def test_debt_report_trend_rejects_missing_owner_reporting_artifact(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    older_dispatch = tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-01T00-00-00Z.yaml"
    older_dispatch.parent.mkdir(parents=True, exist_ok=True)
    older_dispatch.write_text(
        (tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-10T00-00-00Z.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    subprocess.run(
        [sys.executable, "scripts/omo_debt.py", "report-history", "--omo-dir", str(tmp_path / ".omo")],
        check=True,
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    result = subprocess.run(
        [sys.executable, "scripts/omo_debt.py", "report-trend", "--omo-dir", str(tmp_path / ".omo")],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "missing reporting artifact for owner trend" in result.stderr
```

- [ ] **Step 6: Run the new CLI tests to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py -q -k "owner_intersection_respects_last_window or missing_owner_reporting_artifact"
```

Expected: FAIL until the loader and helper behavior line up on window-relative shared owners and missing files.

- [ ] **Step 7: Make the smallest CLI-side fixes and rerun the focused CLI subset**

If the `--last` test fails because the intersection is computed over all visible runs, fix the helper — not the CLI test. Then run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py -q -k "report_trend and (owner_block_from_reporting_run_artifacts or owner_intersection_respects_last_window or missing_owner_reporting_artifact)"
```

Expected: PASS.

- [ ] **Step 8: Commit the nested CLI change**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt.py && git -c core.hooksPath=/dev/null commit -m "feat(debt): wire owner trend inputs" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 3: Document the owner trend surface and refresh live artifacts

**Files:**
- Modify: `.omo/tests/test_omo_debt_docs.py`
- Modify: `.omo/AGENT.md`
- Refresh: `.omo/debt/reporting/trend/current.yaml`
- Refresh: `.omo/debt/reporting/trend/current.md`
- Test: `.omo/tests/test_omo_debt_docs.py`

- [ ] **Step 1: Write the failing docs regression**

Extend `.omo/tests/test_omo_debt_docs.py::test_omo_agent_documents_debt_refresh_flow` with:

```python
assert "owners_trend_status" in content
assert "shared_owner_count" in content
assert "owners_excluded_count" in content
assert "item_count" in content
assert "shared-owner intersection" in content.lower()
assert "selected window only" in content.lower()
assert "no_shared_owners" in content
assert "owners_trend_available" in content
assert "owners: null" in content.lower() or "owners is null" in content.lower()
assert "sparse gaps" in content.lower()
```

- [ ] **Step 2: Run the docs test to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py -q -k omo_agent_documents_debt_refresh_flow
```

Expected: FAIL because `.omo/AGENT.md` still says owner trends are deferred.

- [ ] **Step 3: Update `.omo/AGENT.md` with the live owner trend guidance**

Replace the current trend guidance block with additive bullets like:

```md
- `report-trend` can now enrich the summary trend with an owner-level trend block for shared owners across the selected window
- Owner trend enrichment still uses `reporting/history/current.yaml` to choose runs, then follows each selected run's `reporting_ref` to read owner metrics from the already-derived per-run reporting artifact
- Owner trends are shared-owner only in Version 1: an owner appears only when it is present in every selected run in the chosen full-history / `--last` / explicit-range window
- `owners_trend_status` is explicit: `owners_trend_available` when at least one shared owner exists, `no_shared_owners` when the selected multi-run window has no shared owners, and `owners` stays `null` when `trend_status` is `insufficient_history`
- Owner trend metrics are owner-scoped: `item_count`, `executed_item_count`, `approval_coverage_rate`, and `execution_completion_rate`
- `owners_excluded_count` reports owners that appeared somewhere in the selected window but not in every selected run
- Sparse owner gaps, owner migration semantics, and slope math remain deferred
```

- [ ] **Step 4: Run the docs test to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py -q -k omo_agent_documents_debt_refresh_flow
```

Expected: PASS.

- [ ] **Step 5: Refresh the live trend artifacts**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 scripts/omo_debt.py report-trend --omo-dir .omo --from-run-stamp 2026-06-10T00-00-00Z --to-run-stamp 2026-06-10T00-00-00Z
```

Expected: `generated debt reporting trend packet`

Because the live repo currently has a single reporting run in scope, `current.yaml` should now contain:

```yaml
trend_status: insufficient_history
owners: null
```

- [ ] **Step 6: Commit the root-side docs/tests/artifact change**

Run:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/tests/test_omo_debt_reporting_trend.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_docs.py .omo/AGENT.md .omo/debt/reporting/trend/current.yaml .omo/debt/reporting/trend/current.md scripts && git -c core.hooksPath=/dev/null commit -m "feat(omo): add debt owner trend" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 4: Final verification

**Files:**
- Test: `.omo/tests/test_omo_debt_reporting_trend.py`
- Test: `.omo/tests/test_omo_debt_cli.py`
- Test: `.omo/tests/test_omo_debt_docs.py`

- [ ] **Step 1: Run the focused owner-trend suite**

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
cd /Users/xiamingxing/Workspace && git --no-pager status --short -- scripts .omo/tests/test_omo_debt_reporting_trend.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_docs.py .omo/AGENT.md .omo/debt/reporting/trend/current.yaml .omo/debt/reporting/trend/current.md && cd /Users/xiamingxing/Workspace/scripts && git --no-pager status --short -- omo_debt.py omo_debt_reporting_trend.py
```

Expected: clean for the feature paths after the nested commits and root commit.
