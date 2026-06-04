# Debt Reporting Diff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a narrow `report-diff` surface that compares the latest run against the immediately prior run using summary-only reporting deltas, while treating `no_prior_run` as a valid packet state.

**Architecture:** Keep the slice additive and derived. Add one pure helper module that computes summary-only diff packets from two in-memory reporting packets, then wire `scripts/omo_debt.py` to use the history index only for run selection and to re-derive both reporting packets from dispatch/approval/execution facts before diffing them. Because `scripts/` is a nested git repo / gitlink and may already be dirty from unrelated work, every mixed `scripts/*` + root change must use pathspec-limited two-repo commits without cleaning unrelated files.

**Tech Stack:** Python 3, PyYAML, pytest, existing `scripts/omo_debt.py` debt-governance CLI, `scripts/omo_debt_reporting.py`, `scripts/omo_debt_reporting_history.py`, `.omo` governance docs/tests

---

## File structure map

- Create: `scripts/omo_debt_reporting_diff.py`
  - Pure helper layer for `diff_available` / `no_prior_run` packet construction, summary delta computation, and Markdown rendering.
- Create: `.omo/tests/test_omo_debt_reporting_diff.py`
  - Focused unit coverage for summary deltas, `no_prior_run`, reserved `owners: null`, and Markdown output.
- Modify: `scripts/omo_debt.py`
  - Add `report-diff` CLI wiring, history-pair resolution, fresh reporting re-derivation, diff writer, and live diff generation.
- Modify: `.omo/tests/test_omo_debt_cli.py`
  - CLI regressions for missing history, `no_prior_run`, and proof that diff uses fresh fact re-derivation instead of history metadata.
- Create/refresh: `.omo/debt/reporting/diff/current.yaml`
  - Canonical machine-readable latest-vs-prior diff packet.
- Create/refresh: `.omo/debt/reporting/diff/current.md`
  - Human-readable latest-vs-prior diff summary.
- Modify: `.omo/AGENT.md`
  - Document `report-diff`, the new diff surface, `no_prior_run`, and the continued owner-level deferral.
- Modify: `.omo/tests/test_omo_debt_docs.py`
  - Lock the updated operator guidance.

## Implementation notes before starting

- Work from `/Users/xiamingxing/Workspace`.
- Do **not** clean or revert unrelated changes inside `scripts/`; pathspec every add/commit.
- Keep this slice narrow:
  1. summary-only diff
  2. no owner-level deltas
  3. no burndown or trend analytics
  4. no explicit `--latest-run` / `--prior-run` overrides
- Use `reporting/history/current.yaml` only to select the run pair. Do not read its copied metrics as diff truth.
- Reuse the existing latest-run derivation path: `build_selected_campaign_packet(...)` + `build_reporting_packet(...)`.
- Reserve `owners: null` now so owner-level diff can be added later without a breaking packet shape.
- Exclude `owner_count` from the Version 1 diff surface.

### Task 1: Build the pure reporting-diff helper layer

**Files:**
- Create: `scripts/omo_debt_reporting_diff.py`
- Create: `.omo/tests/test_omo_debt_reporting_diff.py`
- Test: `.omo/tests/test_omo_debt_reporting_diff.py`

- [ ] **Step 1: Write the failing unit tests**

Create `.omo/tests/test_omo_debt_reporting_diff.py`:

