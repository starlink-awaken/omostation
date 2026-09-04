---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-24
title: 可持续价值闭环与自进化治理 v1 — 架构方案 SSOT
type: doc
---

# 可持续价值闭环与自进化治理 v1 — 架构方案 SSOT

> 最后更新: 2026-08-23
> 定位: 回答"治理能力过剩、价值证明缺位"这一战略错配的体系化方案。
> 来源: 九维复盘(grill-me 七问决策) · 状态: **设计已拍板, 分波落地中**
> 决策记录: 本文 §2 为七问终审结论, 变更须经同等粒度评审。

## 1. 问题定义(实证)

| 编号 | 风险 | 证据(2026-08-23 实测) |
|------|------|----------------------|
| R1 | 价值不可证 | `north_star_meter_v2 → status: unprovable, reason: principal_id_required` |
| R2 | 人在环瓶颈 | BRIEF.md 决策收件箱自述"人类决策是当前系统瓶颈"; 台账可认领=0 |
| R3 | 生成物内容级漂移 | sync 类生成器读工作树而非提交态; 实证 registry 曾落后 SSOT 10 条; agora gitlink 被并发合并回退致 #2055 注册被 clobber |

战略错配一句话: **能精确测量 139 条 GaC 规则的遵守度, 无法测量系统为主人省下的时间。**

## 2. 设计决策记录 (grill-me 七问)

| # | 决策 | 结论 |
|---|------|------|
| D1 | 攻击顺序 | R3 立即止血(P0) → R1 主线设计 → R2 第二波 |
| D2 | 交付形态 | 方案文档(本文) + P0 立即执行 |
| D3 | 价值度量 | **复合制, 以时间账本为锚**: A 时间/注意力(主) + B 决策吞吐 + C 项目推进力(佐证, 零成本导出) |
| D4 | 数据源策略 | **混合**: signal_router 四路自动信号 + 关键节点轻量人工确认("有用吗"一键) |
| D5 | 防腐路线 | **双重阻断**: 本地 preflight(检出态≠记录态拒跑) + drift 非零退出; CI 复检兜底 |
| D6 | 自进化分级 | L1 参数全自动 / L2 结构半自动(提案+门禁留痕) / L3 代码仅人类 PR |
| D7 | 续期机制 | 价值驱动续期: 北极星连续两季度 provable 且正向→自动续期 BET; 否则触发精简退役评审 |

