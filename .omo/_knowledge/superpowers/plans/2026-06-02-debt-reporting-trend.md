---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Debt Reporting Trend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new `report-trend` surface that emits ordered multi-run reporting progress from history metadata with valid `insufficient_history` handling and no owner trends or slope math.

**Architecture:** Keep the slice additive and derived. Add one pure helper module that transforms `reporting/history/current.yaml` into an oldest-to-newest trend packet plus Markdown renderer, then wire `scripts/omo_debt.py` to expose a new `report-trend` command and generated output surface. This repository still uses a nested `scripts/` git repo / gitlink, so mixed `scripts/*` + root changes must use pathspec-limited two-repo commits without cleaning unrelated files; also note that root-level git worktrees are not viable here because the worktree does not materialize the live `scripts/` contents.

**Tech Stack:** Python 3, PyYAML, pytest, existing `scripts/omo_debt.py` CLI, `scripts/omo_debt_reporting_history.py`, `.omo` governance docs/tests

---

## File structure map

- Create: `scripts/omo_debt_reporting_trend.py`
  - Pure helper layer for trend packet construction, oldest-to-newest run ordering, interval delta computation, and Markdown rendering.
- Create: `.omo/tests/test_omo_debt_reporting_trend.py`
  - Focused unit coverage for ordering, interval deltas, and `insufficient_history`.
- Modify: `scripts/omo_debt.py`
  - Add `report-trend` CLI wiring, history-loader reuse, trend writer, and generated `reporting/trend/current.*` output.
- Modify: `.omo/tests/test_omo_debt_cli.py`
  - CLI regressions for missing history, `insufficient_history`, and proof that trend reads copied history metadata rather than re-deriving raw facts.
- Create/refresh: `.omo/debt/reporting/trend/current.yaml`
  - Canonical machine-readable multi-run trend packet.
- Create/refresh: `.omo/debt/reporting/trend/current.md`
  - Human-readable trend summary.
- Modify: `.omo/AGENT.md`
  - Document `report-trend`, the trend surface, `trend_status`, and the fixed Version 1 metric set.
- Modify: `.omo/tests/test_omo_debt_docs.py`
  - Lock the operator guidance.

## Implementation notes before starting

- Work from `/Users/xiamingxing/Workspace`.
- Do **not** clean or revert unrelated changes inside `scripts/`; pathspec every add/commit.
- Do **not** use a root worktree for this slice; the current repo shape records `scripts/` as a gitlink and worktree baselines cannot execute the live scripts toolchain.
- Keep the slice narrow:
  1. add `report-trend`
  2. read from `reporting/history/current.yaml`
  3. use only `total_items`, `executed_item_count`, `approval_coverage_rate`, and `execution_completion_rate`
  4. support `trend_available` and `insufficient_history`
  5. no owner trends
  6. no slope math
  7. no run override flags

### Task 1: Build the pure reporting-trend helper

**Files:**
- Create: `scripts/omo_debt_reporting_trend.py`
- Create: `.omo/tests/test_omo_debt_reporting_trend.py`
- Test: `.omo/tests/test_omo_debt_reporting_trend.py`

- [ ] **Step 1: Write the failing unit tests**

Create `.omo/tests/test_omo_debt_reporting_trend.py` with a minimal history fixture and these tests:

