---
status: active
lifecycle: entry
owner: governance-team
last-reviewed: 2026-09-03
last_updated: 2026-09-03
type: doc
---

# T1-07 Legacy BET Migration Manifest Implementation Plan

**Goal:** Produce a deterministic, read-only classification manifest for every
Ledger BET before any separately authorized migration apply batch.

**Files:**

- Create: `bin/plan/portfolio_migration.py`
- Create: `tests/test_bet_portfolio_migration.py`
- Create: `docs/generated/bet-portfolio-migration-manifest.yaml`

**Authorization gate:** this delivery is manifest-only. No invocation of
`--apply` is authorized here, even if a caller supplies future-looking flags.

### Task 1: Build RED fixtures for immutable inventory

- [x] Fixture a Ledger with terminal, blocked, candidate, malformed and
  non-terminal entries; assert every ID receives exactly one disposition.
- [x] Assert terminal/blocked objects are byte/semantic equal after dry-run;
  assert missing disposition or disallowed migration scope fails with
  `MIGRATION_SCOPE_DRIFT`, and source digest drift fails with
  `PORTFOLIO_CONCURRENT_UPDATE`.
- [x] Assert the exact error partition: unclassified object or disallowed batch
  scope returns `MIGRATION_SCOPE_DRIFT`; source digest drift returns
  `PORTFOLIO_CONCURRENT_UPDATE`; every `--apply` invocation returns
  `MIGRATION_APPLY_NOT_AUTHORIZED` and performs zero mutation. Separately
  assert a request for nine mutations is rejected before any source write.
- [x] Run RED exactly:

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_bet_portfolio_migration.py -q
```

### Task 2: Implement deterministic manifest generation

- [x] Implement `inventory(ledger_bytes)`, `classify(entry)`, and
  `render_manifest(entries, source_digest)` as pure functions.
- [x] Generate one canonical row per ID with disposition, rationale, source
  digest, and no execution/value outcome fields.
- [x] Provide `--dry-run` JSON/YAML output; make `--apply` unconditionally
  reject in this module. A separately authorized migration-batch BET may add
  an apply interface later, but it must not be enabled by this plan.

### Task 3: Verify immutability and repeatability

- [x] Hash the source Ledger and generated manifest twice; assert source bytes
  unchanged and manifest bytes identical.
- [x] Run GREEN exactly:

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_bet_portfolio_migration.py -q
uv run --with pyyaml python bin/plan/portfolio_migration.py --dry-run --json
```

Expected: all IDs occur once, source bytes are unchanged, repeated manifest
hashes match, and every `--apply` test fails without mutation.

### Rollback

Delete the generated manifest and migration code only. No existing BET object
is changed by this BET, so no historical truth rollback exists.
