---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-09
last-reviewed: 2026-09-09
value_indicator_policy: false
title: Claims Authority Bridge WP1 draft Spec bootstrap waiver
type: doc
---

# Claims Authority Bridge WP1 draft Spec bootstrap waiver

## Human delegation

> 我要去休息了，针对上述这种精细化的授权，我估计暂时不能给你处理，直到明天上午10点之前，所有相关授权，你来自主处理，做好备案即可。

## Delegated decision

At 2026-09-10 03:56 Asia/Shanghai, while that delegation was active, the Agent
authorized `AGCP_REQUIREMENT_ITERATION_GATE=0` only as the process-local prefix for
one fresh unbound `governance-state-mutation` workflow start. The transaction is
strictly limited to:

- `docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`,
  written as `status: draft`, `bet_id: unbound`,
  `implementation_authorized: false`;
- this bootstrap waiver.

All commands after workflow start use the default requirement-iteration gate. This
bootstrap does not modify the Ledger, allocate candidate ID `BET-Y1Q4-T10-145`, create
an accepted binding, write an implementation plan, implement child/root code, create
the authority store, issue a receipt/fence, change Git publication, materialize WP2 or
mutate host/runtime state. Independent review and normal required checks remain
mandatory. This delegated authorization ends no later than 2026-09-10 10:00
Asia/Shanghai and is not a standing bypass precedent.

## Frozen design and review evidence

- Parent accepted Spec SHA-256:
  `a419e2fb3cd67026edebd39b25a1e1b77e6c92978ce1cf1be6b8e4be19cf8c58`.
- Frozen WP1 draft Spec SHA-256:
  `d271215e0b8c3fddbc24696eb1f46fb172e34599deeba8dcb15bf041b4851455`.
- Architecture review: `APPROVED / CLEAR` on the frozen digest.
- Remote Git ref/push/PR effect inventory: `CLEAR`; local scripts, Git Data API,
  wrappers and all four identified GitHub publication workflows have explicit
  non-union convergence partitions.
- Gate review: `APPROVE / CLEAR`; candidate `BET-Y1Q4-T10-145` remained unallocated,
  WP2 remained absent, and versions 1.0.0–1.7.0 use complete write-surface
  replacement rather than union.
- Spec-only default workflow verification and staged GaC passed; GaC executed 58
  registered checks successfully and skipped six registered known-unavailable checks
  under current policy.

The repository change-lane gate intentionally rejects `docs + governance_state` in
one staged commit. Following the existing two-commit bootstrap precedent, the Spec was
validated and committed in the `docs` lane first. This waiver is validated and
committed separately in the `governance_state` lane. Both commits remain in one exact
two-path PR; no gate is bypassed by the split.
