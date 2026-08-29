# T10-62 OMO ingress write-boundary and schema gate recovery — Delivery Report

Date: 2026-08-29 · Bet: `BET-Y1Q3-T10-62` · Spec:
`docs/superpowers/specs/2026-08-29-omo-ingress-gate-recovery-design.md`

## Finding

The governance interface failures came from two independent extraction seams:

1. `omo_ingress_task_execution.py` was split from the authorized task ingress
   surface but was omitted from the existing sensitive-write exemption list,
   producing 17 false-positive direct-write findings.
2. The root gitlink pointed to child `d01675a`, while child `origin/main` had
   already landed `18bc886`, which removed six dead imports from `omo_audit.py`.

## Change

- Child OMO commit `e0fd7ab` adds exactly one existing ingress-module allowlist
  entry and one regression test. Synthetic direct-write negative tests remain
  unchanged.
- Root `projects/omo` is advanced to `e0fd7ab`, whose ancestry includes
  `18bc886`.
- No task execution behavior, receipt/schema semantics, broker routing,
  Documents content, host schedule, runtime state, capability registry, or
  dispatcher changed.

## Verification

| Check | Result | Evidence |
|---|---|---|
| TDD RED | PASS | The new real-module test failed with 17 direct-write findings before the allowlist entry. |
| Child focused regression | PASS | In the composite root workspace: `34 passed` for `tests/test_omo_direct_io_gate.py` and `tests/test_omo_lint_schemas.py`. |
| Sensitive-write lint | PASS | `cd projects/omo && uv run python -m omo.cli lint sensitive-governed-writes` → `direct_writes=0`. |
| Schema lint | PASS | `cd projects/omo && uv run python -m omo.cli lint schemas` → 7/7 consumers, 0 dead imports, complete schema registry. |
| Child CI | PASS | OMO PR #117: lint, test, and test-cov all passed. |
| Root mainline | PENDING | Root gitlink update is prepared for its own PR; no mainline/required-CI completion claim yet. |

## Verdict

Child behavior and gate contract are repaired. T10-62 remains `candidate` until
the root gitlink PR is merged and a fresh recursive root CI confirms the
governance interface. This repair is governance evidence, not principal-bound
Documents value evidence; value remains `NOT_PROVEN`.

## Rollback

Restore `projects/omo` to `d01675ac7251e52ddbb15c500a4784aecf9794f0` and revert
child commit `e0fd7ab`. No runtime or host rollback is needed.
