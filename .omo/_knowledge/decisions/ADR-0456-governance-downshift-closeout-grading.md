---
schema: md/v1
status: PROPOSED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-26
type: ssot
id: ADR-0456
related: ADR-0249, ADR-0453
---


# ADR-0456 — 治理降档：closeout/retro 分级与 docs+chore 占比回落机制

- **Status**: PROPOSED（等待 principal 批准；批准前本 ADR 不改变任何强制行为）
- **Date**: 2026-09-26
- **Related**: ADR-0249（治理预算 40/40/20）、ADR-0453（声明/执行鸿沟定性）、BET-Y2Q4-T6-01

## 背景与问题

1. 近 30 天提交构成 docs+chore 占比 **45%**（feat 499 / chore 444 / fix 420 / docs 341），
   贴近 ADR-0249 治理预算 40% 上限；其中相当部分是"每个 BET 统一强度"的 closeout
   文档与 retro 叙事。
2. 治理基建已建成（BET 完成 99.6%→478/482、12/12 域 Harness 绿、账本/门禁/证据链完备），
   closeout 文档强度与 BET 等级无关，边际收益递减——P2 小单写满篇幅叙事的信号价值极低。
3. 产能轨（真实业务 backlog）0 交付 vs 治理交付接近全绿的落差（ADR-0419 转向未兑现），
   要求把治理强度让渡给业务交付。

## 决策（提案）

**分级只影响文档密度，不动三轴证据门禁（engineering/operational/value REQUIRED 键集不变）。**

| BET 等级 | closeout 文档 | retro |
|---|---|---|
| P0 / P1 | 全量（现状：TL;DR + 计划 vs 实际 + 改动面 + 验证 + 反思） | 必写 |
| P2 及以下 | **轻量模板**：交付物清单 + verify 结果 + 证据引用（≤40 行，免叙事段） | 失败/复杂单必写；常规单按 20% 抽样（抽样规则由 resident 轮转决定，防选择性豁免） |

目标：docs+chore 占比 45% → **≤35%**（复算命令与基线同 test-density-baseline 报告模式，
30 天滚动窗口），释放的治理预算转投产能轨。

## 影响面与不做的事

- **不改**：三轴证据矩阵键集、bet-ledger complete 校验、D0–D6 纪律、retro-before-done 门禁
  （D5：被抽样豁免的 P2 单以「retro: sampled-out」登记代替缺省缺失，仍过门禁）。
- **不改**：ADR/标准/registry 类文件的既有元数据契约（本轮 legacy-enum 预算刚回落，
  新模板直接用合规枚举，不新增 legacy 计数）。

## 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 轻量 closeout 丢关键证据 | 模板强制保留证据引用三行（commit/diff/tests） | 无需回滚——证据始终在案 |
| 抽样漏掉复杂单的教训 | 失败/复杂单定义宽口径（blocked/返工/跨仓）必写 | 抽样率调回 100%（改回即回滚） |
| 占比目标被 gaming（把 docs 塞进 feat） | 复算命令含前缀误分类局限声明；review 抽查 | 目标注销，回到观察 |

回滚 = 本 ADR status 改 SUPERSEDED + 标准条目还原，无数据迁移成本。

## Shadow 方案（批准后执行，本 ADR 附带计划）

前 10 个关闭的 BET（含 shadow 期起所有 P2 单）双轨运行：P2 单按轻量模板交付，
同时由 governance-agent 按**全量模板**补写 shadow 版本（不进 PR，落
`.omo/_delivery/shadow-closeouts/`）。第 10 单收口时抽检 3 个：

- 判据 1：shadow 版是否含有轻量版遗漏的、会影响后续复用的信息（>0 即判失败案例）；
- 判据 2：轻量版证据三行是否可独立复算（复算失败即失败案例）；
- 判据 3：写文档耗时对比（凭 closeout run 时长字段）。

3 个判据全过 → 转常规（升级本 ADR 为 ACCEPTED 附 shadow 结果）；任一失败 → 回滚。

## 人类门禁记录

- [ ] principal 批准（decision_ref: `decision://accepted/BET-Y2Q4-T6-01` 批准时回填）
- 批准范围 = 分级方案 + shadow 启动；**强制收紧（若观察期满转常规）另走一次确认**。
