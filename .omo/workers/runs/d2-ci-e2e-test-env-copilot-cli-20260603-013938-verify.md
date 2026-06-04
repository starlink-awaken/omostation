# D2-CI-E2E-TEST-ENV verification note

- verifier: copilot-cli
- verified_at: 2026-06-03T01:39:38Z
- command: `cd projects/kairon && make test-e2e-core`
- result: passed

## Outcome

The local containerized core E2E path now passes after aligning the runner with the repo's uv/package model.

## What changed

1. The E2E runner image now builds a dedicated ontoderive/core-models uv environment instead of relying on a partial workspace sync.
2. The compose harness no longer exposes PostgreSQL on a host port, avoiding local port-collision failures.
3. The ontoderive smoke path now writes `_derivation_logs` into a container-scoped writable volume while leaving the source tree read-only.
4. The local `test-e2e-core` target now rebuilds the runner image before execution, so it validates the current harness changes instead of a stale image.

## Coordinator judgment

- D2 is back to `review`.
- The remaining gap is CI confirmation of the updated workflow job; local core verification is now green.
