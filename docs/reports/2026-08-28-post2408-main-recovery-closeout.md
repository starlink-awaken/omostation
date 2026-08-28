# Post-2408 Main Recovery — R1 evidence

## Immutable baseline

- GitHub main: `591540105c446b44faab0b185bd33ae1ea58586a`
- Delivery attempt: `20260828T081618Z-bet-execution-7729bcb6`
- Scope: repository recovery only; no host or submodule pointer mutation.

## R1 repairs

The execution-time failure set was rechecked against the canonical main:

- script registry and baseline are already aligned at `519/519`;
- ADR-0432 is restored as `candidate` with `UNPROVABLE` evidence status and
  indexed exactly once;
- the unreferenced tracked empty `bin/INDEX.md` and
  `runtime/heartbeats/weijian-daily-health` are removed from the final tree.

## Verification

Compile, full conflict scan, registry validation, ADR coverage, tracked hygiene,
diff check and repository-side strict GaC pass under the standard PyYAML runner.
The local-only service-config drift check remains external host evidence and is
not changed by this repository PR.

H1/H1c and R2 remain gated on main integration and their own receipts.
