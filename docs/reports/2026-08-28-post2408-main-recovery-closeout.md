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

## Gate disposition

Repository-side R1 checks pass, including registry `519/519`, ADR coverage,
tracked hygiene, root directory governance, compile, conflict scan and diff
check. Strict gate remains blocked by the pre-existing document-governance
warning budget: 104 legacy frontmatter/metadata warnings, with
`legacy-omo-truth-frontmatter` observed at 3 against a budget of 2. Historical
BET completion evidence also has 37 pre-existing digest/state mismatches.
Neither issue is corrected by raising a budget or rewriting evidence in this
R1 packet.

H1/H1c and R2 remain gated on resolution/accepted disposition of these mainline
debts and their own receipts. Local host retention remains `UNPROVABLE`.
