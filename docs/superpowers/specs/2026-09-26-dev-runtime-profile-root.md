---
schema_version: specification/v1
spec_version: 1.0.0
title: Dev/Runtime Profile Root Convergence (B1)
bet_id: BET-Y2Q4-T10-203
status: accepted
lifecycle: contract
last-reviewed: 2026-09-26
adr: ADR-0456
---

# B1 — Dev/Runtime Profile Root Convergence

## Problem

`/Users/xiamingxing/Workspace` is simultaneously the development checkout and the runtime
deployment. Measured on 2026-09-26: 43 of 56 `~/Library/LaunchAgents` plists, ~40 crontab
entries and 20+ live daemons execute from the git working copy, so a `git worktree` branch
switch pulls code out from under running processes.

The workspace cannot be relocated until the *root* is a parameter instead of a fact. Two
resolvers exist and have forked:

- `bin/lib/repo_root.py:canonical_root()` resolves `$OMOSTATION_ROOT → ~/Workspace → raise`,
  and its docstring records the shared root cause of two 2026-08-08 incidents: tools that
  write machine-level config must use it rather than deriving from `__file__`.
- `projects/omo/src/omo/omo_paths.py` is the one central module that ignores it:
  `WORKSPACE_ROOT = _MODULE_DIR.parents[3]`, from which `OMO_ROOT`, `TRUTH_DIR`, `STATE_DIR`
  and `RUNTIME_OMO_ROOT` all derive.

Measured adoption of the seam is near zero: exactly **one** live consumer
(`bin/gac/install-watch-agent.py:18`), and the lint that enforced the rule
(`bin/_archive/2026-09-20-b2-archive/machine-config-write-lint.py`, advice text
`是 → 改用 bin/lib/repo_root.canonical_root()`) was archived on 2026-09-20. That is why the seam
never spread. B1 therefore has to *adopt* the seam and leave a guard behind that outlives the
bet — not merely converge two existing callers.

Nine sites additionally compute the event-ledger default path independently. Separately,
`.omo/cron/registry.yaml` — a **tracked** SSOT — carries 24 `/Users/xiamingxing/…` literals,
and `tests/unit/test_agent_cell_scheduler.py` (5) and `tests/unit/test_panorama_runtime_scheduler.py`
(8) assert them, pinning the suite to this machine. Those literals describe installed launchd
jobs, so they are B3's surface (service registration and label namespacing), not B1's; B1
records them as measured evidence and leaves them alone.

A second, larger fork surfaced while implementing: **31 occurrences across 17 files inside the
governance kernel** resolve the workspace as
`os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace"))` — a host literal, not the
checkout (`omo_event.py:18`, `event_ledger/surface.py:37`, `omo_bos.py:43,92`,
`omo_alert.py:28`, `omo_sync.py:28`, `omo_trail.py:46`, `cli.py:13`, `sovereignty/enforcement.py:119`,
and the rest). Two of them are ledger defaults, which makes the kernel's own ledger writer the
one producer B1 cannot move without a principal decision — see *Consequence* below.

## Requirement

Separate the two roots and converge every consumer onto one seam, with **no behavior change
for the current single-install production layout**.

1. **code_root follows the checkout.** Derived from `__file__`; this is what keeps a
   development checkout runnable at any time, which is a hard constraint of ADR-0456.
2. **state_root is profile-declared.** Resolved by `bin/lib/repo_root.py` from
   `OMOSTATION_STATE_ROOT`, defaulting to the current in-repo locations so that an unset
   profile reproduces today's paths byte-for-byte.
3. **One contract, no parallel mechanism.** `OMOSTATION_ROOT` (already existing),
   `OMOSTATION_STATE_ROOT` (new) and the already-canonical `OMO_EVENT_LEDGER_DB`
   (`projects/omo/src/omo/sovereignty/enforcement.py:106`) are the whole delivered surface.
   Existing env-var seams are folded in, not duplicated. `OMOSTATION_PROFILE` — which names an
   install so that launchd labels and port bands can be namespace-prefixed — is **not**
   introduced here: it has no consumer until B3/B4, and a variable nobody reads is a second
   fork waiting to happen.
