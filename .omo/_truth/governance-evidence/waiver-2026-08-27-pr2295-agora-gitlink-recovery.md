---
lifecycle: contract
owner: xiamingxing
last_updated: 2026-08-27
review-state: user-authorized
title: #2295 Agora unreachable gitlink baseline recovery waiver
type: doc
---

# #2295 Agora unreachable gitlink baseline recovery waiver

```text
waiver: user-explicit
when: 2026-08-27T02:43:14Z
who: xiamingxing
scope: projects/agora; .omo/_truth/governance-evidence/waiver-2026-08-27-pr2295-agora-gitlink-recovery.md
reason: Root main pinned an Agora commit that the authoritative child remote could not fetch, preventing full writer admission before the pointer repair.
risk: The one-time recovery skipped workflow start and initially used a degraded root-only attempt; no run, claim, or lock existed for that repair.
residual: Pointer recovery landed externally in PR #2302; this latest-main closeout records the exact user waiver and preserves the verified full-clone evidence.
gate_bypass: 1
no-run-id: true
```

## User authorization

> 本次 #2295 Agora unreachable gitlink baseline recovery 跳过 workflow start，并授权一次性 degraded root-only repair，允许使用 AGCP_REQUIREMENT_ITERATION_GATE=0；仅限 projects/agora 将 f4284c37adfc1d3af7650047320f61292273caf6 恢复为 child main a8a920197079c0a9999ba408d9bd536c8bcc5236，以及 .omo/_truth/governance-evidence/waiver-2026-08-27-pr2295-agora-gitlink-recovery.md 记录本句；不得修改其他 gitlink、BET、Spec、completion/value evidence、实现代码或运行态；从最新 main 建唯一 recovery PR，full clone、recursive checkout、reachability 与必要 CI 通过后立即退役 clone。

## Closeout truth

- Original broken root pin: `f4284c37adfc1d3af7650047320f61292273caf6`
- Authoritative Agora child main: `a8a920197079c0a9999ba408d9bd536c8bcc5236`
- Pointer landing: root PR `#2302`, merge `fafcbbea7ea741c838400ac0ae83447937379e68`
- Full-profile verification clone: `pr2295-agora-waiver-closeout-20260827-45`
- Full clone readiness: `ready`
- Root `projects/agora`: `a8a920197079c0a9999ba408d9bd536c8bcc5236`
- Root `projects/ecos`: `61df8d12ab79d238c7081f7258a2f91e144f4c44`

No other root gitlink, BET, Spec, completion/value evidence, implementation, hook, debt registry, or runtime surface is changed by this closeout evidence commit.
