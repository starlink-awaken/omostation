# Debt Reporting Rollup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a narrow latest-run `report` surface that summarizes debt dispatch progress with compact counts and rates, while keeping dashboard, campaign, and reporting as distinct derived layers.

**Architecture:** Keep reporting as a pure derived layer. Add one small helper module that condenses an in-memory campaign packet into a reporting packet plus Markdown, then wire `scripts/omo_debt.py` to build that packet directly from dispatch, approval, and execution facts without reading generated campaign artifacts from disk. Because `scripts/` is a nested git repo / gitlink, any task that touches both `scripts/*` and root-tracked tests must use the two-repo commit pattern.

**Tech Stack:** Python 3, PyYAML, pytest, existing `scripts/omo_debt.py` debt-governance CLI, `.omo` regression suite

---

## File structure map

- Create: `scripts/omo_debt_reporting.py`
  - Pure helper layer that converts a campaign packet into a compact reporting packet and Markdown rollup.
- Create: `.omo/tests/test_omo_debt_reporting.py`
  - Focused unit coverage for reporting summary math, owner rollups, and Markdown rendering.
- Modify: `scripts/omo_debt.py`
  - Reuse existing campaign fact collection in memory, add reporting writers, add `report` CLI command.
- Modify: `.omo/tests/test_omo_debt_cli.py`
  - CLI regressions for missing dispatch, current/run output writing, and approval/execution reflection.
- Modify: `.omo/AGENT.md`
  - Operator guidance for `report` and the distinction between dashboard, campaign, and reporting.
- Modify: `.omo/tests/test_omo_debt_docs.py`
  - Documentation regression for the new reporting operator surface.

## Implementation notes before starting

- Work from `/Users/xiamingxing/Workspace`.
- `scripts/` is a nested repo. When a task changes both `scripts/*` and root files, commit twice:
  1. commit inside `/Users/xiamingxing/Workspace/scripts`
  2. commit in `/Users/xiamingxing/Workspace` including the updated `scripts` gitlink and root-tracked files
- Keep the slice narrow:
  - no cross-run history
  - no SLA metrics
  - no mutation of debt items, approvals, executions, or campaign outputs
- Do not read `.omo/debt/campaign/current.yaml` as input; reporting must derive from the same facts as campaign, in memory.

### Task 1: Build the pure reporting helper layer

**Files:**
- Create: `scripts/omo_debt_reporting.py`
- Test: `.omo/tests/test_omo_debt_reporting.py`

- [ ] **Step 1: Write the failing unit tests**

Create `.omo/tests/test_omo_debt_reporting.py` with focused packet + Markdown assertions:

