---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-29
type: ssot
last_updated: 2026-09-03
---
# Product P0 WP5 Human Adjudication and Value Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record exactly one authority-bound real-human adjudication as one canonical Event Ledger decision-outcome event and expose a restart-safe Cockpit query without promoting shadow/file projections.

**Architecture:** Resolve decision/signal/episode/latest-candidate lineage from the existing Personal Episode Event Ledger. Store adjudication and decision outcome as two logical objects inside one atomic `DecisionOutcome.Recorded.v1` append, which also creates the existing outbox row in the same transaction. Cockpit authenticates via the merged WP4 authority context, delegates the write to OMO, and reads qualifying outcomes from the OMO observer; file JSONL/MOS projections remain non-authoritative.

**Tech Stack:** Python 3.13, dataclasses, pytest, OMO Personal Episode/Event Ledger, Cockpit FastAPI, WP4 authority receipt, WP3 outbox, child-first Git delivery.

## Global Constraints

- BET: `BET-Y1Q3-T4-07`; depends on WP1, WP4, and WP3.
- Accepted Spec: `docs/superpowers/specs/2026-08-28-product-p0-wp5-human-adjudication-value-design.md`.
- Only `source_class=real_human` with verified WP4 authority, persisted decision/scene/episode, and current revision may qualify.
- One Event Ledger append contains adjudication and outcome logical objects; no cross-store transaction and no direct MOS/YAML/JSONL truth write.
- Existing engineering-delivery records remain `tier=shadow`, `value_indicator_policy=false`, and non-qualifying.
- PR, tests, CI, transport, agent self-report, synthetic, fixture, and `user_provided` evidence never increments qualifying count.
- OMO child PR/main precedes Cockpit child PR/main, then root pointers, then one real human canary.
- WP5 is the only child allowed to derive `outcome_accepted`; a single outcome proves the path, not long-term value.

---

### Task 1: Amend WP5 to Lock Canonical Lineage and Query Surfaces

**Files:**
- Modify: `docs/superpowers/specs/2026-08-28-product-p0-wp5-human-adjudication-value-design.md`
- Modify: `docs/plans/3y-bet-ledger.yaml`

**Interfaces:**
- Produces: one-event atomic truth, the missing Cockpit outcomes test surface, and explicit rejection of shadow/file projections.

- [ ] **Step 1: Add the exact missing test and authority semantics**

Ensure the Spec authorizes `projects/cockpit/src/cockpit/tests/test_api_outcomes.py` and requires the adjudication endpoint to consume WP4's verified authority context rather than caller-supplied `principal_id`.

- [ ] **Step 2: Lock the one-event representation**

Use `DecisionOutcome.Recorded.v1` with `payload.adjudication` and `payload.decision_outcome`. MOS/file projections are downstream WP3 consumers and never part of the atomic truth transaction.

- [ ] **Step 3: Recalculate T4-07's digest and merge the amendment**

Compile the WorkPacket, merge Spec/ledger lane commits, close the superseded run, and start a fresh implementation run from merged main.

---

### Task 2: Add Canonical Decision Lineage to Personal Episode

**Files:**
- Modify: `projects/omo/src/omo/personal_episode.py`
- Modify: `projects/omo/tests/test_personal_episode.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class HumanAdjudication:
    adjudication_id: str
    decision_id: str
    principal_id: str
    verdict: str
    source_class: str
    authority_receipt_digest: str
    adjudicated_at: str


@dataclass(frozen=True)
class DecisionLineage:
    decision_id: str
    principal_id: str
    scene_id: str
    episode_id: str
    signal_event_id: str
    candidate_ref: str
    candidate_revision_digest: str


def load_decision_lineage(
    broker: LedgerBroker,
    *,
    decision_id: str,
    scene_id: str,
    episode_id: str,
) -> DecisionLineage: ...
```

- [ ] **Step 1: Add stale-candidate and missing-lineage RED tests**

Seed `SignalObserved.v1 -> Episode.Decision.v1 -> Evidence.LocalDraft.v1` with two candidate revisions. Assert `load_decision_lineage` returns only the latest revision and rejects a requested stale digest, missing decision, wrong scene, wrong episode, and cross-principal lineage without appending events.

- [ ] **Step 2: Implement a pure ledger reader**

Read by episode, identify the exact decision event ID, require its signal causation, select the last local-draft evidence by sequence, derive `candidate_revision_digest` from the safe evidence URI/current revision material, and return the frozen lineage. Do not expose raw signal body, absolute path, API key, or credential.

- [ ] **Step 3: Run Personal Episode GREEN**

```bash
cd projects/omo
uv run pytest tests/test_personal_episode.py -q
uv run ruff check src/omo/personal_episode.py tests/test_personal_episode.py
```

---

### Task 3: Implement the Single OMO Adjudication/Outcome Writer

**Files:**
- Modify: `projects/omo/src/omo/engineering_delivery_consumer.py`
- Modify: `projects/omo/tests/test_engineering_delivery_consumer.py`

**Interfaces:**

