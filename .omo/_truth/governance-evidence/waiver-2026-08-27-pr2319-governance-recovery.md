---
lifecycle: contract
owner: xiamingxing
last_updated: 2026-08-27
review-state: user-authorized
title: #2319 post-merge governance baseline recovery waiver
type: doc
---

# #2319 post-merge governance baseline recovery waiver

```text
waiver: user-explicit
when: 2026-08-27
who: xiamingxing
scope: exact paths enumerated in the original authorization and two supplements
reason: Concurrent post-merge changes left conflict markers, orphan downloads, an accidental script registration, a widened warning budget, and a staged-only conflict-marker gate on root main.
risk: This one-time recovery skips workflow start. It must not rewrite the 12 resident projections already cleaned on main, and it does not prove any BET completion or value outcome.
gate_bypass: 1
no-run-id: true
```

## Original user authorization

> 本次 #2319 post-merge governance baseline recovery 跳过 workflow start，允许使用 AGCP_REQUIREMENT_ITERATION_GATE=0；仅限以下 12 个 .omo/_knowledge/retros/resident 文件：bet-execution.md、external-adapter-sync.md、governance-audit.md、governance-state-mutation.md、handoff-resume.md、index.md、mini.md、mof-model-change.md、observer-audit.md、observer-mini.md、project-code-change.md、project-doc-change.md 移除 Git 冲突标记并保留最新 generated_at，删除 bin/verify-config.sh，将以下 5 个 docs/downloads 文件：2026-08-14-shared-runtime-coordination-gap.md、AGENT-BRIEF-OPS-INFRA-GOVERNANCE.md、AGENT-BRIEF-STRATEGY-CONVERGENCE-REMAINDER.md、ARCHITECTURE-STRATEGY-OUTLOOK-2026-08.md、DECISION-SCENARIO-DERIVATION-CONFIRMATION-2026-08.md 归档到 Documents 后从 Workspace 删除，修改 bin/gac/gac-local-gate.py 与 tests/unit/gac/test_gac_local_gate_purity.py 使 conflict-marker gate 在 full gate/CI 使用 --all，以及 .omo/_truth/governance-evidence/waiver-2026-08-27-pr2319-governance-recovery.md 记录本句；不得修改其他文件、BET、completion/value evidence、gitlink、warning budget、CI workflow、branch protection、运行态或用户配置；从最新 main 建唯一 recovery PR，必要检查与 post-merge Governance Check 全绿后清理 clone。

## Supplemental authorization — governance history

> 补充本次 #2319 post-merge governance baseline recovery waiver：允许额外修改 .omo/_knowledge/governance-history.jsonl，仅删除围绕 timestamp 为 2026-08-27T06:31:18Z 与 2026-08-27T06:34:05Z 两条完整 JSON 记录的 `<<<<<<< HEAD`、`||||||| fafcbbea7`、`=======`、`>>>>>>> origin/main` 四行 Git 冲突标记，保留两条 JSON 记录原文，并把本补充句追加写入 .omo/_truth/governance-evidence/waiver-2026-08-27-pr2319-governance-recovery.md；其余授权范围、禁止项、唯一 PR、验证与清理要求保持不变。

## Supplemental authorization — absorbed residents, registry, and budget

> 补充本次 #2319 post-merge governance baseline recovery waiver：当前 main 已由 #2323 清理原授权的 12 个 .omo/_knowledge/retros/resident 文件，后续 recovery 不得重写这些文件；允许随 bin/verify-config.sh 一并删除 bin/_registry/scripts/governance/verify-config.yaml；允许仅将 .omo/_truth/registry/document-governance.yaml 中 concurrent-plans-orphan-docs.max_findings 从 50 恢复为 8，并恢复该条目在 #2321 前的 reason 文本，不得修改其他 warning budget；把本补充句追加写入 .omo/_truth/governance-evidence/waiver-2026-08-27-pr2319-governance-recovery.md；其余已授权范围、禁止项、唯一 PR、验证与清理要求保持不变。

## Supplemental authorization — schema validation timeout

> 补充本次 #2319 post-merge governance baseline recovery waiver：允许在既有授权路径 bin/gac/gac-local-gate.py 中仅为 mof-schema-validate 设置显式 timeout: 45，替代当前默认 15 秒，并在既有授权路径 tests/unit/gac/test_gac_local_gate_purity.py 中增加对应 timeout 契约测试；原因是 PR #2329 Governance Check run 33072974655 的 attempt 1 与 attempt 2 均仅在该检查发生 TIMEOUT after 15s，而同一检查本地约 2.6 秒通过、enclosing full governance verification 与其余 GaC checks 均通过；把本补充句追加写入 .omo/_truth/governance-evidence/waiver-2026-08-27-pr2319-governance-recovery.md；不得修改其他 gate、timeout、命令顺序、文件、CI workflow、registry、BET、completion/value evidence、gitlink、运行态或用户配置；其余授权范围、禁止项、唯一 PR、验证与清理要求保持不变。

## Recovery boundaries

- Root base: `da0f68cf2d0cd6a767b59a0ca7f0a1d00f736561`
- The 12 resident projection files are verified marker-free on this base and are intentionally not part of the diff.
- The five `docs/downloads` files were archived byte-identically under `/Users/xiamingxing/Documents/学习进化/基建架构/evidence/2026-08-27-pr2319-recovery-downloads/` before deletion.
- `governance-history.jsonl` retains both authorized JSON records byte-for-byte; only their four surrounding conflict-marker lines are removed.
- Only the `concurrent-plans-orphan-docs` warning entry is restored to its pre-#2321 budget and reason.
- No BET, completion/value evidence, gitlink, CI workflow, branch protection, runtime, service, user configuration, or other warning budget is changed.
