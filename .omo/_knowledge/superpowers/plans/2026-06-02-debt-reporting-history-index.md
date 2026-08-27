---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Debt Reporting History Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a narrow `report-history` surface that indexes known debt reporting runs, resolves `latest` and `prior` run stamps, and prepares the control plane for a later latest-vs-prior diff slice.

**Architecture:** Keep the slice additive and derived. Add one pure helper module that builds a compact history packet from dispatch-run identities plus optional per-run reporting packets, then wire `scripts/omo_debt.py` to enumerate dispatch runs, attach matching reporting artifacts when present, and write one canonical history surface under `.omo/debt/reporting/history/`. Because `scripts/` is a nested git repo / gitlink and may already be dirty from unrelated work, every mixed `scripts/*` + root change must use pathspec-limited two-repo commits without cleaning unrelated files.

**Tech Stack:** Python 3, PyYAML, pytest, `scripts/omo_debt.py`, existing debt reporting/campaign helpers, `.omo` governance docs/tests

---

## File structure map

- Create: `scripts/omo_debt_reporting_history.py`
  - Pure helper layer for history packet construction, run ordering, validation, and Markdown rendering.
- Create: `.omo/tests/test_omo_debt_reporting_history.py`
  - Focused unit coverage for one-run history, two-run ordering, missing reporting artifacts, duplicate/malformed run stamps, and Markdown output.
- Modify: `scripts/omo_debt.py`
  - Add `report-history` CLI wiring, dispatch-run enumeration, reporting artifact attachment, history writer, and live history generation.
- Modify: `.omo/tests/test_omo_debt_cli.py`
  - CLI regressions for missing dispatch runs, ordered history output, and missing per-run reporting artifact behavior.
- Create/refresh: `.omo/debt/reporting/history/current.yaml`
  - Canonical machine-readable reporting history index.
- Create/refresh: `.omo/debt/reporting/history/current.md`
  - Human-readable reporting history summary.
- Modify: `.omo/AGENT.md`
  - Document `report-history`, the new history surface, and that it is the prerequisite for later diff work.
- Modify: `.omo/tests/test_omo_debt_docs.py`
  - Lock the new operator guidance.

## Implementation notes before starting

- Work from `/Users/xiamingxing/Workspace`.
- Do **not** clean or revert unrelated changes inside `scripts/`; pathspec every add/commit.
- Keep this slice narrow:
  1. no latest-vs-prior diff output
  2. no burndown math
  3. no new state/system promotion
  4. no auto-regeneration from `approve` or `revalidate`
- Keep dispatch runs as the canonical cross-run identity. Reporting run files are attached evidence, not identity truth.
- Preserve the existing architecture rule: future diff work must re-derive from dispatch, approval, and execution facts, not read generated reporting snapshots as source truth.

### Task 1: Build the pure reporting-history helper layer

**Files:**
- Create: `scripts/omo_debt_reporting_history.py`
- Create: `.omo/tests/test_omo_debt_reporting_history.py`
- Test: `.omo/tests/test_omo_debt_reporting_history.py`

- [ ] **Step 1: Write the failing unit tests**

Create `.omo/tests/test_omo_debt_reporting_history.py`:

```python
from __future__ import annotations

import pytest

from scripts.omo_debt_reporting_history import build_reporting_history_packet, render_reporting_history_markdown


def _dispatch_runs() -> tuple[dict[str, str], ...]:
    return (
        {
            "run_stamp": "2026-06-10T00-00-00Z",
            "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        },
        {
            "run_stamp": "2026-06-01T00-00-00Z",
            "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
        },
    )


def _reporting_packet(
    run_stamp: str,
    *,
    generated_at: str,
    total_items: int,
    executed_item_count: int,
    approval_coverage_rate: float,
    execution_completion_rate: float,
) -> dict[str, object]:
    return {
        "generated_at": generated_at,
        "dispatch_run_ref": f".omo/debt/dispatch/runs/{run_stamp}.yaml",
        "run_stamp": run_stamp,
        "summary": {
            "owner_count": 2,
            "total_items": total_items,
            "state_counts": {
                "pending_approval": 1,
                "ready_to_execute": total_items - executed_item_count - 1,
                "executed": executed_item_count,
            },
            "gate_item_count": 1,
            "approved_gate_item_count": 1 if approval_coverage_rate == 1.0 else 0,
            "approval_coverage_rate": approval_coverage_rate,
            "executed_item_count": executed_item_count,
            "execution_completion_rate": execution_completion_rate,
        },
        "owners": [],
    }


def test_build_reporting_history_packet_orders_runs_and_sets_latest_prior() -> None:
    packet = build_reporting_history_packet(
        generated_at="2026-06-12T00:00:00Z",
        dispatch_runs=tuple(reversed(_dispatch_runs())),
        reporting_packets_by_run={
            "2026-06-10T00-00-00Z": _reporting_packet(
                "2026-06-10T00-00-00Z",
                generated_at="2026-06-12T00:00:00Z",
                total_items=9,
                executed_item_count=2,
                approval_coverage_rate=1.0,
                execution_completion_rate=2 / 9,
            ),
            "2026-06-01T00-00-00Z": _reporting_packet(
                "2026-06-01T00-00-00Z",
                generated_at="2026-06-01T02:00:00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
        },
    )

    assert packet["latest_run_stamp"] == "2026-06-10T00-00-00Z"
    assert packet["prior_run_stamp"] == "2026-06-01T00-00-00Z"
    assert packet["run_count"] == 2
    assert [entry["run_stamp"] for entry in packet["runs"]] == [
        "2026-06-10T00-00-00Z",
        "2026-06-01T00-00-00Z",
    ]
    assert packet["runs"][0]["reporting_exists"] is True
    assert packet["runs"][0]["approval_coverage_rate"] == 1.0


def test_build_reporting_history_packet_marks_missing_reporting_artifacts_without_dropping_run() -> None:
    packet = build_reporting_history_packet(
        generated_at="2026-06-12T00:00:00Z",
        dispatch_runs=_dispatch_runs(),
        reporting_packets_by_run={
            "2026-06-10T00-00-00Z": _reporting_packet(
                "2026-06-10T00-00-00Z",
                generated_at="2026-06-12T00:00:00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            )
        },
    )

    assert packet["run_count"] == 2
    assert packet["prior_run_stamp"] == "2026-06-01T00-00-00Z"
    assert packet["runs"][1] == {
        "run_stamp": "2026-06-01T00-00-00Z",
        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
        "reporting_ref": None,
        "reporting_exists": False,
        "report_generated_at": None,
        "total_items": None,
        "executed_item_count": None,
        "approval_coverage_rate": None,
        "execution_completion_rate": None,
    }


def test_build_reporting_history_packet_rejects_duplicate_or_malformed_run_stamps() -> None:
    with pytest.raises(ValueError, match="duplicate dispatch run stamp"):
        build_reporting_history_packet(
            generated_at="2026-06-12T00:00:00Z",
            dispatch_runs=(
                {
                    "run_stamp": "2026-06-10T00-00-00Z",
                    "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
                },
                {
                    "run_stamp": "2026-06-10T00-00-00Z",
                    "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z-copy.yaml",
                },
            ),
            reporting_packets_by_run={},
        )

    with pytest.raises(ValueError, match="invalid dispatch run stamp"):
        build_reporting_history_packet(
            generated_at="2026-06-12T00:00:00Z",
            dispatch_runs=(
                {
                    "run_stamp": "not-a-run-stamp",
                    "dispatch_run_ref": ".omo/debt/dispatch/runs/not-a-run-stamp.yaml",
                },
            ),
            reporting_packets_by_run={},
        )


def test_render_reporting_history_markdown_lists_latest_prior_and_run_presence() -> None:
    packet = build_reporting_history_packet(
        generated_at="2026-06-12T00:00:00Z",
        dispatch_runs=_dispatch_runs(),
        reporting_packets_by_run={
            "2026-06-10T00-00-00Z": _reporting_packet(
                "2026-06-10T00-00-00Z",
                generated_at="2026-06-12T00:00:00Z",
                total_items=9,
                executed_item_count=2,
                approval_coverage_rate=1.0,
                execution_completion_rate=2 / 9,
            )
        },
    )

    markdown = render_reporting_history_markdown(packet)

    assert "# Debt Reporting History" in markdown
    assert "Latest run: 2026-06-10T00-00-00Z" in markdown
    assert "Prior run: 2026-06-01T00-00-00Z" in markdown
    assert "reporting_exists=yes" in markdown
    assert "reporting_exists=no" in markdown
```

- [ ] **Step 2: Run the unit tests to verify they fail**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_history.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.omo_debt_reporting_history'`.

- [ ] **Step 3: Write the minimal reporting-history helper**

Create `scripts/omo_debt_reporting_history.py`:

```python
from __future__ import annotations

from datetime import datetime


def _validate_run_stamp(run_stamp: str) -> None:
    try:
        datetime.strptime(run_stamp, "%Y-%m-%dT%H-%M-%SZ")
    except ValueError as exc:
        raise ValueError(f"invalid dispatch run stamp: {run_stamp}") from exc


def _history_entry(
    dispatch_run: dict[str, str],
    reporting_packet: dict[str, object] | None,
) -> dict[str, object]:
    run_stamp = dispatch_run["run_stamp"]
    entry = {
        "run_stamp": run_stamp,
        "dispatch_run_ref": dispatch_run["dispatch_run_ref"],
        "reporting_ref": None,
        "reporting_exists": False,
        "report_generated_at": None,
        "total_items": None,
        "executed_item_count": None,
        "approval_coverage_rate": None,
        "execution_completion_rate": None,
    }
    if reporting_packet is None:
        return entry
    if reporting_packet.get("run_stamp") != run_stamp:
        raise ValueError(f"reporting run stamp mismatch: {reporting_packet.get('run_stamp')} != {run_stamp}")
    summary = reporting_packet["summary"]
    entry.update(
        {
            "reporting_ref": f".omo/debt/reporting/runs/{run_stamp}/current.yaml",
            "reporting_exists": True,
            "report_generated_at": reporting_packet["generated_at"],
            "total_items": summary["total_items"],
            "executed_item_count": summary["executed_item_count"],
            "approval_coverage_rate": summary["approval_coverage_rate"],
            "execution_completion_rate": summary["execution_completion_rate"],
        }
    )
    return entry


def build_reporting_history_packet(
    *,
    generated_at: str,
    dispatch_runs: tuple[dict[str, str], ...],
    reporting_packets_by_run: dict[str, dict[str, object]],
) -> dict[str, object]:
    ordered_runs = sorted(dispatch_runs, key=lambda run: run["run_stamp"], reverse=True)
    run_stamps = [run["run_stamp"] for run in ordered_runs]
    for run_stamp in run_stamps:
        _validate_run_stamp(run_stamp)
    if len(run_stamps) != len(set(run_stamps)):
        raise ValueError("duplicate dispatch run stamp in reporting history")
    runs = [
        _history_entry(dispatch_run, reporting_packets_by_run.get(dispatch_run["run_stamp"]))
        for dispatch_run in ordered_runs
    ]
    return {
        "generated_at": generated_at,
        "latest_run_stamp": runs[0]["run_stamp"] if runs else None,
        "prior_run_stamp": runs[1]["run_stamp"] if len(runs) > 1 else None,
        "run_count": len(runs),
        "runs": runs,
    }


def render_reporting_history_markdown(packet: dict[str, object]) -> str:
    lines = [
        "# Debt Reporting History",
        "",
        f"Generated at: {packet['generated_at']}",
        f"Latest run: {packet['latest_run_stamp'] or 'none'}",
        f"Prior run: {packet['prior_run_stamp'] or 'none'}",
        "",
    ]
    for run in packet["runs"]:
        lines.extend(
            [
                f"## Run: {run['run_stamp']}",
                "",
                f"dispatch_run_ref={run['dispatch_run_ref']}",
                f"reporting_exists={'yes' if run['reporting_exists'] else 'no'}",
                f"approval_coverage_rate={run['approval_coverage_rate']}",
                f"execution_completion_rate={run['execution_completion_rate']}",
                "",
            ]
        )
    return "\n".join(lines)
```

- [ ] **Step 4: Run the unit tests to verify they pass**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_history.py -q
```

Expected: PASS with all 4 tests green.

- [ ] **Step 5: Commit the helper layer with the two-repo pattern**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_reporting_history.py && git -c core.hooksPath=/dev/null commit -m $'feat(debt): add reporting history helper\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
cd /Users/xiamingxing/Workspace && git add -- .omo/tests/test_omo_debt_reporting_history.py scripts && git -c core.hooksPath=/dev/null commit -m $'test(omo): cover reporting history helper\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Expected: one `scripts/` commit for the helper module and one root commit for the test + gitlink update.

### Task 2: Wire `report-history` into the CLI and generate the live history surface

**Files:**
- Modify: `scripts/omo_debt.py`
- Modify: `.omo/tests/test_omo_debt_cli.py`
- Create/refresh: `.omo/debt/reporting/history/current.yaml`
- Create/refresh: `.omo/debt/reporting/history/current.md`
- Test: `.omo/tests/test_omo_debt_cli.py`

- [ ] **Step 1: Add failing CLI tests**

Extend `.omo/tests/test_omo_debt_cli.py`:

```python
def test_debt_report_history_requires_dispatch_runs(tmp_path: Path) -> None:
    debt_dir = tmp_path / ".omo" / "debt"
    debt_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-history",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "dispatch/runs" in result.stderr