```python
from __future__ import annotations

import pytest

from scripts.omo_debt_reporting_trend import build_reporting_trend_packet, render_reporting_trend_markdown


def _history_entry(
    run_stamp: str,
    *,
    total_items: int,
    executed_item_count: int,
    approval_coverage_rate: float,
    execution_completion_rate: float,
) -> dict[str, object]:
    return {
        "run_stamp": run_stamp,
        "dispatch_run_ref": f".omo/debt/dispatch/runs/{run_stamp}.yaml",
        "reporting_ref": f".omo/debt/reporting/runs/{run_stamp}/current.yaml",
        "reporting_exists": True,
        "report_generated_at": "2026-06-12T00:00:00Z",
        "total_items": total_items,
        "executed_item_count": executed_item_count,
        "approval_coverage_rate": approval_coverage_rate,
        "execution_completion_rate": execution_completion_rate,
    }


def test_build_reporting_trend_packet_reorders_runs_oldest_to_newest() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 3,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
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

    assert packet["trend_status"] == "trend_available"
    assert packet["window_run_count"] == 3
    assert packet["oldest_run_stamp"] == "2026-05-20T00-00-00Z"
    assert packet["latest_run_stamp"] == "2026-06-10T00-00-00Z"
    assert [entry["run_stamp"] for entry in packet["runs"]] == [
        "2026-05-20T00-00-00Z",
        "2026-06-01T00-00-00Z",
        "2026-06-10T00-00-00Z",
    ]
    assert packet["intervals"] == [
        {
            "from_run_stamp": "2026-05-20T00-00-00Z",
            "to_run_stamp": "2026-06-01T00-00-00Z",
            "total_items_delta": -1,
            "executed_item_count_delta": 1,
            "approval_coverage_rate_delta": 1.0,
            "execution_completion_rate_delta": 1 / 9,
        },
        {
            "from_run_stamp": "2026-06-01T00-00-00Z",
            "to_run_stamp": "2026-06-10T00-00-00Z",
            "total_items_delta": 0,
            "executed_item_count_delta": -1,
            "approval_coverage_rate_delta": -1.0,
            "execution_completion_rate_delta": -(1 / 9),
        },
    ]


def test_build_reporting_trend_packet_writes_insufficient_history_state() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": None,
        "run_count": 1,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            )
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
    )

    assert packet["trend_status"] == "insufficient_history"
    assert packet["window_run_count"] == 1
    assert packet["oldest_run_stamp"] == "2026-06-10T00-00-00Z"
    assert packet["latest_run_stamp"] == "2026-06-10T00-00-00Z"
    assert len(packet["runs"]) == 1
    assert packet["intervals"] == []


def test_build_reporting_trend_packet_rejects_missing_reporting_metadata() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
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
                "reporting_ref": None,
                "reporting_exists": False,
                "report_generated_at": None,
                "total_items": None,
                "executed_item_count": None,
                "approval_coverage_rate": None,
                "execution_completion_rate": None,
            },
        ],
    }

    with pytest.raises(ValueError, match="missing reporting trend metadata for run: 2026-06-01T00-00-00Z"):
        build_reporting_trend_packet(
            generated_at="2026-06-12T01:00:00Z",
            history_packet=history_packet,
        )


def test_render_reporting_trend_markdown_shows_trend_and_insufficient_history_states() -> None:
    trend_packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet={
            "generated_at": "2026-06-12T00:00:00Z",
            "latest_run_stamp": "2026-06-10T00-00-00Z",
            "prior_run_stamp": "2026-06-01T00-00-00Z",
            "run_count": 2,
            "runs": [
                _history_entry(
                    "2026-06-10T00-00-00Z",
                    total_items=9,
                    executed_item_count=0,
                    approval_coverage_rate=0.0,
                    execution_completion_rate=0.0,
                ),
                _history_entry(
                    "2026-06-01T00-00-00Z",
                    total_items=9,
                    executed_item_count=1,
                    approval_coverage_rate=1.0,
                    execution_completion_rate=1 / 9,
                ),
            ],
        },
    )
    insufficient_packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet={
            "generated_at": "2026-06-12T00:00:00Z",
            "latest_run_stamp": "2026-06-10T00-00-00Z",
            "prior_run_stamp": None,
            "run_count": 1,
            "runs": [
                _history_entry(
                    "2026-06-10T00-00-00Z",
                    total_items=9,
                    executed_item_count=0,
                    approval_coverage_rate=0.0,
                    execution_completion_rate=0.0,
                )
            ],
        },
    )

    trend_markdown = render_reporting_trend_markdown(trend_packet)
    insufficient_markdown = render_reporting_trend_markdown(insufficient_packet)

    assert "# Debt Reporting Trend" in trend_markdown
    assert "Trend status: trend_available" in trend_markdown
    assert "2026-06-01T00-00-00Z -> 2026-06-10T00-00-00Z" in trend_markdown
    assert "Trend status: insufficient_history" in insufficient_markdown
    assert "Trend baseline not established yet." in insufficient_markdown
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q
```

Expected:

```text
FAIL ... ModuleNotFoundError: No module named 'scripts.omo_debt_reporting_trend'
```

- [ ] **Step 3: Write the minimal implementation**

Create `scripts/omo_debt_reporting_trend.py` with the smallest helper layer that satisfies the tests:

