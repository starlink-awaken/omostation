---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# OMO Promotion History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a canonical promotion history/current surface so OMO can read promotion facts from one stable derived packet instead of raw globbing under `.omo/workers/runs/`.

**Architecture:** Add a small pure helper layer in `scripts/omo_promotion_history.py` that scans immutable `*-promotion-*.yaml` envelopes, validates them, sorts them newest-to-oldest, and renders `.omo/workers/promotion/current.yaml` plus `.md`. Keep the user-facing entrypoint in `scripts/omo_worker.py task promotion-history`, and hydrate the live surface from the existing ORPHANED rehearsal envelope once the command is in place.

**Tech Stack:** Python 3, `pathlib`, `yaml`, existing `scripts/omo_io.py` atomic writers, `argparse`, pytest under `.omo/tests`, `.omo` YAML SSOT files

---

## File map

- **Create:** `scripts/omo_promotion_history.py`
  - Pure helper layer for scanning promotion envelopes, validating compact history input, sorting entries, and rendering YAML/Markdown output.
- **Modify:** `scripts/omo_worker.py`
  - Add `task promotion-history --omo-dir .omo` and wire it to the helper.
- **Create:** `.omo/tests/test_omo_promotion_history.py`
  - Focused helper tests for empty history, sort order, and fail-closed malformed input.
- **Modify:** `.omo/tests/test_omo_automation.py`
  - Add CLI regression coverage for `task promotion-history`.
- **Modify:** `.omo/tests/test_worker_mechanism_consistency.py`
  - Add docs regression so the new promotion history surface stays documented.
- **Modify:** `.omo/workers/README.md`
  - Document the new history/current surface and command.
- **Modify:** `.omo/AGENT.md`
  - Document where operators should read promotion history facts.
- **Create:** `.omo/workers/promotion/current.yaml`
  - Canonical derived promotion history surface hydrated from the existing ORPHANED rehearsal envelope.
- **Create:** `.omo/workers/promotion/current.md`
  - Human-readable summary of the same derived surface.

---

### Task 1: Build the promotion history helper

**Files:**
- Create: `scripts/omo_promotion_history.py`
- Test: `.omo/tests/test_omo_promotion_history.py`

- [ ] **Step 1: Write the failing helper tests**

Create `.omo/tests/test_omo_promotion_history.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.omo_promotion_history import build_promotion_history


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_build_promotion_history_returns_empty_surface_when_no_promotions_exist(tmp_path: Path):
    result = build_promotion_history(tmp_path, omo_dir=".omo", now="2026-06-03T00:00:00Z")

    assert result["yaml"]["promotion_count"] == 0
    assert result["yaml"]["latest_promotion_id"] is None
    assert result["yaml"]["promotions"] == []
    assert "Latest promotion: none" in result["markdown"]


def test_build_promotion_history_sorts_promotions_newest_first(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "TASK-A-promotion-2026-06-02T00-00-00Z.yaml",
        {
            "promotion_id": "TASK-A-promotion-2026-06-02T00-00-00Z",
            "task_id": "TASK-A",
            "promoted_at": "2026-06-02T00:00:00Z",
            "promoted_by": "copilot-cli",
            "task_ref_before": ".omo/tasks/planned/TASK-A.yaml",
            "task_ref_after": ".omo/tasks/active/TASK-A.yaml",
            "approval": {"required": False, "approval_ref": None},
            "phase_gate": {"target_phase": 17},
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "TASK-B-promotion-2026-06-03T00-00-00Z.yaml",
        {
            "promotion_id": "TASK-B-promotion-2026-06-03T00-00-00Z",
            "task_id": "TASK-B",
            "promoted_at": "2026-06-03T00:00:00Z",
            "promoted_by": "copilot-cli",
            "task_ref_before": ".omo/tasks/planned/TASK-B.yaml",
            "task_ref_after": ".omo/tasks/active/TASK-B.yaml",
            "approval": {"required": False, "approval_ref": None},
            "phase_gate": {"target_phase": 17},
        },
    )

    result = build_promotion_history(tmp_path, omo_dir=".omo", now="2026-06-03T00:10:00Z")

    assert result["yaml"]["latest_promotion_id"] == "TASK-B-promotion-2026-06-03T00-00-00Z"
    assert result["yaml"]["prior_promotion_id"] == "TASK-A-promotion-2026-06-02T00-00-00Z"
    assert [entry["task_id"] for entry in result["yaml"]["promotions"]] == ["TASK-B", "TASK-A"]


def test_build_promotion_history_rejects_missing_required_fields(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "BROKEN-promotion-2026-06-03T00-00-00Z.yaml",
        {
            "promotion_id": "BROKEN-promotion-2026-06-03T00-00-00Z",
            "task_id": "BROKEN",
            "promoted_at": "2026-06-03T00:00:00Z",
        },
    )

    with pytest.raises(ValueError, match="missing required promotion field"):
        build_promotion_history(tmp_path, omo_dir=".omo", now="2026-06-03T00:00:00Z")
```

