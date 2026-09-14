---
status: active
lifecycle: plan
owner: governance-team
created: 2026-08-30
last-reviewed: 2026-08-30
last_updated: 2026-09-03
title: Documents retired runner-log exact quarantine implementation plan
type: doc
---

# Documents Retired Runner-Log Exact Quarantine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing Documents quarantine transaction to move exactly two cache-classified runner logs with non-target preservation, completed verification, and executable rollback.

**Architecture:** Preserve the current runtime-only default path. Activate exact mode only with explicit include paths and selected kinds, classify exact paths against the full Documents root, guard every non-selected source node, and reuse the existing v1 completed manifest for apply/verify/rollback.

**Tech Stack:** Python 3.13-compatible standard library, pytest, Ruff, YAML registry, Agent Workflow, GaC, GitHub PR checks.

## Global Constraints

- No production edit before a failing behavior test.
- No new CLI file, registry family, dispatcher, ontology, or migration primitive.
- Existing calls without exact options remain runtime-only and behavior-compatible.
- Exact mode accepts only safe explicit relative paths and `runtime|cache` kinds.
- Classify exact sources against the complete Documents root, not the scoped source root.
- Never select or mutate non-target `_inbox` content.
- Capability PR must merge and replay before host apply.
- Target is `/Users/xiamingxing/Workspace/runtime/quarantine/documents-root-inbox-runner-logs-20260831`.
- Permanent deletion is forbidden; root-oneoff-assets remains pending.

---

### Task 1: Exact inventory and non-target guard

**Files:**
- Modify: `tests/test_documents_runtime_quarantine.py`
- Modify: `lib/documents_runtime_quarantine.py`

**Interfaces:**
- Produces: `_normalize_relative_paths(values: list[str]) -> tuple[str, ...]`.
- Produces: `_scope_snapshot(source_root: Path, excluded: set[str]) -> dict[str, Any]`.
- Produces: `_load_exact_inventory(documents_root: Path, source_root: Path, relative_paths: list[str]) -> list[dict[str, Any]]`.
- Extends: `build_plan(..., selected_kinds: set[str] | None = None, exact_relative_paths: list[str] | None = None) -> dict[str, Any]`.

- [ ] **Step 1: Add exact-selection RED tests**

Add tests that create `Documents/_inbox/hourly_runner.log`,
`hourly_runner_err.log`, and `note.md`. Assert:

```python
inventory = module._load_exact_inventory(
    documents,
    inbox,
    ["hourly_runner.log", "hourly_runner_err.log"],
)
plan = module.build_plan(
    documents_root=documents,
    source_root=inbox,
    target_root=target,
    inventory=inventory,
    consumer_receipt=_consumer_receipt(),
    now="2026-08-31T02:30:00Z",
    selected_kinds={"cache"},
    exact_relative_paths=["hourly_runner.log", "hourly_runner_err.log"],
)
assert [item["relative_path"] for item in plan["files"]] == [
    "hourly_runner.log",
    "hourly_runner_err.log",
]
assert plan["selected_kinds"] == ["cache"]
assert plan["selection_mode"] == "exact"
assert plan["non_target_guard"]["files"] == 1
```

Add separate tests for duplicate, absolute, `..`, missing, and content-kind
includes; exact-set mismatch; and default runtime-only `build_plan` output.

- [ ] **Step 2: Run RED**

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_documents_runtime_quarantine.py -q
```

Expected: new tests fail because `_load_exact_inventory` and exact arguments do
not exist; existing tests continue passing before the first new assertion.

- [ ] **Step 3: Implement safe path normalization and snapshots**

Implement closed validation:

```python
_ALLOWED_KINDS = frozenset({"runtime", "cache"})


def _normalize_relative_paths(values: list[str]) -> tuple[str, ...]:
    normalized: set[str] = set()
    for raw in values:
        candidate = Path(raw)
        if not raw or candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
            raise QuarantineError(f"exact include path is unsafe: {raw}")
        value = candidate.as_posix()
        if value in normalized:
            raise QuarantineError(f"exact include path is duplicated: {value}")
        normalized.add(value)
    if not normalized:
        raise QuarantineError("exact include paths are empty")
    return tuple(sorted(normalized))