```python
from __future__ import annotations


def _trend_run(entry: dict[str, object]) -> dict[str, object]:
    if not entry["reporting_exists"] or any(
        entry[field] is None
        for field in (
            "total_items",
            "executed_item_count",
            "approval_coverage_rate",
            "execution_completion_rate",
        )
    ):
        raise ValueError(f"missing reporting trend metadata for run: {entry['run_stamp']}")
    return {
        "run_stamp": entry["run_stamp"],
        "dispatch_run_ref": entry["dispatch_run_ref"],
        "reporting_ref": entry["reporting_ref"],
        "total_items": entry["total_items"],
        "executed_item_count": entry["executed_item_count"],
        "approval_coverage_rate": entry["approval_coverage_rate"],
        "execution_completion_rate": entry["execution_completion_rate"],
    }


def _interval(previous: dict[str, object], current: dict[str, object]) -> dict[str, object]:
    return {
        "from_run_stamp": previous["run_stamp"],
        "to_run_stamp": current["run_stamp"],
        "total_items_delta": current["total_items"] - previous["total_items"],
        "executed_item_count_delta": current["executed_item_count"] - previous["executed_item_count"],
        "approval_coverage_rate_delta": current["approval_coverage_rate"] - previous["approval_coverage_rate"],
        "execution_completion_rate_delta": current["execution_completion_rate"] - previous["execution_completion_rate"],
    }


def build_reporting_trend_packet(
    *,
    generated_at: str,
    history_packet: dict[str, object],
) -> dict[str, object]:
    ordered_runs = [_trend_run(entry) for entry in reversed(history_packet["runs"])]
    intervals = [
        _interval(ordered_runs[index], ordered_runs[index + 1])
        for index in range(len(ordered_runs) - 1)
    ]
    oldest_run_stamp = ordered_runs[0]["run_stamp"] if ordered_runs else None
    latest_run_stamp = ordered_runs[-1]["run_stamp"] if ordered_runs else None
    return {
        "generated_at": generated_at,
        "trend_status": "trend_available" if len(ordered_runs) >= 2 else "insufficient_history",
        "window_run_count": len(ordered_runs),
        "oldest_run_stamp": oldest_run_stamp,
        "latest_run_stamp": latest_run_stamp,
        "runs": ordered_runs,
        "intervals": intervals,
    }


def render_reporting_trend_markdown(packet: dict[str, object]) -> str:
    lines = [
        "# Debt Reporting Trend",
        "",
        f"Generated at: {packet['generated_at']}",
        f"Trend status: {packet['trend_status']}",
        f"Oldest run: {packet['oldest_run_stamp'] or 'none'}",
        f"Latest run: {packet['latest_run_stamp'] or 'none'}",
        "",
    ]
    if packet["trend_status"] == "insufficient_history":
        lines.extend(["Trend baseline not established yet.", ""])
    for run in packet["runs"]:
        lines.extend(
            [
                f"## Run: {run['run_stamp']}",
                "",
                f"total_items={run['total_items']}",
                f"executed_item_count={run['executed_item_count']}",
                f"approval_coverage_rate={run['approval_coverage_rate']}",
                f"execution_completion_rate={run['execution_completion_rate']}",
                "",
            ]
        )
    for interval in packet["intervals"]:
        lines.extend(
            [
                f"## Interval: {interval['from_run_stamp']} -> {interval['to_run_stamp']}",
                "",
                f"total_items_delta={interval['total_items_delta']}",
                f"executed_item_count_delta={interval['executed_item_count_delta']}",
                f"approval_coverage_rate_delta={interval['approval_coverage_rate_delta']}",
                f"execution_completion_rate_delta={interval['execution_completion_rate_delta']}",
                "",
            ]
        )
    return "\n".join(lines)
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py -q
```

Expected:

```text
...                                                                    [100%]
all tests in .omo/tests/test_omo_debt_reporting_trend.py pass
```

- [ ] **Step 5: Commit**

Use the required two-repo commit flow:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_reporting_trend.py && git -c core.hooksPath=/dev/null commit -m "feat(debt): add reporting trend helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
cd /Users/xiamingxing/Workspace && git add scripts .omo/tests/test_omo_debt_reporting_trend.py && git -c core.hooksPath=/dev/null commit -m "test(omo): cover reporting trend helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 2: Wire `report-trend` into the CLI

