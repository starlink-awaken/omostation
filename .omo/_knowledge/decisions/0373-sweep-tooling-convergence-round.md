---
id: ADR-0373
title: Sweep-tooling Convergence — A4 / C5 / D3 / B2 / E2 plus GaC iteration
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-05
type: ssot
---

# 0373 — Sweep-tooling Convergence Round

> Parent: ADR-0367 (sweep-tooling-scaling roadmap, status=done).
> Roadmap slot: `governance-evolution-roadmap.yaml::sweep-tooling-scaling` follow-up.
> Dependency: ADR-0203 (requirement iterations), ADR-0211 (P74 silence policy).

## Context

ADR-0367 shipped the three Phase 1–3 commits and rendered the
`sweep-tooling-scaling` roadmap initiative `done (progress=100)` with all
gate scopes green. The roadmap's `next_step` already enumerated five
follow-ups that were punted at the time:

1. **A4** `bin/sweep/scan.py --diff-mode` — only scan packages touched
   by a PR instead of sweeping all 14 Python projects end-to-end.
2. **C5** `.omo/_knowledge/sweeps/INDEX.md` auto-maintenance —
   eliminate hand-maintained table that already drifted after the first
   baseline (manual edit gets out of sync with `<date>.json` payloads).
3. **D3** Push `adr-frontmatter-backfill` into the strict CI lane so a
   new ADR file without an `id:` is treated as a merge blocker instead
   of being silently fixed in a follow-up PR.
