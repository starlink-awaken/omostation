---
lifecycle: stable
owner: governance-team
last_updated: 2026-08-24
title: omostation 项目级战略架构 v1 (2026-08-24)
type: doc
---

# omostation 项目级战略架构 v1 (2026-08-24)

> **定位**: 项目粒度的九维战略架构 SSOT — 跨越场景/功能/旅程/体验/愿景/运营/运维/防腐/约束
> **回答的问题**: "omostation 接下来两年走向哪里? 每一维度现在在哪, 离终态多远, 卡点是什么?"
> **来源**: 9 维系统性综合分析 (2026-08-22~24 期间的所有交付 + 已存在的 14 份架构 SSOT + T6-14 深度复盘)
> **决策级**: 与 `sustainable-value-loop-v1.md` 同级 — 变更须经同等粒度评审
> **生命周期**: stable (随 T6-14 复盘节奏季度复审)

---

## 0. 阅读路径

本文档按九维递进, 每一维都遵循"现状 → 目标 → 卡点 → 落地路径"四段式:

```
维度 1-2:  场景 + 功能     — 业务侧 (我们做什么)
维度 3-4:  旅程 + 体验     — 用户侧 (人怎么用)
维度 5-7:  愿景 + 运营 + 运维  — 战略侧 (我们要到哪里, 如何维持)
维度 8-9:  防腐 + 约束     — 风险侧 (什么会摧毁我们, 我们怎么挡)
```

**TL;DR**: 系统已从"机制过剩、价值不可证" (2026-08-22) 进化到"机制完备、三方口径对齐、价值闭环初现" (2026-08-24). 接下来 12 个月, 战略主轴是 **从"系统建设"转向"价值兑现"** — 把现有 8.2/10 的成熟度转化为可证的主人的时间节省, 同时维持防腐接线避免腐烂。

---

## 1. 场景 (Scenarios)

### 1.1 现状盘点

| 场景 ID | 名称 | 当前 lifecycle | 距终态 | 状态 |
|---------|------|----------------|--------|------|
| `unified-inbox` | 统一收件箱 | shadow | assisted | 0 触发 |
| `document-review` | 公文审查 | shadow | assisted | 0/30 samples |
| `meeting-supervision` | 会议督办 | shadow | assisted | 0 触发 |
| `project-supervision` | 项目督办 | shadow | assisted | 0 触发 |
| `research-pipeline` | 调研流水线 | shadow | assisted | 0 触发 |
| `periodic-reporting` | 周期报告 | shadow | assisted | 0 触发 |
| `engineering-delivery-dogfood` | 工程交付 dogfood | shadow | assisted | 0 触发 |
| `knowledge-curation` | 知识策展 | shadow | assisted | 0 触发 |
| `agora-bos-gateway` | Agora BOS 网关 | shadow | assisted | 0 触发 |

**关键观察**: 9 张场景卡全部处于 `shadow` 阶段, 0 samples 触发. 这是**最大的用户价值瓶颈** — 系统建好了, 但主人从未真正走过任何一条。

### 1.2 目标

**3 个月目标**: 至少 **3 张场景卡升级到 `assisted`** lifecycle, 每张有 ≥3 useful samples (mini-shadow 模式)
**12 个月目标**: 全部 9 张升级到 `assisted`, 至少 3 张升级到 `autonomous` (主路径上无人工介入)

### 1.3 卡点

| 编号 | 卡点 | 根因 | 影响 |
|------|------|------|------|
| S1 | 入口触发器未连通 | 主人侧没有"我今天要用它"的肌肉记忆 | 场景无样本 |
| S2 | shadow 阶段的卡无法直接被使用 | 设计上正确, 但缺乏"5 分钟内可走完一次"的轻量路径 | 升级无证据 |
| S3 | activation 评审门槛过高 (30 samples + 0.6 calibration) | 缺乏 review 校准数据 | 卡在 shadow 跨年 |

### 1.4 落地路径

