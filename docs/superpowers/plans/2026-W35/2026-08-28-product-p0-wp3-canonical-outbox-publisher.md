---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-29
type: ssot
last_updated: 2026-09-03
---
# Product P0 WP3 Canonical Outbox Publisher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing Event Ledger outbox into one leased, replay-safe, deterministic publisher with a real OMO CLI production entry and bus-foundation receipt.

**Architecture:** Extend the existing `event_outbox` table through an explicit schema migration; keep `(event_id, destination)` as the idempotency identity. Claim rows atomically, call the destination adapter outside the transaction, and settle only through lease-owner methods. Expose one `omo ledger publish-once` entry that uses `publisher.publish_due` and the existing bus-foundation facade; do not add a scheduler, queue, broker, or second outbox.

**Tech Stack:** Python 3.13, SQLite, pytest, Ruff, OMO Event Ledger, bus-foundation `OmniEnvelope`, OMO CLI, Git child/root delivery.

## Global Constraints

- BET: `BET-Y1Q3-T4-06`; depends on completed WP2 `BET-Y1Q3-T4-05`.
- Accepted Spec: `docs/superpowers/specs/2026-08-28-product-p0-wp3-canonical-outbox-publisher-design.md`.
- Existing table `event_outbox` remains the only queue; no second table or database.
- Existing logical destination `ledger` is retained as the compatibility destination and maps only to the bus-foundation adapter in the production CLI.
- Timeout, connection reset, empty receipt, and expired publishing lease become `uncertain`; they are not automatically republished.
- Deterministic attempts 1-4 back off by exactly 5/30/120/600 seconds; attempt 5 becomes failed with a stable failure receipt.
- Sent/failed/uncertain rows are not due; explicit replay reads prior receipt through `outbox_receipt(event_id, destination)`.
- OMO child PR/main precedes root `projects/omo` pointer PR; value stays `NOT_PROVEN`, final state `delivery_accepted`.

---

### Task 1: Amend WP3 for the Production Entry and Migration

**Files:**
- Modify: `docs/superpowers/specs/2026-08-28-product-p0-wp3-canonical-outbox-publisher-design.md`
- Modify: `docs/plans/3y-bet-ledger.yaml`

**Interfaces:**
- Produces new authorized surfaces: `projects/omo/src/omo/omo_ledger.py` and `projects/omo/tests/test_omo_ledger.py`.
- Locks the production owner to `omo ledger publish-once`; the command invokes `publish_due` and bus-foundation, with no daemon/scheduler addition.

- [ ] **Step 1: Add exact production surfaces and semantics**

The Spec must explicitly authorize the two files above, `outbox_receipt`, schema v1-to-v2 migration, and a shadow canary that invokes `publish-once` against an isolated real SQLite ledger plus real bus-foundation backend.

- [ ] **Step 2: Recalculate T4-06's Spec digest and merge the amendment**

Compile `prepare_bet_execution('BET-Y1Q3-T4-06')`, commit Spec and ledger separately, merge required checks, close the superseded amendment run, and start a fresh implementation run from merged main.

---

### Task 2: Add an Explicit Outbox Schema Migration

**Files:**
- Modify: `projects/omo/src/omo/event_ledger/schema.py`
- Modify: `projects/omo/tests/test_event_ledger.py`

**Interfaces:**
- Consumes: valid schema v1 database and its recorded checksum.
- Produces: schema v2 with nullable `lease_owner`, `lease_expires_at`, `receipt_id`, and `error_class` columns plus recorded migration checksum.

- [ ] **Step 1: Add a v1 migration RED test**

Use the existing legacy-schema fixture helpers and add:

```python
def test_v1_database_migrates_outbox_lease_columns(tmp_path: Path) -> None:
    db = tmp_path / "ledger-v1.db"
    create_legacy_v1_database(db)

    broker = LedgerBroker.connect(db)
    try:
        columns = {
            row["name"]
            for row in broker._conn.execute("PRAGMA table_info(event_outbox)").fetchall()
        }
        assert {"lease_owner", "lease_expires_at", "receipt_id", "error_class"} <= columns
        assert [row["version"] for row in broker.migration_status()] == ["1", "2"]
    finally:
        broker.close()
```

- [ ] **Step 2: Run RED**

```bash
cd projects/omo
uv run pytest tests/test_event_ledger.py::test_v1_database_migrates_outbox_lease_columns -q
```

Expected: FAIL because schema version is `1` and the columns do not exist.

- [ ] **Step 3: Implement migration v2 without silent drift repair**

Set `LEDGER_SCHEMA_VERSION = "2"`, extend the expected outbox column map, and add a canonical migration statement list:

```python
OUTBOX_V2_MIGRATION = (
    "ALTER TABLE event_outbox ADD COLUMN lease_owner TEXT",
    "ALTER TABLE event_outbox ADD COLUMN lease_expires_at TEXT",
    "ALTER TABLE event_outbox ADD COLUMN receipt_id TEXT",
    "ALTER TABLE event_outbox ADD COLUMN error_class TEXT",
)
OUTBOX_V2_CHECKSUM = hashlib.sha256("\n".join(OUTBOX_V2_MIGRATION).encode("utf-8")).hexdigest()
```

