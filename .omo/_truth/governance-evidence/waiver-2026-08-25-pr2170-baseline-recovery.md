---
lifecycle: history
owner: governance-team
last_updated: 2026-08-25
title: Workflow waiver 证据 — #2170 post-merge baseline recovery
type: doc
---

# Workflow waiver 证据 — #2170 post-merge baseline recovery

```text
waiver: user-explicit
when: 2026-08-25T08:08:04Z
who: xiamingxing
quote: "本次 #2170 post-merge baseline recovery 跳过 workflow start，允许使用 AGCP_REQUIREMENT_ITERATION_GATE=0；仅限 .omo/_truth/registry/governance-checks.yaml 将 subtraction_quota.script_baseline: 487 更新为 490、.omo/_knowledge/decisions/INDEX.md 登记 ADR-0425，以及 .omo/_truth/governance-evidence/waiver-2026-08-25-pr2170-baseline-recovery.md 记录本句；不得修改其他治理规则、BET、完成证据、实现代码或运行态。"
scope:
  - .omo/_truth/registry/governance-checks.yaml::gac.subtraction_quota.script_baseline
  - .omo/_knowledge/decisions/INDEX.md::ADR-0425
  - .omo/_truth/governance-evidence/waiver-2026-08-25-pr2170-baseline-recovery.md
reason: #2170 merged three active bin scripts without synchronizing the subtraction baseline and omitted ADR-0425 from the authoritative index, leaving unrelated PRs red.
risk: no workflow run, claim, or lock exists for this three-file corrective change.
residual: ADR-0425 frontmatter lacks id: ADR-0425, but that file is outside this waiver and is not modified here; rerun the full gates to expose any further baseline layer.
gate_bypass: 1
no_run_id: true
```
