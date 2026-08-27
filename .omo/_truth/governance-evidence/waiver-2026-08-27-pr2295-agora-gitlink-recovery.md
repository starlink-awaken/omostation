---
status: active
lifecycle: contract
owner: xiamingxing
last-reviewed: 2026-08-27
review-state: user-authorized
---

# #2295 Agora unreachable gitlink baseline recovery waiver

```text
waiver: user-explicit
when: 2026-08-27T02:03:52Z
who: xiamingxing
scope: projects/agora; .omo/_truth/governance-evidence/waiver-2026-08-27-pr2295-agora-gitlink-recovery.md
reason: Root main pins an Agora commit that the authoritative child remote cannot fetch, so a full writer clone cannot obtain admission before the pointer is repaired.
risk: No workflow run, claim, lock, or full-profile writer admission exists for this one-time repair.
residual: Merge one pointer-only recovery PR, prove full clone/recursive checkout/reachability/CI, then retire the degraded clone and this active recovery state.
gate_bypass: 1
no-run-id: true
```

## User authorization

> 本次 #2295 Agora unreachable gitlink baseline recovery 跳过 workflow start，并授权一次性 degraded root-only repair，允许使用 AGCP_REQUIREMENT_ITERATION_GATE=0；仅限 projects/agora 将 f4284c37adfc1d3af7650047320f61292273caf6 恢复为 child main a8a920197079c0a9999ba408d9bd536c8bcc5236，以及 .omo/_truth/governance-evidence/waiver-2026-08-27-pr2295-agora-gitlink-recovery.md 记录本句；不得修改其他 gitlink、BET、Spec、completion/value evidence、实现代码或运行态；从最新 main 建唯一 recovery PR，full clone、recursive checkout、reachability 与必要 CI 通过后立即退役 clone。

## Exact change

- Root base: `d3b2c72fcf155f0281927df105b4c5060a730c67`
- Before: `projects/agora = f4284c37adfc1d3af7650047320f61292273caf6`
- After: `projects/agora = a8a920197079c0a9999ba408d9bd536c8bcc5236`
- Child authority: `https://github.com/starlink-awaken/omostation-agora.git#refs/heads/main`

No other root gitlink, BET, Spec, completion/value evidence, implementation, hook, debt registry, or runtime surface is authorized by this waiver.