Inside `apply_schema`, after verifying the recorded v1 checksum, execute the four statements in the same explicit transaction, insert schema migration version `2`, and then run the complete drift verifier. Fresh databases must create the v2 columns directly and record versions in the same canonical order expected by the tests.

- [ ] **Step 4: Run migration and drift GREEN**

```bash
cd projects/omo
uv run pytest tests/test_event_ledger.py -q
```

Expected: existing v1 migration, fresh v2, extra/missing column, checksum, trigger, and index tests all PASS.

---

### Task 3: Implement Atomic Lease and Owner-Checked Settlement

**Files:**
- Modify: `projects/omo/src/omo/event_ledger/broker.py`
- Modify: `projects/omo/tests/test_event_outbox_publisher.py`

**Interfaces:**
- Produces: `outbox_claim_due`, `outbox_succeed`, `outbox_retry`, `outbox_uncertain`, and `outbox_receipt`.

- [ ] **Step 1: Add concurrent lease RED**

```python
def test_two_publishers_claim_one_row_once(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    seed_outbox(db)
    barrier = threading.Barrier(2)

    def claim(worker_id: str) -> list[dict[str, Any]]:
        broker = LedgerBroker.connect(db)
        try:
            barrier.wait()
            return broker.outbox_claim_due(
                "ledger",
                worker_id=worker_id,
                now="2026-08-28T00:00:00Z",
                limit=1,
            )
        finally:
            broker.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        batches = list(pool.map(claim, ["worker-a", "worker-b"]))

    assert sum(len(batch) for batch in batches) == 1
```

Expected RED: broker has no lease API.

- [ ] **Step 2: Implement claim in one `BEGIN IMMEDIATE` transaction**

The method must:

```text
1. convert expired publishing leases to uncertain;
2. select pending rows whose next_attempt_at <= now;
3. set state=publishing, lease_owner, lease_expires_at, attempts=attempts+1;
4. join event_log payload/event_type for the claimed rows;
5. commit before returning.
```

No `PublishFn` call occurs under the SQLite transaction.

- [ ] **Step 3: Implement owner-checked terminal methods**

Every update includes `WHERE event_id=? AND destination=? AND state='publishing' AND lease_owner=?`; zero updated rows raise `LedgerError("outbox lease owner mismatch")`.

```python
def outbox_receipt(self, event_id: str, destination: str) -> dict[str, Any] | None:
    row = self._conn.execute(
        "SELECT * FROM event_outbox WHERE event_id=? AND destination=?",
        (event_id, destination),
    ).fetchone()
    return dict(row) if row is not None else None
```

- [ ] **Step 4: Remove the public unowned mark path**

Replace production/tests using `outbox_mark` with owner-checked methods. Do not keep a callable route that can mark sent without a lease and receipt.

---

### Task 4: Implement the Publisher State Machine

**Files:**
- Create: `projects/omo/src/omo/event_ledger/publisher.py`
- Create: `projects/omo/tests/test_event_outbox_publisher.py`

**Interfaces:**

```python
PublishFn = Callable[[str, dict[str, Any], str], str]
BACKOFF_SECONDS = (5, 30, 120, 600)


@dataclass(frozen=True)
class PublishResult:
    event_id: str
    destination: str
    state: str
    attempts: int
    receipt_id: str | None
    next_attempt_at: str
    error_class: str | None


class DeterministicPublishError(RuntimeError):
    pass


class UncertainPublishError(RuntimeError):
    pass
```

- [ ] **Step 1: Add RED tests for retry, uncertainty, replay, and failure**

Add exact-clock tests for 5/30/120/600 seconds, attempt five failure receipt, timeout/connection reset/empty receipt uncertainty, expired lease uncertainty after restart, sent row not due, and explicit `outbox_receipt` replay.

- [ ] **Step 2: Implement `publish_due`**

```python
def publish_due(
    broker: LedgerBroker,
    destination: str,
    publish: PublishFn,
    *,
    worker_id: str,
    now: str,
    limit: int = 100,
) -> list[PublishResult]:
    rows = broker.outbox_claim_due(
        destination,
        worker_id=worker_id,
        now=now,
        limit=limit,
    )
    results: list[PublishResult] = []
    for row in rows:
        key = f"outbox:{row['event_id']}:{destination}"
        try:
            receipt_id = publish(row["event_id"], row, key)
            if not receipt_id:
                raise UncertainPublishError("publisher returned no receipt")
            updated = broker.outbox_succeed(
                row["event_id"], destination,
                worker_id=worker_id, receipt_id=receipt_id, now=now,
            )
        except (TimeoutError, ConnectionError, UncertainPublishError) as exc:
            updated = broker.outbox_uncertain(
                row["event_id"], destination,
                worker_id=worker_id, now=now, error_class=type(exc).__name__,
            )
        except DeterministicPublishError as exc:
            updated = broker.outbox_retry(
                row["event_id"], destination,
                worker_id=worker_id, now=now, error_class=type(exc).__name__,
            )
        results.append(PublishResult(**updated))
    return results
```

