---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Debt Reporting Owner Diff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing `report-diff` surface so it emits deterministic owner-level diff output for shared owners and explicit added/removed owner lists while preserving the current summary diff and `no_prior_run` behavior.

**Architecture:** Keep the slice additive and derived. Reuse the existing `report-diff` command, history-based run selection, and fact re-derivation path; only the diff helper contract, Markdown renderer, tests, and operator docs should grow. Because `scripts/` is a nested git repo / gitlink and may already be dirty from unrelated work, any task that changes both `scripts/*` and root-repo files must use pathspec-limited two-repo commits without cleaning unrelated files.

**Tech Stack:** Python 3, PyYAML, pytest, existing `scripts/omo_debt_reporting.py` / `scripts/omo_debt_reporting_diff.py` helpers, `scripts/omo_debt.py` `report-diff` CLI, `.omo` governance docs/tests

---

## File structure map

- Modify: `scripts/omo_debt_reporting_diff.py`
  - Extend the diff helper so `diff_available` packets emit deterministic owner diff output keyed by `owner`, surface `added` / `removed` owners, and render owner sections in Markdown.
- Modify: `.omo/tests/test_omo_debt_reporting_diff.py`
  - Add focused unit coverage for by-owner matching, added/removed owner visibility, `no_prior_run`, and Markdown parity.
- Modify: `.omo/tests/test_omo_debt_cli.py`
  - Add CLI regressions that prove `report-diff` re-derives owner data from synthetic dispatch/approval/execution facts and does not depend on owner list order.
- Modify: `.omo/AGENT.md`
  - Update operator guidance from `owners: null` deferral to live owner diff semantics (`compared`, `added`, `removed`).
- Modify: `.omo/tests/test_omo_debt_docs.py`
  - Lock the updated owner diff workflow language.

## Implementation notes before starting

- Work from `/Users/xiamingxing/Workspace`.
- Do **not** clean or revert unrelated changes inside `scripts/`; pathspec every `git add` and commit.
- Keep the slice narrow:
  1. preserve `report-diff`
  2. preserve `summary_diff`
  3. compute metric deltas only for shared owners
  4. surface added/removed owners as name-only entries
  5. keep `owners: null` only for `no_prior_run`
  6. continue deferring burndown, trend analytics, and explicit run overrides
- Owner matching is a correctness rule, not a convenience:
  1. compare by `owner`
  2. never zip reporting owner lists by index
  3. sort output owner lists lexicographically by owner name

### Task 1: Build the owner diff packet model

**Files:**
- Modify: `scripts/omo_debt_reporting_diff.py`
- Modify: `.omo/tests/test_omo_debt_reporting_diff.py`
- Test: `.omo/tests/test_omo_debt_reporting_diff.py`

- [ ] **Step 1: Write the failing unit tests**

Update `.omo/tests/test_omo_debt_reporting_diff.py` so the packet fixture can carry owner rollups and add these tests:

```python
from __future__ import annotations

from scripts.omo_debt_reporting_diff import build_reporting_diff_packet, render_reporting_diff_markdown


def _owner_packet(
    owner: str,
    *,
    item_count: int,
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
        "owner": owner,
        "item_count": item_count,
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
    }


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
    owners: list[dict[str, object]] | None = None,
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
        "owners": owners or [],
    }


def test_build_reporting_diff_packet_matches_shared_owners_by_name() -> None:
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
        owners=[
            _owner_packet(
                "omo-governance",
                item_count=3,
                pending_approval=0,
                ready_to_execute=2,
                executed=1,
                gate_item_count=0,
                approved_gate_item_count=0,
                approval_coverage_rate=1.0,
                executed_item_count=1,
                execution_completion_rate=1 / 3,
            ),
            _owner_packet(
                "commerce-governance",
                item_count=2,
                pending_approval=0,
                ready_to_execute=2,
                executed=0,
                gate_item_count=1,
                approved_gate_item_count=1,
                approval_coverage_rate=1.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
        ],
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
        owners=[
            _owner_packet(
                "commerce-governance",
                item_count=1,
                pending_approval=1,
                ready_to_execute=0,
                executed=0,
                gate_item_count=1,
                approved_gate_item_count=0,
                approval_coverage_rate=0.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
            _owner_packet(
                "omo-governance",
                item_count=2,
                pending_approval=1,
                ready_to_execute=1,
                executed=0,
                gate_item_count=0,
                approved_gate_item_count=0,
                approval_coverage_rate=1.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
        ],
    )

    packet = build_reporting_diff_packet(
        generated_at="2026-06-12T01:00:00Z",
        latest_packet=latest,
        prior_packet=prior,
    )

    assert packet["diff_status"] == "diff_available"
    assert packet["owners"]["compared"][0]["owner"] == "commerce-governance"
    assert packet["owners"]["compared"][0]["item_count"] == {"latest": 2, "prior": 1, "delta": 1}
    assert packet["owners"]["compared"][1]["owner"] == "omo-governance"
    assert packet["owners"]["compared"][1]["executed_item_count"] == {"latest": 1, "prior": 0, "delta": 1}
    assert packet["owners"]["added"] == []
    assert packet["owners"]["removed"] == []


def test_build_reporting_diff_packet_surfaces_added_and_removed_owners() -> None:
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
        owners=[
            _owner_packet(
                "commerce-governance",
                item_count=2,
                pending_approval=0,
                ready_to_execute=2,
                executed=0,
                gate_item_count=1,
                approved_gate_item_count=1,
                approval_coverage_rate=1.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
            _owner_packet(
                "new-owner",
                item_count=1,
                pending_approval=0,
                ready_to_execute=1,
                executed=0,
                gate_item_count=0,
                approved_gate_item_count=0,
                approval_coverage_rate=1.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
        ],
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
        owners=[
            _owner_packet(
                "commerce-governance",
                item_count=1,
                pending_approval=1,
                ready_to_execute=0,
                executed=0,
                gate_item_count=1,
                approved_gate_item_count=0,
                approval_coverage_rate=0.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
            _owner_packet(
                "old-owner",
                item_count=2,
                pending_approval=1,
                ready_to_execute=1,
                executed=0,
                gate_item_count=0,
                approved_gate_item_count=0,
                approval_coverage_rate=1.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
        ],
    )

    packet = build_reporting_diff_packet(
        generated_at="2026-06-12T01:00:00Z",
        latest_packet=latest,
        prior_packet=prior,
    )

    assert [entry["owner"] for entry in packet["owners"]["compared"]] == ["commerce-governance"]
    assert packet["owners"]["added"] == [{"owner": "new-owner"}]
    assert packet["owners"]["removed"] == [{"owner": "old-owner"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_diff.py -q
```

Expected:

```text
FAIL ... KeyError / TypeError / AssertionError because build_reporting_diff_packet() still returns owners=None for diff_available packets
```

- [ ] **Step 3: Write the minimal implementation**

Update `scripts/omo_debt_reporting_diff.py` with deterministic owner diff helpers and hook them into `build_reporting_diff_packet(...)`:

```python
def _owner_diff_entry(
    owner: str,
    latest_owner: dict[str, object],
    prior_owner: dict[str, object],
) -> dict[str, object]:
    prior_state_counts = prior_owner["state_counts"]
    latest_state_counts = latest_owner["state_counts"]
    return {
        "owner": owner,
        "item_count": _delta_metric(int(latest_owner["item_count"]), int(prior_owner["item_count"])),
        "state_counts": {
            "pending_approval": _delta_metric(
                int(latest_state_counts["pending_approval"]),
                int(prior_state_counts["pending_approval"]),
            ),
            "ready_to_execute": _delta_metric(
                int(latest_state_counts["ready_to_execute"]),
                int(prior_state_counts["ready_to_execute"]),
            ),
            "executed": _delta_metric(
                int(latest_state_counts["executed"]),
                int(prior_state_counts["executed"]),
            ),
        },
        "gate_item_count": _delta_metric(int(latest_owner["gate_item_count"]), int(prior_owner["gate_item_count"])),
        "approved_gate_item_count": _delta_metric(
            int(latest_owner["approved_gate_item_count"]),
            int(prior_owner["approved_gate_item_count"]),
        ),
        "approval_coverage_rate": _delta_metric(
            float(latest_owner["approval_coverage_rate"]),
            float(prior_owner["approval_coverage_rate"]),
        ),
        "executed_item_count": _delta_metric(
            int(latest_owner["executed_item_count"]),
            int(prior_owner["executed_item_count"]),
        ),
        "execution_completion_rate": _delta_metric(
            float(latest_owner["execution_completion_rate"]),
            float(prior_owner["execution_completion_rate"]),
        ),
    }


def _owners_diff(
    latest_owners: list[dict[str, object]],
    prior_owners: list[dict[str, object]],
) -> dict[str, object]:
    latest_by_owner = {str(owner["owner"]): owner for owner in latest_owners}
    prior_by_owner = {str(owner["owner"]): owner for owner in prior_owners}
    shared_names = sorted(latest_by_owner.keys() & prior_by_owner.keys())
    added_names = sorted(latest_by_owner.keys() - prior_by_owner.keys())
    removed_names = sorted(prior_by_owner.keys() - latest_by_owner.keys())
    return {
        "compared": [
            _owner_diff_entry(owner, latest_by_owner[owner], prior_by_owner[owner])
            for owner in shared_names
        ],
        "added": [{"owner": owner} for owner in added_names],
        "removed": [{"owner": owner} for owner in removed_names],
    }


def build_reporting_diff_packet(
    *,
    generated_at: str,
    latest_packet: dict[str, object],
    prior_packet: dict[str, object] | None,
) -> dict[str, object]:
    latest_summary = latest_packet["summary"]
    prior_summary = prior_packet["summary"] if prior_packet else None
    owners = None if prior_packet is None else _owners_diff(latest_packet["owners"], prior_packet["owners"])
    return {
        "generated_at": generated_at,
        "diff_status": "diff_available" if prior_packet else "no_prior_run",
        "latest_run_stamp": latest_packet["run_stamp"],
        "prior_run_stamp": prior_packet["run_stamp"] if prior_packet else None,
        "latest_dispatch_run_ref": latest_packet["dispatch_run_ref"],
        "prior_dispatch_run_ref": prior_packet["dispatch_run_ref"] if prior_packet else None,
        "summary_diff": _summary_diff(latest_summary, prior_summary),
        "owners": owners,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_diff.py -q
```

