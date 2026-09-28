---
schema: md/v1
status: active
lifecycle: contract
owner: governance-team
type: ssot
last-reviewed: 2026-09-28
---

# ADR Index — 架构决策记录

> **编号空间声明**：本目录的 ADR 编号（ADR-0190 ~ ADR-0205）是**架构 ADR 编号空间**，
> 与 `.omo/_knowledge/decisions/` 的决策记录编号空间**独立**。
> 同一编号在两个目录中可能指向不同主题的文档，这是**设计意图**，不是碰撞。
>
> - `docs/adr/` — 架构 ADR（正式架构决策，内容完整，含上下文/决策/影响范围）
> - `.omo/_knowledge/decisions/` — 决策记录（细粒度决策日志，417 条）

## 文件清单

| 编号 | 文件 | 主题 |
|------|------|------|
| ADR-0190 | ADR-0190-mof-dynamic-constraint-engine.md | MOF 动态约束与 Agent 实时治理体系 |
| ADR-0191 | ADR-0191-workspace-documents-dual-plane-architecture.md | 工作区文档双平面架构 |
| ADR-0192 | ADR-0192-domain-agent-fact-extraction-and-hygiene-patrol.md | 域代理事实提取与卫生巡检 |
| ADR-0193 | ADR-0193-domain-policy-as-code-engine.md | 域策略即代码引擎 |
| ADR-0194 | ADR-0194-dual-plane-truth-canvas-and-chaos-governance.md | 双平面真值画布与混沌治理 |
| ADR-0195 | ADR-0195-intent-to-spec-compiler.md | 意图到规格编译器 |
| ADR-0196 | ADR-0196-shadow-challenger-and-adversarial-governance.md | 影子挑战者与对抗治理 |
| ADR-0197 | ADR-0197-sovereign-hybrid-compute-and-kv-cache-snapshots.md | 主权混合计算与 KV 缓存快照 |
| ADR-0198 | ADR-0198-domain-cartridge-factory.md | 域卡带工厂 |
| ADR-0199 | ADR-0199-unified-bos-cockpit-and-cognitive-workflow.md | 统一 BOS 驾驶舱与认知工作流 |
| ADR-0200 | ADR-0200-y1q4-code-loc-gate-rebaseline.md | Y1Q4 代码门禁再基线 |
| ADR-0201 | ADR-0201-git-stage-submodule-pin-discipline.md | Git stage 子模块固定纪律 |
| ADR-0202 | ADR-0202-harness-structure-completeness.md | Harness 结构完整性 |
| ADR-0203 | ADR-0203-harness-mof-integration.md | Harness MOF 集成 |
| ADR-0204 | ADR-0204-harness-operations-probe-value-loop.md | Harness 操作探针与价值回路 |
| ADR-0205 | ADR-0205-harness-governance-debt-sync-anti-corrosion.md | Harness 治理债务同步与防腐 |

## 引用约定

- 引用本目录 ADR 时，使用 `docs/adr/ADR-NNNN-*.md` 路径
- 引用 decisions/ 决策记录时，使用 `.omo/_knowledge/decisions/NNNN-*.md` 路径
- 两者编号空间独立，不互相引用
