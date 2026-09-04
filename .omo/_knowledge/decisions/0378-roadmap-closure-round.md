---
id: ADR-0378
title: Roadmap closure round — verify and close all delivered governance initiatives
status: ACCEPTED
lifecycle: spec
owner: governance-team
last_updated: 2026-08-05
---

# 0378 — Roadmap Closure Round (R-archive)

> Parent: ADR-0373..0377 (convergence rounds), ADR-0367 (sweep tooling).
> The governance-evolution roadmap SSOT listed 8 initiatives as
> `active` although every acceptance criterion was already delivered.
> This round verifies each one with its executable verifier, flips them
> to `done` with closure evidence, and adds a validator guard so a
> `done` initiative can never again be closed without a written record.

## Context

`gac-healthcheck` and `make gac-local-gate` have been fully green since
ADR-0377 (16/16 checks, 39/39 gates, debts 9/9 resolved). The remaining
stale surface was the roadmap registry itself:
`.omo/_truth/registry/governance-evolution-roadmap.yaml` still reported
`8 active / 1 done`, but the 8 "active" initiatives were delivered —
several by the ADR-0373..0377 convergence rounds (e.g. release
packaging by ADR-0377 G12, sweep tooling by ADR-0373), others by
earlier P-series work (cockpit governance command, BOS governance
routes, claim policy tiers).

A roadmap that says "active" for delivered work is SSOT drift: the
status dashboard and `next_active` list keep telling agents there is
work to do, and future closure rounds have no written record of what
was verified when.

## Decision

### D1. G13 — Verify each active initiative against its acceptance

Executed the acceptance verifiers for all 8 active initiatives in a
clean worktree:

| Initiative | Key verifier | Result |
|-----------|--------------|--------|
| worktree-release-convergence | `governance-evolution.py packages --json` | ok=true, unknown=0, release_ready=true |
| cockpit-governance-status-plane | `commands/governance.py` + cli delegation | exists, delegate wired |
| claim-policy-tiering | `agent-workflows.yaml` claim_policy tiers | core-governance-required tier present |
| bos-governance-evolution-routes | bos-services.yaml 6 routes + test asserts 7 | present |
| capability-traceability | `traces --json` | 6 traces with verifier |
| governance-operating-rhythm | roadmap operating_rhythm | daily/weekly/pre_release commands |
| golden-path-e2e | `golden-paths --json` | 4 paths; validator enforces structure |
| entrypoint-convergence | roadmap entrypoints.human | `cockpit governance evolution` |

8/8 PASS.

### D2. G14 — Flip delivered initiatives to done with closure evidence

All 8 initiatives get `status: done` plus a `closure` mapping
(`adr: ADR-0378`, `verified`, `verifier`, `note`). The pre-existing
`sweep-tooling-scaling` (done) gets its missing `closure` (ADR-0373)
for consistency. Roadmap now reports `9 done / 0 active`.

### D3. G15 — Validator guard: done requires closure

`validate_roadmap` now emits an error when `status: done` without a
`closure` field, so a delivered-but-unclosed initiative is a red gate
item, not a silent drift. Two regression tests lock the behavior
(`test_validate_done_initiative_requires_closure` /
`test_validate_done_initiative_with_closure_passes`).

## Consequences

### Positive

- Roadmap SSOT matches reality: `status` dashboard shows 9 done, 0
  active; `next_active` is empty.
- Every closure is now machine-checkable evidence (ADR + date +
  verifier), so a future audit can reconstruct when and how each
  initiative was closed.
- The G15 guard turns "close initiatives" into a gated operation:
  forgetting the closure record is a validate error in CI.

### Negative / Trade-offs

- `closure` evidence is self-reported (the verifier commands are the
  evidence, but the note text is prose). Acceptable: the acceptance
  verifiers remain executable and are the objective part.
- Roadmap `status` no longer distinguishes "active but not yet
  started" from "planned"; with 0 active items the distinction is
  moot, and new initiatives enter as `planned`/`in_progress`.

## Compliance

- ADR-0367: sweep-tooling-scaling closure now recorded (was done
  without evidence).
- ADR-0373..0377: the convergence-round family is reflected in the
  roadmap as closed initiatives with ADR references.
- ADR-0203: requirement iteration; workflow run registered with path
  coverage.
- ADR-0220 D1: claim `round-0378` (deleted after merge).

## Verification

```bash
# D1/D2 — roadmap closed, validate green
python3 bin/gac/governance-evolution.py validate --json
#   {"ok": true, "errors": []}
python3 bin/gac/governance-evolution.py status --json
#   by_status: {"done": 9}, next_active: []

# D3 — guard tests
python3 -m pytest tests/test_governance_evolution.py -q
#   19 passed

# 全量
make gac-local-gate
python3 bin/gac/gac-healthcheck.py
```
