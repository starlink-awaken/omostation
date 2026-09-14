---
schema_version: retro/v1
status: active
lifecycle: history
owner: governance-team
created: 2026-09-03
last-reviewed: 2026-09-03
bet: BET-Y1Q4-T8-02
title: Mobile Cockpit PWA 滑动署名
symptom: cockpit-ui 台账前瞻但物理不存在; workflow start 未落 run 文件
solution: 主仓直接跟踪新目录; 手续后补
type: ephemeral
status: archived
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

---

## 2026-09-05 追加 — HITL Retroactive Adoption (BET-Y1Q4-T1-12)

**背景**: Mobile Cockpit 移动轻控制台 BET 于 2026-09-03 完成,涉及 iOS PWA 集成 + 滑动署名,风险等级 L1。HITL v1.0 于 2026-09-04 落地后,本 BET 适合 retroactive 标记 HITL adoption。

**HITL 适配性**:
- 风险等级: L1
- 关键路径: 移动端用户操作需要 principal (夏明星) 滑动作出署名
- 当时实现: 客户端触摸事件直接通过 webhook 调用签字服务
- HITL 模式: 移动端动作 → 提案 → bin/cockpit decide approve (未来 mobile UI 直接调用)

**价值**:
- 移动端用户操作天然需要 human 确认,HITL 比 in-band 更可追溯
- 滑动署名本身是 0.5-2s 短操作,HITL proposal TTL 24h 完全覆盖
- 多设备操作 (iOS/PWA/web) 共享同一 proposal ID,统一审计

**关联**: BET-Y1Q4-T1-12 (adoption), HITL-01 (tool), T8-04 + T10-03 (前 2 个 HITL production users)