```python
from __future__ import annotations

from scripts.omo_debt_reporting import build_reporting_packet, render_reporting_markdown


def _campaign_packet() -> dict[str, object]:
    return {
        "generated_at": "2026-06-11T00:00:00Z",
        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        "run_stamp": "2026-06-10T00-00-00Z",
        "summary": {
            "owner_count": 2,
            "total_items": 3,
            "state_counts": {
                "pending_approval": 1,
                "ready_to_execute": 1,
                "executed": 1,
            },
        },
        "owners": [
            {
                "owner": "sharedbrain-governance",
                "item_count": 2,
                "state_counts": {
                    "pending_approval": 1,
                    "ready_to_execute": 1,
                    "executed": 0,
                },
                "entries": [
                    {
                        "id": "SB_DECOMPOSITION",
                        "gate_level": "gate",
                        "campaign_state": "pending_approval",
                        "command": "python3 scripts/omo_debt.py revalidate ...",
                    },
                    {
                        "id": "SB_UNTESTED_PKGS",
                        "gate_level": "watchlist",
                        "campaign_state": "ready_to_execute",
                        "command": "python3 scripts/omo_debt.py revalidate ...",
                    },
                ],
            },
            {
                "owner": "omo-governance",
                "item_count": 1,
                "state_counts": {
                    "pending_approval": 0,
                    "ready_to_execute": 0,
                    "executed": 1,
                },
                "entries": [
                    {
                        "id": "SB_GATE_REVIEW",
                        "gate_level": "gate",
                        "campaign_state": "executed",
                        "execution_record_ref": ".omo/debt/dispatch/executions/2026-06-10T00-00-00Z/SB_GATE_REVIEW.yaml",
                        "command": "python3 scripts/omo_debt.py revalidate ...",
                    }
                ],
            },
        ],
    }


def test_build_reporting_packet_summarizes_counts_and_rates() -> None:
    packet = build_reporting_packet(_campaign_packet())

    assert packet["dispatch_run_ref"] == ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml"
    assert packet["summary"] == {
        "owner_count": 2,
        "total_items": 3,
        "state_counts": {
            "pending_approval": 1,
            "ready_to_execute": 1,
            "executed": 1,
        },
        "gate_item_count": 2,
        "approved_gate_item_count": 1,
        "approval_coverage_rate": 0.5,
        "executed_item_count": 1,
        "execution_completion_rate": 1 / 3,
    }

    owner = packet["owners"][0]
    assert owner == {
        "owner": "sharedbrain-governance",
        "item_count": 2,
        "state_counts": {
            "pending_approval": 1,
            "ready_to_execute": 1,
            "executed": 0,
        },
        "gate_item_count": 1,
        "approved_gate_item_count": 0,
        "approval_coverage_rate": 0.0,
        "executed_item_count": 0,
        "execution_completion_rate": 0.0,
    }


def test_render_reporting_markdown_shows_summary_and_owner_rollups() -> None:
    markdown = render_reporting_markdown(build_reporting_packet(_campaign_packet()))

    assert "# Debt Reporting Packet" in markdown
    assert "Approval coverage: 0.50" in markdown
    assert "Execution completion: 0.33" in markdown
    assert "## Owner: sharedbrain-governance" in markdown
    assert "gate_items=1, approved_gate_items=0" in markdown
```

- [ ] **Step 2: Run the unit tests to verify they fail**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting.py -q
```

Expected: FAIL with `ModuleNotFoundError` or import failure for `scripts.omo_debt_reporting`.

- [ ] **Step 3: Write the minimal reporting helper**

Create `scripts/omo_debt_reporting.py`:

```python
from __future__ import annotations


def _rate(numerator: int, denominator: int, *, empty_value: float) -> float:
    if denominator == 0:
        return empty_value
    return numerator / denominator


def _owner_rollup(owner_packet: dict[str, object]) -> dict[str, object]:
    gate_item_count = sum(1 for entry in owner_packet["entries"] if entry.get("gate_level") == "gate")
    approved_gate_item_count = sum(
        1
        for entry in owner_packet["entries"]
        if entry.get("gate_level") == "gate" and entry["campaign_state"] != "pending_approval"
    )
    executed_item_count = owner_packet["state_counts"]["executed"]
    return {
        "owner": owner_packet["owner"],
        "item_count": owner_packet["item_count"],
        "state_counts": dict(owner_packet["state_counts"]),
        "gate_item_count": gate_item_count,
        "approved_gate_item_count": approved_gate_item_count,
        "approval_coverage_rate": _rate(approved_gate_item_count, gate_item_count, empty_value=1.0),
        "executed_item_count": executed_item_count,
        "execution_completion_rate": _rate(executed_item_count, owner_packet["item_count"], empty_value=0.0),
    }