- [ ] **Step 2: Run the focused helper tests to confirm RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_promotion_history.py -q
```

Expected: import failure because `scripts/omo_promotion_history.py` does not exist yet.

- [ ] **Step 3: Write the minimal helper implementation**

Create `scripts/omo_promotion_history.py`:

```python
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _parse_iso8601(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _history_entry(omo_ref: Path, envelope_path: Path) -> dict[str, object]:
    envelope = _load_yaml(envelope_path)
    required_paths = [
        ("promotion_id", envelope.get("promotion_id")),
        ("task_id", envelope.get("task_id")),
        ("promoted_at", envelope.get("promoted_at")),
        ("promoted_by", envelope.get("promoted_by")),
        ("task_ref_before", envelope.get("task_ref_before")),
        ("task_ref_after", envelope.get("task_ref_after")),
        ("approval.required", envelope.get("approval", {}).get("required")),
        ("phase_gate.target_phase", envelope.get("phase_gate", {}).get("target_phase")),
    ]
    for field_name, field_value in required_paths:
        if field_value is None:
            raise ValueError(f"missing required promotion field: {field_name}")

    return {
        "promotion_id": envelope["promotion_id"],
        "promotion_ref": str(omo_ref / "workers" / "runs" / envelope_path.name),
        "task_id": envelope["task_id"],
        "promoted_at": envelope["promoted_at"],
        "promoted_by": envelope["promoted_by"],
        "task_ref_before": envelope["task_ref_before"],
        "task_ref_after": envelope["task_ref_after"],
        "approval_required": envelope["approval"]["required"],
        "approval_ref": envelope.get("approval", {}).get("approval_ref"),
        "target_phase": envelope["phase_gate"]["target_phase"],
    }


def build_promotion_history(root: Path, omo_dir: str | Path = ".omo", now: str = "2026-06-03T00:00:00Z") -> dict[str, object]:
    omo_ref = Path(omo_dir)
    runs_dir = root / omo_ref / "workers" / "runs"
    entries = [_history_entry(omo_ref, path) for path in sorted(runs_dir.glob("*-promotion-*.yaml"))]
    entries.sort(key=lambda item: _parse_iso8601(item["promoted_at"]), reverse=True)

    latest = entries[0] if entries else None
    prior = entries[1] if len(entries) > 1 else None
    yaml_packet = {
        "generated_at": now,
        "latest_promotion_id": latest["promotion_id"] if latest else None,
        "latest_promotion_ref": latest["promotion_ref"] if latest else None,
        "prior_promotion_id": prior["promotion_id"] if prior else None,
        "prior_promotion_ref": prior["promotion_ref"] if prior else None,
        "promotion_count": len(entries),
        "promotions": entries,
    }
    markdown_lines = [
        "# Task Promotion History",
        "",
        f"Generated at: {now}",
        f"Latest promotion: {yaml_packet['latest_promotion_id'] or 'none'}",
        f"Prior promotion: {yaml_packet['prior_promotion_id'] or 'none'}",
    ]
    for entry in entries:
        markdown_lines.extend(
            [
                "",
                f"## Promotion: {entry['promotion_id']}",
                "",
                f"task_id={entry['task_id']}",
                f"promotion_ref={entry['promotion_ref']}",
                f"task_ref_after={entry['task_ref_after']}",
                f"approval_required={'yes' if entry['approval_required'] else 'no'}",
                f"target_phase={entry['target_phase']}",
            ]
        )

    return {"yaml": yaml_packet, "markdown": "\n".join(markdown_lines) + "\n"}
```

- [ ] **Step 4: Re-run the helper tests to confirm GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_promotion_history.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit the helper slice**

Commit in `scripts/` first, then in the root repo:

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_promotion_history.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion history helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

cd /Users/xiamingxing/Workspace && \
git add scripts .omo/tests/test_omo_promotion_history.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion history helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one `scripts` commit plus one root commit limited to the helper slice.

---

### Task 2: Add the CLI materializer and docs guardrails

**Files:**
- Modify: `scripts/omo_worker.py`
- Modify: `.omo/tests/test_omo_automation.py`
- Modify: `.omo/tests/test_worker_mechanism_consistency.py`
- Modify: `.omo/workers/README.md`
- Modify: `.omo/AGENT.md`

- [ ] **Step 1: Write the failing CLI and docs tests**

Add a CLI regression to `.omo/tests/test_omo_automation.py`:

```python
def test_task_promotion_history_command_writes_current_surfaces(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "TASK-A-promotion-2026-06-03T00-00-00Z.yaml",
        {
            "promotion_id": "TASK-A-promotion-2026-06-03T00-00-00Z",
            "task_id": "TASK-A",
            "promoted_at": "2026-06-03T00:00:00Z",
            "promoted_by": "copilot-cli",
            "task_ref_before": ".omo/tasks/planned/TASK-A.yaml",
            "task_ref_after": ".omo/tasks/active/TASK-A.yaml",
            "approval": {"required": False, "approval_ref": None},
            "phase_gate": {"target_phase": 17},
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "promotion-history", "--omo-dir", ".omo"],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    assert "promotion_count=1" in output
    assert (tmp_path / ".omo" / "workers" / "promotion" / "current.yaml").exists()
    assert (tmp_path / ".omo" / "workers" / "promotion" / "current.md").exists()
```

Add a docs regression to `.omo/tests/test_worker_mechanism_consistency.py`:

```python
def test_worker_docs_describe_promotion_history_surface():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "AGENT.md").read_text(encoding="utf-8")

    assert "promotion-history" in workers_text
    assert ".omo/workers/promotion/current.yaml" in workers_text
    assert "promotion/current.yaml" in agent_text
```

- [ ] **Step 2: Run the focused CLI/docs tests to confirm RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py -q -k 'promotion_history_command or promotion_history_surface'
```

Expected: failures because the new CLI subcommand and docs do not exist yet.

- [ ] **Step 3: Wire the CLI and update docs**

Extend `scripts/omo_worker.py`:

```python
try:
    from scripts.omo_promotion_history import build_promotion_history
except ModuleNotFoundError:
    from omo_promotion_history import build_promotion_history


def _write_task_promotion_history(root: Path, omo_dir: str | Path = ".omo") -> int:
    result = build_promotion_history(root, omo_dir=omo_dir, now=_utc_now())
    omo = _omo_path(root, omo_dir)
    current_yaml = omo / "workers" / "promotion" / "current.yaml"
    current_md = omo / "workers" / "promotion" / "current.md"
    _write_yaml(current_yaml, result["yaml"])
    write_text_atomic(current_md, result["markdown"])
    print(
        f"promotion_count={result['yaml']['promotion_count']} "
        f"latest_promotion_ref={result['yaml']['latest_promotion_ref']}"
    )
    return 0
```

Add parser + dispatch:

```python
promotion_history_parser = task_sub.add_parser("promotion-history")
promotion_history_parser.add_argument("--omo-dir", default=".omo")

if args.command == "task" and args.task_command == "promotion-history":
    return _write_task_promotion_history(Path.cwd(), omo_dir=args.omo_dir)
```

Update docs:

```md
<!-- .omo/workers/README.md -->
Generate the canonical promotion history surface:

- `python3 scripts/omo_worker.py task promotion-history --omo-dir .omo`

This writes:

1. `.omo/workers/promotion/current.yaml`
2. `.omo/workers/promotion/current.md`
```

```md
<!-- .omo/AGENT.md -->
如需查看最近有哪些 planned packet 被正式晋升，不要直接 glob `workers/runs/*-promotion-*.yaml`；先运行 `python3 scripts/omo_worker.py task promotion-history --omo-dir .omo`，再以 `.omo/workers/promotion/current.yaml` 作为 canonical read surface。
```

- [ ] **Step 4: Re-run the focused CLI/docs tests to confirm GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py -q -k 'promotion_history_command or promotion_history_surface'
```

Expected: `2 passed`.

- [ ] **Step 5: Commit the CLI/docs slice**

Commit `scripts/` first, then the root repo:

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_worker.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion history command" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

cd /Users/xiamingxing/Workspace && \
git add scripts .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py .omo/workers/README.md .omo/AGENT.md && \
git -c core.hooksPath=/dev/null commit -m "docs(omo): document promotion history surface" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: the subcommand lands in `scripts/`, and the root commit captures tests/docs plus the gitlink.

---

### Task 3: Hydrate the live promotion history packet

**Files:**
- Create: `.omo/workers/promotion/current.yaml`
- Create: `.omo/workers/promotion/current.md`

- [ ] **Step 1: Run the real materializer against the ORPHANED promotion envelope**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 scripts/omo_worker.py task promotion-history --omo-dir .omo
```

Expected output includes:

```text
promotion_count=1
latest_promotion_ref=.omo/workers/runs/ORPHANED-TASKS-STRUCTURED-REGISTRY-promotion-2026-06-03T00-00-00Z.yaml
```

- [ ] **Step 2: Inspect the generated current surfaces**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 - <<'PY'
import yaml
from pathlib import Path

packet = yaml.safe_load(Path(".omo/workers/promotion/current.yaml").read_text())
markdown = Path(".omo/workers/promotion/current.md").read_text()

assert packet["promotion_count"] == 1
assert packet["latest_promotion_id"] == "ORPHANED-TASKS-STRUCTURED-REGISTRY-promotion-2026-06-03T00-00-00Z"
assert packet["promotions"][0]["task_id"] == "ORPHANED-TASKS-STRUCTURED-REGISTRY"
assert "Latest promotion: ORPHANED-TASKS-STRUCTURED-REGISTRY-promotion-2026-06-03T00-00-00Z" in markdown
print("promotion history surface verified")
PY
```

Expected: prints `promotion history surface verified`.

- [ ] **Step 3: Run focused verification plus canonical `.omo` verify**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest .omo/tests/test_omo_promotion_history.py .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py -q -k 'promotion_history or promotion_history_surface' && \
python3 scripts/omo_worker.py task promotion-history --omo-dir .omo && \
python3 scripts/omo_worker.py task validate --all-planned && \
bash bin/verify-omo.sh
```

Expected:

1. promotion-history focused tests pass
2. live materializer re-runs cleanly
3. planned validator passes
4. canonical verify passes

- [ ] **Step 4: Commit the hydrated live surface**

Commit in the root repo:

```bash
cd /Users/xiamingxing/Workspace && \
git add .omo/workers/promotion/current.yaml .omo/workers/promotion/current.md && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): hydrate promotion history surface" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one root commit containing the canonical derived history surface.

---

## Self-review checklist

- **Spec coverage:** Task 1 covers compact history derivation, empty surface, sorting, and fail-closed malformed input. Task 2 covers the explicit `task promotion-history` materializer and operator docs. Task 3 hydrates the live ORPHANED-derived surface and re-runs canonical verification.
- **Placeholder scan:** this plan uses exact file paths, exact commands, and concrete YAML/Markdown contracts; there are no TBDs or deferred implementation markers inside the task steps.
- **Type consistency:** the plan consistently uses `build_promotion_history`, `task promotion-history`, `.omo/workers/promotion/current.yaml`, and the `latest_promotion_* / prior_promotion_* / promotion_count / promotions[]` contract across all tasks.