```python
from __future__ import annotations

from scripts.omo_debt_reporting_diff import build_reporting_diff_packet, render_reporting_diff_markdown


def _reporting_packet(
    run_stamp: str,
    *,
    dispatch_run_ref: str,
    total_items: int,
    pending_approval: int,
    ready_to_execute: int,
    executed: int,
    gate_item_count: int,
    approved_gate_item_count: int,
    approval_coverage_rate: float,
    executed_item_count: int,
    execution_completion_rate: float,
) -> dict[str, object]:
    return {
        "generated_at": "2026-06-12T00:00:00Z",
        "dispatch_run_ref": dispatch_run_ref,
        "run_stamp": run_stamp,
        "summary": {
            "owner_count": 4,
            "total_items": total_items,
            "state_counts": {
                "pending_approval": pending_approval,
                "ready_to_execute": ready_to_execute,
                "executed": executed,
            },
            "gate_item_count": gate_item_count,
            "approved_gate_item_count": approved_gate_item_count,
            "approval_coverage_rate": approval_coverage_rate,
            "executed_item_count": executed_item_count,
            "execution_completion_rate": execution_completion_rate,
        },
        "owners": [],
    }


def test_build_reporting_diff_packet_computes_summary_deltas() -> None:
    latest = _reporting_packet(
        "2026-06-10T00-00-00Z",
        dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        total_items=9,
        pending_approval=0,
        ready_to_execute=7,
        executed=2,
        gate_item_count=1,
        approved_gate_item_count=1,
        approval_coverage_rate=1.0,
        executed_item_count=2,
        execution_completion_rate=2 / 9,
    )
    prior = _reporting_packet(
        "2026-06-01T00-00-00Z",
        dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
        total_items=9,
        pending_approval=1,
        ready_to_execute=8,
        executed=0,
        gate_item_count=1,
        approved_gate_item_count=0,
        approval_coverage_rate=0.0,
        executed_item_count=0,
        execution_completion_rate=0.0,
    )

    packet = build_reporting_diff_packet(
        generated_at="2026-06-12T01:00:00Z",
        latest_packet=latest,
        prior_packet=prior,
    )

    assert packet["diff_status"] == "diff_available"
    assert packet["latest_run_stamp"] == "2026-06-10T00-00-00Z"
    assert packet["prior_run_stamp"] == "2026-06-01T00-00-00Z"
    assert packet["owners"] is None
    assert packet["summary_diff"]["total_items"] == {"latest": 9, "prior": 9, "delta": 0}
    assert packet["summary_diff"]["state_counts"]["executed"] == {"latest": 2, "prior": 0, "delta": 2}
    assert packet["summary_diff"]["approval_coverage_rate"] == {"latest": 1.0, "prior": 0.0, "delta": 1.0}
    assert "owner_count" not in packet["summary_diff"]


def test_build_reporting_diff_packet_writes_no_prior_run_state() -> None:
    latest = _reporting_packet(
        "2026-06-10T00-00-00Z",
        dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        total_items=9,
        pending_approval=1,
        ready_to_execute=8,
        executed=0,
        gate_item_count=1,
        approved_gate_item_count=0,
        approval_coverage_rate=0.0,
        executed_item_count=0,
        execution_completion_rate=0.0,
    )

    packet = build_reporting_diff_packet(
        generated_at="2026-06-12T01:00:00Z",
        latest_packet=latest,
        prior_packet=None,
    )

    assert packet["diff_status"] == "no_prior_run"
    assert packet["prior_run_stamp"] is None
    assert packet["prior_dispatch_run_ref"] is None
    assert packet["owners"] is None
    assert packet["summary_diff"]["total_items"] == {"latest": 9, "prior": None, "delta": None}
    assert packet["summary_diff"]["state_counts"]["pending_approval"] == {
        "latest": 1,
        "prior": None,
        "delta": None,
    }


def test_render_reporting_diff_markdown_shows_diff_and_no_prior_states() -> None:
    latest = _reporting_packet(
        "2026-06-10T00-00-00Z",
        dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        total_items=9,
        pending_approval=0,
        ready_to_execute=7,
        executed=2,
        gate_item_count=1,
        approved_gate_item_count=1,
        approval_coverage_rate=1.0,
        executed_item_count=2,
        execution_completion_rate=2 / 9,
    )
    prior = _reporting_packet(
        "2026-06-01T00-00-00Z",
        dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
        total_items=9,
        pending_approval=1,
        ready_to_execute=8,
        executed=0,
        gate_item_count=1,
        approved_gate_item_count=0,
        approval_coverage_rate=0.0,
        executed_item_count=0,
        execution_completion_rate=0.0,
    )

    markdown = render_reporting_diff_markdown(
        build_reporting_diff_packet(
            generated_at="2026-06-12T01:00:00Z",
            latest_packet=latest,
            prior_packet=prior,
        )
    )
    no_prior_markdown = render_reporting_diff_markdown(
        build_reporting_diff_packet(
            generated_at="2026-06-12T01:00:00Z",
            latest_packet=latest,
            prior_packet=None,
        )
    )

    assert "# Debt Reporting Diff" in markdown
    assert "Diff status: diff_available" in markdown
    assert "approval_coverage_rate: latest=1.0, prior=0.0, delta=1.0" in markdown
    assert "Diff status: no_prior_run" in no_prior_markdown
    assert "Prior baseline not established yet." in no_prior_markdown
```

