---
title: 控制规则
description: Obsidian Vault 控制面规则表。
status: 已采纳
type: canonical
owner: 未指定
created: 2026-06-08
last_updated: 2026-06-08
tags: [控制面, 控制器]
---

# control-rules — 控制规则

## 内核规则（l4-kernel 强制）

| ID | 输入 | 动作 |
|----|------|------|
| CR01 | signals 出现 🔴 信号 | 触发域内事件响应 + 跨域通知 (@驾驶舱) |
| CR02 | 任务线停滞超过 SLA | 更新 STATE.md 阶段定位 + 检查 CARDS 触发时机 |
| CR03 | STATUS 从 STABLE 变为 ALERT | 通知 @驾驶舱 + 写入 signals |

## 域扩展规则

| ID | 输入 | 动作 |
|----|------|------|
| CR04 | _entities/ 实体 last-reviewed > 30 天 | 触发实体审查 |
