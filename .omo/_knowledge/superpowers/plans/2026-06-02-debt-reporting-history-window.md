---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Debt Reporting History Window Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `report-trend` with a narrow `--last N` history-window override that selects the most recent N runs while preserving current no-flag behavior, oldest-to-newest ordering, and fail-closed metadata validation.

**Architecture:** Keep the slice additive. Reuse `reporting/history/current.yaml` as the canonical trend input, teach the pure trend helper to accept an optional window size, then wire `scripts/omo_debt.py` to expose `--last`. Preserve the existing `report-diff` contract unchanged, keep missing-reporting metadata fail-closed inside the selected window, and document the new packet field `window_requested`.

**Tech Stack:** Python 3, argparse, PyYAML, pytest, existing `scripts/omo_debt.py` CLI, `scripts/omo_debt_reporting_trend.py`, `.omo` governance docs/tests

---

## File structure map

- Modify: `scripts/omo_debt_reporting_trend.py`
  - Add optional window selection support to `build_reporting_trend_packet(...)` while preserving default full-history behavior and oldest-to-newest interval computation.
- Modify: `.omo/tests/test_omo_debt_reporting_trend.py`
  - Add focused helper regressions for `--last` semantics, especially the “slice before reverse” correctness rule.
- Modify: `scripts/omo_debt.py`
  - Add `--last` argument to `report-trend` and pass the value into the helper.
- Modify: `.omo/tests/test_omo_debt_cli.py`
  - Add CLI regressions for `report-trend --last N`, invalid `--last`, full-history parity when N exceeds visible history, and fail-closed behavior inside the selected window.
- Refresh: `.omo/debt/reporting/trend/current.yaml`
  - Hydrate live trend artifact with the new `window_requested` field.
- Refresh: `.omo/debt/reporting/trend/current.md`
  - Hydrate the human-readable trend artifact after the helper/CLI changes land.
- Modify: `.omo/AGENT.md`
  - Document `report-trend --last <N>`, `window_requested`, and the fact that selection applies to the most recent N runs before oldest-to-newest rendering.
- Modify: `.omo/tests/test_omo_debt_docs.py`
  - Lock the updated operator guidance.

## Implementation notes before starting

- Work from `/Users/xiamingxing/Workspace`.
- This repository shape still requires pathspec-limited commits because `scripts/` is a nested git repo / gitlink; mixed `scripts/*` + root changes must be committed in repo order without cleaning unrelated changes.
- Do **not** use a root-level worktree for this slice; prior attempts showed that root worktrees do not materialize the live `scripts/` contents needed by the canonical verification flow.
- Keep the slice narrow:
  1. add only `--last <N>`
  2. `--last` is optional and defaults to current full-history behavior
  3. selection happens on history's newest-to-oldest list **before** oldest-to-newest reversal
  4. keep `report-diff` untouched
  5. no run-stamp range flags
  6. no skip-missing semantics
  7. no owner trends or projections

### Task 1: Teach the pure trend helper to support bounded windows

**Files:**
- Modify: `scripts/omo_debt_reporting_trend.py`
- Modify: `.omo/tests/test_omo_debt_reporting_trend.py`
- Test: `.omo/tests/test_omo_debt_reporting_trend.py`

- [ ] **Step 1: Write the failing helper tests**

Add these tests to `.omo/tests/test_omo_debt_reporting_trend.py`:

```python
def test_build_reporting_trend_packet_selects_most_recent_window_before_reordering() -> None:
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
        window_requested=3,
    )

    assert packet["window_requested"] == 3
    assert packet["window_run_count"] == 3
    assert [entry["run_stamp"] for entry in packet["runs"]] == [
        "2026-05-20T00-00-00Z",
        "2026-06-01T00-00-00Z",
        "2026-06-10T00-00-00Z",
    ]


def test_build_reporting_trend_packet_uses_full_history_when_requested_window_exceeds_visible_runs() -> None:
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

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        window_requested=5,
    )

    assert packet["window_requested"] == 5
    assert packet["window_run_count"] == 2
    assert [entry["run_stamp"] for entry in packet["runs"]] == [
        "2026-06-01T00-00-00Z",
        "2026-06-10T00-00-00Z",
    ]


def test_build_reporting_trend_packet_rejects_missing_reporting_metadata_inside_selected_window() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 3,
        "runs": [
            _history_entry("2026-06-10T00-00-00Z", total_items=9, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
            {
                "run_stamp": "2026-06-01T00-00-00Z",
                "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                "reporting_ref": None,
                "reporting_exists": False,
                "report_generated_at": None,
                "total_items": None,
                "executed_item_count": None,
                "approval_coverage_rate": None,
                "execution_completion_rate": None,
            },
            _history_entry("2026-05-20T00-00-00Z", total_items=10, executed_item_count=0, approval_coverage_rate=0.0, execution_completion_rate=0.0),
        ],
    }

    with pytest.raises(ValueError, match="missing reporting trend metadata for run: 2026-06-01T00-00-00Z"):
        build_reporting_trend_packet(
            generated_at="2026-06-12T01:00:00Z",
            history_packet=history_packet,
            window_requested=2,
        )
```