## 3. 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│ L4' 价值层(v3 新增): north_star v3                            │
│   时间账本 ← signal_router 自动信号 + confirm-inbox 人工确认   │
│   佐证轴   ← debt velocity · BET throughput (现有数据零成本)   │
├──────────────────────────────────────────────────────────────┤
│ L3  人类接口面: cockpit decision-inbox                        │
│   一键勾选 → 自动执行链 → 结果回写价值账本                     │
├──────────────────────────────────────────────────────────────┤
│ L2  自进化三级制(D6):                                         │
│   L1 参数: T0/T1 自动修+开债 (已在产)                         │
│   L2 结构: generator-evolution proposal → PR 门禁自动审       │
│   L3 代码: 仅提案, 人类审批 (现状不变)                         │
├──────────────────────────────────────────────────────────────┤
│ L1  防腐硬化(D5): 全部 sync 类生成器统一 preflight 契约        │
│   检出态==HEAD 记录态 ∧ 目标文件干净 ∨ 拒跑(exit 2)           │
│   drift 输出非零退出; CI --check 只读复检                      │
│   覆盖清单: bos-registry(#2061✅) · capability-registry ·     │
│            INDEX-MCP · CLI-REFERENCE · mof-capabilities      │
└──────────────────────────────────────────────────────────────┘
```

## 4. R1 价值闭环 — north_star v3

### 4.1 度量 schema (`value-truth-snapshot/v2`)

```yaml
snapshot:
  anchor:                       # 锚指标: 时间账本
    delegated_done: 12          # 本周 agent 代办完成事项
    est_minutes_saved: 340      # 每事项带 est_minutes 字段, 求和
    confidence: auto|confirmed  # 人工确认过的占比
  corroboration:                # 佐证轴(现有数据导出)
    decision_throughput: {inbox_pending: 1, median_age_days: 3}
    bet_velocity: {done_30d: 6}
  verdict: provable             # unprovable 的反面: 三源齐即 provable
```

### 4.2 数据流

```
signal_router(doc/meeting/research/code)
  → 信号入 inbox (已有 W1-D2)
  → 执行落地的信号自动记 delegated_done + est_minutes(规则估算)
  → confirm-inbox 每周一次批量人工确认(D4 轻量点选)
  → north_star_meter_v3 聚合出快照
```

### 4.3 principal_id 解法

不建身份系统。`config/x1/node_identity.json` 已有机器身份; 新增
`spaces/<ws>/value-profile.yaml`(手工一次性配置: 主人时区/时薪锚点/确认节奏),
meter 读它替代缺失的 principal_id。**冷启动顺序: 先 B/C 轴点亮(provable-lite),
A 轴数据满 4 周后转全量 provable。**

## 5. R2 决策收件箱产品化(第二波)

- 形态: `cockpit decide` 子命令 + BRIEF.md 渲染同一数据源
- 每张卡带: 建议(default action) + 影响 + 一键 `[y/n/defer]`
- SLA 机制: 卡龄 >7d 自动升级 P1 开债; >14d 进 BRIEF 头部红区
- 与 R1 接线: 每次决策落地回写 decision_throughput 佐证轴

## 6. R3 生成物防腐体系(泛化契约)

所有"sync 型生成器"(读源→写派生入库)必须实现:

1. `preflight()`: 子模块检出态==gitlink 记录态 ∧ 源文件无未提交改动, 否则 exit 2
2. drift 时 `--check` 退出非零(CI 用), `--write` 显式修复
3. 输出自带 raw/mirror 计数与过滤语义(防误读)
4. CI 侧 `--check` 只读复检纳入 ci-surfaces 登记

进度: bos-registry preflight ✅(#2061) · 配额清偿 448→442 ✅(#2066) · capability-registry → INDEX-MCP/CLI-REFERENCE(sync-all-docs) → mof-capabilities 待推广。

**勘误 (2026-08-24)**: 前报 "BOS split-brain / #2055 注册被 clobber" 系测量方法错误 —
`git show origin/main:projects/agora/...` 无法读子模块内容(静默返回空), 实测 canonical
yaml 含全部注册且三源一致(sync drift=no)。同日 UHS governance 归零亦为
多文档 yaml 解析缺陷(已修)。教训: 子模块内省必须在子模块检出内进行。

**新增配套门禁(提案)**: gitlink bump 必须满足 `new_sha 是 old_sha 后代 或 PR 描述含 regress 理由`
—— 防 #2055 注册被并发回退类事故复发。挂点: pre-push hook 的 pointer-drift 检查处。

## 7. 自进化三级制契约 (D6)

| 层 | 对象 | 权限 | 留痕 |
|----|------|------|------|
| L1 | 规则阈值·配额数值·调度频率 | agent 全自动 | heartbeats + T1 债务项 |
| L2 | 增删 GaC 规则·cron 任务·BOS 注册 | agent 提案+证据 → PR 门禁自动合 | PR 引用 run-id |
| L3 | bin//projects 代码 | 仅提案 issue/patch 草稿 | 人类 PR 审批 |

判据: **改"数"自动, 改"结构"留痕半自动, 改"行为"必人审。**

## 8. 续期与退役 (D7)

```
每季度末: north_star 快照归档 → 评估
  ├─ 连续两季 provable 且 Δ≥0 → 自动开下一轮维护性 BET(小步)
  └─ 不达标 → sunset-review: 按 domain 价值排序裁撤
       persona/capability 未激活域为首批候选
     裁撤产物进 bin/_archive + registry 移除(走 L2 流程)
```

存续资格由创造的价值决定, 不由沉没成本决定。

## 9. Y3 BET 拆票建议(待台账登记)

| 提案 ID | 内容 | 对应 |
|---------|------|------|
| BET-Y3H1-V1 | value-profile.yaml + meter v3(B/C 轴先亮) | §4 |
| BET-Y3H1-V2 | 时间账本采集 + confirm-inbox | §4.2 |
| BET-Y3H1-V3 | cockpit decide + SLA 升级机制 | §5 |
| BET-Y3H1-V4 | 生成器防腐契约推广至剩余 4 个 sync 点 | §6 |
| BET-Y3H1-V5 | gitlink ancestry gate(GaC 新规) | §6 配套 |

## 10. 开放问题

1. est_minutes 估算规则的公平性(防 agent 高估工时刷分) → 初版用固定任务类型系数表
2. 多工作区/多主人扩展 → value-profile 按 space 隔离, schema 预留 namespace 字段
3. ~~agora gitlink 回退损失盘点~~ → 已证伪(见 §6 勘误), 无损失。
4. **gitlink ancestry gate 设计**(真实风险: 并发 PR 自陈旧 base 合并会回退指针,
   本周观测多次 SHA 抖动): pre-push 的 pointer-drift 处追加 `merge-base --is-ancestor
   old_sha new_sha` 校验, 非后代须 PR 描述含 regress 理由; 落点待 owner 排期。