- [ ] **Step 2: Run the unit tests to verify they fail**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_diff.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.omo_debt_reporting_diff'`.

- [ ] **Step 3: Write the minimal reporting-diff helper**

Create `scripts/omo_debt_reporting_diff.py`:

```python
from __future__ import annotations


def _delta_metric(latest: int | float, prior: int | float | None) -> dict[str, int | float | None]:
    if prior is None:
        return {"latest": latest, "prior": None, "delta": None}
    return {"latest": latest, "prior": prior, "delta": latest - prior}


def _summary_diff(latest_summary: dict[str, object], prior_summary: dict[str, object] | None) -> dict[str, object]:
    prior_state_counts = prior_summary["state_counts"] if prior_summary else None
    return {
        "total_items": _delta_metric(int(latest_summary["total_items"]), int(prior_summary["total_items"]) if prior_summary else None),
        "state_counts": {
            "pending_approval": _delta_metric(
                int(latest_summary["state_counts"]["pending_approval"]),
                int(prior_state_counts["pending_approval"]) if prior_state_counts else None,
            ),
            "ready_to_execute": _delta_metric(
                int(latest_summary["state_counts"]["ready_to_execute"]),
                int(prior_state_counts["ready_to_execute"]) if prior_state_counts else None,
            ),
            "executed": _delta_metric(
                int(latest_summary["state_counts"]["executed"]),
                int(prior_state_counts["executed"]) if prior_state_counts else None,
            ),
        },
        "gate_item_count": _delta_metric(
            int(latest_summary["gate_item_count"]),
            int(prior_summary["gate_item_count"]) if prior_summary else None,
        ),
        "approved_gate_item_count": _delta_metric(
            int(latest_summary["approved_gate_item_count"]),
            int(prior_summary["approved_gate_item_count"]) if prior_summary else None,
        ),
        "approval_coverage_rate": _delta_metric(
            float(latest_summary["approval_coverage_rate"]),
            float(prior_summary["approval_coverage_rate"]) if prior_summary else None,
        ),
        "executed_item_count": _delta_metric(
            int(latest_summary["executed_item_count"]),
            int(prior_summary["executed_item_count"]) if prior_summary else None,
        ),
        "execution_completion_rate": _delta_metric(
            float(latest_summary["execution_completion_rate"]),
            float(prior_summary["execution_completion_rate"]) if prior_summary else None,
        ),
    }


def build_reporting_diff_packet(
    *,
    generated_at: str,
    latest_packet: dict[str, object],
    prior_packet: dict[str, object] | None,
) -> dict[str, object]:
    latest_summary = latest_packet["summary"]
    prior_summary = prior_packet["summary"] if prior_packet else None
    return {
        "generated_at": generated_at,
        "diff_status": "diff_available" if prior_packet else "no_prior_run",
        "latest_run_stamp": latest_packet["run_stamp"],
        "prior_run_stamp": prior_packet["run_stamp"] if prior_packet else None,
        "latest_dispatch_run_ref": latest_packet["dispatch_run_ref"],
        "prior_dispatch_run_ref": prior_packet["dispatch_run_ref"] if prior_packet else None,
        "summary_diff": _summary_diff(latest_summary, prior_summary),
        "owners": None,
    }


def render_reporting_diff_markdown(packet: dict[str, object]) -> str:
    lines = [
        "# Debt Reporting Diff",
        "",
        f"Generated at: {packet['generated_at']}",
        f"Diff status: {packet['diff_status']}",
        f"Latest run: {packet['latest_run_stamp']}",
        f"Prior run: {packet['prior_run_stamp'] or 'none'}",
        "",
    ]
    if packet["diff_status"] == "no_prior_run":
        lines.extend(["Prior baseline not established yet.", ""])
    for field, payload in packet["summary_diff"].items():
        if field == "state_counts":
            lines.append("## state_counts")
            lines.append("")
            for state_name, state_payload in payload.items():
                lines.append(
                    f"{state_name}: latest={state_payload['latest']}, prior={state_payload['prior']}, delta={state_payload['delta']}"
                )
            lines.append("")
            continue
        lines.append(f"{field}: latest={payload['latest']}, prior={payload['prior']}, delta={payload['delta']}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run the unit tests to verify they pass**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_diff.py -q
```

