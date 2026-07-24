---
status: ACCEPTED
lifecycle: decision
owner: 夏明星
last-reviewed: 2026-07-24
related:
  - 0210-three-year-strategy-execution-convergence.md
  - 0225-g-del-physical-multihost-gate-caliber.md
  - 0228-m1-acceptance-physical-deferred-reorder.md
  - STRAT-P81-strategic-roadmap.md
supersedes: []
---

# ADR-0232: G-DEL.2b 官方达标宣布（3 角色协作完成率 100%）+ Batch 2 批准

> **编号**: `next-adr-id.py --session g-del-2b-announce --claim` → **0232**。
> 用户 2026-07-24 拍板批准两项（会话记录为凭）。

## Context

Batch 1 B4 测量: n=30 真实 backlog 任务, 3 角色（engineering/governance/audit, ADR-0229 框架）
协作完成率 **rate=1.0000**, `env_class=in-process_simulation`（process-local）。
Evidence: `audits/2026-07-24-batch1-g-del-2b-measure.md`。
Agent 依红线未自宣, 交申请卡 `needs-human-batch1-g-del-2b-application` 待人类决定。

## Decision

### D1 · G-DEL.2b **官方达标**（2026-07-24, 兑现期第一个正式达标门禁）

- **口径合规性**: 按 ADR-0225 §Decision 表, G-DEL.2b（collab complete > 95%）为**非跨机网络 KPI**,
  process-local 协议**允许官方 `meets_gate`** — 本宣布不构成物理口径违例, 与 G-DEL.1/3 的
  fail-closed 约束无冲突。
- KPI: 完成率 100% > 95% 门槛, 样本 n=30 ≥ 30。
- 生效动作: `phase-scope.yaml` / G-DEL 指标记录回填 `meets_gate=true`（G-DEL.2b）;
  两张卡（g-del-2b-application）关闭引用本 ADR。
- 提前量: 原计划 2027Q1-Q3 的 Phase 3 验收指标, 提前约两个季度。

### D2 · Batch 2 批准（scope 采纳 closeout 提案, 物理项仍以机器恢复为前提）

Batch 2 工单 → `.omo/plans/strat-p81-batch2-workorder.md`。核心: C2 三天 cron 补账 ·
B2b 角色协作常态化运营 · 物理恢复预备包 · KOS 质量深化 · X3 交付冲刺。
S3/涌现类继续排除（kill-switch 评审前不启动）。

## Consequences

- 正面: 兑现期首个门禁正式落袋; 多角色能力从"验证"转入"常态运营"。
- 边界: 达标口径为 process-local, 对外表述不得混同于"多机蜂群达标"（G-DEL.1/3 另计, 待物理底座）。
- 影响面: phase-scope G-DEL.2b 字段 · 两张 needs-human 卡 · STRAT-P81 §1 进度。

## Confirmation

- `adr-coverage.py` / `doc-ssot-lint.py` 通过
- phase-scope G-DEL.2b 回填由 Batch 2 A 波执行并附 evidence
- 卡片关闭引用本 ADR