4. **B2** `cleanup_claim_marker` is currently covered by static text
   greps; expand `tests/test_gac_worktree_lifecycle.py` to actually
   send `INT`/`TERM` (and the SIGHUP/HUP paths from
   `bash 3.0`'s `kill -TRAP`) to a controlled subprocess and assert
   the marker is removed.
5. **E2** Subagent hooks — wire the sweep-check tool into
   `bin/agent-workflow.py start` so a session that touches
   `bin/sweep/**` or `projects/*/pyrightconfig.json` runs one final
   baseline, instead of relying on humans to remember.

Each of these is a real P74 (常态化) gap — every one was reasoned out
during ADR-0367 but never made the gate. This round closes them in a
single coordinated ADR so that:

- The implementations share one architectural frame: scan.py owns the
  sweep surface, sweep-index.py owns the history projection, the
  `diff_check` extends naturally to cover both, the closeout hook
  reuses the existing `append_ledger_event` channel, and the GaC
  registration rule stays consistent with the 5-source pattern from
  PR #60.
- The governance evolution registry learns one new SSOT field
  (`convergence_provenance`) that ties each roadmap initiative to
  its successor initiative, instead of letting each follow-up appear
  ad-hoc.

## Decision

### D1. Single-PR, single-ADR convergence (closes A4/C5/D3/B2/E2 + 2 GaC rule iterations)

| Direction | Touched surface | Mechanism |
|-----------|-----------------|-----------|
| **A4** `scan.py --diff-mode [--strict]` | `bin/sweep/scan.py` | `git diff --name-only origin/main..HEAD` intersected with `projects/*/pyproject.toml` discover sets the project list. `--strict` upgrades the suppression gate to exit 1 when any `file_suppressions > 0` (per-package), regardless of `suppression_ratio`. |
| **C5** Sweep history projection | `bin/sweep/sweep_index.py` + `scan.py` | Separate CLI that materializes `.omo/_knowledge/sweeps/INDEX.md` from the existing `<date>.json` payloads. `--write` mutates the file in place; `--check` exits 1 on drift; default is dry-run. `scan.py` runs `sweep_index.py --write` after every successful `--date` (no `--no-index` escape hatch). |
| **D3** `adr-frontmatter-backfill --strict` | `bin/adr/adr-frontmatter-backfill.py` + `.github/workflows/pyright-sweep.yml` | `--strict` exits 1 on any change *needed* (id missing or mismatched) — same idempotent semantics as default, but as a CI gate. Existing `adr-coverage` already flags id mismatches; `--strict` adds the missing case to the same gate. PR pushes that add new ADRs without `id:` are now merge-blocked. |
| **B2** Real-signal `cleanup_claim_marker` traps | `tests/test_gac_worktree_lifecycle.py` + `tests/test_gac_worktree_trap.sh` | Spawn `bash bin/gac/gac-worktree.sh claim <session>` as a subprocess, wait for the marker to appear, then `os.kill(pid, SIGINT)` and assert the marker is removed within 1s. Repeat for `SIGTERM`. SIGHUP is covered by Python's default behavior of exiting the interpreter on SIGHUP in a foreground process; we **document that as the expected path** (we are not changing `gac-worktree.sh` semantics, only test coverage). |
| **E2** Subagent closeout sweep hook | `projects/omo/src/omo/workflow/lifecycle.py` + `bin/agent-workflow.py` | Append a `agent_workflow_close` event with `event="sweep-closeout"` *and* call `bin/sweep/scan.py --diff-mode --strict` when the touched path set intersects `bin/sweep/**`, `projects/*/pyrightconfig.json`, or `.omo/_knowledge/sweeps/**`. Add the new command as a `closeout_required` field on the `pyright-sweep` workflow profile. The hook is **fail-soft in local**, **fail-hard in CI** — `AGENT_WORKFLOW_SWEEP_FAIL_HARD=1` controls it. |

### D2. Governance rule / registry iteration

| Iteration | Justification |
|-----------|---------------|
| **CR-SWEEP-INDEX-AUTO** added to `governance-checks.yaml::gac.rules` | New rule: `sweeps/INDEX.md` must match `bin/sweep/sweep_index.py --check` output. Executor: `bin/sweep/sweep_index.py --check`. Path set: `.omo/_knowledge/sweeps/**`. Severity: `warn` by default, promotes to `error` when the strict diff_check touches `bin/sweep/**`. Registers in `bin/gac-drift.py::EXECUTOR_PRESENCE` and `bin/gac-executor.py::EXECUTOR_PRESENCE` (5-source align, ADR-0106). |
| **`pyright-sweep-check` paths expansion** in `agent-workflows.yaml::diff_checks` | Add `.omo/_knowledge/sweeps/**` so the existing diff_check covers both A4 and C5. Same required=true. |
| **`convergence_provenance` field** on `governance-evolution-roadmap.yaml` | Each initiative may record `supersedes: <id>` / `succeeded_by: <id>` to link parent/child rounds. The first user is `sweep-tooling-scaling → sweep-tooling-convergence`. Validated by `governance-evolution.py validate` (no schema break — new optional field). |

### D3. Architectural frame (one narrative, five files)

- **One entrypoint**: `bin/sweep/scan.py` becomes the *only* CLI humans
  invoke. `sweep_index.py` is the library + module that `scan.py` shells
  into (or imports for `--check` mode).
- **One metric vocabulary**: `errors / line_suppressions /
  file_suppressions / suppression_ratio` (per ADR-0366 §P91). New
  fields (`diff_projects`, `strict_violations`) extend the existing
  payload, never replace it.
- **One history surface**: `.omo/_knowledge/sweeps/<date>.json` is
  the only writable artifact; `.omo/_knowledge/sweeps/INDEX.md` is
  derived (regenerated) — never manually edited.
- **One subagent hook shape**: every `close_run` call now produces a
  `sweep-closeout` event in `events.jsonl`, regardless of whether the
  surface intersects sweep scope. Subscribers (`bin/sweep/scan.py` /
  external scripts) filter by path set inside their own code.

### D4. Out-of-scope (explicit)

- **A5 sweep history dashboard** (already done in ADR-0367 Phase 3).
  This round does not change `bin/sweep/scan.py`'s JSON shape.
- **Refactor bin/sweep/pyright.py** beyond the existing
  `--suppression-gate` flag. ADR-0366 already locks its semantics.
- **Cockpit/MCP exposure** of sweep metrics. Out of ADR-0367's
  surface; left for the L3 entry initiative.
- **CI hardening of `.github/workflows/pyright-sweep.yml`** beyond
  adding the `--strict` switch on the `adr-backfill` step. Workflow
  cron schedule stays weekly; ad-hoc dispatch unchanged.

## Consequences

### Positive

- **CI is now safe-by-default against new ADR drift**: a contributor
  adding `0369-foo.md` without `id:` fails `bin/adr/adr-frontmatter-backfill.py --strict` in the `pyright-sweep.yml` strict lane, instead of being discovered weeks later in `adr-coverage.py` (P74 detection latency drops from weeks to minutes).
- **Sweep history is now first-class**: `INDEX.md` no longer relies on
  a human copy-pasting new baselines into a markdown table. Tests assert
  the projection is reproducible.
- **A4 diff-mode shrinks the manual sweep cost** from ~14 projects
  per agent session to ~1–3 changed projects per session. The gate
  speedup is at least 4x on a typical PR.
- **B2 finally proves the trap works under real signals**, not just
  text-match greps. The current `tests/test_gac_worktree_lifecycle.py` is
  smoke-test only; INT/TERM coverage was filed as future work in PR #971.
- **E2 turns sweep into a `closeout_required`** for the
  `pyright-sweep` workflow — no more silent deferral.

### Negative / Trade-offs

- **Two new executables** (`sweep_index.py`, `bin/gac/gac-executor.py`
  extension) require updating the 5-source executor enum. Mitigated
  by following the `governance-ssot-edit` skill's checklist (verified
  by the test in `tests/test_sweep_index.py` that gates the executor
  enum).