```python
def record_decision_outcome(
    adjudication: HumanAdjudication,
    *,
    scene_id: str,
    episode_id: str,
    burden_minutes: float | None,
    revision_digest: str,
    broker: LedgerBroker,
) -> dict[str, Any]: ...


def observe_qualifying_decision_outcomes(
    broker: LedgerBroker,
    *,
    principal_id: str | None = None,
) -> dict[str, Any]: ...
```

- [ ] **Step 1: Add real-human idempotency RED**

```python
def test_real_authority_bound_adjudication_records_once_and_replays(
    broker: LedgerBroker,
    seeded_lineage: dict[str, str],
) -> None:
    adjudication = HumanAdjudication(
        adjudication_id="adj-real-1",
        decision_id=seeded_lineage["decision_id"],
        principal_id=seeded_lineage["principal_id"],
        verdict="adopt",
        source_class="real_human",
        authority_receipt_digest="a" * 64,
        adjudicated_at="2026-08-28T01:00:00+00:00",
    )

    first = record_decision_outcome(
        adjudication,
        scene_id=seeded_lineage["scene_id"],
        episode_id=seeded_lineage["episode_id"],
        burden_minutes=1.5,
        revision_digest=seeded_lineage["revision_digest"],
        broker=broker,
    )
    replay = record_decision_outcome(
        adjudication,
        scene_id=seeded_lineage["scene_id"],
        episode_id=seeded_lineage["episode_id"],
        burden_minutes=1.5,
        revision_digest=seeded_lineage["revision_digest"],
        broker=broker,
    )

    assert first["status"] == "recorded"
    assert replay["status"] == "deduplicated"
    assert observe_qualifying_decision_outcomes(broker)["qualifying_count"] == 1
```

- [ ] **Step 2: Add the non-value rejection matrix**

Parameterize `source_class=synthetic`, `source_class=user_provided`, empty/invalid authority digest, principal mismatch, missing decision, wrong scene/episode, stale revision, duplicate ID with changed payload, and cross-principal replay. Capture `before = broker.count()` and assert count is unchanged on every rejection.

- [ ] **Step 3: Implement the atomic append**

After loading and matching lineage, append exactly once:

```python
sequence = broker.append(
    "DecisionOutcome.Recorded.v1",
    producer="omo-human-adjudication",
    principal_id=adjudication.principal_id,
    space_id="personal",
    correlation_id=f"decision-outcome|{adjudication.decision_id}",
    idempotency_key=f"adjudication|{adjudication.adjudication_id}",
    episode_id=episode_id,
    causation_id=adjudication.decision_id,
    payload={
        "adjudication": asdict(adjudication),
        "decision_outcome": {
            "decision_id": adjudication.decision_id,
            "scene_id": scene_id,
            "episode_id": episode_id,
            "signal_event_id": lineage.signal_event_id,
            "candidate_ref": lineage.candidate_ref,
            "revision_digest": revision_digest,
            "burden_minutes": burden_minutes,
            "value_indicator_policy": True,
        },
    },
)
```

Handle `DuplicateEventError` by reading the existing event and returning `deduplicated` only when the entire adjudication/outcome payload matches.

- [ ] **Step 4: Implement the strict observer**

Read only `DecisionOutcome.Recorded.v1`, validate the nested record, require `real_human`, 64-hex authority digest, non-empty lineage, current revision, and `value_indicator_policy=True`; partition invalid/shadow/synthetic records and return them separately without incrementing `qualifying_count`.

- [ ] **Step 5: Prove restart safety**

Close/reopen the same SQLite database and assert the observer returns the same qualifying count, IDs, authority digest, and lineage.

- [ ] **Step 6: Run OMO GREEN**

```bash
cd projects/omo
uv run pytest tests/test_personal_episode.py tests/test_engineering_delivery_consumer.py -q
uv run ruff check src/omo/personal_episode.py src/omo/engineering_delivery_consumer.py \
  tests/test_personal_episode.py tests/test_engineering_delivery_consumer.py
```

---

### Task 4: Add the Cockpit Decision Read/Adjudicate API

**Files:**
- Modify: `projects/cockpit/src/cockpit/web/api_decision_inbox.py`
- Modify: `projects/cockpit/src/cockpit/tests/test_api_decision_inbox.py`

**Interfaces:**

```text
GET  /api/decision-inbox/decisions
POST /api/decision-inbox/decisions/{decision_id}/adjudicate
```

- [ ] **Step 1: Add API RED tests**

GET returns only `decision_id`, `scene_id`, `episode_id`, `revision_digest`, and `candidate_ref`. POST accepts `verdict`, `revision_digest`, and `burden_minutes`; the principal and authority digest come from WP4-authenticated request context, never JSON body.

```python
def test_adjudicate_delegates_once_and_never_writes_projection(monkeypatch) -> None:
    captured: list[tuple[HumanAdjudication, dict[str, Any]]] = []
    monkeypatch.setattr(
        api_decision_inbox,
        "record_decision_outcome",
        lambda adjudication, **kwargs: captured.append((adjudication, kwargs))
        or {"status": "recorded", "decision_outcome_id": "do-real-1"},
    )

    response = TestClient(_app()).post(
        "/api/decision-inbox/decisions/evt-decision-1/adjudicate",
        headers={"X-Api-Key": "real-review-key"},
        json={
            "verdict": "adopt",
            "revision_digest": "a" * 64,
            "burden_minutes": 1.5,
        },
    )

    assert response.status_code == 200
    assert len(captured) == 1
```

