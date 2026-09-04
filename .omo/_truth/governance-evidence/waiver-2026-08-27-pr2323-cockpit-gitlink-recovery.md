---
lifecycle: contract
owner: xiamingxing
last_updated: 2026-08-27
review-state: user-authorized
title: #2323 Cockpit unreachable gitlink recovery waiver
type: doc
---

# #2323 Cockpit unreachable gitlink recovery waiver

```text
waiver: user-explicit
when: 2026-08-27T12:14:30Z
who: xiamingxing
scope: projects/cockpit; .omo/_truth/governance-evidence/waiver-2026-08-27-pr2323-cockpit-gitlink-recovery.md
reason: Root main pinned a Cockpit commit that the authoritative child remote could not fetch, preventing recursive checkout and required CI from starting.
risk: This one-time pointer recovery skips workflow start; no run, claim, or lock is created for the repair.
residual: The repair is limited to the last reachable child-main commit named in the authorization and does not prove any BET, Spec, completion, or value outcome.
gate_bypass: 1
no-run-id: true
```

## User authorization

> 本次 #2323 post-merge Cockpit unreachable gitlink recovery 跳过 workflow start，允许使用 AGCP_REQUIREMENT_ITERATION_GATE=0；仅限 projects/cockpit 将 88d3f39324aae4e1eb0f1b7294972535e927d71d 恢复为当前 child main 67f2687afc9a538d7c5300d636472a2ab69141a1，以及 .omo/_truth/governance-evidence/waiver-2026-08-27-pr2323-cockpit-gitlink-recovery.md 记录本句；不得修改其他 gitlink、BET、Spec、completion/value evidence、实现代码、测试、hook、CI、registry、warning budget或运行态；从最新 main 建唯一 recovery PR，full clone、recursive checkout、14/14 require-main reachability 与必要 CI 通过后立即退役 clone。

## Recovery boundary

- Root base: `5dace79d842ec545822f088a419a4588470efd3f`
- Unreachable root pin: `88d3f39324aae4e1eb0f1b7294972535e927d71d`
- Authorized reachable Cockpit child-main pin: `67f2687afc9a538d7c5300d636472a2ab69141a1`
- Delivery clone: full, non-shallow clone `pr2323-cockpit-gitlink-recovery-20260827-02`

The superseded, pre-#2325 attempt is preserved outside the repository as historical evidence and is not part of this delivery.

No other gitlink, BET, Spec, completion/value evidence, implementation, test, hook, CI, registry, warning budget, runtime, or user configuration is changed by this recovery.