- **`bin/agent-workflow.py` close path grows ~20 lines**. Tests in
  `tests/test_agent_workflow.py` already cover `agent_workflow_close`
  events; we extend fixtures, not assertions.
- **E2 introduces a `closeout_required` that fires even for
  hand-curated baselines** (e.g. ad-hoc `sweep --projects <one>`).
  Failure is fail-soft locally; only CI promotes to blocking.
- **`.omo/_knowledge/sweeps/INDEX.md` historical entries are
  regenerated**. The single pre-existing row (`2026-08-04.json` →
  manual row) becomes machine-generated, identical content.

## Compliance

- ADR-0203: this ADR is itself a requirement iteration. The workflow
  run is `20260805T010408Z-pyright-sweep-2bd6f8f3` with full path
  coverage (see Claim section in the run yaml).
- ADR-0211 §D1 (P74 silence detection): closeout events
  (`agent_workflow_close`, `sweep-closeout`) feed
  `p74_solidification_report` so a silent `pyright-sweep` workflow is
  surfaced in 7d instead of 30d.
- ADR-0106 (GaC 5-source): `EXECUTOR_ENUM`, `EXECUTOR_PRESENCE`, and
  the rule's `executor` field all align through `gac-m1-sync.py
  --sync`.
- ADR-0292 (M3 grace baseline cap): the new rule bumps `cap` by 1; the
  handshake with `bin/gac/check-work-landed.py` is unchanged.

## Verification

```bash
# Run after merge:
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_sweep_tools.py tests/test_sweep_index.py \
  tests/test_gac_worktree_lifecycle.py tests/test_adr_frontmatter_backfill.py \
  -q

# Re-derive INDEX.md and assert identical to committed version:
python3 bin/sweep/sweep_index.py --check

# Verify the agent-workflow closeout hook fires:
uv run --with pyyaml python bin/agent-workflow.py start pyright-sweep \
  --profile governance-agent --objective "smoke E2 hook" --dry-run --json
```

Done when: A4/C5/D3/B2/E2 implemented, all gates green,
`adr-coverage.py` reports `id_mismatches=0`, `INDEX.md` regenerates
to identical content, `executor_enum` drift = 0.
