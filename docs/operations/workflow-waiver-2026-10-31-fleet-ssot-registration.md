---
type: operations
status: active
lifecycle: ephemeral
owner: governance-agent
created: 2026-10-31
last-reviewed: 2026-10-31
scope: workflow-requirement-iteration-waiver
---

# 一次性准入豁免：多机 SSOT 入口修订登记

## 原因与授权

当前台账的已检索 BET 均为 done；`project-doc-change` 的 start 要求可启动 BET，绑定已完成的 BET 被拒绝。用户于本会话明确授权一次性、仅用于登记的豁免，授权在隔离 worktree 登记针对入口文档修正的新 BET 与规范，之后恢复正常 bootstrap/start/claim。

## 范围和失效

仅允许编制与登记 `BET-Y2Q4-T10-278` 及其 `docs/superpowers/specs/2026-10-31-fleet-ssot-entry-alignment.md` 规范，使用 `bin/gac/ledger-safe-insert.py` 先 dry-run 后写入。登记完成或失败时豁免即失效。`AGENTS.md` 和 `ARCHITECTURE.md` 的实际修改必须在正常 run 和范围 claim 之后进行。

本豁免不允许改写既有 BET 状态或历史证据，不允许跳过其他门禁、修改生产、启停服务、数据迁移、提交、推送或发布。