4. **`omo_paths` honors the profile without moving the read side.** `OMO_ROOT`, `TRUTH_DIR`,
   `CONTROL_DIR` and every `_truth/registry/**` path stay derived from code_root — they are
   *reads of repo-internal governance files*, and the `repo_root.py` docstring's own rule says
   those must follow the current checkout. Repointing them would make a worktree resolve the
   registry out of the main workspace, which is a behavior change no operator asked for.
   Only the write targets move: `STATE_DIR`, `STATE_SYSTEM_YAML` and `RUNTIME_OMO_ROOT` derive
   from `state_root`, and in `projection_path()` the canonical side follows `state_root` while
   the legacy side stays on code_root so a dev profile can still read the committed file.
   `STATE_ROOT_ENV` is declared a second time inside the package rather than imported from
   `bin/lib`, because `projects/omo` is a submodule and must not depend on parent-repo files;
   the guard test pins both declarations to the same string.
5. **The duplicated ledger defaults route through the seam**, each honoring
   `OMO_EVENT_LEDGER_DB` first. Eight of the nine are converted. The ninth,
   `bin/panorama/panorama-collect.py:70`, is deliberately **not** converted, for three measured
   reasons: its root is already env-overridable (`PANORAMA_ROOT`, set by two installed plists),
   it is deployed as a single file outside any checkout
   (`~/.local/share/zhixing-dashboard/`) where a `bin/lib` import would fail at startup, and
   `docs/plans/3y-bet-ledger.yaml:31518` requires it to stay byte-identical to
   `bin/panorama/assets/host/panorama-collect-main.py.asset`. It already honors
   `OMO_EVENT_LEDGER_DB` first, so the canonical env name keeps working; the guard test accepts
   that as the one legitimate non-seam form.
6. **A guard outlives the bet.** Because the previous enforcement lint was archived and the
   seam decayed to one consumer, a regression test must fail if any `bin/` script re-introduces
   a hard-coded `runtime/omo/event-ledger` default. The guard is a test, not a new `bin/`
   script (script quota). It detects path concatenation through the AST, so comments, error
   strings and `repo://` URIs mentioning the file do not count — and it was mutation-checked
   against all three forms.

## Consequence the kernel fork is left open for

Routing `event_ledger/surface.py:_default_db_path()` and
`sovereignty/enforcement.py:_default_db_path()` through `state_root` is mechanically a
two-line change, and it is what would finally stop development actions from writing
production state. B1 does not make it, because that writer is the closeout → scene bridge
that produces governed evidence: `bin/ssot/scene-outcome-recorder.py` reaches the ledger
*only* through `omo.event_ledger.surface._resolve_db_path()`, so moving it changes where agent
closeouts land episodes whenever they run from a worktree — i.e. it changes the authority
chain that BET-Y2Q4-SH-5 depends on. That is a principal decision, not a seam detail.

The alternative that removes the host literal without moving evidence is to have the producer
jobs declare `OMO_EVENT_LEDGER_DB` explicitly (prod → the canonical file, dev → its own),
which belongs to B3's service-registration surface, and to retire the `home()/Workspace`
fallback only after every producer declares it.

## Non-goals

