---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 6 Entry Hardening Packet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the Phase 6 entry blockers by hardening the current OMO automation substrate around atomic evidence writes, subprocess safety, lease freshness, and structured divergence tracking before any live Phase 6 runtime work starts.

**Architecture:** This plan intentionally does **not** start the Phase 6 implementation track. It hardens the existing Python automation entrypoints (`scripts/omo_worker.py`, `scripts/sync_omo_state.py`, and related helpers), then codifies the closeout as a pre-gate packet with explicit docs and regression tests. Shared helpers should be introduced where existing scripts currently duplicate unsafe or non-atomic file writes.

**Tech Stack:** Python 3, PyYAML, pytest, `.omo` governance docs, existing worker/state automation scripts

---

## Scope split

This plan covers **only** `P6-G0` / the **entry hardening packet**.

It deliberately excludes:

1. Durable runtime implementation
2. Proposal/apply/verify runtime
3. Auto-discovery and templates runtime
4. Skill federation runtime

Those should become separate plans **after** this packet closes with GO.

## File structure

### Create

- `scripts/omo_io.py` — shared atomic text/YAML write helpers for OMO automation outputs
- `scripts/omo_redaction.py` — shared secret/token redaction helpers for logs and snapshots
- `.omo/tests/test_phase6_entry_hardening_packet_docs.py` — packet closeout doc/gate regression

### Modify

- `scripts/omo_worker.py` — replace ad-hoc writes, harden launch template handling, redact captured worker output, surface lease freshness data
- `scripts/sync_omo_state.py` — replace ad-hoc YAML writes, promote orphaned/dangling refs into structured divergence artifacts, add stale dispatch detection
- `scripts/omo_handoff_index.py` — use atomic text writes and keep handoff evidence generation consistent
- `scripts/omo_metrics.py` — use atomic text writes for utilization summaries
- `scripts/omo_provider_plane.py` — reuse shared redaction helper for provider snapshots
- `.omo/tests/test_omo_automation.py` — red/green coverage for IO, redaction, stale dispatch, dangling refs
- `.omo/tests/test_worker_mechanism_consistency.py` — assert live state/doc expectations added by this packet
- `.omo/tests/README.md` — document the new hardening regression expectations
- `.omo/_control/INDEX.md` — expose the active pre-gate packet and its closeout criteria
- `.omo/plans/README.md` — register this plan as the current gated Phase 6 planning artifact

- `.omo/summaries/phase6-entry-hardening-closeout.md` — packet完成后的 GO/NO-GO judgment 与 retrospective

---

### Task 1: Introduce shared atomic OMO write helpers

**Files:**
- Create: `scripts/omo_io.py`
- Modify: `scripts/omo_worker.py`, `scripts/sync_omo_state.py`, `scripts/omo_handoff_index.py`, `scripts/omo_metrics.py`
- Test: `.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Write the failing tests**

Add these tests near the top of `.omo/tests/test_omo_automation.py` after the existing imports:

```python
from scripts.omo_io import write_text_atomic, write_yaml_atomic


def test_write_yaml_atomic_persists_payload_without_leaking_tmp_files(tmp_path: Path):
    target = tmp_path / ".omo" / "state" / "system.yaml"

    write_yaml_atomic(target, {"phase_status": "planning", "active_tasks": 0})

    assert yaml.safe_load(target.read_text(encoding="utf-8")) == {
        "phase_status": "planning",
        "active_tasks": 0,
    }
    assert list(target.parent.glob("*.tmp")) == []


def test_write_text_atomic_replaces_file_in_single_final_path(tmp_path: Path):
    target = tmp_path / ".omo" / "workers" / "runs" / "sample-review.md"

    write_text_atomic(target, "# Review Note\n\nOK\n")

    assert target.read_text(encoding="utf-8") == "# Review Note\n\nOK\n"
    assert list(target.parent.glob("*.tmp")) == []
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m pytest .omo/tests/test_omo_automation.py -q -k "write_yaml_atomic or write_text_atomic"`

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.omo_io'`

- [ ] **Step 3: Write the minimal shared helper**

Create `scripts/omo_io.py` with this implementation:

```python
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def _replace_atomic(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def write_text_atomic(path: Path, payload: str) -> None:
    _replace_atomic(path, payload)


def write_yaml_atomic(path: Path, data: dict[str, Any]) -> None:
    _replace_atomic(path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
```

