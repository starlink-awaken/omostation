---
id: ADR-0384
title: Meta-meta governance — rebase-regen automation + gate effectiveness tool + roadmap A1-A3/B1
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-06
type: ssot
---

# 0384 — Meta-Meta Governance Round (PLANNED)

> Parent: ADR-0373..0383 (CI plane + drift noise + closure).
> Strategic shift: from "more mechanisms" to "meta-meta governance" — automate
> the friction cycle (rebase-regen), instrument the existing mechanisms (gate
> effectiveness), and publish a multi-milestone roadmap.

## Context

10 convergence rounds shipped a fully-covered governance plane (rules 136,
surfaces 98, gate 41/41, healthcheck green). Strategic analysis identified
three operational frictions:

1. **Manual rebase cycle eats 30-60% of round time** — M1 sync + capability gen +
   bos-registry sync + ruff fix + ci-surfaces regen + submodules push is the
   same 5-7 step dance every round under concurrent-agent pressure.
2. **Mechanism count is growing** but no signal on which gates actually
   *catch* problems vs which are decorative. Without measurement, the
   registry will keep accumulating useless surface.
3. **Healthcheck has only 1 transient red** (concurrent plans doc) — the
   drift detection plane is now over-instrumented for the steady state.

## Strategy

Three orthogonal deliverables in one round, sized to ship together:

- **A1 rebase-regen** automation (eliminate the manual cycle)
- **A3 residual red cleanup** (close out current state)
- **B1 gate effectiveness tool** (meta-meta: measure the measurer)

Picked intentionally: A1 saves future rounds' time, B1 closes the strategic
loop (first measurement of governance impact), A3 ties off loose end.

## Decision

### D1. A1 — `bin/ssot/rebase-regen.sh` + Makefile target

Single-shot post-rebase regeneration:

```
make rebase-regen
  → check-status-and-stash-if-dirty
  → gac-m1-sync (re-derive from registry)
  → gen-capability-registry (cockpit doc regen)
  → sync-bos-registry (live=file match)
  → gen-help-docs
  → ruff check --fix on bin/ scripts/
  → gac-m1-sync once more (post-ruff)
  → check-mof-capabilities-drift --bump-stats
  → print "staged changes summary"
  → exit 0 if clean, 1 with diff if not
```

Each step is idempotent and individually re-runnable. Never invokes `--apply`
or `--force`. Composes existing tools, no new logic.

Acceptance: round on a stale branch ≤ 1 minute to fully regenerated state.

### D2. A3 — close out the doc-ssot concurrent-plans red

`.omo/standards/doc-ssot-contract.md` + `document-governance.yaml` already
track `docs/plans/` via the 0381 exception budget. Plan:

1. Update SYSTEM-INDEX to reference `docs/plans/` with the B1-P1-LEDGER
   section landing here (look at the actual file content from the
   concurrent phase12/13 round).
2. Reduce the exception budget from 2 → 1 (or close it) once the
   canonical plans doc is moved into the right surface.

### D3. B1 — `bin/_archive/2026-08-conv3/gate-effectiveness.py`

Read `.omo/_knowledge/governance-history.jsonl` (or fallback to
gate-runner output), compute per-gate:

- **last_fired_at**: timestamp of most recent non-zero exit.
- **fired_count_30d**: count of non-zero exits in last 30 days.
- **distinct_messages**: number of distinct stderr/stdout fingerprints.
- **effectiveness_score**: heuristic — `(fired_count_30d / total_runs_30d) × distinctness_factor`.

Output:
- Human-readable table (terminal): name / 30d fires / last fired / score.
- `--json` for cron/dashboard.
- `--threshold N` flag: exits 0 only if all gates have score ≥ N
  (for embedding in gac-local-gate as a slow-burn protection).

Plus `--report --out path.md`: produces a "governance value report" for the
workbook, listing the most and least effective gates with trend arrows.

The mechanism-score registry becomes the first ever meta-meta gate: if
some gate fires ≥ X times / 30 days with Y distinct messages, that's
*good* — it caught real problems. If a gate never fires but exists, that's
*waste* — propose retiring it.

### D4. Roadmap publication — `docs/GOVERNANCE-META-ROADMAP.md`

Concrete multi-milestone plan (publishes ADR-0384 commitment):

| Milestone | Round | Scope |
|-----------|-------|-------|
| M1 (this round) | 0384 | A1, A3, B1 |
| M2 | 0385+ | A2 cron pruner; B2 SSOT healthcheck auto-report |
| M3 | later | C1 drift history → concurrent hot-spot prediction |
| M4 | later | C2 convergence proposal generator (semi-automated ADR draft) |
| M5 | later | C3 governance value report (quarterly executive summary) |

## Consequences

### Positive

- Next round's rebase-regen step: 1 command, ~60s (was 5-7 manual steps,
  15-30 minutes including rebase dance).
- B1 gives the first empirical measurement of which gates earn their
  place — sets up B-series (mechanism governance) work.
- Roadmap publishes the strategic direction so future agents and humans
  have a clear sequence rather than re-deciding per round.

### Negative / Trade-offs

- B1 effectiveness_score is a heuristic, not a measure of ground truth.
  False positives (gate fires due to flaky infra) possible; v1 accepts
  this with the distinct_messages factor to dampen noise.
- A1 rebase-regen assumes existing tools are correct; if `gac-m1-sync`
  itself has bugs, automation amplifies them. Acceptance test against
  a known clean branch is the gate.

## Compliance

- ADR-0106 (GaC): B1 is the first mechanism whose target is the GaC plane
  itself — i.e. meta-meta, compatible with the framework.
- ADR-0379/0380 (CI plane): B1 reads gate output (compatible with runner).
- ADR-0203: requirement iteration; workflow run registered.
- ADR-0220 D1: claim `round-0384`.

## Verification

```bash
# A1
make rebase-regen                           # exits 0, ~60s, clean tree
diff <(git status --porcelain) <(echo -n "")  # empty

# A3
python3 bin/ssot/doc-ssot-lint.py            # 0 conflicts
python3 bin/gac/gac-healthcheck.py           # 全绿

# B1
python3 bin/_archive/2026-08-conv3/gate-effectiveness.py         # top 5 + bottom 5 table
python3 bin/_archive/2026-08-conv3/gate-effectiveness.py --json | jq '.gates | length'
# ≥ 41 (all gates), with score ≥ 0 on at least the actively-firing ones

# 全量
make gac-local-gate                          # PASS
```