Expected:

```text
...                                                                    [100%]
all tests in .omo/tests/test_omo_debt_reporting_diff.py pass
```

- [ ] **Step 5: Commit**

Use the required two-repo commit flow:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_reporting_diff.py && git -c core.hooksPath=/dev/null commit -m "feat(debt): add owner diff packet model" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
cd /Users/xiamingxing/Workspace && git add scripts .omo/tests/test_omo_debt_reporting_diff.py && git -c core.hooksPath=/dev/null commit -m "test(omo): cover owner diff packet model" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 2: Render owner diff output and prove the CLI path

**Files:**
- Modify: `scripts/omo_debt_reporting_diff.py`
- Modify: `.omo/tests/test_omo_debt_reporting_diff.py`
- Modify: `.omo/tests/test_omo_debt_cli.py`
- Test: `.omo/tests/test_omo_debt_reporting_diff.py`
- Test: `.omo/tests/test_omo_debt_cli.py`

- [ ] **Step 1: Write the failing Markdown and CLI regressions**

Add a Markdown-focused unit test to `.omo/tests/test_omo_debt_reporting_diff.py`:

```python
def test_render_reporting_diff_markdown_shows_owner_sections() -> None:
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
        owners=[
            _owner_packet(
                "commerce-governance",
                item_count=2,
                pending_approval=0,
                ready_to_execute=2,
                executed=0,
                gate_item_count=1,
                approved_gate_item_count=1,
                approval_coverage_rate=1.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
            _owner_packet(
                "new-owner",
                item_count=1,
                pending_approval=0,
                ready_to_execute=1,
                executed=0,
                gate_item_count=0,
                approved_gate_item_count=0,
                approval_coverage_rate=1.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
        ],
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
        owners=[
            _owner_packet(
                "commerce-governance",
                item_count=1,
                pending_approval=1,
                ready_to_execute=0,
                executed=0,
                gate_item_count=1,
                approved_gate_item_count=0,
                approval_coverage_rate=0.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
            _owner_packet(
                "old-owner",
                item_count=2,
                pending_approval=1,
                ready_to_execute=1,
                executed=0,
                gate_item_count=0,
                approved_gate_item_count=0,
                approval_coverage_rate=1.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
        ],
    )

    markdown = render_reporting_diff_markdown(
        build_reporting_diff_packet(
            generated_at="2026-06-12T01:00:00Z",
            latest_packet=latest,
            prior_packet=prior,
        )
    )

    assert "## Owner Diff" in markdown
    assert "### Shared owners" in markdown
    assert "#### commerce-governance" in markdown
    assert "- item_count: latest=2, prior=1, delta=1" in markdown
    assert "- pending_approval: latest=0, prior=1, delta=-1" in markdown
    assert "- ready_to_execute: latest=2, prior=0, delta=2" in markdown
    assert "- executed: latest=0, prior=0, delta=0" in markdown
    assert "- gate_item_count: latest=1, prior=1, delta=0" in markdown
    assert "- approved_gate_item_count: latest=1, prior=0, delta=1" in markdown
    assert "- approval_coverage_rate: latest=1.0, prior=0.0, delta=1.0" in markdown
    assert "- executed_item_count: latest=0, prior=0, delta=0" in markdown
    assert "- execution_completion_rate: latest=0.0, prior=0.0, delta=0.0" in markdown
    assert "### Added owners" in markdown
    assert "- `new-owner`" in markdown
    assert "### Removed owners" in markdown
    assert "- `old-owner`" in markdown
```