```

`_scope_snapshot` walks without following directory symlinks, records every
non-directory node with `_entry_from_source`, excludes the exact set, and
returns sorted entries, file/byte counts, and `_canonical_digest(entries)`.

- [ ] **Step 4: Implement exact full-root classification**

For every normalized include, sample `_entry_from_source` before and after
`classify_artifact(documents_root, source)`. Reject drift, then replace the
artifact dictionary's `relative_path` with the source-root-relative include.
Do not run `audit_content_plane(source_root)` in exact mode.

- [ ] **Step 5: Extend build_plan without changing defaults**

Use `{"runtime"}` when `selected_kinds is None`. Reject an empty or out-of-set
kind. Filter inventory by the selected set. When exact paths are supplied,
require selected relative paths to equal them exactly and add only these new
fields:

```python
plan["selection_mode"] = "exact"
plan["selected_kinds"] = sorted(kinds)
plan["expected_relative_paths"] = list(exact)
plan["non_target_guard"] = _scope_snapshot(source, set(exact))
```

Legacy plans omit these fields.

- [ ] **Step 6: Guard apply before and after movement**

Add `_validate_non_target_guard(plan)` and call it immediately before creating
the target and immediately before writing the manifest. Any mismatch raises
`QuarantineError("non-target source scope changed")`; existing `_restore`
reverses selected moves on the post-move failure.

- [ ] **Step 7: Run GREEN and commit Task 1**

```bash
uv run --with pyyaml --with pytest python -m pytest tests/test_documents_runtime_quarantine.py -q
uv run --with ruff ruff check lib/documents_runtime_quarantine.py tests/test_documents_runtime_quarantine.py
git add tests/test_documents_runtime_quarantine.py lib/documents_runtime_quarantine.py
git commit -m "feat(documents): add exact quarantine selection"
```

Expected: all quarantine tests pass and Ruff exits zero.

---

### Task 2: Completed verification, rollback, and CLI routing

**Files:**
- Modify: `tests/test_documents_runtime_quarantine.py`
- Modify: `lib/documents_runtime_quarantine.py`
- Modify: `tests/test_quarantine_retention_policy.py`

**Interfaces:**
- Produces: `verify_completed_manifest(manifest_path: Path) -> dict[str, Any]`.
- Produces: `rollback_completed_manifest(manifest_path: Path, *, now: str) -> dict[str, Any]`.
- Produces rollback schema `documents-runtime-quarantine-rollback/v1`.
- Adds CLI options `--include-relative`, `--artifact-kind`, `--verify-manifest`, and `--rollback-manifest` while preserving default plan and `--apply`.

- [ ] **Step 1: Add verify/rollback RED tests**

Create an exact two-file plan, apply it, then assert:

```python
verification = module.verify_completed_manifest(target / "manifest.json")
assert verification["status"] == "verified"
assert verification["summary"] == {"files": 2, "bytes": 0}
assert verification["rollback_available"] is True
assert verification["permanent_deletion"] is False

receipt = module.rollback_completed_manifest(
    target / "manifest.json",
    now="2026-08-31T03:00:00Z",
)
assert receipt["schema"] == "documents-runtime-quarantine-rollback/v1"
assert receipt["status"] == "rolled_back"
assert (inbox / "hourly_runner.log").exists()
assert (target / "manifest.json").exists()
```

Add tests for target/source/hash/mode collision, unexpected target entry,
non-target drift, immutable manifest bytes, rollback collision before any move,
and rollback receipt durability.

- [ ] **Step 2: Run RED**

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_documents_runtime_quarantine.py -q
```

Expected: new tests fail because verify and rollback functions do not exist.

- [ ] **Step 3: Implement completed verification**

Load a JSON object, require v1 schema and `status=completed`, validate
`permanent_deletion is False`, exact target inventory excluding
`manifest.json` and `rollback.json`, every target entry, selected source
absence, source/target fingerprint equality, and non-target guard equality.
Return a read-only v1 envelope with `status=verified` and
`rollback_available=True`.

- [ ] **Step 4: Implement rollback**

Call verification first. Preflight every source absence and target equality,
then move targets to sources in reverse order. If a move fails, use `_restore`
with reversed tuples to put already-restored entries back in quarantine.
Verify restored metadata and write `rollback.json` atomically without modifying
`manifest.json`.

- [ ] **Step 5: Add CLI routing**

Make target/receipt required only for plan/apply. A mutually exclusive action
group routes apply, verify-manifest, or rollback-manifest. Exact plan/apply uses
the new include/kind lists and `_load_exact_inventory`; legacy mode continues
through `_load_l4_inventory`.

- [ ] **Step 6: Add retention-path regression**

Extend `tests/test_quarantine_retention_policy.py` to assert
`runtime/quarantine/documents-root-inbox-runner-logs-20260831/manifest.json`
is ignored by the existing policy.

- [ ] **Step 7: Run GREEN and commit Task 2**

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_documents_runtime_quarantine.py tests/test_quarantine_retention_policy.py -q
uv run --with ruff ruff check \
  lib/documents_runtime_quarantine.py \
  tests/test_documents_runtime_quarantine.py \
  tests/test_quarantine_retention_policy.py
