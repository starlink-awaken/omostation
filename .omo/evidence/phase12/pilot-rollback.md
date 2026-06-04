# Phase 12 pilot rollback notes

> Pilot: `LiteLLM -> agentmesh Gateway`
> Mode: dry-run evidence only

## Rollback

1. Remove or disable `.omo/registry/pilot-contract.yaml`.
2. Keep existing provider routing unchanged.
3. Re-run `scripts/omo pkg sync --dry-run` and confirm `mutations_applied: 0`.
4. Re-run `scripts/omo scenario trace --scenario .omo/scenarios/research-pipeline.yaml --output .omo/evidence/phase12/research-pipeline-trace.yaml`.

## Current result

No live provider routing mutation was applied in Phase 12. Rollback is therefore a metadata disable path.
