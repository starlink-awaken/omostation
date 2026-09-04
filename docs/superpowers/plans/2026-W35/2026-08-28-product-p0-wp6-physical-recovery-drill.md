---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-29
type: ssot
last_updated: 2026-09-03
---
# Product P0 WP6 Physical Recovery Drill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute and prove a real backup, isolated restore, SQLite integrity/replay, external post-result human confirmation, and safe cleanup without ever overwriting the source.

**Architecture:** Preserve the existing dry-run planner. Add a separate explicit live adapter that preflights all paths before writes, copies source to a new backup, restores only into an existing empty isolated target, compares tree and Event Ledger replay digests, and writes an immutable provisional receipt. A second command verifies an external human confirmation bound to that provisional digest before producing the final passing receipt; cleanup is a third guarded operation.

**Tech Stack:** Python 3.13, pathlib, shutil, SQLite read-only URI, dataclasses, SHA-256, pytest, immutable JSON receipts, root-only Git delivery.

## Global Constraints

- BET: `BET-Y1Q3-T4-08`; depends on WP3 `BET-Y1Q3-T4-06`.
- Accepted Spec: `docs/superpowers/specs/2026-08-28-product-p0-wp6-physical-recovery-drill-design.md`.
- Dry-run always has `executed=false`, `meets_physical_gate=false`, and `meets_gate=false`.
- Live execution requires an exact user-approved non-production source, a new backup path, an existing empty isolated restore directory, and a pre-execution approval reference.
- Post-result confirmation is separate from pre-execution approval and binds the provisional receipt digest.
- `source_digest == backup_digest == restored_digest`; replay digest compares canonical source/restored Event Ledger snapshots and is not required to equal the tree digest.
- Symlink, socket, device, FIFO, path overlap, non-empty restore target, integrity mismatch, replay mismatch, or missing human confirmation fails closed.
- Root-only PR; no runtime/production source writes. Final state `delivery_accepted`, value `NOT_PROVEN`.

---

### Task 1: Amend WP6 for Two-Stage Human Confirmation

**Files:**
- Modify: `docs/superpowers/specs/2026-08-28-product-p0-wp6-physical-recovery-drill-design.md`
- Modify: `docs/plans/3y-bet-ledger.yaml`

**Interfaces:**
- Distinguishes `approval_ref` before the drill from `confirmation_ref` after the provisional receipt.

- [ ] **Step 1: Replace the single ambiguous confirmation requirement**

The Spec must require:

```text
approval_ref authorizes starting the live drill.
confirmation_ref is an external human receipt bound to provisional_receipt_digest.
Equal digests without confirmation_ref keep human_confirmed=false and the gate false.
```

- [ ] **Step 2: Recalculate T4-08's digest and merge the amendment**

Compile the WorkPacket, merge Spec/ledger lane commits, close the superseded run, and start a fresh implementation run from main.

---

### Task 2: Freeze Receipt, Error, and Digest Contracts

**Files:**
- Modify: `bin/delivery/physical_recovery.py`
- Modify: `tests/test_batch2_physical_recovery.py`
- Create: `tests/test_physical_recovery_live_drill.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class RecoveryReceipt:
    drill_id: str
    source_digest: str
    backup_digest: str
    restored_digest: str
    replay_digest: str
    isolated_target: str
    executed: bool
    integrity_ok: bool
    human_confirmed: bool
    started_at: str
    completed_at: str

    @property
    def meets_physical_gate(self) -> bool: ...

    def to_dict(self) -> dict[str, Any]: ...


class RecoveryError(ValueError):
    def __init__(self, reason: str, message: str) -> None: ...


def tree_digest(root: Path) -> str: ...
```

- [ ] **Step 1: Strengthen planner-only tests**

```python
@pytest.mark.parametrize("dry_run", [True, False])
def test_run_recovery_planner_never_sets_executed_or_gate(tmp_path: Path, dry_run: bool) -> None:
    report = _load().run_recovery(
        dry_run=dry_run,
        hosts=["127.0.0.1"],
        out_dir=tmp_path,
    )
    assert report.get("executed", False) is False
    assert report["meets_physical_gate"] is False
    assert report["meets_gate"] is False
```

- [ ] **Step 2: Add deterministic tree digest tests**

Create the same files in different creation orders and assert identical digests; change one byte and assert a different digest. Reject symlinks and non-regular files before hashing.

- [ ] **Step 3: Implement the frozen contracts**

`RecoveryReceipt.meets_physical_gate` returns true only when `executed`, `integrity_ok`, and `human_confirmed` are all true and the three tree digests are equal and non-empty.

---

### Task 3: Reject Unsafe Paths Before Any Write

**Files:**
- Modify: `bin/delivery/physical_recovery.py`
- Modify: `tests/test_physical_recovery_live_drill.py`

**Interfaces:**