Expected: PASS with all 3 tests green.

- [ ] **Step 5: Commit the helper layer with the two-repo pattern**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_reporting_diff.py && git -c core.hooksPath=/dev/null commit -m $'feat(debt): add reporting diff helper\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
cd /Users/xiamingxing/Workspace && git add -- .omo/tests/test_omo_debt_reporting_diff.py scripts && git -c core.hooksPath=/dev/null commit -m $'test(omo): cover reporting diff helper\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Expected: one `scripts/` commit for the helper and one root commit for the test + gitlink update.

### Task 2: Wire `report-diff` into the CLI and generate the live diff surface

**Files:**
- Modify: `scripts/omo_debt.py`
- Modify: `.omo/tests/test_omo_debt_cli.py`
- Create/refresh: `.omo/debt/reporting/diff/current.yaml`
- Create/refresh: `.omo/debt/reporting/diff/current.md`
- Test: `.omo/tests/test_omo_debt_cli.py`

- [ ] **Step 1: Add failing CLI tests**

Extend `.omo/tests/test_omo_debt_cli.py`:

```python
def test_debt_report_diff_requires_history_packet(tmp_path: Path) -> None:
    debt_dir = tmp_path / ".omo" / "debt"
    debt_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-diff",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "reporting/history/current.yaml" in result.stderr


def test_debt_report_diff_writes_no_prior_run_packet_for_single_history_run(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report-diff",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load((tmp_path / ".omo" / "debt" / "reporting" / "diff" / "current.yaml").read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "generated debt reporting diff packet"
    assert packet["diff_status"] == "no_prior_run"
    assert packet["latest_run_stamp"] == "2026-06-10T00-00-00Z"
    assert packet["prior_run_stamp"] is None
    assert packet["owners"] is None
    assert packet["summary_diff"]["total_items"]["latest"] == 9
    assert packet["summary_diff"]["total_items"]["prior"] is None


def test_debt_report_diff_rederives_metrics_from_facts_not_history_metadata(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    older_dispatch = tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-01T00-00-00Z.yaml"
    older_dispatch.parent.mkdir(parents=True, exist_ok=True)
    older_dispatch.write_text(
        (tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-10T00-00-00Z.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    approval_dir = tmp_path / ".omo" / "debt" / "approvals" / "SB_DECOMPOSITION"
    approval_dir.mkdir(parents=True, exist_ok=True)
    approval_dir.joinpath("current.yaml").write_text(
        yaml.safe_dump(
            {
                "item_id": "SB_DECOMPOSITION",
                "approved_by": "omo-governance",
                "approved_at": "2026-06-01T01:00:00Z",
                "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                "approval_scope": "execute_revalidate",
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    execution_dir = tmp_path / ".omo" / "debt" / "dispatch" / "executions" / "2026-06-01T00-00-00Z"
    execution_dir.mkdir(parents=True, exist_ok=True)
    execution_dir.joinpath("SB_UNTESTED_PKGS.yaml").write_text(
        yaml.safe_dump(
            {
                "item_id": "SB_UNTESTED_PKGS",
                "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                "executed_at": "2026-06-01T02:00:00Z",
                "reviewed_at": "2026-06-01T02:00:00Z",
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    history_path = tmp_path / ".omo" / "debt" / "reporting" / "history" / "current.yaml"
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
                        "report_generated_at": "2026-06-02T10:52:31Z",
                        "total_items": 999,
                        "executed_item_count": 999,
                        "approval_coverage_rate": 999.0,
                        "execution_completion_rate": 999.0,
                    },
                    {
                        "run_stamp": "2026-06-01T00-00-00Z",
                        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                        "reporting_ref": ".omo/debt/reporting/runs/2026-06-01T00-00-00Z/current.yaml",
                        "reporting_exists": True,
                        "report_generated_at": "2026-06-01T02:00:00Z",
                        "total_items": 999,
                        "executed_item_count": 999,
                        "approval_coverage_rate": 999.0,
                        "execution_completion_rate": 999.0,
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
            "report-diff",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load((tmp_path / ".omo" / "debt" / "reporting" / "diff" / "current.yaml").read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stderr
    assert packet["diff_status"] == "diff_available"
    assert packet["summary_diff"]["total_items"] == {"latest": 9, "prior": 9, "delta": 0}
    assert packet["summary_diff"]["approval_coverage_rate"] == {"latest": 0.0, "prior": 1.0, "delta": -1.0}
    assert packet["summary_diff"]["executed_item_count"] == {"latest": 0, "prior": 1, "delta": -1}
```

