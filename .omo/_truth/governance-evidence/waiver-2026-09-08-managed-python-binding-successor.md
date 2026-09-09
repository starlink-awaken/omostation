---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-09
last-reviewed: 2026-09-09
value_indicator_policy: false
title: A3 managed-Python test-only recovery dual-transaction waiver
type: doc
---

# A3 Managed-Python Test-Only Recovery Dual-Transaction Waiver

## Principal authorization, verbatim

> 批准上轮 A3 managed-Python test-only recovery 双事务授权原文。

The approved prior-turn authorization package is reproduced verbatim below:

> 批准 A3 managed-Python test-only recovery 双事务。第一事务仅在现有 managed full clone `managed-python-binding-successor-20260909-01` 中，允许 `AGCP_REQUIREMENT_ITERATION_GATE=0` 作为一次 `governance-state-mutation` fresh unbound start 的进程级前缀；人工 tracked 写面仅限 `docs/superpowers/specs/2026-09-08-managed-python-integration-recovery-design.md`、`docs/plans/3y-bet-ledger.yaml` 只新增碰撞安全的 `BET-Y1Q4-T10-142` candidate、唯一 accepted specification 与初始 NOT_STARTED/NOT_PROVEN/evaluating matrix并重算 `meta.total_bets`，以及 `.omo/_truth/governance-evidence/waiver-2026-09-08-managed-python-binding-successor.md` 记录本句。若执行时该 ID、路径或 writer 出现碰撞立即停止。绑定 PR required checks 全绿并 squash merge后，第二事务从届时最新 main 创建唯一 fresh managed full implementation clone，使用默认门和正常绑定的 `BET-Y1Q4-T10-142` workflow；人工 tracked 写面仅限 `tests/unit/gac/test_managed_python_runtime.py`，只修复 thin-hook fixture 携带真实 `bin/gac/hook-runner.sh` 及 clone-snapshot fixture 传入 `DELIVERY_ATTEMPT_ID`，不得修改生产 hook、managed-python selector、Makefile、其他测试、其他 BET、completion/value evidence、gitlink、CI、运行态或用户配置。focused tests、默认门、唯一 PR、required checks、post-merge exact verification通过后合规退役两个 clone；任何门禁拒绝即停止，不扩面、不旁路。

## Transaction 1 identity and bounded bootstrap

- Actor: `codex-agent-os-recovery`
- Delivery attempt: `managed-python-binding-successor-20260909-01`
- Managed full clone:
  `/Users/xiamingxing/agents/codex-agent-os-recovery/attempts/managed-python-binding-successor-20260909-01/ws`
- Branch:
  `agent/codex-agent-os-recovery--managed-python-binding-successor-20260909-01`
- Frozen and execution-time remote-main SHA:
  `39a3da5b18169c62780fc419f544b1733e0ba1ce`
- Workflow run:
  `20260909T102353Z-governance-state-mutation-9d294686`
- Workflow binding: unbound bootstrap; it must not be reused for implementation.
- Affected-graph receipt hash:
  `3b89346a9814fb35338006a288dc53171fe0948b802f2fcb7838bd44bb5118d7`
- Affected project: `workspace-root`

Immediately before the workflow start, the clone was clean, its HEAD equaled
the independently read remote `main`, no active workflow or lock existed, and
open PRs, remote heads, the Ledger, Spec registry and waiver directory showed
no `BET-Y1Q4-T10-142`, managed-Python binding writer or target-path collision.

`AGCP_REQUIREMENT_ITERATION_GATE=0` was supplied only to the one process that
created the run above. It was not exported and was not supplied to
affected-graph generation, claims, edits, validation, Git, CI or closeout.
Every command after `start` uses the default requirement-iteration gate.

The first affected-graph invocation used an environment without PyYAML and
failed at import time before publishing a receipt. The successful invocation
used the tracked command with the declared PyYAML dependency and exclusively
published the receipt named for this run. This was a dependency correction,
not a gate bypass or a second workflow start.

The run claimed exactly:

1. `docs/superpowers/specs/2026-09-08-managed-python-integration-recovery-design.md`
2. `docs/plans/3y-bet-ledger.yaml`
3. `.omo/_truth/governance-evidence/waiver-2026-09-08-managed-python-binding-successor.md`

## Binding facts

- New BET: `BET-Y1Q4-T10-142`, status `candidate`.
- Accepted Spec version: `1.0.0`.
- Accepted Spec SHA-256:
  `e097950a5979c2a7b05edb75d8e432171a4050e8cf6a259f3053a308d9d639a1`.
- Accepted bindings for the new BET: exactly one.
- Initial engineering axis: `NOT_STARTED`.
- Initial operational and value axes: `NOT_PROVEN`.
- Initial overall state: `evaluating`.
- `value_indicator_policy: false`.
- Ledger object count after the single addition: `380`.
- Recomputed `meta.total_bets`: `380`.

The prerequisite A1 branch-admission recovery is present in this base through
PR #3480 (`eadf96b17…`). On the binding base, the merged policy, focused
contract test and R0 waiver SHA-256 values are respectively:

- `98b07814532ba3c09c6411c36f3f13db648ac443dd88f8126303631bb3cc5f4d`
- `0768b09127c3a77dd09a37d92ab54e8f677f7e02b3f8d21dc074a87550af3d01`
- `3c859d313eddb20db5141f6183c09c6670e7ab765bbdb6e01ad83ac2cb8be4fb`

These hashes prove the binding base contains the R0 artifacts; they do not
expand this transaction's write scope or assert A3 operational completion.

## Transaction 2 boundary

Transaction 2 may begin only after this binding PR is squash-merged with every
required context green and the accepted Spec digest is re-read exactly from
`main`. It must use a new managed full clone and a fresh, normally bound
`BET-Y1Q4-T10-142` workflow. The only human-authored tracked implementation
surface is:

```text
tests/unit/gac/test_managed_python_runtime.py
```

The implementation may only add the real tracked hook runner to the thin-hook
fixture and provide `DELIVERY_ATTEMPT_ID` to the clone-snapshot fixture, with
the bounded stubs and negative propagation assertion required by the accepted
Spec.

## Exclusions and residual truth

This waiver does not authorize production hook, runner, selector, manifest,
Makefile, other-test, CI, branch-protection, gitlink, host, service, runtime,
user-configuration, existing BET/Spec, completion-evidence or value-evidence
changes. It does not authorize a second unbound bootstrap or reuse of this run
for implementation. Any actual default gate rejection, collision, digest
drift or expanded WorkPacket stops the transaction without bypass or scope
expansion.

This binding creates a candidate contract only. Engineering remains
`NOT_STARTED`; operational and value evidence remain `NOT_PROVEN`; and a later
test-only green result cannot by itself establish the full A3 operational
release or personal value.
