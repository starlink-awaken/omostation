---
type: ephemeral
created: 2026-09-03
---

# T10-61 Registry-driven meta-doctor refs-only binding — Delivery Report

Date: 2026-08-29 · Bet: `BET-Y1Q3-T10-61` · Spec:
`docs/superpowers/specs/2026-08-29-meta-doctor-refs-only-registry-design.md`

## Finding

The registry-driven runner already supported per-surface arguments, but the
canonical `bin-gac-meta-doctor-py` entry did not declare the argument required
by its existing CI contract. The workflow job itself already used
`--refs-only`. This was a registry-to-execution binding gap, not a
meta-doctor rule defect.

## Change

- Added `args: [--refs-only]` to the active
  `.omo/_truth/registry/ci-surfaces.yaml` entry.
- Added a regression test that intercepts registry-driven subprocess calls and
  asserts the exact command is
  `python bin/gac/meta-doctor.py --refs-only`.
- Left `ci-check-runner.py`, `meta-doctor.py`, the GitHub workflow, schedules,
  runtime state, and Documents content unchanged.

## Verification

| Check | Result | Evidence |
|---|---|---|
| TDD RED before registry edit | PASS | The new test observed the command without `--refs-only` and failed as expected. |
| Targeted binding test | PASS | `pytest tests/test_ci_surfaces.py::test_meta_doctor_registry_binds_refs_only -q` |
| CI surface registry audit | PASS | `python3 bin/gac/check-ci-surfaces.py --json` returned `ok=true`, `error_count=0`. |
| Full `tests/test_ci_surfaces.py` | PARTIAL | The new test and 14 existing tests passed; two unrelated baseline failures remain: temporary orphan-script detection and missing `bin/gac/gate-effectiveness.py` on this base. |
| Registry runner | PARTIAL | The runner selected the registered meta-doctor surface with `--refs-only`; the local run still reported existing host dead refs and Python 3.9 compatibility failures in unrelated checks. |
| Workflow verify | PARTIAL | Claim coverage and doc-claims passed; `ssot-guardian` was blocked by pre-existing dirty `projects/ecos`/`projects/omo` pointers and the full local gate did not clear. |

## Verdict

The T10-61 implementation is technically correct and removes the specific
registry argument gap. Delivery remains `candidate` until the authoritative
CI interface check on the pushed branch confirms the full governance workflow
in a clean Python 3.13 recursive checkout. No Documents or host mutation is
required for this repair.

## Rollback

Remove the two-line `args` field from the same registry entry. No runtime or
host rollback is needed.
