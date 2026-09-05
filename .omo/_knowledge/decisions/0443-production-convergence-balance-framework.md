---
id: ADR-0443
status: accepted
lifecycle: spec
owner: xiamingxing
last-reviewed: 2026-08-30
type: ssot
---

# ADR-0443: 产出/收敛平衡框架

- **状态**: ACCEPTED（principal 授权 2026-08-30，grilling 四轮 18 决策定案）
- **日期**: 2026-08-30
- **BOS**: `bos://governance/anti-corrosion/convergence-balance/*`
- **关联**: ADR-0431（规则生命周期）、ADR-0389（gate-ROI）、ADR-0424（防腐管道）、ADR-0441（DW 协同）

## Context

2026-08 月度复盘（2848 commits / 158 ADR / Y1Q3 97%）识别五大风险，实证诊断收敛为一个病：
**产出速率 > 收敛速率**。决策通胀（RSS draft 占号）、返工率 58%（fix 507/feat 876）、
门禁密度临界（gate 出现 135 次）是同一失衡的三张脸。侦察实证的横切根因是
**调度断链**：rules-lifecycle / escape-digest / gate-roi 三个防腐工具工具在、数据流活、
零自动化调度；gate-roi-report.py 已归档、报告数据冻结在 2026-07-31。

测试腐化与单点裸奔是环境债/设计债，走既有通道（debt.yaml / standards），不入本框架。

## Decision

### 1. 收敛速率轴（事件口径 v1）

只数**有 SSOT 记录的治理事件**，人工自报不算（延续 value-indicator 的排除 self-data 原则）：

| 侧 | 事件源 | 载体 |
|----|--------|------|
| 收敛侧 | gate 拦截 / escape 指纹豁免 / ADR 退役 / 规则 review / debt 清偿 | governance-history.jsonl、swarm-escape 台账、registry、debt items |
| 产出侧 | commit / ADR 登记 / 规则新增 / debt 新开 | git、decisions/、registry、debt items |

载体：`convergence-pulse-weekly` periodic workflow →
`.omo/state/convergence-pulse-{YYYY-WNN}.json`。复合口径的存量快照对账排 Q4。

### 2. 三级部件引用（全部既有，不改动其本身）

- **L 层（规则怎么生怎么死）**: ADR-0431 规则生命周期（added_at/review_before/justification）
- **评估层（门禁值不值）**: ADR-0389 gate-ROI（trend / est_hours_saved / RETIRE|NOISY|KEEP 判定）
- **回路层（信号→进化）**: BCOS 进化引擎 + 本框架新增的事故→规则流水线（pitfalls 阈值
  晋升，接 ADR-0424 的 L0-L3 强度分层）

### 3. 事故→规则流水线（接断头路，不建新通道）

pitfalls 库 `times_encountered ≥ 5` 时自动生成**规则草案**（带 0431 契约字段 + pitfall
证据链）落 `.omo/_delivery/rule-drafts/`，人审后 roundtrip 入册
（`lib/yaml_ssot_edit.py`，禁字符串手术）。gate 报错即教学是实证最有效感知路径
（每个拦截带修复命令），本流水线把"事故→拦截→规则"闭环焊死。

### 4. ADR 分级（增量止血）

- **L1 架构决策**：占号全量（decisions/ 目录）
- **L2 战术决策**：并入战役 ADR 尾部（独立文件被检出 → warn）
- **信号/draft**：落 `.omo/_knowledge/signals/` 不占号；RSS→ADR 自动管道出口改指信号库
- 校验载体：`bin/ssot/adr-number-check.py`（撞号 + 分级双查）

## 演进路径（设计进接口，本骨架不焊死）

- **resident monitor 订阅**：收敛事件未来可被 resident monitor 角色（ADR-0396 规则级
  路由订阅）消费，异常（如 Top 指纹周增超阈）自动 alert——本周仅 periodic workflow
- **RAG 注入扩容**：gac-consensus-inject 检索源纳入 pitfalls/patterns（现仅 KOS 共识
  Top-2）
- **精准 submodule 校验**：write_surfaces 声明面 → submodule 映射校验（比 .gitmodules
  全量更精准）
- **返工门禁**：escape 指纹重复率数据积累一个月后定阈值，只挂"同类复发"模式

## 已知雷（Q4 首件处置，本骨架声明不暗埋）

1. **到期风暴**：80 条规则 review_before 同日 2026-11-26 过期——Q4 初做 added_at 哈希
   分期打散（90-150 天窗口）
2. **justification 占位**：79/80 规则为 "[ADR-0431 D2] {id} — 待补存在理由" 占位符——
   Q4 减法评审时回填真实依据，减法评审就是回填时机
3. **escape 台账只写不读**：digest 聚类已接线（本框架），known-debt 收缩仍靠人工月审

## Consequences

- 防腐三工具从"人手跑"变为"周期调度"，收敛侧第一次有持续数据流
- 决策通胀源头（RSS draft 占号）被结构性切断，而非依赖当事人自觉
- 事故→规则从"打印一句话"变为"出草案等人审"，晋升有人工把关（HITL，0431 D4）
- 框架自身遵循减法原则：能挂既有通道的不新建（本框架仅 1 ADR + 1 采集器 + 1 workflow
  + 3 处既有工具改出口/扩面）
