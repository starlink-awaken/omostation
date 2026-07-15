# INDEX-KNOWLEDGE.md — 知识资产统一索引

> **维护规则**
> - owner: governance-team
> - trigger: 新增 ADR / 新增审计 / 新增模式
> - method: 脚本生成 (bin/ssot/gen-knowledge-index.py)
> - validation: ADR 数与实际目录一致
> - status: active
> - created_at: 2026-07-14
> - generated_at: 2026-07-15T06:45:53.542317

---

## 知识资产概览

| 类型 | 位置 | 说明 |
|------|------|------|
| ADR 决策 | `.omo/_knowledge/decisions/` | 架构决策记录 |
| 审计报告 | `.omo/_knowledge/audits/` | 各类审计结果 |
| 设计文档 | `.omo/_knowledge/design/` | 设计方案 |
| 管理文档 | `.omo/_knowledge/management/` | 管理指南 |
| 模式总结 | `.omo/_knowledge/patterns/` | 沉淀的模式 |
| 流程文档 | `.omo/_knowledge/process/` | 工作流程 |
| 参考文档 | `.omo/_knowledge/reference/` | 参考资料 |
| 总结文档 | `.omo/_knowledge/summaries/` | 各类总结 |

---

## 按项目索引 ADR

### eCOS & 协议相关

| 类型 | 文件 | 主题 |
|------|------|------|
| ADR | 0078-p84-mof-coverage-x2-freshness.md | 0078-p84-mof-coverage-x2-freshness |
| ADR | 0108-p110a-ecos-domain-manager-split.md | 0108-p110a-ecos-domain-manager-split |
| ADR | 0132-l0-mof-m4-metamodel.md | 0132-l0-mof-m4-metamodel |
| ADR | 0133-l0-constraints-v2-cutover.md | 0133-l0-constraints-v2-cutover |

### GaC 治理相关

| 类型 | 文件 | 主题 |
|------|------|------|
| ADR | 0054-p60-governance-internalization.md | 0054-p60-governance-internalization |
| ADR | 0056-p62-readiness-thresholds-stale-governance.md | 0056-p62-readiness-thresholds-stale-governance |
| ADR | 0098-p104-governance-surfaces-snapshots-split.md | 0098-p104-governance-surfaces-snapshots-split |
| ADR | 0099-p105-governance-surfaces-ingress-split.md | 0099-p105-governance-surfaces-ingress-split |
| ADR | 0100-p106-governance-surfaces-4-submodules.md | 0100-p106-governance-surfaces-4-submodules |
| ADR | 0101-p107-governance-surfaces-6-submodules.md | 0101-p107-governance-surfaces-6-submodules |
| ADR | 0102-p108-governance-surfaces-8-submodules.md | 0102-p108-governance-surfaces-8-submodules |
| ADR | 0103-p109-governance-tooling-trio.md | 0103-p109-governance-tooling-trio |
| ADR | 0106-gac-governance-as-code.md | 0106-gac-governance-as-code |
| ADR | 0114-l4-gac-exemption.md | 0114-l4-gac-exemption |

### 架构演进相关

| 类型 | 文件 | 主题 |
|------|------|------|
| ADR | 0002-pkg-archive-p28-w2.md | 0002-pkg-archive-p28-w2 |
| ADR | 0004-kcb-archived.md | 0004-kcb-archived |
| ADR | 0005-architecture-p29-upgrade.md | 0005-architecture-p29-upgrade |
| ADR | 0105-phase0-bos-contract-linter.md | 0105-phase0-bos-contract-linter |
| ADR | 0107-phase3-bos-contract-linter.md | 0107-phase3-bos-contract-linter |
| ADR | 0113-phase2-bos-contract-linter.md | 0113-phase2-bos-contract-linter |
| ADR | phase0-bos-contract-linter-pre-analysis.md | phase0-bos-contract-linter-pre-analysis |
| ADR | phase2-bos-contract-linter-pre-analysis.md | phase2-bos-contract-linter-pre-analysis |
| ADR | phase3-bos-contract-linter-pre-analysis.md | phase3-bos-contract-linter-pre-analysis |

### P7x 系列（声明/执行鸿沟）