**Files:**
- Modify: `scripts/omo_debt.py`
- Modify: `.omo/tests/test_omo_debt_cli.py`
- Create/refresh: `.omo/debt/reporting/trend/current.yaml`
- Create/refresh: `.omo/debt/reporting/trend/current.md`
- Test: `.omo/tests/test_omo_debt_cli.py`

- [ ] **Step 1: Write the failing CLI tests**

Append these tests to `.omo/tests/test_omo_debt_cli.py`:

```python
def test_debt_report_trend_requires_history_packet(tmp_path: Path) -> None:
    debt_dir = tmp_path / ".omo" / "debt"
    debt_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-trend",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "reporting/history/current.yaml" in result.stderr


def test_debt_report_trend_writes_insufficient_history_packet_for_single_history_run(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-trend",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load((tmp_path / ".omo" / "debt" / "reporting" / "trend" / "current.yaml").read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "generated debt reporting trend packet"
    assert packet["trend_status"] == "insufficient_history"
    assert packet["window_run_count"] == 1
    assert packet["oldest_run_stamp"] == "2026-06-10T00-00-00Z"
    assert packet["latest_run_stamp"] == "2026-06-10T00-00-00Z"
    assert [entry["run_stamp"] for entry in packet["runs"]] == ["2026-06-10T00-00-00Z"]
    assert packet["intervals"] == []


def test_debt_report_trend_reads_history_summary_metadata_not_raw_facts(tmp_path: Path) -> None:
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
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load((debt_dir / "reporting" / "trend" / "current.yaml").read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stderr
    assert [entry["run_stamp"] for entry in packet["runs"]] == [
        "2026-05-20T00-00-00Z",
        "2026-06-01T00-00-00Z",
        "2026-06-10T00-00-00Z",
    ]
    assert packet["intervals"] == [
        {
            "from_run_stamp": "2026-05-20T00-00-00Z",
            "to_run_stamp": "2026-06-01T00-00-00Z",
            "total_items_delta": -1,
            "executed_item_count_delta": 1,
            "approval_coverage_rate_delta": 1.0,
            "execution_completion_rate_delta": 1 / 9,
        },
        {
            "from_run_stamp": "2026-06-01T00-00-00Z",
            "to_run_stamp": "2026-06-10T00-00-00Z",
            "total_items_delta": 0,
            "executed_item_count_delta": -1,
            "approval_coverage_rate_delta": -1.0,
            "execution_completion_rate_delta": -(1 / 9),
        },
    ]


def test_debt_report_trend_fails_closed_on_missing_history_reporting_metadata(tmp_path: Path) -> None:
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
                "run_count": 2,
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
                        "reporting_ref": None,
                        "reporting_exists": False,
                        "report_generated_at": None,
                        "total_items": None,
                        "executed_item_count": None,
                        "approval_coverage_rate": None,
                        "execution_completion_rate": None,
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
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "missing reporting trend metadata for run: 2026-06-01T00-00-00Z" in result.stderr
```

- [ ] **Step 2: Run the CLI tests to verify they fail**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py -q -k 'debt_report_trend'
```

Expected:

```text
FAIL ... because `report-trend` is not a recognized subcommand yet
```

- [ ] **Step 3: Write the minimal CLI implementation**

Modify `scripts/omo_debt.py` in four places:

1. Import the new helper near the reporting imports:

```python
try:
    from scripts.omo_debt_reporting_trend import build_reporting_trend_packet, render_reporting_trend_markdown
except ModuleNotFoundError:
    from omo_debt_reporting_trend import build_reporting_trend_packet, render_reporting_trend_markdown
```

2. Add a writer beside `write_reporting_history_packet(...)` and `write_reporting_diff_packet(...)`:

```python
def write_reporting_trend_packet(omo_dir: Path, trend_packet: dict[str, object]) -> None:
    trend_dir = omo_dir / "debt" / "reporting" / "trend"
    markdown = render_reporting_trend_markdown(trend_packet)
    _write_yaml(trend_dir / "current.yaml", trend_packet)
    current_md_path = trend_dir / "current.md"
    current_md_path.parent.mkdir(parents=True, exist_ok=True)
    current_md_path.write_text(markdown, encoding="utf-8")
