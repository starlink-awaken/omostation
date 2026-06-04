# Debt Reporting Run Range Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `report-trend` with an explicit closed-interval run-stamp range mode so operators can inspect an interior historical window with `--from-run-stamp <STAMP> --to-run-stamp <STAMP>`.

**Architecture:** Keep the slice additive. Reuse `reporting/history/current.yaml` as the canonical input, add a small range-selection path to the pure trend helper, then wire `scripts/omo_debt.py` to expose mutually exclusive selection modes (`full history`, `--last`, or explicit run range). Preserve `report-diff`, keep missing-reporting metadata fail-closed, and surface the requested range through additive packet fields.

**Tech Stack:** Python 3, argparse, PyYAML, pytest, existing `scripts/omo_debt.py` CLI, `scripts/omo_debt_reporting_history.py`, `scripts/omo_debt_reporting_trend.py`, `.omo` governance docs/tests

---

## File structure map

- Modify: `scripts/omo_debt_reporting_trend.py`
  - Add range-aware selection logic, explicit run-stamp validation, and additive requested-range packet fields.
- Modify: `.omo/tests/test_omo_debt_reporting_trend.py`
  - Add focused helper regressions for inclusive range selection, invalid stamps, missing stamps, reversed ranges, and missing metadata inside the selected interval.
- Modify: `scripts/omo_debt.py`
  - Add CLI args `--from-run-stamp` / `--to-run-stamp`, conflict detection with `--last`, and dispatch those values into the helper.
- Modify: `.omo/tests/test_omo_debt_cli.py`
  - Add CLI regressions for happy-path range mode, partial bounds, mutual exclusion with `--last`, and malformed/missing bounds.
- Refresh: `.omo/debt/reporting/trend/current.yaml`
  - Hydrate live trend artifact with `from_run_stamp_requested` / `to_run_stamp_requested`.
- Refresh: `.omo/debt/reporting/trend/current.md`
  - Refresh the human-readable trend artifact after the range path lands.
- Modify: `.omo/AGENT.md`
  - Document the new range-mode command, inclusive semantics, and requested-range packet fields.
- Modify: `.omo/tests/test_omo_debt_docs.py`
  - Lock the updated operator guidance.

## Implementation notes before starting

- Work from `/Users/xiamingxing/Workspace`.
- This repo still requires pathspec-limited commits because `scripts/` is a nested git repo / gitlink; mixed `scripts/*` + root changes must be committed in repo order without cleaning unrelated changes.
- Do **not** use a root worktree; the live `scripts/` contents still do not materialize correctly there.
- Keep the slice narrow:
  1. require both `--from-run-stamp` and `--to-run-stamp`
  2. keep endpoints inclusive
  3. keep `--last` semantics unchanged
  4. forbid combining range flags with `--last`
  5. keep `report-diff` untouched
  6. do not add single-bound open ranges
  7. do not add owner trends or projection math

### Task 1: Teach the pure trend helper to select inclusive run ranges

**Files:**
- Modify: `scripts/omo_debt_reporting_trend.py`
- Modify: `.omo/tests/test_omo_debt_reporting_trend.py`
- Test: `.omo/tests/test_omo_debt_reporting_trend.py`

- [ ] **Step 1: Write the failing helper tests**

Add these tests to `.omo/tests/test_omo_debt_reporting_trend.py`:

```python
def test_build_reporting_trend_packet_selects_inclusive_range_by_run_stamp() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 5,
        "runs": [
            _history_entry("2026-06-10T00-00-00Z", total_items=9, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
            _history_entry("2026-06-01T00-00-00Z", total_items=9, executed_item_count=1, approval_coverage_rate=1.0, execution_completion_rate=1 / 9),
            _history_entry("2026-05-20T00-00-00Z", total_items=10, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
            _history_entry("2026-05-10T00-00-00Z", total_items=11, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
            _history_entry("2026-05-01T00-00-00Z", total_items=12, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        from_run_stamp_requested="2026-05-20T00-00-00Z",
        to_run_stamp_requested="2026-06-10T00-00-00Z",
    )

    assert packet["window_requested"] is None
    assert packet["from_run_stamp_requested"] == "2026-05-20T00-00-00Z"
    assert packet["to_run_stamp_requested"] == "2026-06-10T00-00-00Z"
    assert packet["window_run_count"] == 3
    assert [entry["run_stamp"] for entry in packet["runs"]] == [
        "2026-05-20T00-00-00Z",
        "2026-06-01T00-00-00Z",
        "2026-06-10T00-00-00Z",
    ]


def test_build_reporting_trend_packet_rejects_invalid_requested_range_stamp() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry("2026-06-10T00-00-00Z", total_items=9, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
            _history_entry("2026-06-01T00-00-00Z", total_items=9, executed_item_count=1, approval_coverage_rate=1.0, execution_completion_rate=1 / 9),
        ],
    }

    with pytest.raises(ValueError, match="invalid from-run-stamp: 2026-06-01T00:00:00Z"):
        build_reporting_trend_packet(
            generated_at="2026-06-12T01:00:00Z",
            history_packet=history_packet,
            from_run_stamp_requested="2026-06-01T00:00:00Z",
            to_run_stamp_requested="2026-06-10T00-00-00Z",
        )


def test_build_reporting_trend_packet_rejects_missing_requested_range_stamp() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry("2026-06-10T00-00-00Z", total_items=9, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
            _history_entry("2026-06-01T00-00-00Z", total_items=9, executed_item_count=1, approval_coverage_rate=1.0, execution_completion_rate=1 / 9),
        ],
    }

    with pytest.raises(ValueError, match="from-run-stamp not in history: 2026-05-20T00-00-00Z"):
        build_reporting_trend_packet(
            generated_at="2026-06-12T01:00:00Z",
            history_packet=history_packet,
            from_run_stamp_requested="2026-05-20T00-00-00Z",
            to_run_stamp_requested="2026-06-10T00-00-00Z",
        )


def test_build_reporting_trend_packet_rejects_reversed_semantic_range() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 3,
        "runs": [
            _history_entry("2026-06-10T00-00-00Z", total_items=9, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
            _history_entry("2026-06-01T00-00-00Z", total_items=9, executed_item_count=1, approval_coverage_rate=1.0, execution_completion_rate=1 / 9),
            _history_entry("2026-05-20T00-00-00Z", total_items=10, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
        ],
    }

    with pytest.raises(ValueError, match="from-run-stamp must not be newer than to-run-stamp"):
        build_reporting_trend_packet(
            generated_at="2026-06-12T01:00:00Z",
            history_packet=history_packet,
            from_run_stamp_requested="2026-06-10T00-00-00Z",
            to_run_stamp_requested="2026-05-20T00-00-00Z",
        )
```

- [ ] **Step 2: Run the helper tests to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q
```

Expected: FAIL because `build_reporting_trend_packet(...)` does not yet accept requested-range arguments, does not emit requested-range fields, and has no run-stamp validation or interior range selection path.

- [ ] **Step 3: Write the minimal helper implementation**

Update `scripts/omo_debt_reporting_trend.py` like this:

```python
from scripts.omo_debt_reporting_history import _validate_run_stamp


def _run_index(runs: list[dict[str, object]], run_stamp: str, *, label: str) -> int:
    for index, entry in enumerate(runs):
        if entry["run_stamp"] == run_stamp:
            return index
    raise ValueError(f"{label} not in history: {run_stamp}")


def _select_runs(
    history_packet: dict[str, object],
    *,
    window_requested: int | None,
    from_run_stamp_requested: str | None,
    to_run_stamp_requested: str | None,
) -> list[dict[str, object]]:
    runs = history_packet["runs"]
    if from_run_stamp_requested is not None or to_run_stamp_requested is not None:
        if from_run_stamp_requested is None or to_run_stamp_requested is None:
            raise ValueError("range mode requires both from-run-stamp and to-run-stamp")
        try:
            _validate_run_stamp(from_run_stamp_requested)
        except ValueError as exc:
            raise ValueError(f"invalid from-run-stamp: {from_run_stamp_requested}") from exc
        try:
            _validate_run_stamp(to_run_stamp_requested)
        except ValueError as exc:
            raise ValueError(f"invalid to-run-stamp: {to_run_stamp_requested}") from exc
        to_index = _run_index(runs, to_run_stamp_requested, label="to-run-stamp")
        from_index = _run_index(runs, from_run_stamp_requested, label="from-run-stamp")
        if from_index < to_index:
            raise ValueError("from-run-stamp must not be newer than to-run-stamp")
        return runs[to_index : from_index + 1]
    if window_requested is not None:
        return runs[:window_requested]
    return runs