Add this CLI regression to `.omo/tests/test_omo_debt_cli.py`:

```python
def test_debt_report_diff_writes_owner_diff_from_rederived_run_facts(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    latest_run = tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-10T00-00-00Z.yaml"
    prior_run = tmp_path / ".omo" / "debt" / "dispatch" / "runs" / "2026-06-01T00-00-00Z.yaml"
    prior_payload = yaml.safe_load(latest_run.read_text(encoding="utf-8"))
    prior_payload["dispatched_at"] = "2026-06-01T00:00:00Z"
    prior_payload["latest_run_ref"] = ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml"
    removed_owner = prior_payload["owners"][3]
    removed_owner["owner"] = "retired-governance"
    for entry in removed_owner["entries"]:
        entry["owner"] = "retired-governance"
    prior_payload["owners"] = [
        removed_owner,
        prior_payload["owners"][1],
        prior_payload["owners"][0],
    ]
    prior_payload["owners"][0]["entries"] = prior_payload["owners"][0]["entries"][:2]
    prior_payload["owners"][1]["entries"] = prior_payload["owners"][1]["entries"][:1]
    prior_payload["owners"][2]["entries"] = prior_payload["owners"][2]["entries"][:3]
    prior_run.write_text(yaml.safe_dump(prior_payload, sort_keys=False, allow_unicode=True), encoding="utf-8")

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
                        "report_generated_at": "2026-06-10T00:00:00Z",
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
                        "report_generated_at": "2026-06-01T00:00:00Z",
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
    assert [entry["owner"] for entry in packet["owners"]["compared"]] == [
        "commerce-governance",
        "omo-governance",
        "sharedbrain-governance",
    ]
    assert packet["owners"]["compared"][0]["item_count"]["delta"] == 0
    assert packet["owners"]["compared"][1]["item_count"]["delta"] == 1
    assert packet["owners"]["compared"][2]["item_count"]["delta"] == 1
    assert packet["owners"]["added"] == [{"owner": "platform-governance"}]
    assert packet["owners"]["removed"] == [{"owner": "retired-governance"}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_diff.py .omo/tests/test_omo_debt_cli.py -q -k 'reporting_diff or debt_report_diff'
```

Expected:

```text
FAIL ... because render_reporting_diff_markdown() does not emit owner sections yet and the CLI packet does not contain owners.compared / owners.added / owners.removed
```

- [ ] **Step 3: Write the minimal implementation**

Extend `render_reporting_diff_markdown(...)` in `scripts/omo_debt_reporting_diff.py` so the Markdown output stays in sync with the YAML packet:

```python
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
    if packet["owners"] is not None:
        lines.extend(["", "## Owner Diff", "", "### Shared owners", ""])
        compared = packet["owners"]["compared"]
        if compared:
            for owner in compared:
                lines.extend(
                    [
                        f"#### {owner['owner']}",
                        "",
                        f"- item_count: latest={owner['item_count']['latest']}, prior={owner['item_count']['prior']}, delta={owner['item_count']['delta']}",
                        f"- pending_approval: latest={owner['state_counts']['pending_approval']['latest']}, prior={owner['state_counts']['pending_approval']['prior']}, delta={owner['state_counts']['pending_approval']['delta']}",
                        f"- ready_to_execute: latest={owner['state_counts']['ready_to_execute']['latest']}, prior={owner['state_counts']['ready_to_execute']['prior']}, delta={owner['state_counts']['ready_to_execute']['delta']}",
                        f"- executed: latest={owner['state_counts']['executed']['latest']}, prior={owner['state_counts']['executed']['prior']}, delta={owner['state_counts']['executed']['delta']}",
                        f"- gate_item_count: latest={owner['gate_item_count']['latest']}, prior={owner['gate_item_count']['prior']}, delta={owner['gate_item_count']['delta']}",
                        f"- approved_gate_item_count: latest={owner['approved_gate_item_count']['latest']}, prior={owner['approved_gate_item_count']['prior']}, delta={owner['approved_gate_item_count']['delta']}",
                        f"- approval_coverage_rate: latest={owner['approval_coverage_rate']['latest']}, prior={owner['approval_coverage_rate']['prior']}, delta={owner['approval_coverage_rate']['delta']}",
                        f"- executed_item_count: latest={owner['executed_item_count']['latest']}, prior={owner['executed_item_count']['prior']}, delta={owner['executed_item_count']['delta']}",
                        f"- execution_completion_rate: latest={owner['execution_completion_rate']['latest']}, prior={owner['execution_completion_rate']['prior']}, delta={owner['execution_completion_rate']['delta']}",
                        "",
                    ]
                )
        else:
            lines.append("- none")
        if packet["owners"]["added"]:
            lines.extend(["", "### Added owners", ""])
            lines.extend([f"- `{entry['owner']}`" for entry in packet["owners"]["added"]])
        if packet["owners"]["removed"]:
            lines.extend(["", "### Removed owners", ""])
            lines.extend([f"- `{entry['owner']}`" for entry in packet["owners"]["removed"]])
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_diff.py .omo/tests/test_omo_debt_cli.py -q -k 'reporting_diff or debt_report_diff'
```