| 类型 | 文件 | 主题 |
|------|------|------|
| ADR | 0150-submodule-pr-reverse-review.md | 0150-submodule-pr-reverse-review |
| ADR | 0151-submodule-hygiene-gate.md | 0151-submodule-hygiene-gate |
| ADR | 0152-m4-gac-rules.md | 0152-m4-gac-rules |
| ADR | 0153-m4-agent-workflows-tools.md | 0153-m4-agent-workflows-tools |
| ADR | 0154-m4-omo-cron-integration.md | 0154-m4-omo-cron-integration |
| ADR | 0155-p76-phase1-cleanup.md | 0155-p76-phase1-cleanup |
| ADR | 0156-p76-phase2-call-direction.md | 0156-p76-phase2-call-direction |
| ADR | 0157-p76-phase3-self-meta.md | 0157-p76-phase3-self-meta |
| ADR | 0158-p76-phase4-promotion.md | 0158-p76-phase4-promotion |
| ADR | 0159-p76-phase5-foundry.md | 0159-p76-phase5-foundry |
| ADR | 0160-p76-phase6-foundry-runtime.md | 0160-p76-phase6-foundry-runtime |
| ADR | 0161-p76-phase7-llm-cron-tasks-mesh.md | 0161-p76-phase7-llm-cron-tasks-mesh |
| ADR | 0162-p76-phase8-real-engineering.md | 0162-p76-phase8-real-engineering |
| ADR | 0163-p76-phase9a-commit-assist-hook.md | 0163-p76-phase9a-commit-assist-hook |
| ADR | 0164-p77-phase1-cross-repo-consistency.md | 0164-p77-phase1-cross-repo-consistency |
| ADR | 0165-p77-phase2-evolution-guardrails.md | 0165-p77-phase2-evolution-guardrails |
| ADR | 0166-p77-phase3-cross-repo-remediation.md | 0166-p77-phase3-cross-repo-remediation |
| ADR | 0167-p77-phase4-port-registry-consistency.md | 0167-p77-phase4-port-registry-consistency |
| ADR | 0168-p77-phase5-hardcoded-ports.md | 0168-p77-phase5-hardcoded-ports |
| ADR | 0169-p77-phase6-commit-assist-e2e.md | 0169-p77-phase6-commit-assist-e2e |
| ADR | 0170-p77-phase7-env-var-port-migration.md | 0170-p77-phase7-env-var-port-migration |
| ADR | 0171-constitution-wave1-severity-classification.md | 0171-constitution-wave1-severity-classification |
| ADR | 0172-p78-port-registry-convergence.md | 0172-p78-port-registry-convergence |
| ADR | 0173-p78-phase2-baseline-foundry-v2.md | 0173-p78-phase2-baseline-foundry-v2 |
| ADR | 0174-p79-phase1-foundry-v2-cron.md | 0174-p79-phase1-foundry-v2-cron |
| ADR | 0175-p79-phase2-health-100.md | 0175-p79-phase2-health-100 |
| ADR | 0176-p79-phase3-cross-repo-zero-residual.md | 0176-p79-phase3-cross-repo-zero-residual |
| ADR | 0177-p79-phase4-docs-refresh.md | 0177-p79-phase4-docs-refresh |
| ADR | 0178-p79-phase5-closeout.md | 0178-p79-phase5-closeout |
| ADR | 0179-runtime-probe-false-positive-treatment.md | 0179-runtime-probe-false-positive-treatment |
| ADR | 0180-bus-foundation-rollout.md | 0180-bus-foundation-rollout |
| ADR | 0181-metaos-ecos-scheme-c-planes.md | 0181-metaos-ecos-scheme-c-planes |
| ADR | 0182-ci-evidence-bos-landing.md | 0182-ci-evidence-bos-landing |
| ADR | 0183-wave2-c2g-omo-phase-a.md | 0183-wave2-c2g-omo-phase-a |
| ADR | 0184-scheme-c-5b-container-executor.md | 0184-scheme-c-5b-container-executor |
| ADR | 0185-wave2-phase-b-predictive-viz.md | 0185-wave2-phase-b-predictive-viz |
| ADR | 0186-scheme-c-5c-os-acl-design.md | 0186-scheme-c-5c-os-acl-design |
| ADR | 0187-scheme-c-5c-l1-path-acl-doctor.md | 0187-scheme-c-5c-l1-path-acl-doctor |
| ADR | 0188-wave2-phase-c-governance-feedback.md | 0188-wave2-phase-c-governance-feedback |
| ADR | 0189-scheme-c-5c-l2-acl-plan-apply.md | 0189-scheme-c-5c-l2-acl-plan-apply |
| ADR | 0190-wave2-dashboard-json-contract.md | 0190-wave2-dashboard-json-contract |
| ADR | 0191-wave2-cockpit-ui-dashboard.md | 0191-wave2-cockpit-ui-dashboard |
| ADR | 0192-wave2-proposal-taskcenter-handoff.md | 0192-wave2-proposal-taskcenter-handoff |
| ADR | 0193-wave2-demo-outcome-seed.md | 0193-wave2-demo-outcome-seed |
| ADR | 0194-scheme-c-5c-setfacl-design.md | 0194-scheme-c-5c-setfacl-design |
| ADR | 0195-architecture-convergence-isc2.md | 0195-architecture-convergence-isc2 |
| ADR | 0196-omo-acl-plan-named-ace.md | 0196-omo-acl-plan-named-ace |
| ADR | 0197-wave2-demo-seed-ui-button.md | 0197-wave2-demo-seed-ui-button |
| ADR | 0198-omo-acl-apply-named-ace.md | 0198-omo-acl-apply-named-ace |
| ADR | 0199-omo-doctor-path-acl-rhythm.md | 0199-omo-doctor-path-acl-rhythm |