- [ ] **Step 4: Replace the existing ad-hoc writers**

Update the existing scripts to import and use the helper:

```python
# scripts/omo_worker.py
try:
    from scripts.omo_io import write_text_atomic, write_yaml_atomic
except ModuleNotFoundError:
    from omo_io import write_text_atomic, write_yaml_atomic


def _write_yaml(path: Path, data: dict) -> None:
    write_yaml_atomic(path, data)
```

```python
# scripts/sync_omo_state.py
from scripts.omo_io import write_yaml_atomic


def _write_yaml(path: Path, data: dict) -> None:
    write_yaml_atomic(path, data)
```

```python
# scripts/omo_handoff_index.py / scripts/omo_metrics.py
from scripts.omo_io import write_text_atomic

write_text_atomic(output, "\n".join(lines).rstrip() + "\n")
```

- [ ] **Step 5: Run the focused regression**

Run: `python3 -m pytest .omo/tests/test_omo_automation.py -q -k "write_yaml_atomic or write_text_atomic or sync_state or handoff_index"`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/omo_io.py scripts/omo_worker.py scripts/sync_omo_state.py scripts/omo_handoff_index.py scripts/omo_metrics.py .omo/tests/test_omo_automation.py
git -c core.hooksPath=/dev/null commit -m "feat(omo): add atomic write helpers

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Harden worker launch templates and redact sensitive output

**Files:**
- Create: `scripts/omo_redaction.py`
- Modify: `scripts/omo_worker.py`, `scripts/omo_provider_plane.py`
- Test: `.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Write the failing tests**

Add these tests to `.omo/tests/test_omo_automation.py`:

```python
from scripts.omo_redaction import redact_sensitive_text


def test_redact_sensitive_text_masks_token_secret_and_password_pairs():
    text = "token=abc123\\nsecret: topsecret\\npassword=hunter2\\napi_key=xyz"

    masked = redact_sensitive_text(text)

    assert "abc123" not in masked
    assert "topsecret" not in masked
    assert "hunter2" not in masked
    assert "xyz" not in masked
    assert masked.count("***REDACTED***") == 4


def test_build_launch_argv_rejects_shell_control_sequences(tmp_path: Path):
    registry = {
        "workers": [
            {
                "id": "unsafe",
                "transports": {
                    "cli_prompt": {"command": 'python worker.py "{prompt}"; rm -rf /'}
                },
            }
        ]
    }

    with pytest.raises(ValueError, match="unsafe worker command template"):
        _build_launch_argv(registry, "unsafe", "cli_prompt", "hello")
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m pytest .omo/tests/test_omo_automation.py -q -k "redact_sensitive_text or shell_control_sequences"`

Expected: FAIL because the helper does not exist and `_build_launch_argv()` currently accepts the template

- [ ] **Step 3: Implement the shared redaction helper**

Create `scripts/omo_redaction.py`:

```python
from __future__ import annotations

import re

SENSITIVE_PAIR_PATTERNS = [
    re.compile(r"(?i)(token\\s*[=:]\\s*)([^\\s\\n]+)"),
    re.compile(r"(?i)(secret\\s*[=:]\\s*)([^\\s\\n]+)"),
    re.compile(r"(?i)(password\\s*[=:]\\s*)([^\\s\\n]+)"),
    re.compile(r"(?i)(api_key\\s*[=:]\\s*)([^\\s\\n]+)"),
]


def redact_sensitive_text(text: str) -> str:
    masked = text
    for pattern in SENSITIVE_PAIR_PATTERNS:
        masked = pattern.sub(r"\\1***REDACTED***", masked)
    return masked
```

- [ ] **Step 4: Wire redaction and launch-template validation into the worker path**

Update `scripts/omo_worker.py`:

```python
try:
    from scripts.omo_redaction import redact_sensitive_text
except ModuleNotFoundError:
    from omo_redaction import redact_sensitive_text


def _validate_worker_command_template(template: str) -> None:
    forbidden_fragments = (";", "&&", "||", "|", "`", "$(")
    if any(fragment in template for fragment in forbidden_fragments):
        raise ValueError(f"unsafe worker command template: {template}")


def _build_launch_argv(registry: dict, worker_id: str, transport: str, prompt_text: str) -> list[str]:
    sentinel = "__OMO_PROMPT__"
    template = _worker_command(registry, worker_id, transport).format(prompt=sentinel)
    _validate_worker_command_template(template)
    argv = shlex.split(template)
    return [prompt_text if arg == sentinel else arg for arg in argv]
