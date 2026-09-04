---
lifecycle: entry
owner: governance-team
last_updated: 2026-09-03
last_updated: 2026-09-03
type: doc
---

# T1-08 Portfolio Projection Implementation Plan

**Goal:** Produce deterministic, one-way Objective/KR/Milestone projections
from Ledger truth, using the registered broker for OMO-owned destinations.

**Files:**

- Create: `bin/plan/portfolio_projection.py`
- Modify: `bin/plan/bet-ledger.py`
- Create: `tests/test_bet_portfolio_projection.py`
- Create: `docs/plans/3Y-BET-PORTFOLIO.md`

**Authorization gate:** implementation requires a distinct T1-08
authorization. Before code starts, a read-only ownership discovery must prove
an existing registered broker can own both `.omo/goals/current.yaml` and
`.omo/_control/portfolio-status.json`; otherwise halt and submit a separate
broker-registration/kernel amendment rather than adding a direct writer.

### Task 1: RED projection fixtures

- [ ] Fixture a minimal validated portfolio and assert all three outputs carry
  one identical Ledger SHA-256.
- [ ] Add negative cases for a one-byte output drift, stale/missing source,
  direct `.omo` write attempt, and reverse Ledger mutation request.
- [ ] Assert missing input yields explicit `unavailable`, never inferred
  completion or a synthetic default.
- [ ] Add a broker-failure fixture with known prior digest-bound bytes at both
  governed destinations; assert failure leaves both byte sequences intact and
  returns `unavailable` to the consumer.
- [ ] Run RED exactly:

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_bet_portfolio_projection.py -q
```

### Task 2: Implement pure renderers

- [ ] Implement canonical byte renderers for Goals payload, Markdown, and
  control JSON; their common input is a parsed Ledger plus source digest.
- [ ] Make `--check` compare expected bytes/digests without writing.
- [ ] First run the registered broker discovery/dry-run command selected from
  current OMO ownership metadata and record its exact target set. If it does
  not own both destinations, halt with `PORTFOLIO_BROKER_OWNER_MISSING`; do not
  create a broker, registry entry, or direct writer in this child.
- [ ] The current `omo state sync` / `omo_ingress_state.sync_state_projection`
  path is known to own health/system/brief/governance-data rather than
  `portfolio-status`. Therefore the expected first result is a halt and a
  read-only impact discovery. A later broker-surface amendment must separately
  authorize and claim the exact OMO child paths
  `projects/omo/src/omo/omo_ingress_state.py`,
  `projects/omo/src/omo/omo_state.py`, and
  `projects/omo/tests/test_omo_ingress_state.py`, plus root registry paths
  `.omo/_truth/registry/runtime-projections.yaml` and
  `.omo/_truth/registry/mutation-surfaces.yaml`, before either governed target
  can be registered.
- [ ] The broker amendment must deliver OMO child-first, merge/tag its child
  PR, and then use a standalone root-last `projects/omo` gitlink PR. This plan
  claims none of those paths and must not imply they are already authorized.
- [ ] That amendment must add a dry-run command returning both target paths,
  a single source digest, and an all-or-nothing apply receipt; without it this
  child may generate only the repository Markdown projection and must leave
  both `.omo` targets unavailable.
- [ ] Keep Markdown apply inside the explicit repository path; route Goals and
  control JSON only through the proved registered OMO state/projection broker.

### Task 3: Broker boundary and replay tests

- [ ] Monkeypatch `Path.write_text`/`open` for OMO paths and prove the
  generator cannot bypass the broker.
- [ ] Render each fixture twice and assert byte equality; corrupt one output
  and assert `PROJECTION_DRIFT`.
- [ ] Run GREEN exactly after a legal broker is proved:

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_bet_portfolio_projection.py -q
uv run --with pyyaml python bin/plan/portfolio_projection.py --check
uv run --with pyyaml python bin/plan/bet-ledger.py lint
```

Expected: replayed outputs are byte-identical, corrupted output fails
`PROJECTION_DRIFT`, and injected broker failure preserves prior bytes.

### Rollback

Restore or remove generated projections from their source digest. Never write
back into Ledger or alter completion/value evidence.