- **S1 短期 (2 周)**: 写一份"主人场景卡使用剧本" — 5 步可走完, 每步 < 60 秒
- **S2 中期 (1 个月)**: 引入 `mini-shadow` 模式 (3 useful 升 assisted) — 工具已落地
- **S3 长期 (1 季度)**: 与 `cockpit decide` 联动 — 决策收件箱自动产出 calibration 数据

**关联 BET**: BET-Y1Q3-T10-08 (closeout 硬门) + Y1Q4-T7-01 (document-review 升级门)
**关联工具**: `bin/gac/scene-card-mini-shadow.py` (本战略配套)

---

## 2. 功能 (Functions)

### 2.1 现状盘点

按"能力族"分类, 当前共有 ~24 个能力族, 480 个 bin 工具. 主要能力域:

| 域 | 代表能力 | 成熟度 |
|----|----------|--------|
| 治理 | gac-local-gate, compass_radar, drift-sweep, maturity-scorecard, maturity-align, **strategy-check** | 8.2/10 |
| 工作流 | agent-workflow, workflow-mesh, scene-daemon, journey-runner | 7/10 |
| 知识 | knowledge-graph, staleness-check, KB search, memory-os, knowledge-foundry | 7.5/10 |
| 业务闭环 | BCOS signal_router, evolution_engine, north_star_meter_v2 | 6/10 (价值未证) |
| 推理 | aetherforge, omlxc, sophia/minerva/codeanalyze | 8/10 |
| 防腐 | anti-corrosion-check, rot-defense-pipeline, mass-deletion-guard | 8.5/10 |
| **战略** | **strategy-check (新, 9 维战略矩阵)** | **N/A** |

### 2.2 目标

**3 个月**: BCOS 价值闭环 maturity 从 6 → 8 (north_star provable, evolution engine closed loop)
**12 个月**: 所有能力域 ≥ 8/10, 价值闭环 (V1-01) 与场景卡自主执行 (T6-14 完成度) 双向飞轮运转

### 2.3 卡点

- **F1 能力重叠**: `compass_radar` 与 `maturity-scorecard` 重复计算 health_score 概念 (T10-10 收尾)
- **F2 入口分散**: 480 个 bin 工具无统一入口, 新用户进入困难
- **F3 价值信号缺失**: BCOS north_star meter v2 处于 `unprovable` 状态 (R1 自进化债)

### 2.4 落地路径

- **F1 (已完成)**: T10-10 maturity-align.py + 三方口径对齐
- **F2 短期**: 推 `cockpit` 为唯一入口, 所有工具被 cockpit 收编
- **F3 中期**: V1-01 north_star v3 (复合制, A 时间账本 + B 决策吞吐 + C 项目推进力)

**关联 BET**: BET-Y1Q3-T1-11, BET-Y3H1-V1-01, BET-Y3H1-V3-01

---

## 3. 用户旅程 (User Journeys)

### 3.1 现状盘点

主路径 (从主人意图到交付物):

```
[主人] 意图(口头/笔记)
    │
    ▼
[Step 1] 决策收件箱 (cockpit decide)  ← 已建, 未激活
    │
    ▼
[Step 2] 场景卡触发 (scene daemon)  ← 已建, 0 触发
    │
    ▼
[Step 3] Journey 编排 (intake-review-deliver)  ← 已建, 7 个模板
    │
    ▼
[Step 4] 自治执行 (resident agent / mesh executor)
    │
    ▼
[Step 5] 价值沉淀 (knowledge-curation + north_star v3)
    │
    ▼
[Step 6] 主人签核 + 闭环 (weekly-review / attest-review)
```

### 3.2 目标

**3 个月**: 主路径全程可在 **< 30 分钟** 内被单人手动走完 (走完后, 主人对每一步都有信心)
**12 个月**: 主路径 **80% 步骤零人工介入** (仅 Step 1 入口 + Step 6 签核需主人)

### 3.3 卡点

- **J1**: Step 1 决策收件箱未激活, 主人仍在口头传递意图
- **J2**: Step 2 场景卡 0 触发, 缺乏"自动派单"机制
- **J3**: Step 4 自治执行依赖于人工批准门 (execute --yes), 形成新瓶颈
- **J4**: Step 6 weekly-review 10 分钟一节, 缺主人习惯