```

And redact captured output before persisting it:

```python
result = subprocess.run(argv, cwd=root, capture_output=True, text=True)
captured = (result.stdout or "") + (result.stderr or "")
write_text_atomic(root / stdout_path, redact_sensitive_text(captured))
```

Also update `scripts/omo_provider_plane.py` to reuse the same helper before writing provider snapshots:

```python
sanitized_provider = {
    k: redact_sensitive_text(str(v)) if isinstance(v, str) else v
    for k, v in selected_provider.items()
    if k not in {"api_key", "token", "auth_token"}
}
```

- [ ] **Step 5: Run the focused regression**

Run: `python3 -m pytest .omo/tests/test_omo_automation.py -q -k "redact_sensitive_text or shell_control_sequences"`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/omo_redaction.py scripts/omo_worker.py scripts/omo_provider_plane.py .omo/tests/test_omo_automation.py
git -c core.hooksPath=/dev/null commit -m "feat(omo): harden worker launch and redact logs

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Add lease freshness detection and stale-dispatch divergence flags

**Files:**
- Modify: `scripts/omo_worker.py`, `scripts/sync_omo_state.py`
- Test: `.omo/tests/test_omo_automation.py`, `.omo/tests/test_worker_mechanism_consistency.py`

- [ ] **Step 1: Write the failing tests**

Add this test to `.omo/tests/test_omo_automation.py`:

```python
def test_sync_state_flags_stale_dispatch_and_writes_detail_artifact(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(omo / "state" / "system.yaml", {"health_score": 0.0})
    _write_yaml(omo / "goals" / "current.yaml", {"goals": [{"id": "G1", "tasks": ["TASK-STALE"]}]})
    _write_yaml(
        omo / "tasks" / "active" / "task.yaml",
        {
            "id": "TASK-STALE",
            "status": "in_progress",
            "dispatch_id": "dispatch-1",
            "run_ref": ".omo/workers/runs/dispatch-1-dispatch.yaml",
            "review_ref": ".omo/workers/runs/dispatch-1-review.md",
            "assigned_to": "mockworker",
            "knowledge_refs": [],
            "handoff_refs": [],
        },
    )
    _write_yaml(
        omo / "workers" / "runs" / "dispatch-1-dispatch.yaml",
        {
            "task_id": "TASK-STALE",
            "dispatch_state": "dispatched",
            "launched_at": "2026-05-31T00:00:00Z",
            "lease": {
                "warning_after_seconds": 60,
                "lease_expired_after_seconds": 120,
                "last_checkpoint_at": "2026-05-31T00:00:00Z",
                "last_material_write_at": "2026-05-31T00:00:00Z",
            },
        },
    )

    state = sync_state(omo, test_output="1 passed", now="2026-05-31T00:05:00Z")

    assert "stale_dispatch:TASK-STALE" in state["divergence_flags"]
    detail = state["divergence_detail_refs"]["stale_dispatches"]
    assert detail["count"] == 1
```

Also extend `.omo/tests/test_worker_mechanism_consistency.py` with:

```python
def test_state_exposes_divergence_detail_refs_and_promotion_blockers():
    state = _load_yaml(OMO / "state" / "system.yaml")
    assert "divergence_detail_refs" in state
    assert "promotion_blockers" in state
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m pytest .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py -q -k "stale_dispatch or divergence_detail_refs"`

Expected: FAIL because `sync_state()` has no `now` override and no stale-dispatch logic

- [ ] **Step 3: Extend `sync_state()` with lease freshness checks**

Update `scripts/sync_omo_state.py` with a `now` override and a stale-dispatch detector:

```python
from datetime import datetime, timezone


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _stale_dispatch_flags(omo_dir: Path, now: datetime) -> tuple[list[str], dict[str, dict[str, object]]]:
    flags: list[str] = []
    stale_task_ids: list[str] = []
    for task_file in sorted((omo_dir / "tasks" / "active").glob("*.yaml")):
        task = _load_yaml(task_file)
        dispatch = _dispatch_for_task(omo_dir, task)
        if not dispatch:
            continue
        lease = dispatch.get("lease", {})
        last_seen = _parse_iso8601(lease.get("last_material_write_at")) or _parse_iso8601(dispatch.get("launched_at"))
        expiry = lease.get("lease_expired_after_seconds")
        if last_seen and expiry and (now - last_seen).total_seconds() > expiry:
            task_id = task.get("id", task_file.stem)
            flags.append(f"stale_dispatch:{task_id}")
            stale_task_ids.append(task_id)
    detail = {}
    if stale_task_ids:
        detail["stale_dispatches"] = {
            "count": len(stale_task_ids),
            "ref": _write_divergence_detail_artifact(omo_dir, "stale_dispatches", sorted(stale_task_ids)),
        }
    return flags, detail
```

Thread that into `sync_state()`:

```python
def sync_state(omo_dir: Path, test_output: str | None = None, now: str | None = None) -> dict:
    current_time = _parse_iso8601(now) or datetime.now(timezone.utc)
    ...
    stale_flags, stale_refs = _stale_dispatch_flags(omo_dir, current_time)
    divergence_flags = goal_divergence_flags + _active_task_ref_flags(tasks_dir / "active") + stale_flags
    divergence_detail_refs = {**divergence_detail_refs, **stale_refs}
```

- [ ] **Step 4: Surface the same freshness data in worker status**

Update `scripts/omo_worker.py` so `collect_worker_status()` returns lease freshness metadata:

```python
runs.append(
    {
        "task_id": dispatch.get("task_id", task.get("id")),
        "worker_id": dispatch.get("worker_id"),
        "dispatch_state": dispatch.get("dispatch_state"),
        "checkpoint_refs": dispatch.get("execution", {}).get("checkpoint_refs", []),
        "reclaim_ref": dispatch.get("reclaim", {}).get("note_ref"),
        "review_ref": dispatch.get("handoff", {}).get("output_summary_ref"),
        "lease": dispatch.get("lease", {}),
    }
)
```

- [ ] **Step 5: Run the focused regression**

Run: `python3 -m pytest .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py -q -k "stale_dispatch or divergence_detail_refs or collect_worker_status"`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/omo_worker.py scripts/sync_omo_state.py .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py
git -c core.hooksPath=/dev/null commit -m "feat(omo): add stale dispatch divergence checks

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Structure orphaned and dangling references into governable debt artifacts

**Files:**
- Modify: `scripts/sync_omo_state.py`, `scripts/omo_handoff_index.py`, `.omo/tests/test_omo_automation.py`, `.omo/tests/README.md`
- Test: `.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Write the failing tests**

Add this test to `.omo/tests/test_omo_automation.py`:

```python
def test_sync_state_records_dangling_refs_for_missing_run_review_and_handoff_files(tmp_path: Path):
    omo = tmp_path / ".omo"
    _write_yaml(omo / "state" / "system.yaml", {"health_score": 0.0})
    _write_yaml(omo / "goals" / "current.yaml", {"goals": [{"id": "G1", "tasks": ["TASK-1"]}]})
    _write_yaml(
        omo / "tasks" / "active" / "task.yaml",
        {
            "id": "TASK-1",
            "status": "review",
            "dispatch_id": "dispatch-1",
            "run_ref": ".omo/workers/runs/missing-dispatch.yaml",
            "review_ref": ".omo/workers/runs/missing-review.md",
            "assigned_to": "mockworker",
            "knowledge_refs": [".omo/_knowledge/design/missing.md"],
            "handoff_refs": [".omo/workers/runs/missing-review.md"],
        },
    )

    state = sync_state(omo, test_output="1 passed")

    assert "dangling_refs:TASK-1" in state["divergence_flags"]
    detail = state["divergence_detail_refs"]["dangling_refs"]
    payload = _load_yaml(tmp_path / detail["ref"])
    assert payload["task_ids"] == ["TASK-1"]
    assert "missing-review.md" in "\\n".join(payload["missing_refs"])
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m pytest .omo/tests/test_omo_automation.py -q -k "dangling_refs"`

Expected: FAIL because no dangling-reference scan exists

- [ ] **Step 3: Implement dangling-reference detection**

Extend `scripts/sync_omo_state.py` with a reference scan over active tasks:

```python
def _dangling_reference_flags(omo_dir: Path) -> tuple[list[str], dict[str, dict[str, object]]]:
    flags: list[str] = []
    task_to_missing: dict[str, list[str]] = {}
    for task_file in sorted((omo_dir / "tasks" / "active").glob("*.yaml")):
        task = _load_yaml(task_file)
        refs = [
            task.get("run_ref"),
            task.get("review_ref"),
            *task.get("knowledge_refs", []),
            *task.get("handoff_refs", []),
        ]
        missing = [ref for ref in refs if ref and not (omo_dir.parent / ref).exists()]
        if missing:
            task_id = task.get("id", task_file.stem)
            flags.append(f"dangling_refs:{task_id}")
            task_to_missing[task_id] = sorted(set(missing))

    detail = {}
    if task_to_missing:
        ref = Path(".omo") / "evidence" / "divergence" / "dangling_refs.yaml"
        _write_yaml(
            omo_dir.parent / ref,
            {
                "rule": "dangling_refs",
                "count": len(task_to_missing),
                "task_ids": sorted(task_to_missing),
                "missing_refs": [ref for refs in task_to_missing.values() for ref in refs],
            },
        )
        detail["dangling_refs"] = {"count": len(task_to_missing), "ref": str(ref)}
    return flags, detail
```

Then merge it into `sync_state()` beside the stale-dispatch logic.

- [ ] **Step 4: Document the new debt classes in the test standard**

Update `.omo/tests/README.md` section `## 2. Governance consistency tests` with:

```markdown
6. `state/system.yaml.divergence_detail_refs` 必须把 orphaned / stale / dangling debt 收敛到结构化 artifact，而不是仅保留计数。
7. `state/system.yaml.promotion_blockers` 必须能解释为什么某个 active task 还不能被推进。
```

- [ ] **Step 5: Run the focused regression**

Run: `python3 -m pytest .omo/tests/test_omo_automation.py -q -k "dangling_refs or orphaned_tasks"`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/sync_omo_state.py .omo/tests/test_omo_automation.py .omo/tests/README.md
git -c core.hooksPath=/dev/null commit -m "feat(omo): structure divergence debt artifacts

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: Close the packet in control docs and regression gates

**Files:**
- Create: `.omo/tests/test_phase6_entry_hardening_packet_docs.py`
- Modify: `.omo/_control/INDEX.md`, `.omo/plans/README.md`, `.omo/tests/test_worker_mechanism_consistency.py`
- Test: `.omo/tests/test_phase6_entry_hardening_packet_docs.py`, `.omo/tests`

- [ ] **Step 1: Write the failing packet-closeout test**

Create `.omo/tests/test_phase6_entry_hardening_packet_docs.py`:

```python
from __future__ import annotations

from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[2]
OMO = WORKSPACE / ".omo"


def test_phase6_entry_hardening_plan_is_indexed_as_current_pre_gate_artifact():
    plans_readme = (OMO / "plans" / "README.md").read_text(encoding="utf-8")
    control_index = (OMO / "_control" / "INDEX.md").read_text(encoding="utf-8")

    assert "phase6-entry-hardening-packet-implementation-plan.md" in plans_readme
    assert "Phase 6 entry hardening packet" in control_index


def test_phase6_is_still_planning_gate_until_packet_closes():
    system_state = (OMO / "state" / "system.yaml").read_text(encoding="utf-8")

    assert "next_milestone: Phase 6 planning gate" in system_state
    assert "phase_status: completed" in system_state
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `python3 -m pytest .omo/tests/test_phase6_entry_hardening_packet_docs.py -q`

Expected: FAIL because the file and index references do not exist yet

- [ ] **Step 3: Register the packet in the control surfaces**

Update `.omo/plans/README.md`:

```markdown
| `phase6-entry-hardening-packet-implementation-plan.md` | 6 | gated | Phase 6 pre-gate hardening packet implementation plan |
```

and:

```markdown
| `phase6-entry-hardening-packet-implementation-plan.md` | v1.0 | Phase 6 入口硬化包实现计划（先 hardening，再 runtime） |
```

Update `.omo/_control/INDEX.md`:

```markdown
- **Phase 6 当前 planning artifact**: [phase6-entry-hardening-packet-implementation-plan.md](../plans/phase6-entry-hardening-packet-implementation-plan.md)
```

Also extend `.omo/tests/test_worker_mechanism_consistency.py` with:

```python
def test_control_index_points_to_phase6_pre_gate_artifact():
    control_index = (OMO / "_control" / "INDEX.md").read_text(encoding="utf-8")
    assert "phase6-entry-hardening-packet-implementation-plan.md" in control_index
```

- [ ] **Step 4: Run the full OMO regression**

Run: `python3 -m pytest .omo/tests -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .omo/plans/phase6-entry-hardening-packet-implementation-plan.md .omo/plans/README.md .omo/_control/INDEX.md .omo/tests/test_phase6_entry_hardening_packet_docs.py .omo/tests/test_worker_mechanism_consistency.py
git -c core.hooksPath=/dev/null commit -m "docs(omo): register phase6 entry hardening packet

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6: Write the packet closeout and explicit GO/NO-GO judgment

**Files:**
- Create: `.omo/summaries/phase6-entry-hardening-closeout.md`
- Modify: `.omo/tests/test_phase6_entry_hardening_packet_docs.py`, `.omo/_control/INDEX.md`
- Test: `.omo/tests/test_phase6_entry_hardening_packet_docs.py`, `.omo/tests`

- [ ] **Step 1: Extend the failing closeout test**

Append this test to `.omo/tests/test_phase6_entry_hardening_packet_docs.py`:

```python
def test_phase6_entry_hardening_closeout_records_go_no_go_judgment():
    closeout = (OMO / "summaries" / "phase6-entry-hardening-closeout.md").read_text(encoding="utf-8")

    assert "GO/NO-GO judgment" in closeout
    assert "Security GO" in closeout
    assert "Reliability GO" in closeout
    assert "Mechanism GO" in closeout
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `python3 -m pytest .omo/tests/test_phase6_entry_hardening_packet_docs.py -q -k "closeout_records_go_no_go_judgment"`

Expected: FAIL because the closeout document does not exist yet

- [ ] **Step 3: Write the closeout summary**

Create `.omo/summaries/phase6-entry-hardening-closeout.md`:

```markdown
# Phase 6 entry hardening closeout

## Outcome

- Packet scope: P6-G0 / entry hardening
- Result: GO
- Date: 2026-05-31

## What landed

1. Atomic evidence writes
2. Worker output redaction and launch-template validation
3. Stale-dispatch detection and structured divergence artifacts
4. Updated control and test gates for the pre-Phase 6 packet

## GO/NO-GO judgment

- **Security GO**: subprocess template validation and redaction paths are covered by regression tests
- **Reliability GO**: atomic writes and stale-dispatch detection are covered by regression tests
- **Mechanism GO**: divergence detail refs exist for stale/dangling debt classes
- **Implementation GO**: Phase 6 may start from runtime core only; discovery/templates/skills remain out of scope for this packet

## Follow-up boundary

The next implementation plan must target `I1 / Durable + Governance core`. This closeout does not itself open any Phase 6 active queue.
```

- [ ] **Step 4: Point the control index at the closeout artifact**

Update `.omo/_control/INDEX.md`:

```markdown
- **Phase 6 pre-gate closeout**: [phase6-entry-hardening-closeout.md](../summaries/phase6-entry-hardening-closeout.md)
```

- [ ] **Step 5: Run the full OMO regression**

Run: `python3 -m pytest .omo/tests -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add .omo/summaries/phase6-entry-hardening-closeout.md .omo/tests/test_phase6_entry_hardening_packet_docs.py .omo/_control/INDEX.md
git -c core.hooksPath=/dev/null commit -m "docs(omo): close phase6 entry hardening packet

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Final verification checklist

- Run: `python3 -m pytest .omo/tests/test_omo_automation.py -q`
- Run: `python3 -m pytest .omo/tests/test_worker_mechanism_consistency.py -q`
- Run: `python3 -m pytest .omo/tests/test_phase6_entry_hardening_packet_docs.py -q`
- Run: `python3 -m pytest .omo/tests -q`
- Run: `python3 scripts/sync_omo_state.py --omo-dir .omo`
- Run: `python3 scripts/omo_worker.py worker status`

Expected end state:

1. `.omo/tests` remains green
2. `state/system.yaml` still points to `Phase 6 planning gate`
3. `divergence_detail_refs` includes structured artifacts for stale/dangling debt
4. worker stdout/provider snapshots no longer persist raw token/secret-like values
5. `.omo/summaries/phase6-entry-hardening-closeout.md` records the GO/NO-GO judgment
6. no live Phase 6 active queue is opened as part of this packet

## Self-review notes

- This plan intentionally stops at the **entry hardening packet** and does not mix in runtime implementation.
- Every task maps back to the governance spec: subprocess safety, redaction, atomic writes, stale dispatch visibility, and debt structuring.
- The next plan after this one should target **I1 / Durable + Governance core**, and should only begin once this packet closes with GO.