```python
def execute_live_recovery(
    *,
    source: Path,
    backup_dir: Path,
    restore_dir: Path,
    ledger_relative_path: Path,
    approval_ref: str,
    provisional_receipt_path: Path,
    now: Callable[[], str] = _utc_now,
) -> RecoveryReceipt: ...
```

- [ ] **Step 1: Add zero-write rejection tests**

Parameterize restore equal to source, source parent, backup parent, non-empty target, symlink source/target, and special file. Snapshot the temporary tree before the call and assert it is byte-for-byte unchanged after `RecoveryError`.

```python
with pytest.raises(recovery.RecoveryError) as exc:
    recovery.execute_live_recovery(
        source=source,
        backup_dir=backup,
        restore_dir=restore,
        ledger_relative_path=Path("event-ledger.sqlite3"),
        approval_ref="receipt://human/recovery-approval/1",
        provisional_receipt_path=tmp_path / "evidence" / "provisional.json",
    )
assert exc.value.reason in {
    "restore_overlaps_source",
    "backup_overlaps_source",
    "restore_not_empty",
    "unsafe_file_type",
}
```

- [ ] **Step 2: Implement complete preflight before mkdir/copy/write**

Resolve source strictly and backup/restore parents safely. Require source directory, backup absent, restore existing/empty, and no equality or ancestor/descendant relationship among source/backup/restore. Walk source with `follow_symlinks=False` semantics and reject every non-regular file/directory.

- [ ] **Step 3: Run path preflight GREEN**

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_physical_recovery_live_drill.py -k 'unsafe or overlap or nonempty' -q
```

---

### Task 4: Implement Copy, SQLite Integrity, and Replay Equality

**Files:**
- Modify: `bin/delivery/physical_recovery.py`
- Modify: `tests/test_physical_recovery_live_drill.py`

**Interfaces:**

```python
def _ledger_replay_digest(path: Path) -> str:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RecoveryError("integrity_failed", str(integrity))
        payload = {
            "event_log": [dict(row) for row in conn.execute("SELECT * FROM event_log ORDER BY sequence")],
            "event_outbox": [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM event_outbox ORDER BY event_id, destination"
                )
            ],
        }
    finally:
        conn.close()
    return _sha256_json(payload)
```

- [ ] **Step 1: Add success RED with a real seeded SQLite ledger**

```python
receipt = recovery.execute_live_recovery(
    source=seeded_ledger_tree,
    backup_dir=tmp_path / "backup",
    restore_dir=_empty_dir(tmp_path / "restore"),
    ledger_relative_path=Path("event-ledger.sqlite3"),
    approval_ref="receipt://human/recovery-approval/1",
    provisional_receipt_path=tmp_path / "evidence" / "provisional.json",
)

assert receipt.executed is True
assert receipt.integrity_ok is True
assert receipt.human_confirmed is False
assert receipt.meets_physical_gate is False
assert receipt.source_digest == receipt.backup_digest == receipt.restored_digest
assert receipt.replay_digest
```

- [ ] **Step 2: Add restored corruption RED**

Monkeypatch the restore copy helper to alter one restored byte after copy. Assert `restored_digest_mismatch` or `integrity_failed`, no final-success receipt, and source/backup remain.

- [ ] **Step 3: Implement live copy and provisional receipt**

After preflight, calculate source tree/replay digests, copy to the new backup, verify backup digest, copy backup contents into the empty restore directory, verify restored digest and restored replay digest, then write provisional JSON with exclusive create mode `x`. Set `human_confirmed=False` regardless of equal digests.

- [ ] **Step 4: Run copy/replay GREEN**

```bash
uv run --with pyyaml --with pytest python -m pytest tests/test_physical_recovery_live_drill.py -q
```

---

### Task 5: Add External Confirmation and Guarded Cleanup

**Files:**
- Modify: `bin/delivery/physical_recovery.py`
- Modify: `tests/test_physical_recovery_live_drill.py`

**Interfaces:**

```python
def confirm_recovery_receipt(
    *,
    provisional_receipt_path: Path,
    confirmation_receipt_path: Path,
    final_receipt_path: Path,
) -> RecoveryReceipt: ...


def cleanup_isolated_restore(
    *,
    restore_dir: Path,
    receipt: RecoveryReceipt,
    cleanup_confirmation_ref: str,
) -> dict[str, Any]: ...
```

- [ ] **Step 1: Add confirmation RED**

Use an external file with:

```json
{
  "schema": "human-recovery-confirmation/v1",
  "approved": true,
  "provisional_receipt_digest": "64-lowercase-sha256",
  "confirmed_by": "principal://human-owner",
  "confirmed_at": "2026-08-28T02:00:00Z"
}
```

Wrong digest, missing/false approval, malformed principal/timestamp, or reused different final path must fail. Equal tree/replay digests without this file never pass the gate.

- [ ] **Step 2: Implement immutable final receipt**

Read and hash the provisional receipt, validate external confirmation, create a copy with `human_confirmed=True`, and write the final path using exclusive mode `x`. Never overwrite either input.

- [ ] **Step 3: Add cleanup RED/GREEN**

Cleanup requires final passing receipt, exact resolved target equality, non-overlap recheck, and a non-empty cleanup confirmation ref. Delete only the restore target; assert source, backup, provisional, confirmation, and final receipt still exist.

- [ ] **Step 4: Run full GREEN**

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_batch2_physical_recovery.py tests/test_physical_recovery_live_drill.py -q
```