- `OMO_PRINCIPAL_ID` and `BRIEF.md` generation — owned by the concurrent brief-generation
  delivery (PR #4376), which also touches `docs/plans/3y-bet-ledger.yaml` and `Makefile`.
- Runtime install placement, cron/plist cutover, state migration (`sqlite3 ".backup"`),
  launchd label namespacing and port bands — B2/B3/B4 of ADR-0456.
- Untracking generated state (`.omo/state/**`) via ADR-0129 canonical projections — B5.
- Adding a new entrypoint script under `bin/` — `bin/` caps net-new scripts
  (`check-bin-quota-diff.py`); operator entrypoints go in the `Makefile`.
- Parameterizing `.omo/cron/registry.yaml` (24 host literals) or the two scheduler tests that
  assert it. That registry is the source of installed launchd job content, so changing it is
  B3's service-registration surface with its own set-equality gate — not a root-seam change.
- Declaring `~/.local/share/zhixing-dashboard` as an external dependency with a
  `ZHIXING_DASHBOARD_ROOT` contract — ADR-0456 decision 5, tracked separately.

## Design notes

`repo_root.py` stays the resolver's home for two measured reasons: it is pure stdlib and
already importable from `bin/` scripts through the established
`sys.path.insert(0, parents[1] / "lib")` pattern, and it lives outside the `projects/omo`
submodule, so the bulk of the work avoids the three-step submodule commit dance and the
submodule edit is confined to one env-honoring change. The contract is carried by environment
variables, which is also the only shape that works across the code-root/state-root boundary in
both directions.

Note that `bin/` scripts cannot import `omo_paths` at module scope today — only
`bin/ssot/system-health-check.py:86` reaches `projects/omo/src` at all, and it does so lazily
inside a function. That is part of why each script recomputes the path; the seam must be
importable without pulling the governance kernel into every cron script.

Rejecting "share the ledger file between the two profiles": `fcntl` locks are per-path, so
two installs pointing at one file contend while two installs pointing at different files get
no mutual exclusion at all. Dev therefore gets its own (initially empty) store; prod stays
the single writer. That is the only shape in which "dev always runs" and "no double-write"
hold simultaneously.

One defect surfaced while touching `projection_path()`: it parsed
`.omo/_truth/registry/runtime-projections.yaml` with `yaml.safe_load`, but that registry
carries YAML frontmatter, so it is a two-document stream and **every** call raised
`ComposerError`. Reproduced on the pre-change checkout, so it is not introduced here; it is
fixed in-flight (read the last document) because B1 changed the same function's base roots and
shipping a path-resolution change on a call site that cannot execute would be unverifiable.
Note that the function still had zero consumers — which is the concrete form ADR-0129's
"consumers should use this instead of hard-coding" had decayed into, and the evidence B5 acts
on.

## Verification

- `OMOSTATION_STATE_ROOT` pointed at a scratch directory: `STATE_DIR`, `RUNTIME_OMO_ROOT`,
  `STATE_SYSTEM_YAML` and every `bin/` ledger default land under it, while `OMO_ROOT`,
  `TRUTH_DIR` and `CONTROL_DIR` stay on the checkout.
- With no profile env set, every resolved path equals its pre-change value (regression
  guard for the live production layout). Measured: all nine ledger constants, converted and
  unconverted, resolve to the same path in the same checkout.
- Runtime probe (not just unit assertion): importing all eight converted modules reports the
  checkout-relative `runtime/omo/event-ledger.sqlite3` with no env set,
  `<$OMOSTATION_STATE_ROOT>/runtime/omo/event-ledger.sqlite3` with a declared state root, and
  the `$OMO_EVENT_LEDGER_DB` value when both are set — 8/8 in all three modes, and the probe
  created nothing under the repo.
- The guard test's AST scan over `bin/**/*.py` reports zero `/`-concatenated event-ledger
  path constructions, and it fails when one is re-introduced. (A plain `grep` for the literal
  `runtime/omo/event-ledger` in `bin/` still returns four hits, none of them a resolved path:
  a `repo://` provenance URI in `north_star_meter_v2.py`, docstring prose in
  `episode-source-aggregator.py` and `test-episode-bridge.py`, and the panorama exception. A
  looser regex such as `DEFAULT_(EVENT_)?LEDGER\s*=` additionally matches four **bet**-ledger
  constants in `bin/plan/` and `bin/ssot/`, which are repo-internal reads and stay on
  code_root.)
- `tests/unit/test_repo_root_profile.py` passes on a checkout that is not
  `/Users/xiamingxing/Workspace` (846 cases; this worktree is the non-`Workspace` checkout).
- Targeted suites for the eight converted writers and the two scheduler tests: pass.
  Full governance-kernel suite in the worktree: 2831 passed / 216 skipped, including the
  pre-existing `projection_path()` callers.
- `make gac-local-gate` exit 0 — measured per **lane bundle**, because `change-lane-check`
  enforces one lane per staged set (`projects/ecos/.../sgf-policy.yaml` runs it with
  `--staged`; no hook exports `PUSH_RANGE`). All five bundles green at 68 checks:
  code (`repo_root.py` + 5 consumers + guard test), governance_code (the two `bin/gac/`
  writers), docs+docs_data (this spec + ledger), governance_state (ADR-0456 + decisions
  INDEX), submodule_pointer (`projects/omo`). Passing the whole set in one invocation fails
  by design with `mixed lanes` — that is the rule, not a defect.

## Circuit breaker

Stop on any change that: alters the resolved path for the unset-profile case (the live
production layout must be reproduced exactly), modifies `governance-checks.yaml` registry
rules, writes into `.omo/state/**` as part of verification, or migrates any cron/plist entry
(that is B4 and is blocked behind B3's set-equality gate).
