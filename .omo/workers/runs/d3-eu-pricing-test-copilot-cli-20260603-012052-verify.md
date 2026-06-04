# D3-EU-PRICING-TEST verification note

- verifier: copilot-cli
- verified_at: 2026-06-03T01:20:52Z
- command: `cd projects/kairon/packages/eu-pricing && uv run pytest tests/ -q --tb=short`
- result: failed

## Outcome

The eu-pricing test suite runs, but the package is not yet review-ready because the current implementation still fails 10 tests.

## Failure highlights

1. CLI behavior mismatch: `test_main_handles_bad_subcommand` currently exits via `SystemExit: 2`.
2. Ledger semantics regressions: starvation, closed-ledger leverage, ref-id propagation, and query-by-ref assertions are failing.
3. Reliability regressions: `record_llm_cost` hits `sqlite3.OperationalError: no such table: eu_ledger`.
4. Reputation decay tests show precision drift (`0.9999999999...` instead of `1.0`).

## Coordinator judgment

- Task remains in active execution, not review.
- Next implementation slice should reconcile the ledger and CLI behavior with the existing package test contract.
