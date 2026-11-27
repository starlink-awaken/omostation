---
schema: md/v1
schema_version: specification/v1
bet_id: BET-Y2Q4-T10-360
spec_version: 1.0.0
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-11-27
accepted: "2026-11-26 Principal 会话「继续吧。做能做的」与 2026-11-27「继续吧」— canary 收口与教训立条为断根战役收官的自然延伸"
title: cron 首跑 canary 收口 —— T356/357 done-transition + 「无进程 ≠ 无会话」pitfall
created: 2026-11-27
---

# BET-Y2Q4-T10-360: cron 首跑 canary 收口

## 背景与问题

T356/T357 交付时 operational 轴诚实停在 NOT_PROVEN (done 门要求 canary)。
2026-11-27 首夜两 job 双绿 (capability 04:06 / mcptool 05:46 「产物无漂移,
跳过发布」, 主仓工作区零污染) —— canary 证据到手, 该入账。顺带: 昨晚
T355 done-transition 撞车 (#5639 让行) 的教训「无进程 ≠ 无会话」立条入档。

## 方案

1. canary 回执落 `docs/reports/2026-11-27-cron-canary-first-run-receipt.md`
   (证据载体, operational 四证引用)。
2. T356/357 operational NOT_PROVEN → PROVEN + overall_state →
   delivery_accepted, `complete` 翻 done。
3. pitfalls.md 立条「无进程 ≠ 无会话」+ AGENTS §7 簇表短语。

## 验收标准

1. T356/T357 status: done + done_at 2026-11-27。
2. 台账 YAML 解析通过; lint 对 T356/357/360 零 error。
3. pitfall 条目在档 (rg 「无进程 ≠ 无会话」命中)。

## 非目标

- 不动 T356/357 已 merge 的代码面。
- 不重跑 cron (首跑是自动调度, 本 BET 只收证据)。

## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | canary 证据形态 | 独立回执文档 | #5637 实测回执先例; 矩阵四证 ref 需要单一可检载体 |
| 2 | pitfall 立条时机 | 随本 BET | 教训新鲜 (昨晚); 隔夜立条细节失真 |