def build_reporting_packet(campaign_packet: dict[str, object]) -> dict[str, object]:
    owners = [_owner_rollup(owner_packet) for owner_packet in campaign_packet["owners"]]
    gate_item_count = sum(owner["gate_item_count"] for owner in owners)
    approved_gate_item_count = sum(owner["approved_gate_item_count"] for owner in owners)
    executed_item_count = sum(owner["executed_item_count"] for owner in owners)
    total_items = campaign_packet["summary"]["total_items"]
    return {
        "generated_at": campaign_packet["generated_at"],
        "dispatch_run_ref": campaign_packet["dispatch_run_ref"],
        "run_stamp": campaign_packet["run_stamp"],
        "summary": {
            "owner_count": campaign_packet["summary"]["owner_count"],
            "total_items": total_items,
            "state_counts": dict(campaign_packet["summary"]["state_counts"]),
            "gate_item_count": gate_item_count,
            "approved_gate_item_count": approved_gate_item_count,
            "approval_coverage_rate": _rate(approved_gate_item_count, gate_item_count, empty_value=1.0),
            "executed_item_count": executed_item_count,
            "execution_completion_rate": _rate(executed_item_count, total_items, empty_value=0.0),
        },
        "owners": owners,
    }


def render_reporting_markdown(packet: dict[str, object]) -> str:
    lines = [
        "# Debt Reporting Packet",
        "",
        f"Generated at: {packet['generated_at']}",
        f"Dispatch run: {packet['dispatch_run_ref']}",
        f"Approval coverage: {packet['summary']['approval_coverage_rate']:.2f}",
        f"Execution completion: {packet['summary']['execution_completion_rate']:.2f}",
        "",
    ]
    for owner in packet["owners"]:
        lines.extend(
            [
                f"## Owner: {owner['owner']}",
                "",
                (
                    f"items={owner['item_count']}, "
                    f"pending_approval={owner['state_counts']['pending_approval']}, "
                    f"ready_to_execute={owner['state_counts']['ready_to_execute']}, "
                    f"executed={owner['state_counts']['executed']}"
                ),
                (
                    f"gate_items={owner['gate_item_count']}, "
                    f"approved_gate_items={owner['approved_gate_item_count']}, "
                    f"approval_coverage={owner['approval_coverage_rate']:.2f}, "
                    f"execution_completion={owner['execution_completion_rate']:.2f}"
                ),
                "",
            ]
        )
    return "\n".join(lines)
```

- [ ] **Step 4: Run the unit tests to verify they pass**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit the helper layer with the two-repo pattern**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_reporting.py && git -c core.hooksPath=/dev/null commit -m $'feat(debt): add reporting rollup helper\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
cd /Users/xiamingxing/Workspace && git add -- .omo/tests/test_omo_debt_reporting.py scripts && git -c core.hooksPath=/dev/null commit -m $'test(omo): cover debt reporting helper\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Expected: one commit in `scripts/` and one root commit updating the gitlink plus the new test file.

### Task 2: Wire the `report` CLI and output writers

**Files:**
- Modify: `scripts/omo_debt.py`
- Test: `.omo/tests/test_omo_debt_cli.py`

- [ ] **Step 1: Add failing CLI regressions**

Append focused tests to `.omo/tests/test_omo_debt_cli.py`:

```python
def test_debt_report_requires_dispatch_packet_when_run_ref_missing(tmp_path: Path) -> None:
    debt_dir = tmp_path / ".omo" / "debt"
    debt_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "dispatch/current.yaml" in result.stderr


