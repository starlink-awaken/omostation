---
schema: md/v1
status: completed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-26
type: report
title: BET-Y2Q4-T10-203 profile root convergence — closeout receipt
bet_id: BET-Y2Q4-T10-203
created: '2026-09-26'
run_id: 20260926T140133Z-project-code-change-5055000c
---

# BET-Y2Q4-T10-203 Closeout Receipt

## Delivery

- ADR: `.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md` (**PROPOSED** — ratification is a
  principal decision, still open; the code seam shipped under it does not depend on ratification)
- Spec: `docs/superpowers/specs/2026-09-26-dev-runtime-profile-root.md`
  (digest `sha256:6ff35d73f6c454e51af9ead800544163b73c91599a5d0ec34d36f76da47e8a5c`)
- PR: https://github.com/starlink-awaken/omostation/pull/4403 (squash-merged 2026-09-26T14:14:35Z+08:00)
- Merged reachable commit: `git://origin/main@4be9125a0654e45fd3abff61c82e2231aa1d44ff` (parent `3637006ea`)
- Submodule commit: `projects/omo@0790f8977ec3c14bc1878e3f8d5cda968be11889` (cherry-pick of `8b4e80e`
  onto omo `main@c91b203`; root gitlink moved in the same merge)

## Change surface

15 files, +795 / −15:

- `bin/lib/repo_root.py` — the seam becomes two roots: `code_root()` (follows the checkout, unchanged
  behavior) and `state_root()` (reads `OMOSTATION_STATE_ROOT`, **defaults to `code_root()`**), plus
  `event_ledger_path()` which honors `OMO_EVENT_LEDGER_DB` first. `STATE_ROOT_ENV` is the single
  declared variable name.
- `projects/omo/src/omo/omo_paths.py` (+27 / −5) — `STATE_ROOT` / `RUNTIME_OMO_ROOT` / `STATE_DIR` /
  `STATE_SYSTEM_YAML` / `projection_path()` derive from the profile; `OMO_ROOT` / `TRUTH_DIR` /
  `CONTROL_DIR` stay on the checkout. The kernel cannot import the parent repo, so it re-declares the
  same env name — and a test pins the two declarations together.
- 8 event-ledger consumers rerouted through the seam: `bin/bc-os/{north_star_meter_v2,north_star_meter_v3,weekly-value-report}.py`,
  `bin/ssot/{episode-source-aggregator,resident-orchestrator-daemon,system-health-check}.py`,
  `bin/gac/{check-episode-pipeline,compound-attribution-report}.py`.
- `tests/unit/test_repo_root_profile.py` (new, 149L) — the guard that outlives the bet. It replaces the
  enforcement lost when `machine-config-write-lint.py` was archived on 2026-09-20, which is the reason
  the previous seam never spread.
- Ledger registration + ADR-0456 + spec + `decisions/INDEX.md`.

Deliberately excluded (each is a later bet, not an oversight): `.omo/cron/registry.yaml` and
`services.yaml` parameterization (B3), the runtime install relocation and cron/plist cutover (B4),
untracking generated state (B5), the 17 kernel-side ledger defaults under
`projects/omo/src/omo/**` (ADR-0456 §7, principal decision), and `panorama-collect.py`'s independent
root (it deploys as a single file outside any checkout; it does honor `OMO_EVENT_LEDGER_DB` first).

## Verification (engineering axis)

| Check | Command | Result |
|-------|---------|--------|
| Guard suite | `uv run --with pyyaml --with pytest python -m pytest tests/unit/test_repo_root_profile.py -q` | **846 passed** (7 guards; 839 of them are the `bin/**/*.py` parametrized regression sweep) |
| Unset-profile equality | `env -u OMOSTATION_STATE_ROOT -u OMOSTATION_PROFILE -u OMOSTATION_ROOT python3 -c "...omo_paths..."` on merged main | PASS — `STATE_DIR=<root>/.omo/state`, `RUNTIME_OMO_ROOT=<root>/runtime/omo`, `OMO_ROOT=<root>/.omo` |
| Profile redirect | `OMOSTATION_STATE_ROOT=/tmp/omostation-b1-check` | PASS — writes move to the profile root, `OMO_ROOT`/`TRUTH_DIR` reads stay on the checkout |
| Ledger env precedence | `OMO_EVENT_LEDGER_DB=/tmp/xx.sqlite3` | PASS — wins over the profile |
| No forked defaults in `bin/` | `grep -rEn "^(DEFAULT_(EVENT_)?LEDGER\|LEDGER\|DEFAULT_DB) *= *" bin/ \| grep event-ledger` | **0** hits |
| Ledger declared verify | `python3 bin/plan/bet-ledger.py verify BET-Y2Q4-T10-203 --execute` | 5/5 pass |
| Governance gate | `make gac-local-gate` | exit 0 (the gate's own `.omo/state/system.yaml` timestamp rewrite was restored, not committed) |
| CI | PR #4403 | 24 checks pass, 0 fail |

The three path-resolution checks were re-run **post-merge against `origin/main`** in a throwaway
detached worktree, not only against the branch, so the invariants describe shipped state rather than
proposed state.

## Operational axis

- live_canary: production processes were **not** restarted and no cron/plist changed. Because
  `state_root()` defaults to `code_root()`, every running consumer resolves the same absolute path it
  resolved before the merge — the shipped state root for this host is still `/Users/xiamingxing/Workspace`.
  The blast radius of the merge is therefore zero until a profile env is actually declared, which is B4's job.
- fresh_receipt: this report.
- replay: `.omo/_knowledge/retros/BET-Y2Q4-T10-203.md`.
- cleanup: worktrees `ws-devruntime-b1`, `ws-devruntime-b1s`, `ws-devruntime-b1s2`,
  `ws-devruntime-b1s3` (and the successor `ws-devruntime-b1close`) released after this PR merges;
  superseded PRs #4393 / #4397 / #4400 closed with the reason recorded on each; the temporary
  verification worktree `/tmp/b1-maincheck` removed. No lifecycle receipt, SHA or historical state was
  fabricated or backfilled.

## Rollback

`git revert 4be9125a0654e45fd3abff61c82e2231aa1d44ff` restores the pre-change single-root resolution.
Rollback is safe with respect to runtime data: no state file moved on disk under the default profile,
so there is nothing to migrate back. The omo gitlink reverts to `c91b203` in the same commit.

## Boundary notes

- The unset-profile path is the contract that keeps this merge invisible to the running system; the
  guard test fails if anyone makes `state_root()` require an env var.
- Two environment variables are now load-bearing and were previously not honored anywhere outside
  `repo_root`'s own `OMOSTATION_ROOT`: `OMOSTATION_STATE_ROOT`, `OMO_EVENT_LEDGER_DB`.
  `OMOSTATION_PROFILE` was intentionally **not** introduced — it has no consumer until B3/B4.
- `.omo/_delivery/agent-workflows/runs/` is gitignored and per-checkout. The closeout run record was
  relocated from the delivery worktree to its successor worktree so the run started for this BET is the
  one closed; no run was re-started to create a fresher-looking record.