```

3. Add the output function beside `reporting_history_outputs(...)` and `reporting_diff_outputs(...)`:

```python
def reporting_trend_outputs(omo_dir: Path) -> None:
    history_packet = load_reporting_history_packet(omo_dir)
    write_reporting_trend_packet(
        omo_dir,
        build_reporting_trend_packet(
            generated_at=_timestamp(),
            history_packet=history_packet,
        ),
    )
```

4. Add the parser and main dispatch branch:

```python
report_trend_parser = subparsers.add_parser("report-trend")
report_trend_parser.add_argument("--omo-dir", default=".omo")
```

```python
if args.command == "report-trend":
    reporting_trend_outputs(omo_dir)
    print("generated debt reporting trend packet")
    return 0
```

- [ ] **Step 4: Run the CLI tests to verify they pass**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py -q -k 'debt_report_trend'
```

Expected:

```text
...                                                                    [100%]
all selected debt_report_trend tests pass
```

- [ ] **Step 5: Commit**

Use the required two-repo commit flow:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt.py omo_debt_reporting_trend.py && git -c core.hooksPath=/dev/null commit -m "feat(debt): add reporting trend command" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
cd /Users/xiamingxing/Workspace && git add scripts .omo/tests/test_omo_debt_cli.py .omo/debt/reporting/trend/current.yaml .omo/debt/reporting/trend/current.md && git -c core.hooksPath=/dev/null commit -m "test(omo): cover debt reporting trend cli" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 3: Update docs and run canonical verification

**Files:**
- Modify: `.omo/AGENT.md`
- Modify: `.omo/tests/test_omo_debt_docs.py`
- Test: `.omo/tests/test_omo_debt_reporting_trend.py`
- Test: `.omo/tests/test_omo_debt_cli.py`
- Test: `.omo/tests/test_omo_debt_docs.py`

- [ ] **Step 1: Write the failing docs regression**

Update `.omo/tests/test_omo_debt_docs.py` to assert the new operator guidance:

```python
assert "python3 scripts/omo_debt.py report-trend --omo-dir .omo" in content
assert ".omo/debt/reporting/trend/current.yaml" in content
assert ".omo/debt/reporting/trend/current.md" in content
assert "trend_status" in content
assert "insufficient_history" in content
assert "trend_available" in content
assert "oldest to newest" in content.lower()
assert "total_items" in content
assert "executed_item_count" in content
assert "approval_coverage_rate" in content
assert "execution_completion_rate" in content
assert "owner trends" in content.lower()
assert "slope math" in content.lower()
```

- [ ] **Step 2: Run the docs test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py -q -k omo_agent_documents_debt_refresh_flow
```

Expected:

```text
FAIL ... because .omo/AGENT.md does not document report-trend or the new trend_status contract yet
```

- [ ] **Step 3: Update the operator guide**

Edit `.omo/AGENT.md` to add these bullets directly after the `report-diff` guidance:

```markdown
- Generate the multi-run trend surface with `python3 scripts/omo_debt.py report-trend --omo-dir .omo`
- Reporting trend lives at `.omo/debt/reporting/trend/current.yaml` plus `.omo/debt/reporting/trend/current.md`
- `report-trend` reads the copied run summary metadata from `reporting/history/current.yaml`, reorders runs from oldest to newest, and emits consecutive interval deltas
- `trend_status` is `insufficient_history` until at least two runs exist, then becomes `trend_available`
- Version 1 trend uses only `total_items`, `executed_item_count`, `approval_coverage_rate`, and `execution_completion_rate`
- Owner trends and slope math remain deferred
```

- [ ] **Step 4: Run focused and canonical verification**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_trend.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_docs.py -q -k 'reporting_trend or debt_report_trend or omo_agent_documents_debt_refresh_flow'
cd /Users/xiamingxing/Workspace && bash bin/verify-omo.sh
```

Expected:

```text
....                                                                   [100%]
all selected reporting_trend / debt_report_trend / docs tests pass
...
<canonical verify passes; full suite count increases from the current baseline>
```

- [ ] **Step 5: Commit**

```bash
cd /Users/xiamingxing/Workspace && git add .omo/AGENT.md .omo/tests/test_omo_debt_docs.py && git -c core.hooksPath=/dev/null commit -m "docs(omo): document debt reporting trend surface" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