- [ ] **Step 2: Run the CLI tests to verify they fail**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py -q -k 'debt_report_diff'
```

Expected: FAIL because `report-diff` is not a recognized subcommand and the diff output path does not exist.

- [ ] **Step 3: Add the CLI boundary, history selection, and diff writers**

Update the imports in `scripts/omo_debt.py`:

```python
    from scripts.omo_debt_reporting_diff import build_reporting_diff_packet, render_reporting_diff_markdown
```

```python
    from omo_debt_reporting_diff import build_reporting_diff_packet, render_reporting_diff_markdown
```

Add the diff helpers near the existing reporting/history helpers:

```python
def write_reporting_diff_packet(omo_dir: Path, diff_packet: dict[str, object]) -> None:
    diff_dir = omo_dir / "debt" / "reporting" / "diff"
    markdown = render_reporting_diff_markdown(diff_packet)
    _write_yaml(diff_dir / "current.yaml", diff_packet)
    current_md_path = diff_dir / "current.md"
    current_md_path.parent.mkdir(parents=True, exist_ok=True)
    current_md_path.write_text(markdown, encoding="utf-8")


def load_reporting_history_packet(omo_dir: Path) -> dict[str, object]:
    history_path = omo_dir / "debt" / "reporting" / "history" / "current.yaml"
    if not history_path.exists():
        raise FileNotFoundError(f"missing reporting history packet: {history_path}")
    history_packet = _load_yaml(history_path)
    if not history_packet:
        raise ValueError(f"empty reporting history packet: {history_path}")
    return history_packet


def _history_run_ref(history_packet: dict[str, object], run_stamp: str | None) -> str | None:
    if run_stamp is None:
        return None
    for entry in history_packet["runs"]:
        if entry["run_stamp"] == run_stamp:
            return entry["dispatch_run_ref"]
    raise ValueError(f"missing history run entry for: {run_stamp}")


def reporting_diff_outputs(omo_dir: Path) -> None:
    history_packet = load_reporting_history_packet(omo_dir)
    latest_run_ref = _history_run_ref(history_packet, history_packet.get("latest_run_stamp"))
    if latest_run_ref is None:
        raise ValueError("reporting history is missing latest_run_stamp")
    prior_run_ref = _history_run_ref(history_packet, history_packet.get("prior_run_stamp"))
    latest_reporting = build_reporting_packet(build_selected_campaign_packet(omo_dir, latest_run_ref))
    prior_reporting = (
        build_reporting_packet(build_selected_campaign_packet(omo_dir, prior_run_ref))
        if prior_run_ref
        else None
    )
    write_reporting_diff_packet(
        omo_dir,
        build_reporting_diff_packet(
            generated_at=_timestamp(),
            latest_packet=latest_reporting,
            prior_packet=prior_reporting,
        ),
    )
