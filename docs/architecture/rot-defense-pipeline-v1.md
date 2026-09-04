---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-24
title: 防腐流水线 v1 — 两周机制的体系化接线图
type: doc
---

# 防腐流水线 v1 — 两周机制的体系化接线图

> 最后更新: 2026-08-24
> 回答的问题: "做了一大堆机制，为什么时间久了还是失控？"
> 答案: 因为它们没有接成一条**从违规瞬间到主人视线**的完整管道。本文件就是接线图。
> 来源: 2026-08-22~24 三流并发产出(主线14PR + 迭代流Phase2-6 + 差距治理S1-S5)的全量盘点

## 一、管道总览

```
【L3 动作时刻物理拦截】—— 遗忘不可能发生
  git push ──► bin-quota-diff(#2076 增删守恒)
           ├─► ancestry gate(#2084 指针祖先校验)
           ├─► mass-deletion gate(既有)
           └─► ci-local-fast(全量预检)
                │ 漏网(escape/--no-verify)→ fingerprint 入 known-debt 留痕
                ▼
【L2 周期探测】—— 沉默即异常
  meta-doctor: M1 心跳SLA · M2 引用活性 · M3 仪式心跳(新增) · scheduler-drift
  drift-sweep(#2067): 聚合全部漂移报告为单一输出
  CAP-OWN(#2078): 能力删除防腐(IMPL-EXISTS 阻断)
  predictive-governance: 趋势预测
                │ 发现异常
                ▼
【T1 自动立案】—— 不需要人记得
  meta-doctor → debt_proposals(MDEAD-*, 实战:3条断链当日立案)
  auto-fix-loop(#2068): 可自动修的直接修(T0)
                │ 不可自动修
                ▼
【修复引擎】—— 已有引擎待接线
  remediation-engine(--dry-run/--execute, 迭代流恢复#2096)
  ⚠ 接线缺口G1: 尚未消费 MDEAD proposals(需适配器)
                ▼
【升报层】—— 到主人视线的最后一跳
  alert-router/anomaly-detector(operating-rhythm cron)
  ⚠ 接线缺口G2: meta-doctor 输出未直写 cockpit-inbox(weekly-review --post-inbox 起步)
                ▼
【主人面】—— 每周10分钟
  周一: weekly-review 卡(UHS+债务MDEAD+决策收件箱+价值trend) ← 本文件配套新件
        → 决策进 scan_decision_inbox 数据源(BRIEF.md 同源渲染)
  周日: attest-review 签核(episode-source-aggregator 三源草稿)
                │ 心跳
                ▼
【仪式闭环】—— 主人侧也被防腐
  weekly-review.json 心跳 → meta-doctor M3: >14天断供→债"owner-review-lapsed"→下期卡片首位
```

## 二、两周机制全量清单与入网状态

| 机制 | 来源PR | 层 | 入网 |
|------|--------|---|------|
| bin-quota-diff 变更守恒 | #2076 | L3 | ✅ pre-push+gate |
| ancestry gate 指针祖先 | #2084 | L3 | ✅ pre-push+gate |
| CAP-OWN 删除防腐 | #2078 | L2 | ✅ gate |
| meta-doctor M1/M2 | #1943/#1955 | L2 | ✅ cron+CI 6h |
| drift-sweep 聚合 | #2067 | L2 | ✅ cron 周 |
| gap-gov S1-S5 | #2068 | L2 | ✅ gate |
| MDEAD 自动立案 | #1955 | T1 | ✅ 实战3条 |
| remediation-engine | 迭代流 | 修复 | ⚠ G1 待适配 |
| UHS 六维评分 | 迭代流 | 度量 | ✅(#2096 scorer回归) |
| north-star-meter v2 | 迭代流 | 价值 | ✅ |
| episode-source-aggregator | #2081 | 价值 | ✅ |
| attest-review | #2085 | 主人面 | ✅ |
| est-minutes 系数表 | #2075 | 价值 | ✅ |
| **weekly-review 卡** | 本文件配套 | 主人面 | 🔄建设中 |
| **M3 仪式心跳** | 本文件配套 | L2 | 🔄建设中 |

## 三、诚实边界——管道管不到的三件事

1. **主人侧断供**: 签核/拍板不可强制。M3 只能提醒不能代签。若长期断供→value 诚实衰减→sunset 触发=系统如实汇报自己不再被需要。
2. **门禁绕行**: escape/--no-verify 有钥匙就能过。缓解=bypass 必留 fingerprint,owner 月审 bypass 日志。
3. **探测器自身腐烂**: 缓解=M3 同款心跳可推广至全部探测器(探测器心跳矩阵, backlog)。

## 四、接线缺口登记(后续 PR)

| 缺口 | 内容 | 建议 |
|------|------|------|
| G1 | remediation-engine 消费 MDEAD proposals 的适配器 | 下一迭代 |
| G2 | meta-doctor 直写 cockpit-inbox | weekly-review 已起步同款模式 |
| G3 | 探测器心跳矩阵(全部探测器写 heartbeats/) | 推广 heartbeat-wrapper |