- [ ] **Step 2: Implement read-only list and delegated write**

Reuse WP4 `authenticate_api_principal`/authority context, build `HumanAdjudication` server-side, and call OMO. Do not call the legacy file CRUD engine for these two routes and do not write `.omo/state`, MOS YAML, or scene-outcomes JSONL.

- [ ] **Step 3: Run Decision Inbox GREEN**

```bash
cd projects/cockpit
uv run pytest src/cockpit/tests/test_api_decision_inbox.py -q
```

---

### Task 5: Replace Qualifying Outcome Reads with the OMO Observer

**Files:**
- Modify: `projects/cockpit/src/cockpit/web/api_outcomes.py`
- Create: `projects/cockpit/src/cockpit/tests/test_api_outcomes.py`

**Interfaces:**
- Adds: `GET /api/outcomes/qualifying`.
- Preserves legacy pending/history/calibration endpoints as explicitly non-qualifying projections.

- [ ] **Step 1: Add observer-backed RED**

```python
def test_qualifying_outcomes_preserve_omo_lineage(monkeypatch) -> None:
    monkeypatch.setattr(
        api_outcomes,
        "observe_qualifying_decision_outcomes",
        lambda *_args, **_kwargs: {
            "qualifying_count": 1,
            "items": [{
                "principal_id": "principal:owner",
                "decision_id": "evt-decision-1",
                "scene_id": "personal-followup-dogfood",
                "episode_id": "episode-1",
                "adjudication_id": "adj-real-1",
            }],
            "partitioned": [],
        },
    )

    response = TestClient(_app()).get("/api/outcomes/qualifying")
    assert response.status_code == 200
    assert response.json()["qualifying_count"] == 1
```

- [ ] **Step 2: Implement the OMO query boundary**

Open the configured OMO Event Ledger read-only, call the observer, close in `finally`, and return its lineage-safe output. Do not merge `_read_jsonl`, belief YAML, or engineering shadow records into qualifying results.

- [ ] **Step 3: Run Cockpit GREEN and Ruff**

```bash
cd projects/cockpit
uv run pytest src/cockpit/tests/test_api_decision_inbox.py src/cockpit/tests/test_api_outcomes.py -q
uv run ruff check src/cockpit/web/api_decision_inbox.py src/cockpit/web/api_outcomes.py \
  src/cockpit/tests/test_api_decision_inbox.py src/cockpit/tests/test_api_outcomes.py
```

---

### Task 6: Child/Root Delivery and Real Human Canary

**Files:**
- OMO child files from Tasks 2-3
- Cockpit child files from Tasks 4-5
- Root pointers: `projects/omo`, `projects/cockpit`
- Coordinator-only completion: `docs/plans/3y-bet-ledger.yaml`
- Coordinator-only retro: `.omo/_knowledge/retros/BET-Y1Q3-T4-07.md`

**Interfaces:**
- Produces: OMO/Cockpit mainline, one real adjudication/outcome, restart observer receipt, and `outcome_accepted` candidate evidence.

- [ ] **Step 1: Merge OMO child, then Cockpit child, then root pointers**

Prove each child merge SHA is on child main before one root-last pointer PR. Run `submodule-reachability-gate.py --source head --fetch --require-main --json`.

- [ ] **Step 2: Present one real Decision Inbox item**

Use a non-test signal/episode/candidate with a current revision. Display only safe lineage fields; record the exact decision and candidate digest shown to the principal.

- [ ] **Step 3: Obtain one real authority-bound verdict**

The authenticated human selects adopt/edit/ignore and supplies measured burden minutes. Record the resulting adjudication/outcome Event Ledger ID, outbox row, authority digest, revision, and timestamp.

- [ ] **Step 4: Restart and re-read**

Restart the reader, call `/api/outcomes/qualifying`, and prove the same single outcome and lineage are returned. Partition all test/synthetic/user-provided/shadow records.

- [ ] **Step 5: Serialize value evidence and cleanup**

Only direct `real_signal`, credential-bound `human_verdict`, `revision`, `time_burden`, authority digest, durable outcome event, and signed human attestation may advance value. Merge completion evidence in a coordinator-only PR, then retire all child/root clones, branches, terminals, and locks. A single outcome proves the path; report long-term value separately.

---

## Self-Review

- Spec coverage: canonical lineage, one-event atomicity, negative partitions, Cockpit delegation/query, restart replay, real canary, child/root delivery, and value evidence are explicit.
- Placeholder scan: test IDs are fixed fixtures; runtime IDs are captured from actual receipts rather than prose placeholders.
- Type consistency: `HumanAdjudication` and `DecisionLineage` are shared OMO types; Cockpit never constructs a caller-supplied principal or second outcome model.
