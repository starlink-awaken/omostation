# CLI unification plan

> Status: active
> Phase: 12 Wave 1

---

## Decision

`scripts/omo` remains the governance entrypoint and delegates Phase 12 ecosystem commands to `scripts/omo_capability.py`.

## Command tree

```text
omo capability scan --write
omo capability register <capabilities.yaml>
omo capability discover [--type TYPE] [--tag TAG]
omo capability bind --scenario .omo/scenarios/research-pipeline.yaml
omo registry browse
omo scenario trace --scenario .omo/scenarios/research-pipeline.yaml --output .omo/evidence/phase12/research-pipeline-trace.yaml
omo pkg sync --dry-run --output .omo/evidence/phase12/package-dry-run.yaml
```

## Migration path

- Keep existing worker commands routed to `omo_worker.py`.
- Route only `capability`, `registry`, `scenario`, and `pkg` to the Phase 12 capability module.
- Do not replace project-specific CLIs in Phase 12.
- Defer broader `wksp` CLI convergence to a later phase after registry evidence proves value.