- [ ] **Step 2: Run the helper tests to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q
```

Expected: FAIL because `build_reporting_trend_packet(...)` does not yet accept `window_requested`, does not emit `window_requested` in the packet, and still always consumes the full history list.

- [ ] **Step 3: Write the minimal helper implementation**

Update `scripts/omo_debt_reporting_trend.py` like this:

```python
def build_reporting_trend_packet(
    *,
    generated_at: str,
    history_packet: dict[str, object],
    window_requested: int | None = None,
) -> dict[str, object]:
    selected_runs = history_packet["runs"][:window_requested] if window_requested is not None else history_packet["runs"]
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
        "window_run_count": len(ordered_runs),
        "oldest_run_stamp": oldest_run_stamp,
        "latest_run_stamp": latest_run_stamp,
        "runs": ordered_runs,
        "intervals": intervals,
    }
```

Do **not** change `_trend_run(...)` fail-closed behavior.

- [ ] **Step 4: Run the helper tests to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the helper-layer change in the nested `scripts` repo**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_reporting_trend.py && git -c core.hooksPath=/dev/null commit -m "feat(debt): add trend history window support" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one nested-repo commit containing only `omo_debt_reporting_trend.py`.

### Task 2: Wire `report-trend --last` through the CLI

**Files:**
- Modify: `scripts/omo_debt.py`
- Modify: `.omo/tests/test_omo_debt_cli.py`
- Test: `.omo/tests/test_omo_debt_cli.py`

- [ ] **Step 1: Write the failing CLI tests**

Add these tests to `.omo/tests/test_omo_debt_cli.py`:

```python
def test_debt_report_trend_accepts_last_window_override(tmp_path: Path) -> None:
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
    assert packet["window_run_count"] == 2
    assert [entry["run_stamp"] for entry in packet["runs"]] == [
        "2026-06-01T00-00-00Z",
        "2026-06-10T00-00-00Z",
    ]


def test_debt_report_trend_rejects_non_positive_last_window(tmp_path: Path) -> None:
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
            "0",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "invalid int value" in result.stderr or "must be" in result.stderr
```

- [ ] **Step 2: Run the CLI tests to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py -q -k 'debt_report_trend'
```

Expected: FAIL because `report-trend` does not yet accept `--last` and does not forward any window argument to the trend helper.

- [ ] **Step 3: Write the minimal CLI implementation**

Update `scripts/omo_debt.py` like this:

```python
def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be >= 1")
    return parsed


def reporting_trend_outputs(omo_dir: Path, window_requested: int | None = None) -> None:
    history_packet = load_reporting_history_packet(omo_dir)
    write_reporting_trend_packet(
        omo_dir,
        build_reporting_trend_packet(
            generated_at=_timestamp(),
            history_packet=history_packet,
            window_requested=window_requested,
        ),
    )
```

And in the parser/main branch:

```python
report_trend_parser = subparsers.add_parser("report-trend")
report_trend_parser.add_argument("--omo-dir", default=".omo")
report_trend_parser.add_argument("--last", type=_positive_int)

if args.command == "report-trend":
    reporting_trend_outputs(omo_dir, window_requested=args.last)
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
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt.py && git -c core.hooksPath=/dev/null commit -m "feat(debt): add trend window CLI" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
cd /Users/xiamingxing/Workspace && git add scripts .omo/tests/test_omo_debt_reporting_trend.py .omo/tests/test_omo_debt_cli.py && git -c core.hooksPath=/dev/null commit -m "test(omo): cover debt trend history window" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one nested-repo commit for CLI code, then one root commit for the gitlink update plus root-side tests.

### Task 3: Update docs, hydrate artifacts, and run canonical verification

**Files:**
- Refresh: `.omo/debt/reporting/trend/current.yaml`
- Refresh: `.omo/debt/reporting/trend/current.md`
- Modify: `.omo/AGENT.md`
- Modify: `.omo/tests/test_omo_debt_docs.py`
- Test: `.omo/tests/test_omo_debt_docs.py`

- [ ] **Step 1: Write the failing docs test**

Add these assertions to `.omo/tests/test_omo_debt_docs.py` inside `test_omo_agent_documents_debt_refresh_flow()`:

```python
assert "python3 scripts/omo_debt.py report-trend --omo-dir .omo --last <N>" in content
assert "window_requested" in content
assert "most recent n runs" in content.lower()
assert "before oldest-to-newest rendering" in content.lower()
```

- [ ] **Step 2: Run the docs test to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py -q -k 'omo_agent_documents_debt_refresh_flow'
```

Expected: FAIL because `.omo/AGENT.md` does not yet document `--last` or `window_requested`.

- [ ] **Step 3: Update the docs and hydrate live artifacts**

Add guidance like this to `.omo/AGENT.md`:

```md
- Generate the multi-run trend surface with `python3 scripts/omo_debt.py report-trend --omo-dir .omo [--last <N>]`
- `window_requested` records the requested bounded history window, or `null` when the full visible history is used
- `--last <N>` selects the most recent N runs from `reporting/history/current.yaml` before oldest-to-newest rendering
```

Then refresh the live artifacts:

```bash
cd /Users/xiamingxing/Workspace && python3 scripts/omo_debt.py report-trend --omo-dir .omo --last 5
```

Expected: `.omo/debt/reporting/trend/current.yaml` and `.omo/debt/reporting/trend/current.md` are rewritten with `window_requested: 5` (or the requested count) and the current live `insufficient_history` state.

- [ ] **Step 4: Run focused docs + trend verification**

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
cd /Users/xiamingxing/Workspace && git add .omo/AGENT.md .omo/tests/test_omo_debt_docs.py .omo/debt/reporting/trend/current.yaml .omo/debt/reporting/trend/current.md && git -c core.hooksPath=/dev/null commit -m "docs(omo): document debt trend history window" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one root commit containing docs guidance, docs regression, and hydrated trend artifacts.
