---
id: ADR-0419

title: "ADR-0419: 从基建转向业务 — knowledge-ingest  shadow 落地 + 信号源修复"
status: archived
lifecycle: spec
type: adr
owner: governance-team
date: 2026-08-19
last_updated: 2026-08-20
tags: [business, knowledge-ingest, shadow-mode, signal-sources]
supersedes: []
related:
  - ADR-0415 (能力对齐)
  - ADR-0416 (Y2 年度门)
  - BET-Y3H1-T3-01 (冷启动)
  - BET-Y2Q2-T7-01 (知识入库 assisted)
---

# ADR-0419: 从基建转向业务 — 业务工作流落地

## 状态

**accepted** — 2026-08-19

## 背景

经过 109/114 BET 的基建工作，核心基础设施（独立 clone 拓扑、跨仓变更审计、校准迁移、漂移监控、编排模板）已全部就绪。但 12/14 业务场景仍停留在 shadow 阶段，90% 工作流执行是基础设施治理，业务价值未释放。

**核心问题**：能否从基建转向业务？

## 决策

### D1: 基建成熟度 — 已达标，可并行

- 7/7 服务运行中 ✅
- 核心机制完整（clone/claim/changeset/calibration/drift）✅
- 37 新测试通过 ✅
- **结论**：基建"最小可用"已达标，不需要等 D2 全员迁移完成

### D2: 业务就绪度 — 有瓶颈，需修复

| 维度 | 现状 | 目标 |
|------|------|------|
| 场景生命周期 | 12/14 shadow | knowledge-ingest 升 assisted |
| 旅程规格 | 全部 0 步 | knowledge-capture-pipeline (9 步) |
| 信号源健康 | 1/4 healthy | 4/4 healthy |
| 工作流执行 | 90% 治理 | 50%+ 业务 |

### D3: 优先级 — knowledge-ingest → document-review

- **knowledge-ingest**：唯一 assisted 场景，知识循环入口
- **document-review**：有 healthy 信号源 (apple_mail)

### D4: 验证标准 — Shadow 2 周 → 自动升 assisted

- min_samples=30, min_calibration=0.60, rollback_evidence
- 不达标则延长或回退

## 实施计划

### P0 准备 (Week 1)

| 工作项 | 产出 | 状态 |
|--------|------|------|
| 修复 inbox_folder 信号源 | healthy | ✅ done |
| 修复 github_push 信号源 | healthy | 待执行 |
| 修复 netease_mailmaster 信号源 | healthy | 待执行 |
| 编写 knowledge-capture-pipeline.yaml | 9 步旅程 | ✅ done |
| 编写知识质量评分函数 | quality_score | 待执行 |

### P1 Shadow (Week 2-3)

- knowledge-ingest 手动触发 + 定时扫描
- 人工复核 (cockpit-ui 面板)
- 积累 30+ samples

### P2 评估 (Week 4)

- 达标 → 升 assisted
- 不达标 → 延长 2 周或回退 + ADR

## 退出条件

| 条件 | 动作 |
|------|------|
| samples ≥ 30 AND calibration ≥ 0.60 | 升 assisted |
| samples < 30 | 延长 2 周 |
| calibration < 0.60 | 分析原因 + 重测 |
| 连续 4 周不达标 | 回退 draft + 记 ADR |

## 风险

| 风险 | 概率 | 缓解 |
|------|------|------|
| 知识来源不足 | 中 | 降低触发阈值 + 扩大来源 |
| calibration 不适配 | 中 | 自定义质量评分 |
| 人工复核瓶颈 | 低 | 批量复核界面 |

## 关联

- ADR-0415: 能力对齐路线
- ADR-0416: Y2 年度门
- BET-Y3H1-T3-01: 冷启动 < 2 周
- BET-Y2Q2-T7-01: 知识入库 assisted