def build_reporting_trend_packet(
    *,
    generated_at: str,
    history_packet: dict[str, object],
    window_requested: int | None = None,
    from_run_stamp_requested: str | None = None,
    to_run_stamp_requested: str | None = None,
) -> dict[str, object]:
    selected_runs = _select_runs(
        history_packet,
        window_requested=window_requested,
        from_run_stamp_requested=from_run_stamp_requested,
        to_run_stamp_requested=to_run_stamp_requested,
    )
    ordered_runs = [_trend_run(entry) for entry in reversed(selected_runs)]
    intervals = [
        _interval(ordered_runs[index], ordered_runs[index + 1])
        for index in range(len(ordered_runs) - 1)
    ]
    oldest_run_stamp = ordered_runs[0]["run_stamp"] if ordered_runs else None
    latest_run_stamp = ordered_runs[-1]["run_stamp"] if ordered_runs else None
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
    }
```

Do **not** weaken `_trend_run(...)` fail-closed behavior.

- [ ] **Step 4: Run the helper tests to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the helper-layer change in the nested `scripts` repo**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_reporting_trend.py && git -c core.hooksPath=/dev/null commit -m "feat(debt): add trend run range support" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one nested-repo commit containing only `omo_debt_reporting_trend.py`.

### Task 2: Wire the explicit range mode through the CLI

**Files:**
- Modify: `scripts/omo_debt.py`
- Modify: `.omo/tests/test_omo_debt_cli.py`
- Test: `.omo/tests/test_omo_debt_cli.py`

- [ ] **Step 1: Write the failing CLI tests**

Add these tests to `.omo/tests/test_omo_debt_cli.py`:

```python
def test_debt_report_trend_accepts_inclusive_run_range(tmp_path: Path) -> None:
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
                "run_count": 4,
                "runs": [
                    {
                        "run_stamp": "2026-06-10T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-06-10T00:00:00Z",
                        "total_items": 9,
                        "executed_item_count": 0,
                        "approval_coverage_rate": 0.0,
                        "execution_completion_rate": 0.0,
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
                    {
                        "run_stamp": "2026-05-10T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-05-10T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-05-10T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-05-10T00:00:00Z",
                        "total_items": 11,
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
            "--from-run-stamp",
            "2026-05-20T00-00-00Z",
            "--to-run-stamp",
            "2026-06-10T00-00-00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load((debt_dir / "reporting" / "trend" / "current.yaml").read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stderr
    assert packet["from_run_stamp_requested"] == "2026-05-20T00-00-00Z"
    assert packet["to_run_stamp_requested"] == "2026-06-10T00-00-00Z"
    assert [entry["run_stamp"] for entry in packet["runs"]] == [
        "2026-05-20T00-00-00Z",
        "2026-06-01T00-00-00Z",
        "2026-06-10T00-00-00Z",
    ]


def test_debt_report_trend_rejects_partial_run_range(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-trend",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--from-run-stamp",
            "2026-06-10T00-00-00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "range mode requires both from-run-stamp and to-run-stamp" in result.stderr


def test_debt_report_trend_rejects_last_with_run_range(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-trend",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--last",
            "2",
            "--from-run-stamp",
            "2026-06-01T00-00-00Z",
            "--to-run-stamp",
            "2026-06-10T00-00-00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "--last cannot be combined with --from-run-stamp or --to-run-stamp" in result.stderr
```

- [ ] **Step 2: Run the CLI tests to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py -q -k 'debt_report_trend'
```

Expected: FAIL because `report-trend` does not yet accept range args, detect partial bounds, or detect conflicts with `--last`.

- [ ] **Step 3: Write the minimal CLI implementation**

Update `scripts/omo_debt.py` like this:

```python
def reporting_trend_outputs(
    omo_dir: Path,
    window_requested: int | None = None,
    from_run_stamp_requested: str | None = None,
    to_run_stamp_requested: str | None = None,
) -> None:
    history_packet = load_reporting_history_packet(omo_dir)
    if window_requested is not None and (from_run_stamp_requested is not None or to_run_stamp_requested is not None):
        raise ValueError("--last cannot be combined with --from-run-stamp or --to-run-stamp")
    if (from_run_stamp_requested is None) != (to_run_stamp_requested is None):
        raise ValueError("range mode requires both from-run-stamp and to-run-stamp")
    write_reporting_trend_packet(
        omo_dir,
        build_reporting_trend_packet(
            generated_at=_timestamp(),
            history_packet=history_packet,
            window_requested=window_requested,
            from_run_stamp_requested=from_run_stamp_requested,
            to_run_stamp_requested=to_run_stamp_requested,
        ),
    )
```

And in the parser/main branch:

```python
report_trend_parser = subparsers.add_parser("report-trend")
report_trend_parser.add_argument("--omo-dir", default=".omo")
report_trend_parser.add_argument("--last", type=_positive_int)
report_trend_parser.add_argument("--from-run-stamp")
report_trend_parser.add_argument("--to-run-stamp")

if args.command == "report-trend":
    reporting_trend_outputs(
        omo_dir,
        window_requested=args.last,
        from_run_stamp_requested=args.from_run_stamp,
        to_run_stamp_requested=args.to_run_stamp,
    )
    print("generated debt reporting trend packet")
    return 0
```

- [ ] **Step 4: Run the CLI tests to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py -q -k 'debt_report_trend'
```

Expected: PASS.

- [ ] **Step 5: Commit the CLI wiring in repo order**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt.py && git -c core.hooksPath=/dev/null commit -m "feat(debt): add trend run range CLI" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
cd /Users/xiamingxing/Workspace && git add scripts .omo/tests/test_omo_debt_reporting_trend.py .omo/tests/test_omo_debt_cli.py && git -c core.hooksPath=/dev/null commit -m "test(omo): cover debt trend run range" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one nested-repo commit for CLI code, then one root commit for the gitlink update plus root-side tests.

### Task 3: Update docs, hydrate artifacts, and verify end-to-end

**Files:**
- Modify: `.omo/AGENT.md`
- Modify: `.omo/tests/test_omo_debt_docs.py`
- Refresh: `.omo/debt/reporting/trend/current.yaml`
- Refresh: `.omo/debt/reporting/trend/current.md`
- Test: `.omo/tests/test_omo_debt_docs.py`

- [ ] **Step 1: Write the failing docs test**

Add these assertions to `.omo/tests/test_omo_debt_docs.py`:

```python
assert "python3 scripts/omo_debt.py report-trend --omo-dir .omo --from-run-stamp <STAMP> --to-run-stamp <STAMP>" in content
assert "from_run_stamp_requested" in content
assert "to_run_stamp_requested" in content
assert "inclusive" in content.lower()
assert "cannot be combined with --last" in content.lower()
```

- [ ] **Step 2: Run the docs test to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py -q -k 'omo_agent_documents_debt_refresh_flow'
```

Expected: FAIL because `.omo/AGENT.md` does not yet document run-range mode.

- [ ] **Step 3: Update docs and hydrate live artifact**

Add guidance like this to `.omo/AGENT.md`:

```md
- Generate an identity-bounded trend surface with `python3 scripts/omo_debt.py report-trend --omo-dir .omo --from-run-stamp <STAMP> --to-run-stamp <STAMP>`
- `from_run_stamp_requested` and `to_run_stamp_requested` record the explicit closed interval when range mode is used
- Range mode is inclusive and cannot be combined with `--last`
```

Then refresh the live artifact:

```bash
cd /Users/xiamingxing/Workspace && python3 scripts/omo_debt.py report-trend --omo-dir .omo --from-run-stamp 2026-06-10T00-00-00Z --to-run-stamp 2026-06-10T00-00-00Z
```

Expected: `.omo/debt/reporting/trend/current.yaml` is rewritten with:

```yaml
window_requested: null
from_run_stamp_requested: 2026-06-10T00-00-00Z
to_run_stamp_requested: 2026-06-10T00-00-00Z
```

- [ ] **Step 4: Run focused verification**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_docs.py -q -k 'reporting_trend or debt_report_trend or omo_agent_documents_debt_refresh_flow'
```

Expected: PASS.

- [ ] **Step 5: Run canonical verification**

Run:

```bash
cd /Users/xiamingxing/Workspace && bash bin/verify-omo.sh
```

Expected: PASS.

- [ ] **Step 6: Commit docs/artifacts and close the slice**

Run:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/AGENT.md .omo/tests/test_omo_debt_docs.py .omo/debt/reporting/trend/current.yaml .omo/debt/reporting/trend/current.md && git -c core.hooksPath=/dev/null commit -m "docs(omo): document debt trend run range" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one root commit containing docs guidance, docs regression, and hydrated trend artifacts.