Expected:

```text
.....                                                                  [100%]
all selected reporting_diff / debt_report_diff tests pass
```

- [ ] **Step 5: Commit**

Use the required two-repo commit flow:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_reporting_diff.py && git -c core.hooksPath=/dev/null commit -m "feat(debt): render owner diff output" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
cd /Users/xiamingxing/Workspace && git add scripts .omo/tests/test_omo_debt_reporting_diff.py .omo/tests/test_omo_debt_cli.py && git -c core.hooksPath=/dev/null commit -m "test(omo): cover debt owner diff cli" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 3: Update docs and run canonical verification

**Files:**
- Modify: `.omo/AGENT.md`
- Modify: `.omo/tests/test_omo_debt_docs.py`
- Test: `.omo/tests/test_omo_debt_docs.py`
- Test: `.omo/tests/test_omo_debt_reporting_diff.py`
- Test: `.omo/tests/test_omo_debt_cli.py`

- [ ] **Step 1: Write the failing docs regression**

Update `.omo/tests/test_omo_debt_docs.py` by replacing the old summary-only assertion and adding the new owner diff expectations:

```python
assert "owners: null" not in content.lower()
assert "owners.compared" in content
assert "owners.added" in content
assert "owners.removed" in content
assert "shared owners" in content.lower()
assert "added owners" in content.lower()
assert "removed owners" in content.lower()
assert "no_prior_run" in content
assert "burndown" in content.lower()
```

- [ ] **Step 2: Run the docs test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py -q -k omo_agent_documents_debt_refresh_flow
```

Expected:

```text
FAIL ... because .omo/AGENT.md still documents owners: null and does not describe owners.compared / owners.added / owners.removed
```

- [ ] **Step 3: Update the operator guide**

Edit `.omo/AGENT.md` so the debt reporting section says this explicitly:

```markdown
- Generate the latest-vs-prior diff with `python3 scripts/omo_debt.py report-diff --omo-dir .omo`
- Reporting diff lives at `.omo/debt/reporting/diff/current.yaml` plus `.omo/debt/reporting/diff/current.md`
- `report-diff` uses `reporting/history/current.yaml` only to select the latest/prior run pair, then re-derives both runs from dispatch, approval, and execution facts before comparing them
- If only one run exists, `report-diff` writes a valid `no_prior_run` packet instead of failing
- When a prior run exists, `summary_diff` stays compact and `owners` expands into `owners.compared`, `owners.added`, and `owners.removed`
- `owners.compared` covers shared owners only; added and removed owners are surfaced explicitly instead of being silently dropped
- Burndown and wider trend analytics remain deferred
```

- [ ] **Step 4: Run focused and canonical verification**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_reporting_diff.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_docs.py -q -k 'reporting_diff or debt_report_diff or omo_agent_documents_debt_refresh_flow'
cd /Users/xiamingxing/Workspace && bash bin/verify-omo.sh
```

Expected:

```text
.......                                                                [100%]
all selected reporting_diff / debt_report_diff / docs tests pass
...
<canonical verify passes; full suite count increases from the current baseline>
```

- [ ] **Step 5: Commit**

```bash
cd /Users/xiamingxing/Workspace && git add .omo/AGENT.md .omo/tests/test_omo_debt_docs.py && git -c core.hooksPath=/dev/null commit -m "docs(omo): document debt owner diff surface" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
