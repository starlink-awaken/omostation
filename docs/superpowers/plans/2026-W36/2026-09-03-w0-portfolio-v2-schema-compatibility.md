---
status: active
lifecycle: entry
owner: governance-team
last-reviewed: 2026-09-03
last_updated: 2026-09-03
type: doc
---

# T1-04 Portfolio v2 Schema Compatibility Implementation Plan

**Goal:** Add a pure, additive Portfolio v2 validator while preserving every
legacy Ledger object and v1 command behavior.

**Files:**

- Create: `bin/plan/portfolio_contract.py`
- Modify: `bin/plan/bet-ledger.py`
- Create: `tests/test_bet_portfolio_contract.py`

**Interfaces:** `validate_portfolio(ledger: dict, *, strict: bool) ->
PortfolioValidationResult`; it returns typed errors/warnings and never writes.
`bet-ledger.py portfolio lint [--strict]` calls it after legacy lint succeeds.

**Authorization gate:** before Task 1, stop unless a child-specific recorded
implementation authorization has changed the planning-only binding boundary.

### Task 1: Define a pure additive contract

- [ ] Write fixtures in `tests/test_bet_portfolio_contract.py` for a valid
  minimal `vision/objectives/campaigns/milestones/bets` hierarchy and for each
  missing/duplicate ID case.
- [ ] Verify RED with:

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_bet_portfolio_contract.py -q
```

- [ ] Implement immutable helpers in `portfolio_contract.py`:

```python
def validate_portfolio(ledger: dict[str, object], *, strict: bool) -> PortfolioValidationResult:
    """Return typed findings; never mutate ledger or filesystem."""
```

- [ ] Enforce unique IDs, reference existence, enum/boolean/metric shape,
  ISO-8601 timestamp shape,
  required v2 fields for non-terminal v2 BETs, and `parent_bet` ownership
  without adding dependencies.
- [ ] Add malformed and missing timestamp fixtures and assert each receives a
  typed rejection before any compatibility warning or parser fallback is
  considered.
- [ ] Re-run fixtures GREEN and assert the input YAML object equals a deep copy
  after every call.

### Task 2: Stage total-count enforcement correctly

- [ ] Add a compatibility fixture where `meta.total_bets != len(bets)` and
  assert warning `META_TOTAL_BETS_DRIFT`, not an exception.
- [ ] Add strict-fixture RED assertions that the same mismatch yields a typed
  error in `strict=True`.
- [ ] Do **not** change `meta.total_bets` in this PR. Create a separate,
  claimed one-field recovery only after validator merge and fresh authorization.
- [ ] Add `portfolio lint` CLI parsing in `bet-ledger.py`; default mode must
  preserve v1 reads and strict mode must be opt-in until the repair lands.

### Task 3: Guard side effects and compatibility

- [ ] Snapshot a current Ledger’s parsed BET objects before/after validator
  execution and assert semantic equality.
- [ ] Use a temporary working directory and monkeypatch write APIs to prove
  import/validation performs no filesystem writes.
- [ ] Run:

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_bet_portfolio_contract.py -q
uv run --with pyyaml python bin/plan/bet-ledger.py lint
uv run --with pyyaml python bin/plan/bet-ledger.py portfolio lint
```

Expected: all tests pass; strict full-Ledger validation is not enabled by this
planning-only delivery.

### Task 4: Preserve the required follow-on boundaries

- [ ] After the validator PR merges, start a fresh, separately authorized run
  that claims only `docs/plans/3y-bet-ledger.yaml::meta.total_bets`; derive the
  field from the immutable tree’s `len(bets)` and prove every BET block is
  unchanged.
- [ ] Enable strict full-Ledger mode only after that repair merges and GREEN
  checks reproduce on its exact merge SHA.
- [ ] Start a third, separately authorized self-binding amendment that changes
  only the eight W0 `portfolio_binding.schema_state=bootstrap_unenforced`
  declarations and approved v2 portfolio fields to enforced values. The
  four-key `accepted_specifications` binding is immutable and must compare
  byte/semantic equal before and after; likewise status, dependency,
  completion, and value fields must be unchanged. Halt on any difference
  outside the approved `portfolio_binding`/v2 namespace migration.
- [ ] Do not start T1-05/T1-06/T1-08 implementation until the self-binding
  amendment is merged and exact-SHA verified.

### Rollback

Remove only `portfolio_contract.py`, its CLI branch, and its tests if v1
compatibility fails. Never delete v2 data or alter an existing BET object.