### 3.4 落地路径

- **J1 短期**: 将 cockpit decide 设为周一 morning routine 的固定入口
- **J2 中期**: 引入 `signal_router` 自动派单 (公文/会议/调研/代码四源)
- **J3 中期**: execute --yes 改为基于规则的自动批准 (白名单路径, MOF m3 域)
- **J4 长期**: weekly-review 形成"周一启动+周日签核"的肌肉记忆

**关联 BET**: Y3H1-V3-01 (cockpit decide 子命令), T6-14 (resident 体系), T1-11 (platform-rebase 退役)

---

## 4. 体验 (Experience)

### 4.1 现状盘点

按"五感"评估 (从主人视角):

| 维度 | 现状 | 期望 |
|------|------|------|
| 触达 | 主人用 `make omo-status` 看 4 象限大盘 — 偶尔 | 每日开场 |
| 理解 | 8.2/10 maturity_score — 数字好但缺乏具象 | "今天为我做了什么" |
| 信任 | governance-verify 全绿 + 15 个工作树活跃 + 0 漂移 | 沉默即正确 |
| 控制 | 480 个 bin 工具 + 38 个 skill — 选择过载 | 1 个 cockpit 入口 |
| 愉悦 | 提交后看到 history.jsonl 时间序列 — 有反馈 | 决策后看到 north_star Δ |

### 4.2 目标

**3 个月**: 主人每天花在治理系统上的"必要时间" ≤ 15 分钟 (周一 morning + 周日 attest)
**12 个月**: 主人不再需要读 ARCHITECTURE.md (因为系统已自我描述)

### 4.3 卡点

- **E1 工具过载**: 480 个工具 + 38 个 skill, 没有"该用什么"指南
- **E2 信号噪声**: governance-anomaly 0/100 但仍有 3 个 anomaly — 信任边界不清
- **E3 反馈延迟**: compass_radar run 完才看到 health, 缺乏实时性
- **E4 单点故障**: owner 67% 待处理任务集中于 "human" — 主人即瓶颈

### 4.4 落地路径

- **E1 短期**: 在 `cockpit` 顶层做"今日建议" — 主人登录看到 3 条该做的
- **E2 中期**: anomaly ≠ alarm 的语义分层 (severity × confidence × actionability)
- **E3 中期**: compass_radar 增量模式 + 实时 projection
- **E4 长期**: resident 体系接管 owner 分散 (T6-14 渐进)

**关联 BET**: T6-14 (resident 体系), V3-01 (cockpit decide), V1-01 (north_star 价值证明)

---

## 5. 愿景 (Vision)

### 5.1 三年愿景 (Y1-Y3)

> **"omostation 成为一个自洽的治理-执行-价值闭环: 主人的注意力只花在"决策"和"价值确认"上, 系统的其他部分通过 resident 自治 + cockpit 编排 + BCOS 价值度量, 自我维持。**

具体形态:

- **Y1 (2026H2-2027H1)**: 系统能力完备, 主人与系统达成人机协作 baseline
- **Y2 (2027H1-2027H2)**: 系统开始自主运转, 主人每周 < 1 小时介入
- **Y3 (2028-2029)**: 系统自进化, 主人只在重大决策时介入 (北极星 provable → 自动续期 BET)

### 5.2 北极星指标

**3 年唯一北极星**: **主人每月可证的时间节省 (小时)**, 由 north_star v3 度量:

```
A 时间账本 (主, 70%): signal_router 自动信号 × 单事件平均节省时长
B 决策吞吐 (30%): cockpit decide 平均 cycle time
C 项目推进力 (佐证, 0%): BET done rate (无成本导出)
```

### 5.3 战略错配诊断 (2026-08-22 复盘)

**"能精确测量 142 条 GaC 规则的遵守度, 无法测量系统为主人省下的时间。"** — 这是 v1 阶段的核心错配. v2 阶段已开治本, v3 完成实证.

### 5.4 战略推进节奏