### 战略路线图

| 类型 | 文件 | 主题 |
|------|------|------|

---

## 审计报告索引

| 审计类型 | 代表文件 |
|----------|---------|
| ssot-m0-mof-alignment | 2026-06-29-l0-ssot-m0-mof-alignment.md |
| baseline-recovery-closeout | 2026-07-02-p0-baseline-recovery-closeout.md |
| workflow-solidification-closeout | 2026-07-03-p74-workflow-solidification-closeout.md |
| comprehensive-audit | 2026-07-02-system-comprehensive-audit.md |

> 共 86 份审计报告，完整清单见 `.omo/_knowledge/audits/`

---

## 模式总结

| 模式 | 文件 | 主题 |
|------|------|------|
| adr-concurrent-number-collision | adr-concurrent-number-collision.md | adr-concurrent-number-collision |
| ci-silent-fail-debug-chain | ci-silent-fail-debug-chain.md | ci-silent-fail-debug-chain |
| host-mutation-dual-gate | host-mutation-dual-gate.md | host-mutation-dual-gate |
| p43-closed-loop-pattern | p43-closed-loop-pattern.md | p43-closed-loop-pattern |
| p44-closed-loop-pattern | p44-closed-loop-pattern.md | p44-closed-loop-pattern |
| p71-baseline-recovery-pattern | p71-baseline-recovery-pattern.md | p71-baseline-recovery-pattern |
| p72-follow-up-completion-pattern | p72-follow-up-completion-pattern.md | p72-follow-up-completion-pattern |
| p73-truth-driven-engineering-pattern | p73-truth-driven-engineering-pattern.md | p73-truth-driven-engineering-pattern |
| p74-workflow-solidification-pattern | p74-workflow-solidification-pattern.md | p74-workflow-solidification-pattern |
| p75-ci-red-triage-pattern | p75-ci-red-triage-pattern.md | p75-ci-red-triage-pattern |
| p76-launcher-zombie-false-positive | p76-launcher-zombie-false-positive.md | p76-launcher-zombie-false-positive |
| pre-push-ssot-path-drift | pre-push-ssot-path-drift.md | pre-push-ssot-path-drift |

---

## ADR 索引入口

完整的 ADR 索引请见: `.omo/_knowledge/decisions/INDEX.md`

---

## 说明

> 知识资产由脚本自动索引，最新内容以实际文件为准
> 
> 按主题分类和交叉引用由生成脚本动态构建
> 
> ADR 完整清单见 `.omo/_knowledge/decisions/INDEX.md`
