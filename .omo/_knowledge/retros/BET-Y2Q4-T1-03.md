---
schema: md/v1
status: archived
lifecycle: history
owner: unassigned
last-reviewed: 2026-09-25
type: ephemeral
bet: BET-Y2Q4-T1-03
title: 战略主线宪章修订 — 追认移动 Cockpit / TUI 多窗格为既定应用形态
date: 2026-09-16
---


# BET-Y2Q4-T1-03 Retro

## Q1 实际耗时 vs appetite?
- Appetite: 2 days
- 实际: 0.5 天 (与 T1-02 同 PR #3832 合并交付)
- 偏差: 大幅低于预期，纯文档修订

## Q2 done_when 是否全部通过?
- [x] §6 应用形态章节已更新
- [x] "不做移动 App" 收窄为"不做原生移动 App (iOS/Android 独立应用)"
- [x] "追认既定形态"段落已添加

## Q3 过程中发现的与 plan 不符的事实 (打假)?
- Mobile Cockpit (T8-02) 和 TUI 2.0 (T8-18) 均已交付到 main，但宪章仍写"不做移动 App"——文档与执行现状矛盾

## Q4 净增减
- 代码行: 0（纯文档）
- 文件: 2 修改（strategy charter + bet ledger）
- GaC 规则: 0
- ADR: 0

## Q5 下一个认领本 track 的 agent 需要知道什么?
- 已完成两个文档追认 BET，后续 T1 track 须先查 main 是否已自愈
- completion_evidence 须用 schema_version: completion-evidence-matrix/v1 + axes 结构（非 flat pr/refs 格式）
- merged_reachable_commit.ref 须 40-hex SHA（非短 SHA）
