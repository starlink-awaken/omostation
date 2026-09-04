---
lifecycle: history
owner: governance-team
last_updated: 2026-08-09
title: BET-Y1Q1-T1-01 复盘
type: retro
---
# BET-Y1Q1-T1-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 1 day。随 #1104 一次提交落地（与 T1-03 合并），实际半天内完成，未超出。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| bin/mof/generate-brief.py 移除 count_deliveries_by_month 及其调用 | ✅ 已移除 |
| BRIEF.md X3 工作交付行显示"未接入真实数据源" | ✅ |
| x3-delivery-soft-gate.yaml 标记 deprecated 并指向本 bet | ✅ |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **X3 mtime 指标是伪指标**: 用文件修改时间统计「交付」不可靠，同一文件多次编辑被重复计数，且无法区分真实交付与顺手改动。废除比修复成本低。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净减:
- generate-brief.py 移除 count_deliveries_by_month 函数
- x3-delivery-soft-gate.yaml 标记 deprecated
- 无新增 GaC 规则 / ADR

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. X3 交付指标不再按 mtime 统计；真实交付以 bet closeout + evidence 为准。
2. 若未来需要交付量指标，应基于 agent-workflow 事件（events.jsonl）而非文件系统 mtime。