| 阶段 | 主题 | 验证指标 |
|------|------|----------|
| 现在 → 2026-Q4 | **建设期 → 接入期** | 9 张场景卡中 3 张升级到 assisted, BCOS north_star provable |
| 2026-Q4 → 2027-Q2 | **接入期 → 运转期** | 周 morning routine 稳定运转, 主人 < 15 分钟/日 |
| 2027-Q2 → 2027-Q4 | **运转期 → 自治期** | resident 自治 80% 任务, 主人仅签核 |
| 2028+ | **自治期 → 进化期** | BET 自动化续期 + 自进化 L2 结构优化 |

---

## 6. 长期运营 (Long-term Operations)

### 6.1 现状盘点

当前运营是"机制维护 + 周期巡检", 主要 cadence:

| 频率 | 活动 | 工具 | 状态 |
|------|------|------|------|
| 5min | 5 类 resident daemon (M4.3) | omo resident daemon | 已上线 |
| 60min | meta-doctor / drift-sweep / scheduler-compile | bin/gac/* | 已上线 |
| 周一 | weekly-review 卡片 | bin/ssot/weekly-review | 已建, 未激活 |
| 周日 | attest-review 签核 | bin/ssot/attest-review | 已有但未列入 routine |
| 季度 | T6-14 深度复盘 | (本次 T6-14) | 已建, 节奏稳定 |
| 1min | M1 heartbeat | 5 类角色 cron | 已激活 |
| **新** | **strategy-check (新) — 9 维战略矩阵快照** | **bin/gac/strategy-check.py** | **已落地** |

### 6.2 目标

**3 个月**: weekly-review 周一 routine 化 (主人主动开 + 收件箱自动推送)
**12 个月**: 主人每日运营负担 ≤ 15 分钟, 90% 时间在决策和签核

### 6.3 卡点

- **O1 仪式未成习惯**: weekly-review 工具已建, 但主人未形成"周一 9:00 看"的肌肉记忆
- **O2 反馈链路未闭环**: 巡检发现的问题有时不能直接归入"今日该做"
- **O3 运营数据未量化**: 主人投入时间未记录, 难以评估运营负担

### 6.4 落地路径

- **O1 短期**: 将 weekly-review 自动投递到主人日报, 不需主动开
- **O2 中期**: 巡检 → 卡片 → 决策 → 执行 全链路 closure
- **O3 中期**: O2 落定后, north_star A 轴自动量化

**关联 BET**: V1-01 (north_star v3), T6-14 (resident 体系), T1-11 (provenance)

---

## 7. 运维 (Maintenance)

### 7.1 现状盘点

| 层级 | 工作 | 工具 | 成熟度 |
|------|------|------|--------|
| L0 协议 | 142 条 GaC 规则 + 28 条 L0 约束 | bin/gac/gac-validate | 9/10 |
| L1 运行时 | scheduler / mesh / cron | omo / projects/omo | 7/10 |
| L2 内核 | BCOS / MOF / aetherforge | projects/* | 8/10 |
| L3 入口 | cockpit / 38 个 skill | bin/cockpit | 6.5/10 |
| L4 文档 | 14 份架构 SSOT + 26 份 superpowers spec | docs/architecture | 9/10 |
| **新** | **strategy-check 9 维矩阵** | **bin/gac/strategy-check.py** | **6/10** (新) |

### 7.2 目标

**3 个月**: L3 入口成熟度从 6.5 → 8 (cockpit 一站式, 用户 5 分钟内能找到要的工具)
**12 个月**: L1 运行时 7 → 9 (M1 心跳稳定 + scheduler-drift < 5% + 自愈率 > 70%)

### 7.3 卡点

- **M1 入口过载**: 480 个工具 + 38 个 skill 缺乏统一引导
- **M2 调度漂移**: scheduler-compile 仍有偶发 drift (P79 治本)
- **M3 自愈缺口**: 异常需人工 follow-up, auto-fix-loop 仅覆盖 T0 类

### 7.4 落地路径

- **M1 短期**: cockpit 顶层"今日推荐" — 基于主人历史 + 当前任务
- **M2 中期**: scheduler-drift 接 rot-defense-pipeline, 自动提案
- **M3 中期**: auto-fix-loop 扩到 T1/T2, MOF m3 域

**关联 BET**: T1-11 (platform-rebase 退役), T6-14 (resident 体系), rot-defense-pipeline-v1

---

## 8. 防腐 (Anti-Corruption)

### 8.1 现状盘点

参考 `rot-defense-pipeline-v1.md` 的 6 层管道:

```
L3 动作时刻拦截 (gac-local-gate + bin-quota-diff + ancestry gate)
    ↓
L2 周期探测 (meta-doctor + drift-sweep + CAP-OWN)
    ↓
T1 自动立案 (MDEAD-* + auto-fix-loop)
    ↓
修复引擎 (remediation-engine)
    ↓
升报层 (alert-router + weekly-review)
    ↓
主人面 (周 morning + 日签核)
    ↓
仪式闭环 (review + attest)
```

**当前接线度**: 6 层中 4 层已通, 修复引擎和升报层有 G1/G2 接线缺口 (T6-14 已识别)

### 8.2 目标

**3 个月**: G1/G2 接线缺口闭合 (MDEAD → remediation-engine 适配器, meta-doctor → cockpit-inbox)
**12 个月**: 6 层全通, 主人从"被动发现"转向"主动签核" (沉默即正确)

### 8.3 卡点

- **R1 接线缺口 G1/G2**: 见 8.2
- **R2 主人仪式疲劳**: 6 层最后 2 层依赖主人, 长期看是单点
- **R3 长期演化**: 现防腐契约是 2026-08 设计, 2 年后是否仍适用未知

### 8.4 落地路径

- **R1 短期**: 闭环 G1/G2 (BET 候选 T10-08 类)
- **R2 中期**: resident execute 接管升报层, 主人仅在 critical 介入
- **R3 长期**: 每年 T6 复盘, 评估防腐契约是否需要更新

**关联 BET**: T6-14, rot-defense-pipeline, T1-11

---

## 9. 约束 (Constraints)

### 9.1 硬约束 (不可破)

| 约束 | 来源 | 守护机制 |
|------|------|----------|
| 单人独立可运维 | 主决策 (xiamingxing 单点) | 不做"主人不在就崩"的设计 |
| 本地优先 | `host:` bos:// 协议 | 不依赖外部云服务做核心闭环 |
| SSOT 不可分裂 | `.omo/standards/doc-ssot-contract.md` | doc-ssot-lint 守护 |
| GaC 不可绕过 | 142 条规则 + 增量 quota | gac-local-gate, CI blocking |
| AGCP 不可无 run-id | ADR-0203 | agent-workflow.py 强制 start→closeout |
| 工作树独立性 | T1-05 独立 clone 拓扑 | platform-rebase (退役中) + clone-guard |

### 9.2 软约束 (可权衡)

| 约束 | 默认值 | 权衡 |
|------|--------|------|
| 工具 ≤ 480 | T6-05 减法配额 | 新增工具须配对归档/删除 (增量) |
| 规则 ≤ 142 | T6-05 减法配额 | 同上, 现 baseline = 142 |
| ADR ≥ 361 | 数量 baseline | 新增须留档 |
| 场景卡 activation ≥ 0.6 (standard) / ≥ 3 useful (mini-shadow) | Y1Q4-T7-01 | 30 samples 校准 (standard) / 3 useful (mini) |
| 北极星连续两季 provable | D7 续期 | BET 自动续期 |

### 9.3 战略反模式 (识别即停)

| 反模式 | 现象 | 应对 |
|--------|------|------|
| **机制过剩价值缺位** | 工具多了, 主人并未更省时间 | V1-01 价值闭环 (北极星 A 轴) |
| **多 Agent 抢单** | 多个 resident daemon 并发处理同一任务 | swarm-d4 escape + 独立 clone |
| **shadow 卡片挂年** | 场景卡停在 shadow 跨季度 | mini-shadow 模式 (3 samples 升) |
| **runbook 漂移** | runbook 提到的命令实际不存在 | runbook_command_validity (drift-sweep #2067) |
| **T1-10 债复发** | resident 关掉后债没自动升报 | auto-fix-loop + meta-doctor M3 |

### 9.4 目标

**3 个月**: 反模式清单从 5 项 → 0 项 (全部实装守护)
**12 个月**: 硬约束实现 100% CI 守护, 软约束实现 90% CI 守护

---

## 10. 战略一致性矩阵 (9 维 × 3 时间窗)

| 维度 | 3 个月目标 | 12 个月目标 | 3 年目标 |
|------|-----------|------------|----------|
| 1 场景 | 3/9 assisted (mini-shadow) | 9/9 assisted, 3/9 autonomous | 全部 autonomous + 自进化 |
| 2 功能 | BCOS 6→8 | 全域 ≥ 8 | 自进化 L2 半自动 |
| 3 旅程 | 主路径 < 30min | 80% 零人工 | 主人 < 1h/周 |
| 4 体验 | ≤ 15min/日运营 | 主人不读 ARCHITECTURE | 主人只看北极星 |
| 5 愿景 | north_star provable | 接入期 → 运转期 | 自治期 → 进化期 |
| 6 运营 | weekly-review routine | 90% 自动巡检 | 自治 |
| 7 运维 | L3 入口 6.5→8 | L1 7→9 | 自愈率 > 70% |
| 8 防腐 | G1/G2 闭合 | 6 层全通 | 防腐契约自动演化 |
| 9 约束 | 5 反模式 → 0 | 100% 硬约束守护 | 自演化约束管理 |

**当前快照 (2026-08-25, 9 维)**:

| # | dim | status | 距 3m | key_data |
|---|-----|--------|-------|----------|
| 1 | 场景 | GREEN | 3 张 assisted 卡 | scene-card-mini-shadow 3-sample |
| 2 | 功能 | YELLOW | maturity 7.7/10 | strategy-check timeout 后稳定 |
| 3 | 旅程 | GREEN | validated + active | 动态 |
| 4 | 体验 | RED→YELLOW* | health 53→75 | transient daemon 50% |
| 5 | 愿景 (BCOS) | GREEN | north_star 88/100 provable | A=100 B=50 C=97 |
| 6 | 长期运营 | GREEN | BET 141/147 done | 95.9% |
| 7 | 运维 | YELLOW | maturity proxy < 8.0 | timeout fix applied |
| 8 | 防腐 | GREEN | rot-defense 文档齐 | 6 层接通 |
| 9 | 约束 | GREEN | 5/5 反模式 healthy | anti-pattern detector |

*维度4的RED状态是由于运行时daemon临时离线(service_online_ratio=50%)。daemon恢复后自动回到YELLOW。

**summary: GREEN=6 YELLOW=2 RED=1 (transient) GREY=0**

**战略主轴进展:**
- 北极星 v3: composite 88/100, status: provable
- B轴决策吞吐: 5 decisions/月
- 反模式检测: 5/5 healthy
- staleness: 95→3 issues (-97%)
- alignment: 76-79

**下一步:**
1. 维度 4 体验: daemon 恢复后 health_score 回升
2. 维度 2/7: maturity-scorecard timeout 修复 (180s)
3. PR #2284: 需原作者 rebase
| 4 | 体验 | GREY | health≥80 |
| 5 | 愿景 (BCOS) | RED | north_star provable |
| 6 | 长期运营 | YELLOW | BET ≥95% |
| 7 | 运维 | GREY | 工具聚合 |
| 8 | 防腐 | GREEN | rot-defense 文档齐 |
| 9 | 约束 | GREY | 5 反模式检测 |

**summary: GREEN=2  YELLOW=3  RED=1  GREY=3** (of 9)

---

## 11. 关键里程碑 (12 个月)

| 月份 | 里程碑 | 验证 |
|------|--------|------|
| 2026-09 | T10-08 / T10-09 闭合, Y1Q3 完成 46/49 | BET ledger |
| 2026-10 | T1-11 闭合, Y1Q3 完成 47/49 + V1-01 kickoff | BET ledger |
| 2026-11 | 3 张场景卡 mini-shadow 验证 | shadow 卡片触发数 |
| 2026-12 | weekly-review routine 化, owner-attest 双轨 | weekly-review.json |
| 2027-01 | BCOS north_star v3 provable | BCOS status |
| 2027-02 | Y1 期末审计 (vision-to-retro chain 完整) | retro 报告 |
| 2027-Q2 | 8/9 场景卡 assisted, cockpit 一站式完成 | scene card lifecycle |
| 2027-Q3 | resident 自治 60% 任务, 主人 < 30min/日 | omo resident status |
| 2027-Q4 | Y2 转换: 接入期 → 运转期 | T6-14 复盘 |

---

## 12. 风险登记 (R1-R8)

| ID | 风险 | 概率 | 影响 | 应对 |
|----|------|------|------|------|
| R1 | 主人侧疲劳, 仪式难以持续 | 中 | 高 | 仪式 ≤ 15min/日, 自动化一切可自动化 |
| R2 | 跨季度 shadow 场景卡 (S1) | 高 | 中 | mini-shadow 模式 (3 samples 升) |
| R3 | 工具/规则配额饱和 | 中 | 中 | 减法配额 + 归档驱动 |
| R4 | Agent 失控 / 越权 | 低 | 极高 | 独立 clone + AGCP + execute --yes 门 |
| R5 | 北极星 provable 失败 (BCOS 价值未证) | 中 | 高 | V1-01 + 混合数据源策略 (D4) |
| R6 | 防腐契约 2 年后失效 | 中 | 中 | 季度 T6 复盘 + 2 年大版本 |
| R7 | 影子 IT (主人之外的子工作树滋生) | 中 | 中 | worktree-prune cron + CI 守护 |
| R8 | 单点所有者 | 高 | 中 | resident 自治渐进 + owner 分散 |

---

## 13. 决策记录

| 编号 | 决策 | 结论 |
|------|------|------|
| D1 | 战略主轴 | 2026-09 → 2027-Q4: 从"建设"转向"价值兑现", 北极星 = 主人可证时间节省 |
| D2 | 场景激活策略 | 引入 mini-shadow 模式, 3 useful 即可升 assisted (替代 30-sample) |
| D3 | 入口策略 | cockpit 为唯一入口, 480 个工具被收编 |
| D4 | 防腐策略 | 6 层全通后, 主人从"主动巡检"转向"签核" |
| D5 | 体验策略 | north_star A 轴量化主人负担, ≤ 15min/日 为硬指标 |
| D6 | 长期运营 | weekly-review 周一 morning + attest-review 周日 = 双轨仪式 |
| D7 | 自进化分级 | L1 参数 / L2 结构 / L3 代码, 各级守护机制不同 |

---

## 14. 关联 SSOT

| 文档 | 关系 |
|------|------|
| `sustainable-value-loop-v1.md` | 价值闭环 (D1 主轴) |
| `rot-defense-pipeline-v1.md` | 防腐 (维度 8) |
| `resident-agent-system-v1.md` | 自治 (维度 3, 6) |
| `90pct-maturity-architecture.md` | 成熟度目标 (维度 2) |
| `w0-convergence-map-2026-08-10.md` | L0 收敛基线 |
| `wave-gate-bet-map.md` | 波浪-门-BET 映射 |
| `memory-os.md` | 记忆系统 |
| `knowledge-foundry-cron.md` | 知识铸造 (维度 6) |
| `bcos-system-v1.md` | 业务闭环 (维度 2) |
| `digital-twin-blueprint-v1.md` | 数字孪生 |

---

## 15. 落地

本文档**不是终点, 是后续 6 个落地动作的起点**:

1. **场景卡 mini-shadow 实现** (本周) — `bin/gac/scene-card-mini-shadow.py` ✅
2. **cockpit 入口收敛** (2 周)
3. **weekly-review routine 自动化** (1 个月)
4. **BCOS V1-01 north_star v3** (3 个月)
5. **防腐 G1/G2 接线闭合** (3 个月)
6. **9 维战略矩阵季度复审** (1 季度节奏) — `bin/gac/strategy-check.py` ✅

✅ = 本次 (project-strategy-v1 PR) 落地的工具