```

Add the parser and command branch:

```python
    report_diff_parser = subparsers.add_parser("report-diff")
    report_diff_parser.add_argument("--omo-dir", default=".omo")
```

```python
    if args.command == "report-diff":
        reporting_diff_outputs(omo_dir)
        print("generated debt reporting diff packet")
        return 0
```

Hydrate the live repo output after wiring the command:

```bash
cd /Users/xiamingxing/Workspace && python3 scripts/omo_debt.py report-diff --omo-dir .omo
```

- [ ] **Step 4: Run the focused CLI tests to verify they pass**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py -q -k 'debt_report_diff'
```

Expected: PASS with all 3 `debt_report_diff` tests green, and the live repo now has:

```text
.omo/debt/reporting/diff/current.yaml
.omo/debt/reporting/diff/current.md
```

- [ ] **Step 5: Commit the CLI/diff surface with the two-repo pattern**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt.py && git -c core.hooksPath=/dev/null commit -m $'feat(debt): add reporting diff command\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
cd /Users/xiamingxing/Workspace && git add -- .omo/tests/test_omo_debt_cli.py .omo/debt/reporting/diff/current.yaml .omo/debt/reporting/diff/current.md scripts && git -c core.hooksPath=/dev/null commit -m $'test(omo): cover debt reporting diff cli\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Expected: one `scripts/` commit for CLI wiring and one root commit for the live diff output + tests.

### Task 3: Document the diff surface and run verification

**Files:**
- Modify: `.omo/AGENT.md`
- Modify: `.omo/tests/test_omo_debt_docs.py`
- Test: `.omo/tests/test_omo_debt_docs.py`

- [ ] **Step 1: Add the failing docs assertions**

Extend `.omo/tests/test_omo_debt_docs.py`:

```python
    assert "python3 scripts/omo_debt.py report-diff --omo-dir .omo" in content
    assert ".omo/debt/reporting/diff/current.yaml" in content
    assert ".omo/debt/reporting/diff/current.md" in content
    assert "no_prior_run" in content
    assert "owners: null" in content.lower()
    assert "summary-only diff" in content.lower()
```

- [ ] **Step 2: Run the docs test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py -q
```

Expected: FAIL because `.omo/AGENT.md` does not yet document `report-diff` or the diff surface.

- [ ] **Step 3: Update operator guidance**

Add these bullets to the debt-governance section in `.omo/AGENT.md`, immediately after the history bullets:

```md
- Generate the latest-vs-prior summary diff with `python3 scripts/omo_debt.py report-diff --omo-dir .omo`
- Reporting diff lives at `.omo/debt/reporting/diff/current.yaml` plus `.omo/debt/reporting/diff/current.md`
- `report-diff` uses `reporting/history/current.yaml` only to select the latest/prior run pair, then re-derives both runs from dispatch, approval, and execution facts before comparing them
- If only one run exists, `report-diff` writes a valid `no_prior_run` packet instead of failing
- Version 1 diff remains summary-only and keeps `owners: null`; owner-level deltas and burndown remain deferred
```

- [ ] **Step 4: Run docs + focused diff verification**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_diff.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_docs.py -q -k 'reporting_diff or debt_report_diff or omo_agent_documents_debt_refresh_flow'
cd /Users/xiamingxing/Workspace && bash bin/verify-omo.sh
```

Expected:

1. the focused reporting-diff/docs subset passes
2. canonical `bin/verify-omo.sh` stays green

- [ ] **Step 5: Commit the docs closeout**

Run:

```bash
cd /Users/xiamingxing/Workspace && git add -- .omo/AGENT.md .omo/tests/test_omo_debt_docs.py docs/superpowers/plans/2026-06-02-debt-reporting-diff.md && git -c core.hooksPath=/dev/null commit -m $'docs(omo): document debt reporting diff surface\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Expected: one root commit closing the operator/docs/plan surface for the slice.