- [ ] **Step 3: Run publisher GREEN**

```bash
cd projects/omo
uv run pytest tests/test_event_ledger.py tests/test_event_outbox_publisher.py -q
```

---

### Task 5: Add the Single Production `publish-once` Entry

**Files:**
- Modify: `projects/omo/src/omo/omo_ledger.py`
- Modify: `projects/omo/tests/test_omo_ledger.py`

**Interfaces:**
- Consumes: `omo ledger publish-once --destination ledger --worker-id "$P0_OUTBOX_WORKER_ID" --db "$P0_OUTBOX_DB"` after both task-specific variables are explicitly set.
- Produces: bus-foundation receipt IDs and JSON summary; no scheduler or daemon.

- [ ] **Step 1: Add CLI RED**

```python
def test_publish_once_uses_canonical_publisher(monkeypatch, tmp_path: Path, capsys) -> None:
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        omo_ledger,
        "_publish_bus_foundation",
        lambda event_id, row, key: calls.append((event_id, key)) or "bus-receipt-1",
    )
    db = seed_cli_outbox(tmp_path)

    rc = omo_ledger.main([
        "publish-once", "--destination", "ledger", "--worker-id", "worker-cli",
        "--db", str(db), "--json",
    ])

    assert rc == 0
    assert len(calls) == 1
    assert json.loads(capsys.readouterr().out)["sent"] == 1
```

- [ ] **Step 2: Add parser and production adapter**

Add `publish-once` to `SUBCMDS`, register exact local-only flags, and implement:

```python
def _publish_bus_foundation(event_id: str, row: dict[str, Any], key: str) -> str:
    from bus_foundation import publish as bus_publish
    from bus_foundation.envelope import OmniEnvelope, OmniPlane

    envelope = OmniEnvelope(
        plane=OmniPlane.EVENT,
        topic=f"omo:ledger:{row['event_type']}",
        source_uri="bos://governance/omo/event-ledger",
        payload={
            "event_id": event_id,
            "event_type": row["event_type"],
            "payload": json.loads(row["payload_json"]),
            "idempotency_key": key,
        },
        trace_id=str(row.get("correlation_id") or event_id),
    )
    return str(bus_publish(envelope))
```

Open the broker, call `publish_due`, close it in `finally`, and return nonzero when any result is failed/uncertain. `publish-once` is the only production caller of `publish_due`.

- [ ] **Step 3: Run CLI and full OMO GREEN**

```bash
cd projects/omo
uv run pytest tests/test_event_ledger.py tests/test_event_outbox_publisher.py tests/test_omo_ledger.py -q
uv run ruff check src/omo/event_ledger src/omo/omo_ledger.py \
  tests/test_event_ledger.py tests/test_event_outbox_publisher.py tests/test_omo_ledger.py
```

- [ ] **Step 4: Commit the OMO child change**

```bash
git add src/omo/event_ledger/schema.py src/omo/event_ledger/broker.py \
  src/omo/event_ledger/publisher.py src/omo/omo_ledger.py \
  tests/test_event_ledger.py tests/test_event_outbox_publisher.py tests/test_omo_ledger.py
git commit -m "feat(ledger): add leased outbox publisher"
```

---

### Task 6: Child/Root Delivery and Operational Canary

**Files:**
- Child review: OMO files from Tasks 2-5
- Root pointer: `projects/omo`
- Coordinator-only completion: `docs/plans/3y-bet-ledger.yaml`
- Coordinator-only retro: `.omo/_knowledge/retros/BET-Y1Q3-T4-06.md`

**Interfaces:**
- Produces: OMO child main, root pointer main, one isolated real bus-foundation receipt, restart replay, and `delivery_accepted`.

- [ ] **Step 1: Merge OMO child and root pointer PRs in order**

Prove child merge SHA is on OMO main, then update only `projects/omo` from a fresh root attempt. Run `submodule-reachability-gate.py --source head --fetch --require-main --json` before root merge.

- [ ] **Step 2: Execute the shadow production canary**

Seed one non-sensitive real Event Ledger row in an isolated SQLite database, invoke the merged `omo ledger publish-once` with the real bus-foundation backend, and record the bus receipt plus outbox `sent` row.

- [ ] **Step 3: Prove restart replay**

Close/reopen the broker, call `publish-once` again, and prove no second bus publish occurs. Read the original receipt with `outbox_receipt(event_id, "ledger")`.

- [ ] **Step 4: Serialize completion and cleanup**

Write direct engineering and operational evidence in coordinator-only commits. T4-06 becomes `delivery_accepted`; value remains `NOT_PROVEN`. Retain sent/failed/uncertain rows and receipts; retire child/root clones, branch, terminals, and workflow locks.

---

## Self-Review

- Spec coverage: migration, lease, deterministic backoff, uncertainty, failure receipt, explicit replay, production owner, child/root delivery, canary, rollback, and value firewall are explicit.
- Placeholder scan: command-time IDs are derived; no unnamed adapter, scheduler, or test remains.
- Type consistency: `PublishFn` returns a non-empty bus receipt string; `publish_due` consumes joined ledger rows; `outbox_receipt` is the explicit replay API.