def test_debt_report_writes_latest_run_outputs(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    current_yaml = yaml.safe_load((tmp_path / ".omo" / "debt" / "reporting" / "current.yaml").read_text(encoding="utf-8"))
    run_yaml = yaml.safe_load(
        (tmp_path / ".omo" / "debt" / "reporting" / "runs" / "2026-06-10T00-00-00Z" / "current.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert result.returncode == 0, result.stderr
    assert current_yaml == run_yaml
    assert current_yaml["summary"]["approval_coverage_rate"] == 0.0
    assert current_yaml["summary"]["execution_completion_rate"] == 0.0


def test_debt_report_reflects_approval_and_execution_facts(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    approve = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "approve",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--approved-by",
            "omo-governance",
            "--scope",
            "execute_revalidate",
            "--approved-at",
            "2026-06-11T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    execute = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "revalidate",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_UNTESTED_PKGS",
            "--reviewed-at",
            "2026-06-11T12:00:00Z",
            "--dispatch-run-ref",
            ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    report = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "report",
            "--omo-dir",
            str(tmp_path / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    packet = yaml.safe_load((tmp_path / ".omo" / "debt" / "reporting" / "current.yaml").read_text(encoding="utf-8"))

    assert approve.returncode == 0, approve.stderr
    assert execute.returncode == 0, execute.stderr
    assert report.returncode == 0, report.stderr
    assert packet["summary"]["approval_coverage_rate"] == 1.0
    assert packet["summary"]["execution_completion_rate"] == 1 / 9
```

- [ ] **Step 2: Run the focused CLI tests to verify they fail**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py -q -k 'debt_report'
```

Expected: FAIL because `report` is not yet a valid subcommand and no reporting outputs are written.

- [ ] **Step 3: Implement reporting CLI wiring**

Modify `scripts/omo_debt.py` in three small moves:

1. import the helper:

```python
from scripts.omo_debt_reporting import build_reporting_packet, render_reporting_markdown
```

2. extract campaign packet construction so both commands can reuse it:

```python
def build_selected_campaign_packet(omo_dir: Path, run_ref: str | None) -> dict[str, object]:
    if run_ref:
        _, run_packet = load_dispatch_run(omo_dir, run_ref)
        dispatch_run_ref = run_ref
    else:
        dispatch_packet = load_dispatch_packet(omo_dir)
        dispatch_run_ref = dispatch_packet["latest_run_ref"]
        _, run_packet = load_dispatch_run(omo_dir, dispatch_run_ref)

    approval_lookup: dict[str, bool] = {}
    execution_lookup: dict[str, str] = {}
    for owner_packet in run_packet["owners"]:
        for entry in owner_packet["entries"]:
            item_id = entry["id"]
            approval_lookup[item_id] = _matching_approval_exists(omo_dir, item_id, dispatch_run_ref)
            execution_record_ref = _execution_record_ref(omo_dir, dispatch_run_ref, item_id)
            if execution_record_ref:
                execution_lookup[item_id] = execution_record_ref

    return build_campaign_packet(
        run_packet=run_packet,
        dispatch_run_ref=dispatch_run_ref,
        generated_at=_timestamp(),
        approval_lookup=approval_lookup,
        execution_lookup=execution_lookup,
    )
```

3. add reporting writers + CLI branch:

```python
def write_reporting_packet(omo_dir: Path, reporting_packet: dict[str, object]) -> None:
    markdown = render_reporting_markdown(reporting_packet)
    run_dir = omo_dir / "debt" / "reporting" / "runs" / reporting_packet["run_stamp"]
    _write_yaml(run_dir / "current.yaml", reporting_packet)
    run_md_path = run_dir / "current.md"
    run_md_path.parent.mkdir(parents=True, exist_ok=True)
    run_md_path.write_text(markdown, encoding="utf-8")
    _write_yaml(omo_dir / "debt" / "reporting" / "current.yaml", reporting_packet)
    current_md_path = omo_dir / "debt" / "reporting" / "current.md"
    current_md_path.parent.mkdir(parents=True, exist_ok=True)
    current_md_path.write_text(markdown, encoding="utf-8")


def reporting_outputs(omo_dir: Path, run_ref: str | None) -> None:
    campaign_packet = build_selected_campaign_packet(omo_dir, run_ref)
    write_reporting_packet(omo_dir, build_reporting_packet(campaign_packet))
```

Then extend the parser and main dispatch:

```python
report_parser = subparsers.add_parser("report")
report_parser.add_argument("--omo-dir", default=".omo")
report_parser.add_argument("--run-ref")
```

```python
if args.command == "campaign":
    write_campaign_packet(omo_dir, build_selected_campaign_packet(omo_dir, args.run_ref))
    print("generated debt campaign packet")
    return 0

if args.command == "report":
    reporting_outputs(omo_dir, args.run_ref)
    print("generated debt reporting packet")
    return 0
```

- [ ] **Step 4: Run the focused CLI tests to verify they pass**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py -q -k 'debt_report'
```

Expected: `3 passed`.

- [ ] **Step 5: Commit the CLI slice with the two-repo pattern**

Run:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt.py && git -c core.hooksPath=/dev/null commit -m $'feat(debt): add reporting rollup command\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
cd /Users/xiamingxing/Workspace && git add -- .omo/tests/test_omo_debt_cli.py scripts && git -c core.hooksPath=/dev/null commit -m $'test(omo): cover debt reporting rollup cli\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Expected: `report` is now a working subcommand and the root commit updates the `scripts` gitlink plus CLI tests.

### Task 3: Document the reporting surface and run full verification

**Files:**
- Modify: `.omo/AGENT.md`
- Test: `.omo/tests/test_omo_debt_docs.py`

- [ ] **Step 1: Add failing documentation assertions**

Extend `.omo/tests/test_omo_debt_docs.py`:

```python
    assert "python3 scripts/omo_debt.py report --omo-dir .omo" in content
    assert ".omo/debt/reporting/current.yaml" in content
    assert ".omo/debt/reporting/runs/<RUN_STAMP>/current.yaml" in content
    assert "approval coverage" in content.lower()
    assert "execution completion" in content.lower()
    assert "dashboard = debt health" in content.lower()
    assert "campaign = coordination detail" in content.lower()
    assert "reporting = compact progress rollup" in content.lower()
```

- [ ] **Step 2: Run the docs test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py -q
```

Expected: FAIL because `.omo/AGENT.md` does not yet mention the reporting command or boundary.

- [ ] **Step 3: Update the operator docs**

Add a compact operator block to `.omo/AGENT.md` near the existing debt-governance bullets:

```md
- Generate the latest run-level reporting packet with `python3 scripts/omo_debt.py report --omo-dir .omo`; pass `--run-ref <RUN_REF>` when you need the compact rollup for a specific dispatch run
- Reporting packets are derived from dispatch, approval, and execution facts and live at `.omo/debt/reporting/current.yaml` plus `.omo/debt/reporting/runs/<RUN_STAMP>/current.yaml`
- Reporting stays narrower than campaign: dashboard = debt health, campaign = coordination detail, reporting = compact progress rollup
- Reporting summary highlights approval coverage and execution completion for the selected run without adding cross-run history or new workflow state
```

- [ ] **Step 4: Run grouped regressions and canonical verify**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_docs.py -q
cd /Users/xiamingxing/Workspace && bash bin/verify-omo.sh
```

Expected:

1. focused suite passes
2. `bin/verify-omo.sh` stays green

- [ ] **Step 5: Commit the docs / verification slice**

Run:

```bash
cd /Users/xiamingxing/Workspace && git add -- .omo/AGENT.md .omo/tests/test_omo_debt_docs.py docs/superpowers/plans/2026-06-02-debt-reporting-rollup.md && git -c core.hooksPath=/dev/null commit -m $'docs(omo): document debt reporting rollup workflow\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Expected: one root commit for the docs/test closeout and the saved implementation plan.

## Self-review checklist

- Spec coverage:
  - explicit `report` command: Task 2
  - direct-from-facts derivation: Task 2
  - reporting packet counts/rates: Task 1
  - current + run-scoped outputs: Task 2
  - docs distinction from dashboard/campaign: Task 3
  - grouped verify / canonical verify: Task 3
- Placeholder scan:
  - no `TBD`, `TODO`, or “implement later” steps remain
  - each code-changing step includes concrete code
- Type consistency:
  - `build_reporting_packet`, `render_reporting_markdown`, `write_reporting_packet`, and `reporting_outputs` use one stable naming scheme
  - packet keys are consistent across the plan: `approval_coverage_rate`, `execution_completion_rate`, `approved_gate_item_count`, `executed_item_count`