def test_debt_report_history_writes_latest_and_prior_run_metadata(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    older_dispatch = tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-01T00-00-00Z.yaml"
    older_reporting = tmp_path / ".omo" / "debt" / "reporting" / "runs" / "2026-06-01T00-00-00Z" / "current.yaml"
    older_dispatch.parent.mkdir(parents=True, exist_ok=True)
    older_dispatch.write_text("dispatched_at: '2026-06-01T00:00:00Z'\n", encoding="utf-8")
    older_reporting.parent.mkdir(parents=True, exist_ok=True)
    older_reporting.write_text(
        yaml.safe_dump(
            {
                "generated_at": "2026-06-01T02:00:00Z",
                "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                "run_stamp": "2026-06-01T00-00-00Z",
                "summary": {
                    "owner_count": 4,
                    "total_items": 9,
                    "state_counts": {"pending_approval": 1, "ready_to_execute": 8, "executed": 0},
                    "gate_item_count": 1,
                    "approved_gate_item_count": 0,
                    "approval_coverage_rate": 0.0,
                    "executed_item_count": 0,
                    "execution_completion_rate": 0.0,
                },
                "owners": [],
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
            "report-history",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load(
        (tmp_path / ".omo" / "debt" / "reporting" / "history" / "current.yaml").read_text(encoding="utf-8")
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "generated debt reporting history packet"
    assert packet["latest_run_stamp"] == "2026-06-10T00-00-00Z"
    assert packet["prior_run_stamp"] == "2026-06-01T00-00-00Z"
    assert [entry["run_stamp"] for entry in packet["runs"]] == [
        "2026-06-10T00-00-00Z",
        "2026-06-01T00-00-00Z",
    ]


def test_debt_report_history_keeps_run_when_reporting_artifact_is_missing(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    older_dispatch = tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-01T00-00-00Z.yaml"
    older_dispatch.parent.mkdir(parents=True, exist_ok=True)
    older_dispatch.write_text("dispatched_at: '2026-06-01T00:00:00Z'\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-history",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load(
        (tmp_path / ".omo" / "debt" / "reporting" / "history" / "current.yaml").read_text(encoding="utf-8")
    )

    assert result.returncode == 0, result.stderr
    assert packet["prior_run_stamp"] == "2026-06-01T00-00-00Z"
    assert packet["runs"][1]["reporting_exists"] is False
    assert packet["runs"][1]["reporting_ref"] is None
```

- [ ] **Step 2: Run the CLI tests to verify they fail**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py -q -k 'debt_report_history'
```

Expected: FAIL because `report-history` is not a recognized subcommand.

- [ ] **Step 3: Add the CLI boundary and history writers**

Update the imports in `scripts/omo_debt.py`:

```python
    from scripts.omo_debt_reporting import build_reporting_packet, render_reporting_markdown
    from scripts.omo_debt_reporting_history import build_reporting_history_packet, render_reporting_history_markdown
```

```python
    from omo_debt_reporting import build_reporting_packet, render_reporting_markdown
    from omo_debt_reporting_history import build_reporting_history_packet, render_reporting_history_markdown
```

Add the history helpers near the existing reporting helpers:

```python
def write_reporting_history_packet(omo_dir: Path, history_packet: dict[str, object]) -> None:
    history_dir = omo_dir / "debt" / "reporting" / "history"
    markdown = render_reporting_history_markdown(history_packet)
    _write_yaml(history_dir / "current.yaml", history_packet)
    current_md_path = history_dir / "current.md"
    current_md_path.parent.mkdir(parents=True, exist_ok=True)
    current_md_path.write_text(markdown, encoding="utf-8")


def _reporting_history_inputs(
    omo_dir: Path,
) -> tuple[tuple[dict[str, str], ...], dict[str, dict[str, object]]]:
    dispatch_runs_dir = omo_dir / "debt" / "dispatch" / "runs"
    run_paths = sorted(dispatch_runs_dir.glob("*.yaml"))
    if not run_paths:
        raise FileNotFoundError(f"no dispatch run artifacts found: {dispatch_runs_dir}")

    dispatch_runs: list[dict[str, str]] = []
    reporting_packets_by_run: dict[str, dict[str, object]] = {}
    for run_path in run_paths:
        run_stamp = run_path.stem
        dispatch_runs.append(
            {
                "run_stamp": run_stamp,
                "dispatch_run_ref": f".omo/debt/dispatch/runs/{run_path.name}",
            }
        )
        reporting_path = omo_dir / "debt" / "reporting" / "runs" / run_stamp / "current.yaml"
        if not reporting_path.exists():
            continue
        reporting_packet = _load_yaml(reporting_path)
        if not reporting_packet:
            raise ValueError(f"empty reporting run artifact: {reporting_path}")
        if reporting_packet.get("run_stamp") != run_stamp:
            raise ValueError(f"reporting run stamp mismatch: {reporting_path}")
        reporting_packets_by_run[run_stamp] = reporting_packet
    return tuple(dispatch_runs), reporting_packets_by_run


def reporting_history_outputs(omo_dir: Path) -> None:
    dispatch_runs, reporting_packets_by_run = _reporting_history_inputs(omo_dir)
    write_reporting_history_packet(
        omo_dir,
        build_reporting_history_packet(
            generated_at=_timestamp(),
            dispatch_runs=dispatch_runs,
            reporting_packets_by_run=reporting_packets_by_run,
        ),
    )
```

Add the parser and command branch:

```python
    report_history_parser = subparsers.add_parser("report-history")
    report_history_parser.add_argument("--omo-dir", default=".omo")
```

```python
    if args.command == "report-history":
        reporting_history_outputs(omo_dir)
        print("generated debt reporting history packet")
        return 0
```

Hydrate the live repo output after wiring the command:

```bash
cd /Users/xiamingxing/Workspace && python3 scripts/omo_debt.py report-history --omo-dir .omo
```

- [ ] **Step 4: Run the focused CLI tests to verify they pass**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py -q -k 'debt_report_history'
```

Expected: PASS with all 3 `debt_report_history` tests green, and the live repo now has:

```text
.omo/debt/reporting/history/current.yaml
.omo/debt/reporting/history/current.md
```

- [ ] **Step 5: Commit the CLI/history surface with the two-repo pattern**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt.py && git -c core.hooksPath=/dev/null commit -m $'feat(debt): add reporting history command\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
cd /Users/xiamingxing/Workspace && git add -- .omo/tests/test_omo_debt_cli.py .omo/debt/reporting/history/current.yaml .omo/debt/reporting/history/current.md scripts && git -c core.hooksPath=/dev/null commit -m $'test(omo): cover debt reporting history cli\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Expected: one `scripts/` commit for CLI wiring and one root commit for the live output + tests.

### Task 3: Document the new history surface and run verification

**Files:**
- Modify: `.omo/AGENT.md`
- Modify: `.omo/tests/test_omo_debt_docs.py`
- Test: `.omo/tests/test_omo_debt_docs.py`

- [ ] **Step 1: Add the failing docs assertions**

Extend `.omo/tests/test_omo_debt_docs.py`:

```python
    assert "python3 scripts/omo_debt.py report-history --omo-dir .omo" in content
    assert ".omo/debt/reporting/history/current.yaml" in content
    assert ".omo/debt/reporting/history/current.md" in content
    assert "latest run" in content.lower()
    assert "prior run" in content.lower()
    assert "prerequisite for later diff work" in content.lower()
```

- [ ] **Step 2: Run the docs test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py -q
```

Expected: FAIL because `.omo/AGENT.md` does not yet document `report-history` or the history surface.

- [ ] **Step 3: Update operator guidance**

Add these bullets to the debt-governance section in `.omo/AGENT.md`, immediately after the existing reporting bullets:

```md
- Generate the cross-run history index with `python3 scripts/omo_debt.py report-history --omo-dir .omo`
- Reporting history lives at `.omo/debt/reporting/history/current.yaml` plus `.omo/debt/reporting/history/current.md`
- The history surface resolves `latest_run_stamp` and `prior_run_stamp` from dispatch-run identity and is the prerequisite for later latest-vs-prior diff work
- `report-history` enumerates known dispatch runs, attaches per-run reporting artifacts when present, and keeps missing reporting artifacts visible instead of silently dropping those runs
- Cross-run diff and burndown still remain deferred in this slice
```

- [ ] **Step 4: Run docs + focused history verification**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_history.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_docs.py -q -k 'reporting_history or debt_report_history or omo_agent_documents_debt_refresh_flow'
cd /Users/xiamingxing/Workspace && bash bin/verify-omo.sh
```

Expected:

1. the focused reporting-history/docs subset passes
2. canonical `bin/verify-omo.sh` stays green

- [ ] **Step 5: Commit the docs closeout**

Run:

```bash
cd /Users/xiamingxing/Workspace && git add -- .omo/AGENT.md .omo/tests/test_omo_debt_docs.py docs/superpowers/plans/2026-06-02-debt-reporting-history-index.md && git -c core.hooksPath=/dev/null commit -m $'docs(omo): document debt reporting history index\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Expected: one root commit closing the operator/docs/plan surface for the slice.