git add lib/documents_runtime_quarantine.py tests/test_documents_runtime_quarantine.py tests/test_quarantine_retention_policy.py
git commit -m "feat(documents): verify and rollback exact quarantine"
```

---

### Task 3: Capability verification and merge

**Files:**
- Create: `docs/superpowers/plans/2026-08-31-documents-runner-log-quarantine.md`
- Modify: `lib/documents_runtime_quarantine.py`
- Modify: `tests/test_documents_runtime_quarantine.py`
- Modify: `tests/test_quarantine_retention_policy.py`

- [ ] **Step 1: Commit this plan in the docs lane**

```bash
git add docs/superpowers/plans/2026-08-31-documents-runner-log-quarantine.md
git commit -m "docs: plan T10-110 exact runner-log quarantine"
```

- [ ] **Step 2: Run capability acceptance**

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_documents_runtime_quarantine.py tests/test_quarantine_retention_policy.py -q
uv run --with ruff ruff check \
  lib/documents_runtime_quarantine.py \
  tests/test_documents_runtime_quarantine.py \
  tests/test_quarantine_retention_policy.py
uv run --with pyyaml python bin/ssot/doc-ssot-lint.py --json
make ssot-guardian
make gac-local-gate
git diff origin/main...HEAD --check
```

- [ ] **Step 3: Push and merge the capability PR**

```bash
git push -u origin agent/codex-documents-convergence--t10-110-implementation-20260831-01
gh pr create --base main --head agent/codex-documents-convergence--t10-110-implementation-20260831-01
CAPABILITY_PR="$(gh pr list --state open --head agent/codex-documents-convergence--t10-110-implementation-20260831-01 --json number --jq '.[0].number')"
test -n "$CAPABILITY_PR"
gh pr checks "$CAPABILITY_PR" --watch
gh pr view "$CAPABILITY_PR" --json state,mergeable,mergeStateStatus,statusCheckRollup,headRefOid
gh pr merge "$CAPABILITY_PR" --squash --delete-branch=false
```

- [ ] **Step 4: Replay capability from main before host mutation**

Fetch root main and prove the merge reachable. Run the complete capability
acceptance matrix from a tree equal to root main. Do not apply if any check
fails.

---

### Task 4: Mainline host transaction

**Files:**
- External source: `/Users/xiamingxing/Documents/_inbox/hourly_runner.log`
- External source: `/Users/xiamingxing/Documents/_inbox/hourly_runner_err.log`
- External target: `/Users/xiamingxing/Workspace/runtime/quarantine/documents-root-inbox-runner-logs-20260831`

- [ ] **Step 1: Collect fresh preflight**

Generate a fresh consumer receipt; run two `lsof` checks; scan crontab,
LaunchAgents, Scheduled skills, processes, source metadata, target absence, and
retention policy. Generate two fixed-time plans and require byte equality.

- [ ] **Step 2: Apply once from merged main**

Use source `_inbox`, two exact includes, `--artifact-kind cache`, fixed target,
fresh consumer receipt, `--apply`, and `--json`. Require completed status,
two files, zero bytes, equal source/target fingerprint, and permanent deletion
false.

- [ ] **Step 3: Postflight and delayed recheck**

Run `--verify-manifest`, fresh consumer audit, exact source absence, target
metadata/hash parity, non-target guard equality, and full Documents L4 audit.
After other checks finish, re-hash the manifest and targets to prove retention.
Do not invoke rollback; prove it is available.

---

### Task 5: Registry closeout, PR merge, and workflow close

**Files:**
- Modify: `.omo/_truth/registry/documents-content-plane-migrations.yaml`
- Modify: `docs/plans/3y-bet-ledger.yaml`
- Create: `docs/reports/2026-08-31-documents-runner-log-quarantine.md`
- Create: `.omo/_knowledge/retros/BET-Y1Q3-T10-110.md`

- [ ] **Step 1: Append only the completed root-oneoff transaction**

Record exact scope, target, counts, fingerprints, manifest digest, consumer
receipt, non-target guard, rollback reference, source absence, and permanent
deletion false. Keep family `pending` and preserve the historical evidence gap.

- [ ] **Step 2: Write report, retro, and completion matrix**

Separate engineering, operational relocation, physical family status, and
value. Use merged main commits and digest-valid tracked receipts only.

- [ ] **Step 3: Commit lanes separately and verify**

Commit registry, report, retro, and ledger in their respective lanes. Run full
BET verify, workflow verify, doc SSOT, SSOT guardian, migration check, GaC, and
exact diff review.

- [ ] **Step 4: Push, merge, and replay closeout**

Create a closeout PR from a provenance-valid clone/branch based on latest main.
Wait for all current-tip required checks, require CLEAN, squash merge, replay
manifest verify and BET verify from root main, then close every T10-110 run
`ok`. Keep the broader Documents convergence goal active.