---

### Task 6: Add Exact Operator Commands

**Files:**
- Modify: `docs/operations/physical-recovery-package.md`

**Interfaces:**
- Produces: dry-run, live, confirm, and cleanup commands with no implicit production path.

- [ ] **Step 1: Document fail-closed environment binding**

```bash
test -n "${P0_RECOVERY_SOURCE:?set exact approved non-production source}"
test -n "${P0_RECOVERY_BACKUP:?set exact new backup path}"
test -n "${P0_RECOVERY_RESTORE:?set exact empty isolated restore path}"
test -n "${P0_RECOVERY_APPROVAL_REF:?set human pre-execution approval ref}"
```

- [ ] **Step 2: Document the four explicit commands**

```bash
python3 bin/delivery/physical_recovery.py --dry-run

python3 bin/delivery/physical_recovery.py live \
  --source "$P0_RECOVERY_SOURCE" \
  --backup-dir "$P0_RECOVERY_BACKUP" \
  --restore-dir "$P0_RECOVERY_RESTORE" \
  --ledger-relative-path event-ledger.sqlite3 \
  --approval-ref "$P0_RECOVERY_APPROVAL_REF" \
  --receipt "$P0_RECOVERY_PROVISIONAL_RECEIPT"

python3 bin/delivery/physical_recovery.py confirm \
  --provisional-receipt "$P0_RECOVERY_PROVISIONAL_RECEIPT" \
  --confirmation-receipt "$P0_RECOVERY_CONFIRMATION_RECEIPT" \
  --final-receipt "$P0_RECOVERY_FINAL_RECEIPT"

python3 bin/delivery/physical_recovery.py cleanup \
  --restore-dir "$P0_RECOVERY_RESTORE" \
  --final-receipt "$P0_RECOVERY_FINAL_RECEIPT" \
  --cleanup-confirmation-ref "$P0_RECOVERY_CLEANUP_REF"
```

The operator must set every `P0_RECOVERY_*` variable to an exact path/reference; the tool supplies no broad default.

- [ ] **Step 3: Run documentation and CLI help checks**

```bash
python3 bin/delivery/physical_recovery.py --help
python3 bin/delivery/physical_recovery.py live --help
python3 bin/delivery/physical_recovery.py confirm --help
python3 bin/delivery/physical_recovery.py cleanup --help
make doc-ssot-lint
```

---

### Task 7: Root Delivery, Real Drill, and Completion

**Files:**
- Root implementation files from Tasks 2-6
- Coordinator-only completion: `docs/plans/3y-bet-ledger.yaml`
- Coordinator-only retro: `.omo/_knowledge/retros/BET-Y1Q3-T4-08.md`

**Interfaces:**
- Produces: root mainline, one real provisional/final/cleanup receipt set, and `delivery_accepted`.

- [ ] **Step 1: Run independent review and root CI**

Review path safety, exclusive receipts, SQLite read-only behavior, digest equality, confirmation binding, and cleanup target. Run the two focused test files, Ruff for the Python file/tests, doc lint, and root gates.

- [ ] **Step 2: Merge the unique root implementation PR**

Do not run the real drill from an unmerged branch. After required checks pass, merge and verify the implementation on `origin/main`.

- [ ] **Step 3: Obtain exact human-gated paths and execute the real drill**

The principal supplies one exact non-production Event Ledger/outbox source and all explicit evidence paths. Run live, inspect provisional receipt, obtain external post-result confirmation, run confirm, then cleanup. Capture elapsed time, four digests, integrity result, target, and retained source/backup/receipts.

- [ ] **Step 4: Serialize completion and cleanup evidence**

Engineering GREEN alone is insufficient. With real operational receipts, set T4-08 to `delivery_accepted`, value=`NOT_PROVEN`, and `done`; write retro and cleanup evidence in coordinator-only commits. Retire the branch, clone, terminal, and workflow locks.

---

## Self-Review

- Spec coverage: dry-run, path safety, copy, tree/replay integrity, provisional/final receipts, two-stage human gate, cleanup, operator commands, real drill, rollback, and value firewall are explicit.
- Placeholder scan: all human-gated values are mandatory task-specific environment variables with no defaults.
- Type consistency: provisional and final receipts use one `RecoveryReceipt`; confirmation binds the provisional digest; cleanup consumes only the final passing receipt.
