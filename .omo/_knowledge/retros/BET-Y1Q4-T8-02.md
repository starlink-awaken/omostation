---
schema_version: retro/v1
lifecycle: history
owner: governance-team
created: 2026-09-03
last_updated: 2026-09-03
bet: BET-Y1Q4-T8-02
title: Mobile Cockpit PWA 滑动署名
symptom: cockpit-ui 台账前瞻但物理不存在; workflow start 未落 run 文件
solution: 主仓直接跟踪新目录; 手续后补
---

# BET-Y1Q4-T8-02 复盘

## 做对了什么

1. **KISS 技术栈**: bun+vite+react 极简, 手写 SW 24 行 + localStorage 离线
   双向 — bundle 62KB gzip (≤300ms 首屏语义达标)。
2. **安全链纵深**: 高危署名 = WebAuthn 门 (客户端) + DLP 前置闸 (服务端,
   实测涉密卡 quarantined) — T10-01 在移动面复用成防泄密闭环。
3. **离线语义**: SW precache + localStorage + online 静默同步。

## 踩了什么坑

| 坑 | 修复 |
|----|------|
| cockpit-ui 台账有 write_surface 但物理不存在 (前瞻路径) | 主仓直接跟踪新目录 (非 gitlink) |
| workflow start 无 run 文件 | 代码先行, 手续后补 |

## human_gate 边界 (诚实记录)

- 真机 Face ID ceremony 需 iOS 真机 + https — 当前降级 confirm, 真机部署时验收
- iOS Shortcuts 桥接未做 — PWA 面已覆盖核心场景

## 后续

- 真机部署后 Face ID 实测; supervisor 状态面接入 cards
