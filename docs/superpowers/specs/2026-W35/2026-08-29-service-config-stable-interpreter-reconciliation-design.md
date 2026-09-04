---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-29
last_updated: 2026-08-28
bet_id: BET-Y1Q3-T10-47
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Service-config stable interpreter reconciliation

## Objective

Make `gen-service-configs.py --check` deterministic across normal Python and
`uv run` environments. The generator must compare against the same stable
interpreter path that produced the installed Workspace-owned plist files.

## Contract

- Prefer an existing fixed Homebrew Python path on this macOS host before
  scanning a caller-controlled PATH; never select uv build, temporary, or
  project virtualenv interpreters.
- Preserve `services.yaml` semantics and all generated service arguments,
  resilience, watch paths, and output paths.
- Do not write, load, unload, or mutate host plist files in this BET.
- `--check --json` must return zero drift under both normal and `uv run`
  invocation environments when the installed plist matches the registry.

## Acceptance

- A focused regression test proves uv-like PATH ordering still selects the
  stable interpreter.
- `gen-service-configs.py --validate --json`, `--check --json`, focused tests,
  and `make gac-local-gate` pass.
- Existing host plist files remain byte-unchanged; the repair is generator-only.
